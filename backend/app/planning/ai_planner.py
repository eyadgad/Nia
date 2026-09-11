"""AI-planner-first turn understanding. Legacy routing is unchanged."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import ValidationError

from app.config import get_settings
from app.llm.base import ReasoningProvider, StructuredOutputResult, TransientReasoningError
from app.planning.ai_catalog_coerce import coerce_planned_turn
from app.planning.ai_turn_schema import (
    PlannedConversationAction,
    PlannedQueryAction,
    PlannedTurn,
    PlanReviewResponse,
    ReviewCorrected,
    ReviewNeedsClarification,
    bind_scope,
)
from app.planning.catalog import DatasetSpec, FieldCatalog
from app.planning.conversation_resolver import ConversationContext
from app.planning.input_normalizer import NormalizedTurn, normalize_transport
from app.planning.plan_validator import PlanValidationError, validate_query_plan
from app.planning.predicate_contract import validate_predicate_contract
from app.planning.query_plan_builder import (
    QueryPlanBuildError,
    UnsupportedFieldsError,
    build_query_plan,
)
from app.planning.requirement_parity import (
    check_requirement_parity,
    unaccounted_conditions,
)
from app.planning.response_policy import (
    canned_response,
    only_clarification,
    only_direct_response,
    only_reference,
    resolve_final_response,
)
from app.planning.router import PlanRouteResult
from app.planning.timing import TimingRecorder
from app.planning.turn_schema import (
    ModifyPreviousAction,
    QueryAction,
    TurnPlan,
    VerifyPreviousAction,
)
from app.planning.turn_validator import validate_turn_plan
from app.planning.value_expansion import expand_plan_values
from app.security.access_scope import AccessScope

logger = logging.getLogger("nia.planning.ai")


class PlannerContractError(ValueError):
    """Structured output passed Pydantic but violated a planner contract."""


# Validation failures the self-review is allowed to try to repair before the turn
# falls back to a clarification. Each one means the planner contradicted itself or
# the catalog -- never that the user was unclear -- so a second pass with the error
# as context is a better answer than asking the researcher to restate a clear
# question. access_restricted is deliberately absent: that one always fails closed.
_REVIEWABLE_VALIDATION_CODES = frozenset(
    # "operator" belongs with "unknown_field": both are the planner naming something the
    # registry does not support on that field, and both are fixable by looking at the
    # catalog again. Only unknown_field was salvageable, so "list students whose names
    # start with Z" died on STARTS_WITH being unavailable for the field it chose, with a
    # perfectly good alternative field on the same list.
    {"unknown_field", "operator", "dropped_requirement", "response_contract", "op_contract"}
)

PLANNER_UNAVAILABLE_TEXT = {
    "text": "NIA's planning service is temporarily unavailable. Please try again in a moment.",
    "voice": "My planning service is unavailable. Please try again shortly.",
}
PLANNER_INVALID_TEXT = {
    "text": "NIA couldn't produce a usable plan for that request. Please try again.",
    "voice": "I couldn't make a usable plan. Please try again.",
}

AI_PLANNER_SYSTEM = """You are the only natural-language planner for Nia, a research-record assistant.

You are given ONE already-selected list and its complete field catalog. Every rule below is
expressed over catalog properties, never over particular field names: read SELECTED FIELDS for
each field's semantic_field, type, allowed ops, label, aliases, capabilities, and value_families.
If a concept the user names is not in SELECTED FIELDS, it does not exist here.

SCOPE
Plan against the selected list only. Never emit a dataset identifier, file ID, table name, or SQL.
Never switch, combine, search, or substitute another list. If the user names a different authorized
source, emit a respond action with intent dataset_not_selected and put that source's exact label in
response. If they name an unknown or unauthorized source, use dataset_not_selected with an empty
response. A list name is a source of records; a proper noun that is a value inside a field is not a
list. Match the user's wording against field labels, aliases, and value_families before concluding
they named a source. Do not emit dataset_not_selected for the selected list itself, for years or
numeric ranges, for first/last/page requests, or for generic words such as students, records,
deaths, or names.
When the user names the list that is already selected, that phrase is scope, not content. It is
already applied: do not turn it into a filter value on some field, and do not emit
dataset_not_selected. "How many records are in <the selected list>" is an unfiltered count.
Conversely, when they ask for records IN, FROM, or by SEARCHING some other named list, dataset, or
set of records, that is a source request and the answer is always dataset_not_selected -- never a
query, and never the same question answered from the selected list. This holds whether or not the
name appears in OTHER AUTHORIZED LIST NAMES: if it is listed, put its exact label in response; if it
is not, leave response empty. Answering such a request from the selected list would report a number
about the wrong records.
A bare proper noun naming a place, person, community, or institution is a VALUE, not a collection.
"records from <place>" filters this list; only a name presented as a set of records is a source.

FIELD SELECTION
Resolve the user's wording to a semantic_field through that field's label and aliases.
Before emitting any filter, grouping, sort, or projection, check that the field you chose is the one
the user's words actually name: its semantic_field, label, or one of its aliases must match what they
said. Sharing a topic is not a match -- two fields can both be about people, places, or dates and
still be different questions.
If the concept they named matches no field's name, label, or aliases in SELECTED FIELDS, emit a
clarify action saying that field is not available on this list. That refusal is the correct answer.
Never fall back to a related-sounding field that happens to exist, and never answer a question about
a field this list does not have by quietly using a different one.
Sometimes the user gives only a value and never names its field ("records from <somewhere>", "anyone
called <name>"). Bind it only to a field that plainly holds that kind of value, judged from that
field's label, aliases, type, and value_families. If no field on this list plainly
holds it, refuse in the same way. A field that is merely adjacent in subject is not the one they
meant, and returning a confident zero from the wrong field is worse than saying the list does not
record it.
Each field also reports recorded=<filled>/<total>: how many records actually carry a value
for it. When you are choosing which field holds a value the user named, prefer one that is
populated -- a field almost nobody filled in has probably never held that kind of value, and
a zero drawn from it states something about the records that the records do not support.
This is about choosing between fields, not about refusing: a question asked about a sparse
field is still a fair question, and its true answer may well be a small number or zero.
A field is the one they meant only if it records the fact they asked about. Neither a name that
merely reads alike, nor the words of the concept turning up inside someone's free text, makes it so.
Never invent semantic fields. Never request unauthorized records.

OPERATORS -- choose from the field's own ops list and type
- Use only operators listed in that field's ops.
- Boolean-typed fields use IS_TRUE / IS_FALSE for the true/false split. If such a field also carries
  value_families naming further recorded categories, then matching one of those categories by name is
  a value match over that family -- not IS_TRUE/IS_FALSE, and not IS_UNKNOWN.
- "recorded/known/has a value" is IS_KNOWN; "missing/not recorded/blank/no value" is IS_UNKNOWN.
- IS_KNOWN and IS_UNKNOWN describe presence, not content.
- Before choosing IS_UNKNOWN, look up the user's word among that field's value_families keys. If it
  is a key there, they named a recorded category and you must match its members by value. A field
  can hold both records whose stored value IS that category and records with no value at all; these
  are different questions with different answers, and only the second is IS_UNKNOWN. A category
  whose name happens to be a word like "unknown" is still a recorded value, not an empty cell.
- Match a value against the spellings in value_families when the field has them: CONTAINS_ANY for
  alternatives, NOT_CONTAINS_ANY for their negation.
- Use CONTAINS_ANY for alternatives; use multiple CONTAINS filters under AND for true conjunctions.
- Looking a record up by a person's name is a CONTAINS match, not EQUALS: stored names routinely
  carry extra qualifiers, punctuation, and case that an exact match would miss.
- Emit filter values as concepts, not sentence fragments. Preserve negation polarity.
- Preserve every stated condition as its own filter under filter_logic=and. Never drop a condition
  or replace a requested value, bound, or threshold with a broader proxy.

GOALS
- "how many" over records -> goal=count.
- "how many distinct/unique/different" -> goal=aggregate, aggregate.function=count_distinct,
  aggregate.field set.
- "what different/unique values" -> goal=distinct with the field in group_by.
- "distribution/breakdown" -> goal=rank with the field in group_by and no filter on that same field.
- "most common/most frequent/highest number of" -> goal=rank with the dimension field in group_by
  and top_n=1 unless more are requested. Never put a count or an aggregate name in group_by.
- Records that share a value AND were present at the same time ("at the same time", "during the
  same period", "overlapping") -> goal=duplicates with the shared field in group_by, interval_start
  and interval_end set to the two date fields that bound each record's own period, and
  having_min_count set to how many must overlap (2 unless the question says more).
- "highest/maximum/lowest/minimum/oldest/youngest/earliest/latest" of a value -> goal=aggregate with
  exactly one aggregate spec using max or min on that field.
- "average/median/mode" -> goal=aggregate with exactly one aggregate spec on that field.
- "which/list/show" -> goal=list. Project the identity field plus every field the question names --
  including a field it names only in a condition, so the reader can check the answer against the
  condition that produced it. When the question names no field at all, project the identity field
  alone. Never add a field the question never mentions.
- "show all information for NAME" -> goal=list, CONTAINS filter on the identity field, and every
  field in SELECTED FIELDS in requested_fields. Not a dossier and not narrative synthesis.
- "what fields are available" -> one respond action with intent=describe_available_data and no
  stated_requirements. Never attach goal, filter, grouping, or projection requirements to respond.

include_missing groups records that have no value for the grouped field into their own bucket.
That bucket is part of a complete picture but is never the answer to a superlative:
- A distribution or breakdown enumerates every bucket, so set include_missing=true.
- A superlative ("most common", "most often", "top N", "which X has the most") asks which recorded
  value leads. Records with no value are not a recorded value, so set include_missing=false there.
  Setting it true lets an absence outrank every real value and answer with "not recorded".

ORDER AND WINDOWS
Sort direction and window anchor are independent; do not apply the user's direction twice.
Express the requested ordering in sort_direction, then take the requested end of that order with the
window anchor: "first N" is window={anchor:start,size:N,cursor:0}; "last N" is
window={anchor:end,size:N,cursor:0}. Both keep the sort in the order the user asked for.
"by <field>" after "list" names the projection or the ordering the user asked for. Do not invent a
sort the user did not request. Sort only on fields whose caps include sortable.
A ranking is already ordered by count: never set sort_by for it, and never state a sort or ordering
requirement describing that inherent count order. State only top_n and the grouping.
Reset paging for new requests. Clear incompatible paging for samples.

OTHER
Resolve spoken self-corrections. Ignore fillers and polite wrappers.
If a voice transcript is incomplete, emit a clarify action.
Do not filter on a field that is being enumerated as a grouped breakdown.
Order life-event intervals chronologically by the meaning of the two date fields.
Represent base-name grouping with group_value_part=base_name.
Choose deterministic for counts, lists, ranks, and stats. Use llm_synthesis only when the user asked
for a narrative, summary, explanation, or dossier.
If you are below the supplied confidence threshold, emit a clarification instead of guessing.
For general_conversation, put a bounded workplace-appropriate reply in the respond action response.

OUTPUT CONTRACT
Enumerate every understood requirement in stated_requirements at the same granularity as the actions
(goal, each filter, search text, grouping, sort, each projected field, options, limits, windows,
modify edits).
Every action MUST include type. Every stated_requirement MUST include kind.
Requirement action_index values are zero-based and MUST point to the action that expresses the
requirement. Never emit a requirement for a condition that is absent from its target action.
Use exactly one query action for a single requested result. Do not emit duplicate count, list, rank,
or stats actions.
Every query action MUST use final_response=deterministic unless the user explicitly requests
narrative synthesis. Never use compiler_response with a query action.
"""

AI_REVIEW_SYSTEM = """You review a planned research query for missing or incorrect requirements.

You see the original question, the candidate PlannedTurn, and the selected list's field catalog only.
Judge only against SELECTED FIELDS; every field property you need -- type, allowed ops, label,
aliases, capabilities, value_families -- is in that catalog. Do not rely on knowledge of any
particular dataset. Do not emit dataset identifiers. Do not invent fields. Do not widen scope.

Reconstruct the question independently before judging the candidate. A fluent answer shape is not
evidence that the plan is complete. Check: the goal; every AND/OR condition; presence-versus-value
polarity; whether a named category is a literal value in that field's value_families rather than
missingness; grouping; ranking threshold; sort direction and window anchor applied once rather than
twice; limit; and the projection.

A list answer must project the identity field plus every field the question names, including one it
names only in a condition -- a list filtered on a field the reader cannot see is unverifiable. Add
the missing projection rather than accepting it.
A request for records in, from, or by searching a named source other than the selected list is
dataset_not_selected with no query, never the same question answered from the selected list.
Confirm the plan uses only operators in each field's ops list, and that every field it references
appears in SELECTED FIELDS. If the question names a concept matching no field's name, label, or
aliases, the correct plan is a clarification that the field is unavailable, not a query against a
related-sounding field that happens to exist.
include_missing belongs only where the user explicitly asked for missing values as a category.

If the plan already covers every stated and implied condition, return verdict=complete.
If a required condition is missing or wrong and you can correct it, return verdict=corrected with
missing[] and a full corrected PlannedTurn. Preserve unrelated goals, fields, and conditions.
If you cannot safely correct the plan, return verdict=needs_clarification with missing[] and a short
question.
A candidate that already follows these rules must be marked complete, not corrected.
Every corrected action MUST include type, every corrected requirement MUST include kind, and every
zero-based action_index MUST be valid. Use only operators the schema allows.
"""


@dataclass
class PlannerStageResult:
    stage: str
    status: str
    provider: str = ""
    model: str = ""
    attempts: int = 0
    duration_ms: float = 0.0
    request_metadata: dict[str, Any] = field(default_factory=dict)
    output_metadata: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    error: str = ""


@dataclass
class AIPlanningResult:
    planned: PlannedTurn | None
    bound: TurnPlan | None
    primary: PlannerStageResult
    review: PlannerStageResult | None = None
    review_status: str = "skipped"
    planner_attempts: int = 0
    planner_retry_count: int = 0
    review_attempts: int = 0
    planner_total_model_calls: int = 0
    planner_failure_stage: str | None = None
    status: str = "planned"
    detail: str = ""
    suggested_file_id: int | None = None
    original_planned: PlannedTurn | None = None


@dataclass(frozen=True)
class AuthorizedDatasetOption:
    file_id: int
    label: str
    aliases: tuple[str, ...]
    private: bool = False


class UnavailableAIPlanner:
    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def plan(self, *args, **kwargs) -> AIPlanningResult:
        del args, kwargs
        return AIPlanningResult(
            planned=None,
            bound=None,
            primary=PlannerStageResult(stage="primary", status="unavailable", error=self.reason),
            status="planner_unavailable",
            planner_failure_stage="primary",
            detail=self.reason,
        )


class AIPlanner:
    def __init__(
        self,
        provider: ReasoningProvider,
        *,
        review_provider: ReasoningProvider | None = None,
    ) -> None:
        self._provider = provider
        self._review_provider = review_provider or provider
        self.provider_name = getattr(provider, "provider_name", "unknown")
        self.model_name = getattr(provider, "model_name", "")

    async def plan(
        self,
        question: str,
        *,
        catalog: FieldCatalog,
        selected_file_id: int,
        authorized_options: list[AuthorizedDatasetOption],
        context: ConversationContext,
        input_mode: Literal["text", "voice"] = "text",
        min_confidence: float | None = None,
    ) -> AIPlanningResult:
        settings = get_settings()
        threshold = settings.planner_min_confidence if min_confidence is None else min_confidence
        user = _planner_user_prompt(
            question,
            catalog=catalog,
            selected_file_id=selected_file_id,
            authorized_options=authorized_options,
            context=context,
            input_mode=input_mode,
            min_confidence=threshold,
        )
        primary, planned, retry_count = await self._primary(
            user,
            question=question,
            selected_file_id=selected_file_id,
            authorized_options=authorized_options,
        )
        total = primary.attempts
        if planned is None:
            status = "planner_unavailable" if primary.status == "unavailable" else "planner_invalid_output"
            return AIPlanningResult(
                planned=None,
                bound=None,
                primary=primary,
                planner_attempts=primary.attempts,
                planner_retry_count=retry_count,
                planner_total_model_calls=total,
                planner_failure_stage="primary",
                status=status,
                detail=primary.error,
            )

        return AIPlanningResult(
            planned=planned,
            bound=bind_scope(planned, selected_file_id),
            primary=primary,
            review=PlannerStageResult(stage="review", status="skipped"),
            review_status="skipped",
            planner_attempts=primary.attempts,
            planner_retry_count=retry_count,
            review_attempts=0,
            planner_total_model_calls=total,
            status="planned",
            original_planned=planned,
        )

    async def _primary(
        self,
        user: str,
        *,
        question: str,
        selected_file_id: int,
        authorized_options: list[AuthorizedDatasetOption],
    ) -> tuple[PlannerStageResult, PlannedTurn | None, int]:
        attempts = 0
        retry_count = 0
        last_error = ""
        attempt_user = user
        started = time.perf_counter()
        usage: dict[str, Any] = {}
        while attempts < 2:
            attempts += 1
            try:
                result = await self._call(
                    self._provider, AI_PLANNER_SYSTEM, attempt_user, PlannedTurn
                )
                usage = _usage_from(result)
                _assert_grounded_dataset_not_selected(
                    result.value,
                    question=question,
                    selected_file_id=selected_file_id,
                    options=authorized_options,
                )
                return (
                    PlannerStageResult(
                        stage="primary",
                        status="ok",
                        provider=result.provider,
                        model=result.model,
                        attempts=attempts,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        usage=usage,
                    ),
                    result.value,
                    retry_count,
                )
            except (ValidationError, PlannerContractError) as exc:
                last_error = _sanitize_error(exc)
                logger.warning("ai planner primary validation failed: %s", last_error)
                if attempts == 1:
                    retry_count = 1
                    attempt_user = (
                        "SCHEMA-VALIDATION RETRY: The previous response was rejected. "
                        "Return a complete replacement object. Every action must explicitly include "
                        "its type discriminator, every stated requirement must explicitly include its "
                        "kind discriminator, and every action_index must be valid. "
                        "dataset_not_selected is only valid when the user names a different source. "
                        f"Validation error: {last_error}\n\n{user}"
                    )
                    continue
                return (
                    PlannerStageResult(
                        stage="primary",
                        status="invalid_output",
                        provider=self.provider_name,
                        model=self.model_name,
                        attempts=attempts,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        usage=usage,
                        error=last_error,
                    ),
                    None,
                    retry_count,
                )
            except TransientReasoningError as exc:
                # A timeout or a busy node says nothing about the question, so the second
                # attempt sends it again unchanged rather than the schema-retry preamble.
                last_error = _sanitize_error(exc)
                logger.warning("ai planner primary transient failure: %s", last_error)
                if attempts == 1:
                    continue
                return (
                    PlannerStageResult(
                        stage="primary",
                        status="unavailable",
                        provider=self.provider_name,
                        model=self.model_name,
                        attempts=attempts,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        usage=usage,
                        error=last_error,
                    ),
                    None,
                    retry_count,
                )
            except Exception as exc:
                last_error = _sanitize_error(exc)
                logger.warning("ai planner primary provider failure: %s", last_error)
                return (
                    PlannerStageResult(
                        stage="primary",
                        status="unavailable",
                        provider=self.provider_name,
                        model=self.model_name,
                        attempts=attempts,
                        duration_ms=(time.perf_counter() - started) * 1000,
                        usage=usage,
                        error=last_error,
                    ),
                    None,
                    retry_count,
                )
        return (
            PlannerStageResult(
                stage="primary",
                status="invalid_output",
                attempts=attempts,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=last_error,
            ),
            None,
            retry_count,
        )

    async def _review(
        self,
        question: str,
        planned: PlannedTurn,
        catalog: FieldCatalog,
        selected_file_id: int,
        validation_error: str = "",
        unaccounted: tuple[str, ...] = (),
        absent_fields: tuple[str, ...] = (),
    ) -> PlannerStageResult:
        started = time.perf_counter()
        user = _review_user_prompt(
            question,
            planned,
            catalog,
            selected_file_id,
            validation_error=validation_error,
            unaccounted=unaccounted,
            absent_fields=absent_fields,
        )
        try:
            result = await self._call(self._review_provider, AI_REVIEW_SYSTEM, user, PlanReviewResponse)
            verdict = result.value.root
            metadata: dict[str, Any] = {"verdict": verdict.verdict}
            if isinstance(verdict, ReviewCorrected):
                metadata["missing"] = list(verdict.missing)
                metadata["plan"] = verdict.plan
            elif isinstance(verdict, ReviewNeedsClarification):
                metadata["missing"] = list(verdict.missing)
                metadata["question"] = verdict.question
            return PlannerStageResult(
                stage="review",
                status="ok",
                provider=result.provider,
                model=result.model,
                attempts=1,
                duration_ms=(time.perf_counter() - started) * 1000,
                output_metadata=metadata,
                usage=_usage_from(result),
            )
        except ValidationError as exc:
            error = _sanitize_error(exc)
            logger.warning("ai planner review validation failed: %s", error)
            return PlannerStageResult(
                stage="review",
                status="invalid_output",
                provider=self.provider_name,
                model=self.model_name,
                attempts=1,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=error,
            )
        except Exception as exc:
            error = _sanitize_error(exc)
            logger.warning("ai planner review provider failure: %s", error)
            return PlannerStageResult(
                stage="review",
                status="unavailable",
                provider=self.provider_name,
                model=self.model_name,
                attempts=1,
                duration_ms=(time.perf_counter() - started) * 1000,
                error=error,
            )

    async def _call(self, provider: ReasoningProvider, system: str, user: str, model_type):
        method = getattr(provider, "structured_output_with_metadata", None)
        if callable(method):
            return await method(system=system, user=user, response_model=model_type)
        parsed = await provider.structured_output(system=system, user=user, response_model=model_type)
        return StructuredOutputResult(
            value=parsed,
            provider=getattr(provider, "provider_name", ""),
            model=getattr(provider, "model_name", ""),
        )


def _review_eligible(planned: PlannedTurn) -> bool:
    for action in planned.actions:
        if isinstance(action, PlannedQueryAction | VerifyPreviousAction):
            return True
        if isinstance(action, ModifyPreviousAction) and not _navigation_only(action):
            return True
    return False


def _navigation_only(action: ModifyPreviousAction) -> bool:
    return bool(
        (action.page or action.restore_frame)
        and not action.changes
        and action.goal is None
        and action.sort_by is None
        and action.sort_direction is None
        and action.limit is None
        and action.offset is None
        and action.requested_fields is None
        and action.group_value_part is None
        and action.sample is None
        and action.exhaustive is None
        and action.window is None
        and action.presentation is None
    )


def planner_visible_labels(dataset: DatasetSpec) -> tuple[str, ...]:
    labels = [dataset.user_facing_label, *dataset.aliases]
    cleaned = []
    for label in labels:
        text = str(label).strip()
        if not text:
            continue
        if re.fullmatch(r"(?:file\s+)?\d+", text, re.IGNORECASE):
            continue
        cleaned.append(text)
    return tuple(dict.fromkeys(cleaned))


def authorized_dataset_options(catalog: FieldCatalog) -> list[AuthorizedDatasetOption]:
    return [
        AuthorizedDatasetOption(
            file_id=item.file_id,
            label=item.user_facing_label,
            aliases=planner_visible_labels(item),
            private=item.private,
        )
        for item in catalog.datasets
    ]


def render_dataset_not_selected(
    action: PlannedConversationAction | QueryAction,
    *,
    selected: DatasetSpec,
    options: list[AuthorizedDatasetOption],
) -> tuple[str, int | None]:
    requested = ""
    if isinstance(action, PlannedConversationAction):
        requested = (action.response or "").strip()
    needle = _norm_label(requested)
    if needle:
        for option in options:
            if option.file_id == selected.file_id:
                continue
            names = [_norm_label(option.label), *(_norm_label(alias) for alias in option.aliases)]
            if needle in names:
                return (
                    f"This chat is scoped to {selected.user_facing_label}. "
                    f"Select {option.label} to ask about that list.",
                    option.file_id,
                )
    return (
        f"I can only answer using the currently selected list, {selected.user_facing_label}.",
        None,
    )


def _norm_label(value: str) -> str:
    return " ".join(value.casefold().split())


def _option_names(option: AuthorizedDatasetOption) -> tuple[str, ...]:
    return (option.label, *option.aliases)


def _singular(word: str) -> str:
    """A crude stem, enough to let a plural label meet a singular mention."""
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _phrase_tokens(text: str) -> list[str]:
    """Comparable words: casefolded, punctuation dropped, plurals folded."""
    return [_singular(word) for word in re.findall(r"[a-z0-9]+", text.casefold())]


def _text_names_option(text: str, option: AuthorizedDatasetOption) -> bool:
    """Whether the text names this list, by words rather than by substring.

    Substring matching missed the way people actually write. "List the first 5 additional
    death names" does not contain the string "additional deaths", so a question about the
    selected list read as a question about no list at all, and the reviewer's objection that
    the list holds no such thing went unchallenged. Matching word runs with plurals folded
    lets the label meet the mention, and is stricter at the edges than a substring ever was:
    "master" no longer matches inside "postmaster".
    """
    haystack = _phrase_tokens(text)
    if not haystack:
        return False
    for name in _option_names(option):
        needle = _phrase_tokens(name)
        if not needle or len(needle) > len(haystack):
            continue
        span = len(needle)
        if any(haystack[i : i + span] == needle for i in range(len(haystack) - span + 1)):
            return True
    return False


def _text_names_other_option(
    text: str,
    selected_file_id: int,
    options: list[AuthorizedDatasetOption],
) -> bool:
    return any(
        option.file_id != selected_file_id and _text_names_option(text, option)
        for option in options
    )


def should_honor_dataset_not_selected(
    action: PlannedConversationAction,
    *,
    question: str,
    selected_file_id: int,
    options: list[AuthorizedDatasetOption],
) -> bool:
    """True only when the user actually named a different source."""
    selected = next((item for item in options if item.file_id == selected_file_id), None)
    response = (action.response or "").strip()
    if response:
        if (
            selected is not None
            and _text_names_option(response, selected)
            and not _text_names_other_option(response, selected_file_id, options)
        ):
            return False
        return True
    return _text_names_other_option(question, selected_file_id, options)


def question_names_only_the_selected_list(
    question: str,
    selected_file_id: int,
    options: list[AuthorizedDatasetOption],
) -> bool:
    """True when the user named the list they are already on, and no other authorized list.

    Registry labels and aliases decide this, so it carries no dataset vocabulary of its own.
    """
    selected = next((item for item in options if item.file_id == selected_file_id), None)
    if selected is None:
        return False
    return _text_names_option(question, selected) and not _text_names_other_option(
        question, selected_file_id, options
    )


def _field_phrases(spec) -> list[list[str]]:
    """Every way this field can be named, as comparable word runs."""
    names = [spec.human_label, spec.semantic_field.replace("_", " "), *spec.aliases]
    return [tokens for tokens in (_phrase_tokens(name) for name in names) if tokens]


def absent_fields_named(
    question: str,
    selected_file_id: int,
    catalog: FieldCatalog,
) -> list[str]:
    """Fields some authorized list records, named in the question, that this list has not.

    Only multi-word names count. A single broad word is exactly how the wrong field gets
    picked in the first place -- "student number" was answered from student_name, whose
    aliases include the bare word "student", giving a confident count of records that have a
    name where the researcher asked about a number the list does not record. One word is
    evidence of very little; two in sequence are evidence of a field.
    """
    tokens = _phrase_tokens(question)
    if not tokens:
        return False

    def present(needle: list[str]) -> bool:
        span = len(needle)
        if not span or span > len(tokens):
            return False
        return any(tokens[i : i + span] == needle for i in range(len(tokens) - span + 1))

    selected = [
        phrase
        for spec in catalog.planner_fields_for(selected_file_id)
        for phrase in _field_phrases(spec)
    ]
    found: list[str] = []
    for spec in catalog.fields:
        if spec.file_id == selected_file_id:
            continue
        for needle in _field_phrases(spec):
            if len(needle) < 2 or not present(needle):
                continue
            if any(phrase == needle for phrase in selected):
                continue
            if spec.human_label not in found:
                found.append(spec.human_label)
            break
    return found


def question_names_field_absent_from_selected(
    question: str,
    selected_file_id: int,
    catalog: FieldCatalog,
) -> bool:
    return bool(absent_fields_named(question, selected_file_id, catalog))


def _assert_grounded_dataset_not_selected(
    planned: PlannedTurn,
    *,
    question: str,
    selected_file_id: int,
    options: list[AuthorizedDatasetOption],
) -> None:
    not_selected = [
        action for action in planned.respond_actions() if action.intent == "dataset_not_selected"
    ]
    if not not_selected:
        return
    if planned.query_actions() or planned.modify_actions() or planned.verify_actions():
        return
    if should_honor_dataset_not_selected(
        not_selected[0],
        question=question,
        selected_file_id=selected_file_id,
        options=options,
    ):
        return
    raise PlannerContractError(
        "dataset_not_selected requires the user to name a different source; "
        "this question is about the selected list"
    )


def _field_line(spec) -> str:
    """One catalog line per field: everything the planner needs, nothing hardcoded.

    The prompt must carry no dataset vocabulary, so every property a rule can key
    on -- type, operators, aliases the user may say instead of the semantic name,
    and the recorded spellings of a value family -- travels in the payload for the
    one selected list.
    """
    parts = [
        f"- {spec.semantic_field} ({spec.semantic_type})",
        f"ops={','.join(spec.allowed_operators)}",
        f"label={spec.human_label}",
    ]
    if spec.aliases:
        parts.append("aliases=" + "; ".join(spec.aliases))
    caps = [
        name
        for name, enabled in (
            ("sortable", spec.sortable),
            ("aggregatable", spec.aggregatable),
        )
        if enabled
    ]
    if caps:
        parts.append("caps=" + ",".join(caps))
    families = (spec.validation_rules or {}).get("value_synonyms")
    if isinstance(families, dict) and families:
        rendered = []
        for key, members in families.items():
            if isinstance(members, list) and members:
                rendered.append(f"{key}=[{'; '.join(str(m) for m in members)}]")
        if rendered:
            parts.append("value_families=" + " ".join(rendered))
    rules = spec.validation_rules or {}
    filled = rules.get("recorded_count")
    total = rules.get("record_count")
    if isinstance(filled, int) and isinstance(total, int) and total > 0:
        # How much of this field anyone actually filled in. A label says what a field is
        # for; this says whether it was ever used. File 94's "Nation" is filled in 3 rows of
        # 56 and has never held a place of origin, so binding "from Garden River" to it and
        # answering zero was a statement about the data that the data does not support.
        parts.append(f"recorded={filled}/{total}")
    # recorded_values is deliberately NOT shown to the planner. It was, briefly: it stopped
    # "records from Garden River" binding to a Nation field that is empty in 53 of 56 rows.
    # But listing a field's categories reads as a menu of conditions, and the planner began
    # filtering on values nobody asked for -- turning the list's own name into a predicate,
    # so "how many records are in the confirmed deaths list" answered 25 of 82. Measured
    # over the four cases it broke plus the two it helped: 0/8 with it, 10/16 without.
    #
    # The registry still carries it, and the compiler still uses it -- exact_category_terms
    # needs it to tell "no" inside "unknown" from "School" inside "School (NCTR SOURCE)".
    # It is evidence for canonicalising a value, not a prompt for choosing one.
    return " ".join(parts)


def _planner_user_prompt(
    question: str,
    *,
    catalog: FieldCatalog,
    selected_file_id: int,
    authorized_options: list[AuthorizedDatasetOption],
    context: ConversationContext,
    input_mode: str,
    min_confidence: float,
) -> str:
    selected = catalog.dataset(selected_file_id)
    label = selected.user_facing_label if selected is not None else "selected list"
    # The selected list gets its aliases for the same reason the other lists do: the
    # planner has to recognise the user naming the list it is already on. Without them
    # "how many records are in additional deaths", asked on Additional Deaths, was read as
    # a request about some other source and refused.
    # Every alias, including one that only differs from the label by case. Dropping that
    # one removed the exact wording a user is most likely to type: file 93's label is
    # "Additional Deaths" and its lowercase alias is what someone actually writes.
    selected_aliases = list(selected.aliases if selected is not None else ())
    fields = [_field_line(spec) for spec in catalog.planner_fields_for(selected_file_id)]
    other = []
    for option in authorized_options:
        if option.file_id == selected_file_id:
            continue
        other.append(f"- {option.label}" + (f" aliases={', '.join(option.aliases[1:])}" if len(option.aliases) > 1 else ""))
    active = ""
    if context.active_query is not None:
        active = context.active_query.model_dump_json()
    # Order matters for cost, not for meaning. Providers cache on a shared prefix, so
    # everything that is identical on every turn for this list -- the catalog above all,
    # 1,600 to 3,450 tokens of it -- goes first, and everything that changes per turn goes
    # last. With QUESTION on the first line the cacheable prefix ended after ten
    # characters and the entire catalog was re-read from scratch on every single turn.
    return "\n".join(
        [
            f"SELECTED LIST: {label}"
            + (f" aliases={', '.join(selected_aliases)}" if selected_aliases else ""),
            "SELECTED FIELDS:",
            *(fields if fields else ["- none"]),
            "OTHER AUTHORIZED LIST NAMES (labels only; do not plan against them):",
            *(other if other else ["- none"]),
            f"MODE: {input_mode}",
            f"MIN_CONFIDENCE: {min_confidence}",
            "ACTIVE QUERY:",
            active or "(none)",
            "MEMORY:",
            context.memory_text or "(none)",
            f"QUESTION: {question}",
        ]
    )


def _review_user_prompt(
    question: str,
    planned: PlannedTurn,
    catalog: FieldCatalog,
    selected_file_id: int,
    validation_error: str = "",
    unaccounted: tuple[str, ...] = (),
    absent_fields: tuple[str, ...] = (),
) -> str:
    fields = [_field_line(spec) for spec in catalog.planner_fields_for(selected_file_id)]
    # Same prefix reasoning as the planner prompt: the catalog is identical on every turn,
    # the question and the candidate plan are not.
    lines = [
        "SELECTED FIELDS:",
        *(fields if fields else ["- none"]),
        f"QUESTION: {question}",
        "CANDIDATE PLAN:",
        planned.model_dump_json(),
    ]
    if validation_error:
        lines.extend(
            [
                "TRUSTED VALIDATION ERROR:",
                validation_error,
                "Correct the plan so every field is in SELECTED FIELDS. "
                "Do not invent fields from another list. group_by for 'most common X' is X, never count.",
            ]
        )
    if unaccounted:
        # Present only when the plan actually carries such a condition, so the prompt
        # every ordinary turn sends is unchanged byte for byte, and the cacheable
        # catalog prefix above it is untouched either way.
        lines.extend(
            [
                "CONDITIONS NOT STATED AS REQUIREMENTS:",
                *(f"- {item}" for item in unaccounted),
                "The plan filters on these and does not claim them as requirements. "
                "Read QUESTION and decide each one: if the question does not ask for "
                "it, return the corrected plan without it; if the question does ask "
                "for it, keep it and state it as a requirement. Never drop a condition "
                "the question asks for.",
            ]
        )

    if absent_fields:
        # Present only when the question names a field this list does not record, so
        # the ordinary prompt is unchanged. Without it the reviewer approved answering
        # "how many potential records have a student number" from student_name.
        lines.extend(
            [
                "NAMED BUT NOT ON THIS LIST:",
                *(f"- {item}" for item in absent_fields),
                "The question names these and the selected list does not record them. "
                "Do not answer them from a different field whose name merely overlaps. "
                "If the plan does that, return needs_clarification saying the selected "
                "list does not record it.",
            ]
        )

    return "\n".join(lines)


def _usage_from(result: StructuredOutputResult) -> dict[str, Any]:
    return {
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
    }


def _merge_usage_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)

    def _add(key: str) -> None:
        a = left.get(key)
        b = right.get(key)
        if a is None and b is None:
            return
        try:
            merged[key] = (0 if a is None else a) + (0 if b is None else b)
        except TypeError:
            merged[key] = b if b is not None else a

    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost_usd", "duration_ms"):
        _add(key)
    return merged


def _merged_usage(result: AIPlanningResult) -> dict[str, Any]:
    usage = dict(result.primary.usage or {})
    if result.review is not None:
        usage = _merge_usage_dicts(usage, result.review.usage or {})
    usage["provider"] = result.primary.provider
    usage["model"] = result.primary.model
    return usage


def _sanitize_error(exc: BaseException) -> str:
    # Many transport exceptions (read timeouts, connection resets) carry no message,
    # so str(exc) is empty and the log line reads "provider failure: " with nothing
    # after it. The type name is the only diagnostic available for those.
    text = str(exc).strip()
    text = f"{type(exc).__name__}: {text}" if text else type(exc).__name__
    text = re.sub(r"(?i)(api[_-]?key|bearer|password|secret)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    return text[:400]


def _failure_text(status: str, mode: str) -> str:
    table = PLANNER_UNAVAILABLE_TEXT if status == "planner_unavailable" else PLANNER_INVALID_TEXT
    return table["voice" if mode == "voice" else "text"]


def filter_conversation_for_dataset(
    context: ConversationContext,
    selected_file_id: int,
) -> ConversationContext:
    active = context.active_query
    if active is not None and list(active.datasets) != [selected_file_id]:
        active = None
    frames = tuple(
        item
        for item in context.topic_frames
        if list(item.get("datasets") or item.get("file_ids") or []) == [selected_file_id]
    )
    return ConversationContext(
        active_plan=context.active_plan,
        active_query_text=context.active_query_text if active is not None else "",
        memory_text=context.memory_text,
        active_query=active,
        topic_frames=frames,
        last_action_keys=context.last_action_keys,
        user_display_name=context.user_display_name,
        last_assistant_text=context.last_assistant_text,
    )


async def plan_user_turn_ai(
    question: str,
    scope: AccessScope,
    catalog: FieldCatalog,
    *,
    selected_file_id: int,
    semantic_compiler=None,
    conversation: ConversationContext | None = None,
    memory_text: str = "",
    input_mode: Literal["text", "voice"] = "text",
    reasoner: ReasoningProvider | None = None,
    authorized_catalog: FieldCatalog | None = None,
    **_ignored,
) -> PlanRouteResult:
    """AI-mode planner. No deterministic semantic fallback."""
    del semantic_compiler
    timing = TimingRecorder()
    with timing.measure("normalize_ms"):
        normalized = normalize_transport(question)
    if not (normalized.normalized_text or question).strip():
        return PlanRouteResult(
            plan=None,
            status="empty",
            source="ai_planner",
            normalized_turn=normalized,
            detail="empty transcript",
            response_text="Sorry, I didn't catch that.",
            timings=timing.finish(),
            review_status="skipped",
        )

    settings = get_settings()
    context = filter_conversation_for_dataset(
        conversation or ConversationContext(memory_text=memory_text),
        selected_file_id,
    )
    if memory_text and not context.memory_text:
        context = ConversationContext(
            active_plan=context.active_plan,
            active_query_text=context.active_query_text,
            memory_text=memory_text,
            active_query=context.active_query,
            topic_frames=context.topic_frames,
            last_action_keys=context.last_action_keys,
            user_display_name=context.user_display_name,
            last_assistant_text=context.last_assistant_text,
        )
    scoped = catalog.for_scope(scope)
    options = authorized_dataset_options(authorized_catalog or scoped)
    provider = reasoner
    if provider is None:
        from app.llm.factory import get_reasoning_provider

        planner_model = settings.planner_model.strip() or None
        review_model = settings.planner_review_model.strip() or planner_model
        provider = get_reasoning_provider(planner_model)
        review_provider = get_reasoning_provider(review_model) if review_model else provider
    else:
        review_provider = provider
    planner: AIPlanner | UnavailableAIPlanner
    if provider is None:
        planner = UnavailableAIPlanner("reasoning provider is not configured")
    else:
        planner = AIPlanner(provider, review_provider=review_provider)

    with timing.measure("ai_planner_ms"):
        result = await planner.plan(
            question,
            catalog=scoped,
            selected_file_id=selected_file_id,
            authorized_options=options,
            context=context,
            input_mode=input_mode,
        )

    common = dict(
        source="ai_planner",
        normalized_turn=normalized,
        planner_attempts=result.planner_attempts,
        planner_retry_count=result.planner_retry_count,
        review_attempts=result.review_attempts,
        review_status=result.review_status,
        planner_total_model_calls=result.planner_total_model_calls,
        planner_failure_stage=result.planner_failure_stage,
        reasoning_calls=result.planner_total_model_calls,
        suggested_file_id=result.suggested_file_id,
        planner_provider=result.primary.provider,
        planner_model=result.primary.model,
        planner_usage=_merged_usage(result),
        original_planned=result.original_planned,
    )

    if result.status in {"planner_unavailable", "planner_invalid_output"}:
        return PlanRouteResult(
            plan=None,
            status=result.status,
            detail=result.detail,
            response_text=_failure_text(result.status, input_mode),
            timings=timing.finish(),
            **common,
        )
    if result.status == "clarification":
        return PlanRouteResult(
            plan=None,
            status="clarification",
            detail=result.detail,
            response_text=result.detail,
            clarification_question=result.detail,
            turn_plan=result.bound,
            final_response="compiler_response",
            timings=timing.finish(),
            **common,
        )
    if result.bound is None or result.planned is None:
        return PlanRouteResult(
            plan=None,
            status="planner_invalid_output",
            detail="planner produced no bound turn",
            response_text=_failure_text("planner_invalid_output", input_mode),
            timings=timing.finish(),
            **{**common, "planner_failure_stage": "primary"},
        )

    selected = scoped.dataset(selected_file_id)
    not_selected = next(
        (
            action
            for action in result.planned.respond_actions()
            if action.intent == "dataset_not_selected"
        ),
        None,
    )
    if (
        not_selected is not None
        and selected is not None
        and should_honor_dataset_not_selected(
            not_selected,
            question=question,
            selected_file_id=selected_file_id,
            options=options,
        )
    ):
        text, suggested = render_dataset_not_selected(
            not_selected, selected=selected, options=options
        )
        return PlanRouteResult(
            plan=None,
            status="dataset_not_selected",
            detail=text,
            response_text=text,
            turn_plan=result.bound,
            final_response="compiler_response",
            timings=timing.finish(),
            **{**common, "suggested_file_id": suggested},
        )

    return await _validate_and_route(
        result,
        planner=planner if isinstance(planner, AIPlanner) else None,
        question=question,
        scope=scope,
        catalog=scoped,
        authorized_options=options,
        selected_file_id=selected_file_id,
        context=context,
        input_mode=input_mode,
        normalized=normalized,
        timing=timing,
        common=common,
    )


async def _validate_and_route(
    result: AIPlanningResult,
    *,
    planner: AIPlanner | None,
    question: str,
    scope: AccessScope,
    catalog: FieldCatalog,
    selected_file_id: int,
    context: ConversationContext,
    input_mode: str,
    normalized: NormalizedTurn,
    timing: TimingRecorder,
    common: dict[str, Any],
    authorized_options: list[AuthorizedDatasetOption] | None = None,
    already_reviewed_correction: bool = False,
) -> PlanRouteResult:
    settings = get_settings()
    planned = result.planned
    bound = result.bound
    assert planned is not None and bound is not None
    coerced = coerce_planned_turn(planned, catalog, selected_file_id)
    if coerced is not planned:
        planned = coerced
        bound = bind_scope(planned, selected_file_id)
        result = AIPlanningResult(
            planned=planned,
            bound=bound,
            primary=result.primary,
            review=result.review,
            review_status=result.review_status,
            planner_attempts=result.planner_attempts,
            planner_retry_count=result.planner_retry_count,
            review_attempts=result.review_attempts,
            planner_total_model_calls=result.planner_total_model_calls,
            planner_failure_stage=result.planner_failure_stage,
            status=result.status,
            detail=result.detail,
            suggested_file_id=result.suggested_file_id,
            original_planned=result.original_planned or result.planned,
        )
    has_active = context.active_query is not None or bool(context.topic_frames)
    try:
        with timing.measure("turn_validation_ms"):
            validated = validate_turn_plan(
                bound,
                scope=scope,
                catalog=catalog,
                has_active_query=has_active,
                strict=True,
            )
        if settings.planner_requirement_check:
            check_requirement_parity(planned, validated)
        # Conditions the plan filters on that it never claimed as requirements. Handed to the
        # review below rather than acted on here: at this layer an invented filter and an
        # under-declared one look identical, and only the question tells them apart.
        unaccounted = tuple(unaccounted_conditions(planned, validated))
        policy = resolve_final_response(validated)
        if only_reference(validated):
            return PlanRouteResult(
                plan=None,
                status="reference",
                detail=validated.normalized_request or "reference previous result",
                turn_plan=validated,
                final_response="deterministic",
                timings=timing.finish(),
                **common,
            )
        if only_clarification(validated):
            text = validated.clarify_actions()[0].question
            return PlanRouteResult(
                plan=None,
                status="clarification",
                detail=text,
                response_text=text,
                clarification_question=text,
                turn_plan=validated,
                final_response="compiler_response",
                timings=timing.finish(),
                **common,
            )
        if only_direct_response(validated) or policy == "compiler_response":
            if validated.query_actions() or validated.modify_actions() or validated.verify_actions():
                raise PlanValidationError("compiler_response cannot suppress a query action", code="response_contract")
            from app.planning.router import describe_available_data

            response = canned_response(
                validated,
                mode=input_mode,
                catalog_text=describe_available_data(catalog, file_ids=(selected_file_id,)),
                user_display_name=context.user_display_name,
                last_assistant_text=context.last_assistant_text,
            ) or (validated.respond_actions()[0].response if validated.respond_actions() else "")
            return PlanRouteResult(
                plan=None,
                status="conversational",
                detail=validated.normalized_request or "conversational turn",
                response_text=response,
                turn_plan=validated,
                final_response="compiler_response",
                timings=timing.finish(),
                **common,
            )
        with timing.measure("query_plan_build_ms"):
            plan = build_query_plan(
                validated,
                scope=scope,
                catalog=catalog,
                active_query=context.active_query,
                frames=_frame_map(context),
            )
        with timing.measure("predicate_contract_ms"):
            validate_predicate_contract(plan)
        if (
            planner is not None
            and not already_reviewed_correction
            and get_settings().planner_self_review
            and get_settings().planner_review_mode == "always"
            and result.planned is not None
            and _review_eligible(result.planned)
        ):
            with timing.measure("ai_self_review_ms"):
                review_stage = await planner._review(
                    question,
                    result.planned,
                    catalog,
                    selected_file_id,
                    unaccounted=unaccounted,
                    absent_fields=tuple(
                        absent_fields_named(question, selected_file_id, catalog)
                    ),
                )
            common["review_attempts"] = review_stage.attempts
            common["planner_total_model_calls"] = (
                int(common.get("planner_total_model_calls") or 0) + review_stage.attempts
            )
            common["reasoning_calls"] = common["planner_total_model_calls"]
            common["planner_usage"] = _merge_usage_dicts(
                common.get("planner_usage") if isinstance(common.get("planner_usage"), dict) else {},
                review_stage.usage,
            )
            if review_stage.status == "unavailable":
                # Same reasoning as the invalid_output branch below: the candidate has
                # already passed bind/validate/build/predicate. The review is a safety
                # net over an executable plan, not a gate in front of one, so a review
                # outage must not convert a good answer into a service error.
                logger.warning(
                    "ai planner review unavailable; keeping validated plan: %s",
                    review_stage.error or "no detail",
                )
                common["review_status"] = "unavailable"
                verdict = None
            elif review_stage.status == "invalid_output":
                # The candidate already passed bind/validate/build/predicate.
                # Review schema slop must not destroy that executable plan.
                logger.warning(
                    "ai planner review invalid; keeping validated plan: %s",
                    review_stage.error,
                )
                common["review_status"] = "invalid_output"
                verdict = None
            else:
                verdict = (review_stage.output_metadata or {}).get("verdict")
            if (
                verdict == "needs_clarification"
                and question_names_only_the_selected_list(
                    question, selected_file_id, authorized_options or []
                )
                # ... and the objection cannot be about a field this list genuinely lacks.
                # Without this the overrule is worse than the bug it fixes: "how many
                # potential records have a student number" names the selected list too, so a
                # correct refusal would be overruled into answering from student_name -- 53
                # records that have a name, for a number the list does not record.
                and not question_names_field_absent_from_selected(
                    question, selected_file_id, catalog
                )
            ):
                # The reviewer asked which list this is about when the question named the
                # selected list itself -- "how many records are in additional deaths?" on
                # Additional Deaths came back "the selected list does not contain records
                # about additional deaths", every time. The premise is checkably false, and
                # the same falsehood is already refused on the primary path by
                # _assert_grounded_dataset_not_selected; review simply had no equivalent.
                #
                # Overruled rather than corrected, on this file's own rule that review is a
                # safety net over an executable plan and not a gate in front of one: the
                # candidate has passed bind, validate, build and predicate, so a clarifying
                # question nobody needs must not replace an answer we can give.
                logger.warning(
                    "ai planner review asked to clarify a question that names the selected "
                    "list; keeping validated plan"
                )
                common["review_status"] = "clarification_overruled"
                verdict = None
            if verdict == "needs_clarification":
                question_text = str((review_stage.output_metadata or {}).get("question") or "")
                return PlanRouteResult(
                    plan=None,
                    status="clarification",
                    detail=question_text or "Could you clarify the missing conditions?",
                    response_text=question_text or "Could you clarify the missing conditions?",
                    clarification_question=question_text,
                    turn_plan=validated,
                    final_response="compiler_response",
                    timings=timing.finish(),
                    **{**common, "review_status": "needs_clarification"},
                )
            if verdict == "corrected":
                corrected = (review_stage.output_metadata or {}).get("plan")
                if isinstance(corrected, PlannedTurn):
                    corrected_result = AIPlanningResult(
                        planned=corrected,
                        bound=bind_scope(corrected, selected_file_id),
                        primary=result.primary,
                        review=review_stage,
                        review_status="corrected",
                        planner_attempts=result.planner_attempts,
                        planner_retry_count=result.planner_retry_count,
                        review_attempts=review_stage.attempts,
                        planner_total_model_calls=int(common["planner_total_model_calls"]),
                        status="planned",
                        original_planned=result.planned,
                    )
                    common["review_status"] = "corrected"
                    return await _validate_and_route(
                        corrected_result,
                        planner=planner,
                        question=question,
                        scope=scope,
                        catalog=catalog,
                        authorized_options=authorized_options,
                        selected_file_id=selected_file_id,
                        context=context,
                        input_mode=input_mode,
                        normalized=normalized,
                        timing=timing,
                        common=common,
                        already_reviewed_correction=True,
                    )
            if review_stage.status == "ok" and common.get("review_status") != (
                "clarification_overruled"
            ):
                # The call itself succeeded, so "ok" alone would relabel an overruled
                # clarification as a clean bill of health and hide it from the traces.
                common["review_status"] = "complete"
        elif not already_reviewed_correction:
            common["review_status"] = "skipped"
        with timing.measure("value_expansion_ms"):
            plan = expand_plan_values(plan, catalog, profile="ai")
        with timing.measure("plan_validation_ms"):
            plan = validate_query_plan(plan, scope, catalog)
    except PlanValidationError as exc:
        if exc.code == "access_restricted":
            raise
        if (
            exc.code in _REVIEWABLE_VALIDATION_CODES
            and planner is not None
            and not already_reviewed_correction
            and get_settings().planner_self_review
            and result.planned is not None
        ):
            with timing.measure("ai_self_review_ms"):
                salvage = await planner._review(
                    question,
                    result.planned,
                    catalog,
                    selected_file_id,
                    validation_error=str(exc),
                )
            common["review_attempts"] = salvage.attempts
            common["planner_total_model_calls"] = (
                int(common.get("planner_total_model_calls") or 0) + salvage.attempts
            )
            common["reasoning_calls"] = common["planner_total_model_calls"]
            common["planner_usage"] = _merge_usage_dicts(
                common.get("planner_usage") if isinstance(common.get("planner_usage"), dict) else {},
                salvage.usage,
            )
            if salvage.status == "ok":
                verdict = (salvage.output_metadata or {}).get("verdict")
                if verdict == "needs_clarification":
                    question_text = str((salvage.output_metadata or {}).get("question") or "")
                    return PlanRouteResult(
                        plan=None,
                        status="clarification",
                        detail=question_text or str(exc),
                        response_text=question_text or _safe_clarification(exc),
                        clarification_question=question_text or _safe_clarification(exc),
                        turn_plan=bound,
                        final_response="compiler_response",
                        timings=timing.finish(),
                        **{**common, "review_status": "needs_clarification"},
                    )
                corrected = (salvage.output_metadata or {}).get("plan")
                if verdict == "corrected" and isinstance(corrected, PlannedTurn):
                    common["review_status"] = "corrected"
                    return await _validate_and_route(
                        AIPlanningResult(
                            planned=corrected,
                            bound=bind_scope(corrected, selected_file_id),
                            primary=result.primary,
                            review=salvage,
                            review_status="corrected",
                            planner_attempts=result.planner_attempts,
                            planner_retry_count=result.planner_retry_count,
                            review_attempts=salvage.attempts,
                            planner_total_model_calls=int(common["planner_total_model_calls"]),
                            status="planned",
                            original_planned=result.planned,
                        ),
                        planner=planner,
                        question=question,
                        scope=scope,
                        catalog=catalog,
                        authorized_options=authorized_options,
                        selected_file_id=selected_file_id,
                        context=context,
                        input_mode=input_mode,
                        normalized=normalized,
                        timing=timing,
                        common=common,
                        already_reviewed_correction=True,
                    )
        if exc.code == "dropped_requirement":
            return PlanRouteResult(
                plan=None,
                status="clarification",
                detail=str(exc),
                response_text=f"I may have missed part of that request: {exc}. Could you restate it?",
                clarification_question=str(exc),
                turn_plan=bound,
                final_response="compiler_response",
                timings=timing.finish(),
                **common,
            )
        return PlanRouteResult(
            plan=None,
            status="clarification",
            detail=str(exc),
            response_text=_safe_clarification(exc),
            clarification_question=_safe_clarification(exc),
            turn_plan=bound,
            final_response="compiler_response",
            timings=timing.finish(),
            **common,
        )
    except UnsupportedFieldsError as exc:
        return PlanRouteResult(
            plan=None,
            status="unsupported_fields",
            detail=str(exc),
            response_text=str(exc),
            turn_plan=bound,
            final_response="deterministic",
            timings=timing.finish(),
            **common,
        )
    except QueryPlanBuildError as exc:
        return PlanRouteResult(
            plan=None,
            status="clarification",
            detail=str(exc),
            response_text="I need a more specific question about the selected list.",
            clarification_question="I need a more specific question about the selected list.",
            turn_plan=bound,
            final_response="compiler_response",
            timings=timing.finish(),
            **common,
        )

    return PlanRouteResult(
        plan=plan,
        status="planned",
        detail=validated.normalized_request or "ai planned query",
        turn_plan=validated,
        final_response=policy,
        timings=timing.finish(),
        **common,
    )


def _frame_map(context: ConversationContext) -> dict[str, Any]:
    frames: dict[str, Any] = {}
    for item in context.topic_frames:
        key = str(item.get("frame_key") or item.get("key") or "")
        if key:
            frames[key] = item
    return frames


_SAFE_CLARIFICATIONS = {
    "invalid_followup": "Which records would you like me to look at?",
    "op_contract": "Those conditions contradict each other. Could you restate the request?",
    "response_contract": "I need to treat that as a records question. Could you restate it?",
    "unknown_field": "That field is not available on the selected list.",
    "operator": "I can't filter that field that way on the selected list. Could you restate it?",
    "unknown_dataset": "I can only answer using the currently selected list.",
    "scope": "I can only answer using the currently selected list.",
    "budget": "That request covered too much at once. Could you narrow it?",
}


def _safe_clarification(exc: PlanValidationError) -> str:
    """What the researcher is told when a plan does not validate.

    Never the exception text. These messages are written for whoever has to fix the plan,
    not for whoever asked the question -- "operator STARTS_WITH is not allowed on
    name_search for file 49" reached a researcher verbatim -- and the codes for a refused
    table or refused SQL would put internal schema names in a chat transcript. Only the
    enumerated codes get wording; anything else falls back to a sentence that says the
    request could not be worked out, and the raw text stays on `detail` for the trace.
    """
    return _SAFE_CLARIFICATIONS.get(
        exc.code or "",
        "I wasn't able to work out how to answer that. Could you say it another way?",
    )
