# AI-Planner-First Turn Understanding: End-to-End Implementation and Rollout Plan

## 1. Purpose and status

This document is the implementation-ready plan for replacing Nia's layered natural-language routing with one AI-planner-first path while preserving deterministic security, validation, compilation, and execution.

It covers all three migration phases:

1. Build and qualify the AI path while legacy remains the default.
2. Make the AI path the default while retaining legacy as an emergency rollback.
3. Remove the legacy planner after a continuously stable two-week AI-default period.

The implementation must preserve the intent of `nia_ai_planner_final_plan_updated.md`, with the verified corrections in this document taking precedence where the proposal conflicts with the current repository or installed SDK.

## 2. Decisions already made

- Phase 1 ships first with `PLANNER_MODE=legacy` as the default and `ai` as an opt-in.
- The AI planner is the only natural-language intent reader in AI mode. There is no deterministic semantic fallback after an AI failure.
- The UI-selected dataset, or an already-authorized conversation pin created from that selection, is the sole dataset scope.
- Self-review is enabled throughout Phase 1 and runs for every executable data request, independent of plan size.
- Paid xAI live verification is authorized.
- Live database verification will use the existing WSL2 Docker Compose environment and existing PostgreSQL volume. The volume must not be reset.
- Verified architectural corrections are intentional, not optional deviations.

## 3. Verified current baseline

The repository audit established the following baseline before implementation:

- The Python suite collects 331 tests and currently finishes with 328 passed and 3 database-dependent skips.
- The static planner catalog exposes 22 fields for file 49, 34 for file 91, 15 for file 93, and 13 for file 94.
- `QueryAction` contains semantic fields omitted from the source proposal's abbreviated list: `search_text`, `secondary_group_value_part`, `having_min_count`, `stats_value_part`, and `verify_previous`. The AI schema must retain them.
- `ActiveQuery` already contains `datasets`; no new `dataset_id` field is required in memory frames.
- Existing planner and nested Pydantic models already forbid extra fields, but the new AI-only envelopes must do so as well.
- The current xAI implementation is pinned to `xai-sdk==1.19.0` in lock files. Its `chat.parse()` API requires a `BaseModel` subclass, so a bare annotated union cannot be used as the review response model.
- `reasoning_calls` currently counts every provider call, including final synthesis and conversational generation. It cannot be redefined as planner-only without breaking compatibility.
- The current golden regression document mixes questions for different datasets and cannot validly be replayed verbatim against all four lists.
- WSL2 Ubuntu, Docker 29.6.1, Docker Compose 5.3.0, the backend image with xAI SDK 1.19.0, and the `infra_nia_pg_data` volume are present. PostgreSQL is currently stopped but can be started through the existing Compose project.

## 4. Target architecture and invariants

### 4.1 AI-mode flow

```text
final user input
    -> transport-only normalization
    -> empty-input guard
    -> selected dataset / conversation-pin authorization
    -> dataset-scope conflict guard
    -> selected catalog + authorized other-list names
    -> primary AI planner structured call
    -> bind selected dataset to every query action
    -> strict TurnPlan validation
    -> stated-requirement parity check
    -> unexpanded QueryPlan build
    -> predicate-tree contract validation
    -> AI self-review for eligible data actions
       -> complete: keep candidate
       -> corrected: bind and run the complete validation pipeline once more
       -> needs_clarification: return clarification
       -> provider/output failure: return a planner failure
    -> registry-backed value canonicalization
    -> normal QueryPlan validation
    -> deterministic execution
    -> deterministic response or evidence-backed synthesis
```

### 4.2 Non-negotiable invariants

- No AI-facing schema contains a dataset identifier.
- Trusted code always stamps the selected dataset after model output is parsed.
- The planner sees fields from exactly one dataset.
- The planner may see labels and aliases of other authorized datasets, but never their IDs, fields, records, or private existence.
- A question never changes scope, triggers fan-out, or silently substitutes the current list for another list.
- Authorization is checked on every turn, including stored conversation pins and reviewed corrections.
- Empty input and hard authorization/scope conflicts may terminate before the planner. Every other non-empty AI-mode turn that reaches routing enters the primary planner exactly once.
- Planner output is never executed without schema parsing, strict intent validation, QueryPlan construction, and QueryPlan validation.
- A reviewed or corrected plan receives no additional trust.
- Provider failures and malformed output are operational failures, not user ambiguity.
- Legacy behavior and legacy tests remain unchanged until Phase 3.

## 5. Public and internal contracts

### 5.1 AI-facing schema

Create `backend/app/planning/ai_turn_schema.py` with a strict `AIPlannerModel` base using `ConfigDict(extra="forbid")`.

#### `PlannedQueryAction`

Mirror `QueryAction` exactly except for `datasets`. Preserve:

- `goal`
- `filters` and `filter_logic`
- `denominator_filters`
- `search_text`
- `group_by`, `group_value_part`, and `secondary_group_value_part`
- `having_min_count`
- `top_n` and `per_group_top_n`
- `include_missing`
- `companion_field`
- `stats_value_part`
- `interval_start`, `interval_end`, `interval_min_days`, and `interval_max_days`
- `sort_by` and `sort_direction`
- `sample`
- `requested_fields`
- `window`, `limit`, and `offset`
- `exhaustive` and `presentation`
- `verify_previous`
- `aggregate`
- `compare`, including branch labels, filters, and search text

#### `PlannedTurn`

Mirror `TurnPlan`, substituting `PlannedQueryAction` in the action union and adding:

```python
stated_requirements: list[StatedRequirement]
```

Reuse closed nested models where their shape is already suitable. Add planner-side wrappers where an AI-specific validation rule is needed, including requiring a non-empty response for `general_conversation` while still allowing an empty `dataset_not_selected` response.

#### `StatedRequirement`

Use a discriminated union keyed by `kind`. Every variant carries:

- `action_index`: zero-based index into `PlannedTurn.actions`
- `text`: the requirement in the user's words
- the complete semantic payload needed for one-to-one comparison

The union must cover:

- goal
- filter, with collection (`filters`, `denominator_filters`, or compare branch), field, operator, value, branch index, and branch label
- filter logic
- search text, including compare-branch association
- projection
- grouping field, group position, and value part
- sorting field and direction
- interval fields and numeric minimum/maximum-day thresholds
- aggregate function, field, and statistics value part
- companion field
- `having_min_count`
- numeric slots: `top_n`, `per_group_top_n`, `limit`, and `offset`
- window anchor, size, and cursor
- explicit options: `include_missing`, `sample`, `exhaustive`, `presentation`, and `verify_previous`
- every semantic edit carried by `ModifyPreviousAction`

Validation must reject an out-of-range `action_index`, an incompatible action kind, incomplete compare-branch coordinates, and unknown operators.

Requirements stay on `PlannedTurn`; they are not added to `TurnPlan`. `bind_scope(planned, file_id)` produces the existing infrastructure-bearing `TurnPlan`, while candidate validation compares the original `PlannedTurn` with the bound plan before value expansion.

### 5.2 Review response

Define closed variants:

- `ReviewComplete`: only `verdict="complete"`
- `ReviewCorrected`: `verdict="corrected"`, a non-empty `missing` list, and a corrected `PlannedTurn`
- `ReviewNeedsClarification`: `verdict="needs_clarification"` and a non-empty `missing` list

Wrap their discriminated union in a named `PlanReviewResponse(RootModel[...])` so xAI SDK 1.19 can parse it. Callers unwrap `.root`.

Illegal combinations, unexpected keys, and any attempted dataset field must fail schema validation.

### 5.3 Conversation and result contracts

- Add `dataset_not_selected` to `ConversationAction.intent`, `CONVERSATIONAL_INTENTS`, and `TRUSTED_CONVERSATIONAL_INTENTS`.
- Add the following fields to `PlanRouteResult`, `TurnResult`, audit metadata, HTTP responses, streaming completion payloads, and optional frontend result types:
  - `planner_attempts`
  - `planner_retry_count`
  - `review_attempts`
  - `review_status`
  - `planner_total_model_calls`
  - `planner_failure_stage`
- `review_status` is one of `skipped`, `complete`, `corrected`, `needs_clarification`, `unavailable`, or `invalid_output`.
- Preserve `reasoning_calls` as total model calls across planning, review, synthesis, and any other generation.
- Add `suggested_file_id` and `error_code` propagation to every direct-reply path that currently drops them.

### 5.4 Configuration

Add typed settings and document them in `.env.example`:

```dotenv
PLANNER_MODE=legacy
PLANNER_MIN_CONFIDENCE=0.75
PLANNER_REQUIREMENT_CHECK=true
PLANNER_SELF_REVIEW=true
PLANNER_REVIEW_MODEL=
```

Corresponding `Settings` fields:

```python
planner_mode: Literal["legacy", "ai"] = "legacy"
planner_min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)
planner_requirement_check: bool = True
planner_self_review: bool = True
planner_review_model: str = ""
```

There is no condition-count threshold for self-review.

Tests that change settings must clear `get_settings()`'s cache before and after the case.

## 6. Planner implementation

### 6.1 AI planner component

Create `backend/app/planning/ai_planner.py` containing:

- `AI_PLANNER_SYSTEM`
- `AI_REVIEW_SYSTEM`
- selected-catalog and review prompt builders
- `PlannerStageResult`, with stage, status, provider, model, attempts, duration, request metadata, output metadata, usage, and sanitized error
- `AIPlanningResult`, aggregating primary and review stages
- `AIPlanner`
- `UnavailableAIPlanner`
- `bind_scope()` and candidate-validation orchestration
- `plan_user_turn_ai()`

Keep legacy `CompilerResult` semantics untouched instead of forcing AI review results through its hard-coded `semantic_compiler` layer.

### 6.2 Primary call and retry contract

- Normal primary success: one structured attempt.
- Retry exactly once when `PlannedTurn` parsing raises Pydantic `ValidationError`.
- If the second primary response is malformed, return `planner_invalid_output` at stage `primary` after two calls.
- Do not retry provider/network/authentication/rate-limit/timeout errors. Return `planner_unavailable` at stage `primary`.
- If the first response is malformed and the retry encounters a provider error, the final status is `planner_unavailable`; attempts remain two.
- Log a sanitized validation summary and truncated structured payload at warning level. Never log API keys or database rows.

### 6.3 Prompt responsibilities

The planner prompt becomes normative for semantics previously split across multiple readers. It must instruct the model to:

- plan against exactly one already-selected list and never emit a dataset ID
- produce `dataset_not_selected` for another named source instead of switching or substituting
- distinguish a source name from a proper-noun field value
- resolve spoken self-corrections and ignore fillers/polite wrappers
- clarify incomplete voice transcripts
- emit concepts rather than sentence fragments as filter values
- distinguish alternatives (`CONTAINS_ANY`) from true conjunctions (multiple `CONTAINS` under AND)
- preserve negation polarity
- avoid filtering on a field that is being enumerated as a grouped breakdown
- order life-event intervals chronologically
- represent base-name grouping explicitly
- reset paging for new requests and clear incompatible paging for samples
- choose deterministic versus synthesis output coherently
- emit a clarification below the supplied live confidence threshold
- enumerate every understood requirement at the same granularity used by the actions
- provide a bounded response inside the structured call for general conversation

Remove or rewrite current compiler rules that conflict with this contract, including the low-confidence “best query” rule, model-generated literal-Unknown exclusion, and synonym-family enumeration instructions.

Synonym expansion and literal-Unknown handling remain deterministic compiler behavior.

### 6.4 Requirement parity

Before value expansion:

1. Extract the expressed requirements from each planned/bound action into the same canonical requirement shapes.
2. Normalize only casing and whitespace for comparison.
3. Match each stated requirement to one distinct expressed item with the same action and branch coordinates.
4. Consume matches one-to-one so one predicate cannot satisfy two stated bounds.
5. Reject unmatched stated requirements with `dropped_requirement` and a clarification naming the safe `text` field.

Do not re-read the user question in deterministic code. The check verifies the planner against itself; the independent review handles requirements missed by both structures.

### 6.5 Self-review

Review eligibility depends only on action kind, never on filter or constraint count:

- every `QueryAction`: review
- every `VerifyPreviousAction`: review
- `ModifyPreviousAction` containing any substantive edit: review
- page/restore-only navigation: skip
- respond, clarify, and reference-only plans: skip

The reviewer receives the original question, original `PlannedTurn`, the selected catalog, and no other dataset's fields.

Outcomes:

- `complete`: continue with the original candidate
- `corrected`: replace the candidate, bind scope again, and repeat all strict checks and QueryPlan construction once
- `needs_clarification`: return a clarification naming the missing elements
- provider failure: `planner_unavailable`, stage `review`
- malformed review response: `planner_invalid_output`, stage `review`

The review stage receives one call and no retry. A corrected plan is not reviewed again.

Structured-call ceiling:

| Turn shape | Primary | Review | Planner total |
|---|---:|---:|---:|
| Conversation, clarification, reference | 1 | 0 | 1 |
| Executable data request | 1 | 1 | 2 |
| Data request after malformed-primary retry | 2 | 1 | 3 |
| Primary malformed twice | 2 | 0 | 2 |
| Review failure after clean primary | 1 | 1 | 2 |

Final synthesis is counted separately in `reasoning_calls`, so a retried and reviewed synthesis turn may contain four total provider calls while still respecting the three-call planner ceiling.

## 7. Trusted validation and compilation

### 7.1 Strict turn validation

Add `strict: bool = False` to `validate_turn_plan`.

Legacy passes or defaults to `False`. AI mode passes `True`.

Strict behavior:

- no executable escape hatch below `planner_min_confidence`
- unresolved intent without a clarification is rejected
- orphan modify, verify, or reference actions are not promoted into queries
- orphan follow-ups return “Which records would you like me to look at?”
- mixed conversation and research actions remain intact
- unknown fields, incompatible operators, invalid goals, invalid aggregates, structural injection, and access violations retain trusted validation
- safe validation failures return `clarification` with their underlying reason code rather than generic `invalid_plan`

### 7.2 Predicate contradictions

Because nested `Predicate` groups exist only after `QueryPlan` construction, run contradiction validation on the unexpanded `QueryPlan`, before synonym expansion.

Evaluate predicates only within genuinely conjunctive branches. Reject:

- different `EQUALS` values for one single-valued field in the same AND branch
- the same value both required and excluded on one field
- `IS_KNOWN` and `IS_UNKNOWN` on one field in the same AND branch

Permit:

- two equalities in separate OR branches
- multiple same-field `CONTAINS` predicates under AND
- valid sibling branches when another branch contains no contradiction

Use `op_contract` and surface a clarification without executing the gateway.

### 7.3 AI-mode value canonicalization

Give `expand_plan_values` an explicit profile or add an AI-specific wrapper. Its default must preserve legacy behavior until Phase 3.

AI profile:

- retain registry `value_synonyms` expansion
- retain literal-Unknown exclusion added beside `IS_KNOWN`
- never move a value to a different semantic field
- remove stray trailing punctuation
- clean every search string as free text
- strip leading articles from predicate values only when the field has `validation_rules.article_strip_safe=true`

Add an idempotent migration after the current migration sequence to set `article_strip_safe` only for genuine free-text notes. Mirror the metadata in the static catalog. Do not mark community, school, student/parent names, nation, or place fields safe without a separate data audit.

### 7.4 Response policy

Add AI-only `resolve_final_response()` while retaining `decide_final_response()` for legacy.

- clarification/respond-only plans require `compiler_response`
- references use deterministic resolution
- executable data plans may use `deterministic`
- `llm_synthesis` requires executable data or explicit explanation/inference intent
- `compiler_response` cannot suppress a query action
- incoherent combinations return `clarification` with `response_contract`; they are not silently rewritten

For mixed conversational and data actions, create a safe conversational prefix with existing canned helpers and append it only after the deterministic or synthesized answer is finalized.

## 8. Dataset scope and conversation safety

### 8.1 Dataset resolution order

In AI mode, `AssistantTurnService._answer` uses this order:

1. Handle normalized empty input.
2. Load the current authorized catalog and conversation.
3. Prefer explicit `selected_file_id`.
4. Otherwise use an existing conversation pin.
5. If neither exists, return `dataset_selection_required` and ask the user to select a list.
6. Validate the selected dataset against the current catalog and call `scope.allows_file(..., private=dataset.private)` explicitly.
7. If an explicit selection differs from the pin, return `dataset_scope_conflict` before planning.
8. Narrow the scope and field catalog to exactly the selected file.
9. Invoke the AI planner.

Do not auto-select the default or sole dataset on the backend. The frontend may continue its existing initial-selection convenience.

### 8.2 Disabled AI-mode branches

The following remain available to legacy but are unreachable in AI mode:

- question-based dataset selection
- `_fan_out_datasets` and `_answer_fan_out`
- `_other_list_for_question` and deterministic dataset-mismatch routing
- wrong-list and field-only dataset hints
- trusted natural-language overrides
- deterministic/schema parsers
- plan-coverage question rereading
- deterministic conversation/name interpreters
- canonical-query and semantic-normalizer fallbacks

### 8.3 Other-dataset names

Build trusted `AuthorizedDatasetOption` values from the full authorized catalog. Each option may contain its internal file ID and normalized labels, but the prompt serializer emits labels and aliases only.

Do not reuse `dataset_match_labels()` unfiltered because it currently contains aliases such as `file 93`. Add a model-facing label helper that excludes IDs and numeric/file aliases.

`dataset_not_selected` rendering:

- If the action's response exactly matches a normalized authorized-but-unselected label, return: “This chat is scoped to {selected}. Select {requested} to ask about that list.” and attach its `suggested_file_id`.
- If it is empty or has no exact authorized match, return: “I can only answer using the currently selected list, {selected}.” with no suggestion.

Never use substring matching to resolve the suggestion. Never look up inaccessible catalogs for user-facing rendering.

### 8.4 Dataset-aware memory

Use existing frame and active-query file IDs:

- discard an active frame unless its file IDs are exactly the selected file
- discard every topic frame with a different or multi-file scope before constructing `ConversationContext`
- apply the same filtered frame set in `_source_actions`
- retain `dataset_scope_conflict` as the primary guard

This must protect “list them,” “next,” and ordinal-reference follow-ups even if malformed historical memory exists.

## 9. Provider, failure handling, and observability

### 9.1 Provider interfaces

Add a generic result envelope such as `StructuredOutputResult[T]` containing:

- parsed value
- provider/model
- prompt, completion, and total tokens when available
- reported USD cost when available
- duration

Add `structured_output_with_metadata()` to the xAI and fake providers. Keep `structured_output()` as a compatibility wrapper returning only the parsed value.

Allow `get_reasoning_provider(model_override=None)` to reuse the normal provider cache with a review model override. A blank `PLANNER_REVIEW_MODEL` reuses the primary provider/model.

### 9.2 Terminal outcomes

| Status | Cause | Text response | Voice response |
|---|---|---|---|
| `planner_unavailable` | Missing provider or provider/network/auth/rate-limit/timeout failure | “NIA's planning service is temporarily unavailable. Please try again in a moment.” | “My planning service is unavailable. Please try again shortly.” |
| `planner_invalid_output` | Provider responded but the permitted parse attempts failed | “NIA couldn't produce a usable plan for that request. Please try again.” | “I couldn't make a usable plan. Please try again.” |
| `clarification` | Planner requested clarification or trusted validation rejected an unsafe/ambiguous plan | Planner or validator question | Concise equivalent |

Both planner failure statuses use matching `TurnResult.error_code`, carry `planner_failure_stage`, perform no deterministic fallback, and execute no data query.

### 9.3 Tracing and audit

Emit AI-mode trace layers in order:

```text
normalize -> ai_planner -> turn_validator -> query_plan_builder
          -> predicate_contract -> ai_self_review -> value_expansion
          -> plan_validator -> route
```

When review is skipped, still emit an `ai_self_review` layer with `status=skipped` for a consistent trace shape.

Add stage attributes:

- status and failure reason
- attempt/retry counts
- model and provider
- latency
- token usage and cost
- review verdict
- validation rejection code

Update the tracer so attributes added inside a span are exported to OpenTelemetry on context exit, not copied only at entry.

Audit planner failures as their own event types with `authorization_outcome="allowed"`. Do not classify them as clarifications or access denials.

## 10. Test plan

### 10.1 Schema and unit tests

Add `tests/test_ai_planner.py` and focused provider/validator tests for:

- no dataset field anywhere in `PlannedTurn` or corrected review plans
- complete `QueryAction` semantic-field preservation, including the fields omitted from the source proposal
- extra-field rejection for every AI-facing envelope and nested variant
- illegal review-state rejection
- review `RootModel` compatibility with the provider and fake
- general-conversation response requirements
- action-index and compare-branch requirement validation
- one-to-one requirement matching, inverted polarity, missing bounds, wrong sort direction, dropped projection, dropped limit/window, dropped options, search text, group position/value part, thresholds, and modify edits
- a fully matching requirement set reaching execution unchanged except permitted canonicalization

### 10.2 Planner and failure tests

Assert call counts for greetings, conversation, clarifications, references, clean data plans, retried plans, malformed primary output, and malformed review output.

Cover:

- retry only on `ValidationError`
- no retry on provider failure
- unavailable versus invalid-output versus clarification rendering
- primary versus review failure stage
- no deterministic fallback
- general conversation requiring no second general-answer call
- synthesis increasing total `reasoning_calls` without changing planner counters
- fake-provider stage logs and metadata

### 10.3 Validation and semantic-preservation tests

Cover:

- low confidence
- unresolved intent
- unknown selected-list fields
- first-turn modify/verify/reference
- response-policy incoherence
- same-field `CONTAINS` conjunction reaching the executor
- equality conflicts under AND
- valid equality alternatives under OR
- contradiction inside a nested branch
- goal, field, polarity, boolean structure, grouping, sorting, projection, options, and pagination surviving compilation
- synonym and literal-Unknown canonicalization
- no field reassignment in AI mode
- safe and unsafe leading-article examples, including “The Pas”

### 10.4 Review tests

Cover:

- a three-condition request whose primary plan and requirement list both omit the third condition
- a zero-filter list plan for “Show students admitted after 1905,” proving review is not count-gated
- `complete`, `corrected`, and `needs_clarification`
- correction re-running scope binding, requirement parity, strict validation, predicate validation, and normal QueryPlan validation
- a correction preserving unrelated goal, fields, and conditions
- corrected unknown fields, dropped requirements, or attempted dataset injection being rejected
- no second review after correction

### 10.5 Dataset and authorization tests

Cover:

- required explicit selection or valid pin
- explicit selection winning only when no conflicting pin exists
- pin reauthorization after a private grant is revoked
- authorized other-list name producing a switch suggestion and no query
- unauthorized/private other-list wording producing a generic response and no disclosure
- proper nouns such as Garden River, Shingwauk, and Batchewana remaining values
- adversarial requests to ignore, combine, search, or reuse another list never widening scope
- no QueryPlan, gateway call, row, evidence, or citation involving unauthorized files 93/94
- stale cross-dataset frames being discarded for list, page, and ordinal follow-ups

### 10.6 Named condition-loss tests

Create named cases from the private regression corpus. Assert every required condition reaches the final `QueryPlan`.

Also test:

```text
students from Garden River admitted after 1905 who died from tuberculosis
```

The final predicate contract must contain community AND admitted date AND cause of death.

### 10.7 Compatibility and build checks

- All existing tests continue passing in the default legacy mode.
- Existing zero-reasoning/trusted-fast-path assertions remain legacy-only until Phase 3.
- Run Ruff without rewriting files.
- Run the frontend production build after API type changes.
- Run migration and privilege self-tests against PostgreSQL.

## 11. Benchmark implementation

### 11.1 Regression CLI

Update `backend/benchmarks/regression.py` and its container wrapper:

- `--offline` injects `FakeReasoningProvider`
- `--planner-mode {legacy,ai}` selects the implementation under test
- existing `--file-ids` continues to define authorized scope
- new `--file-id` defines the one selected dataset
- `--runs N` repeats a configuration; default 3 for AI and 1 for legacy, while promotion commands explicitly use 3 for both
- `--suite` selects the committed case manifest
- `--principal` sets the principal
- `--allow-private-files` enables the private-capability flag but does not create grants
- `--fail-on-gate` exits non-zero for a failed required criterion
- `--json-out` records every run plus aggregates

### 11.2 Scoped suite manifest

Add a committed JSON manifest. Each case records:

- source question ID
- question
- selected file ID
- applicable category
- expected outcome kind
- expected semantic requirements or golden answer
- required private scope
- critical/non-critical flag
- repetitions override

Categories:

- cross-dataset core
- master-specific
- confirmed-specific
- additional-deaths-specific
- potential-specific
- unsupported-field refusal
- authorized switch-list response
- unauthorized generic scope refusal

Run both modes against the same scoped case instances. Cross-list questions from the old suite are reclassified according to the single-list rule rather than graded against a multi-list answer. Unsupported fields pass when the system refuses them correctly before gateway execution.

### 11.3 Repeated-run scoring

- Run every normal configuration three times for promotion.
- Run named condition-loss cases five times.
- Emit per-run pass/partial/fail counts, mean, and worst case.
- A critical requirement must pass on every run; averages cannot hide a failure.
- Compare AI and legacy on the identical scoped manifest. The historical 49 pass / 12 partial / 32 fail result remains reference data, not the new denominator.

### 11.4 Review benefit metrics

For a corrected review outcome, store the original and final `PlannedTurn`. In benchmark mode only:

1. Rebind and validate the already-produced original plan with review disabled.
2. Execute it without another planning call.
3. Grade original and final results against the same expected result.

Classify:

- benefit: original partial/fail, final pass
- false positive: original pass and final is worse, or final score is otherwise lower
- neutral: correction does not change the grade

Track `needs_clarification` separately from corrections.

### 11.5 Database-truth matrix

Generalize `database_question_matrix.py` so its scope and oracle queries derive from selected cases rather than fixed files 49/91.

Retain the existing 58 cases and add files 93/94 cases covering:

- total counts
- bounded lists and requested projections
- known/missing values
- date equality/ranges and sorting
- age filters/statistics
- cause-of-death filtering and grouping
- grouping/ranking thresholds
- pagination/window behavior
- file 94 refusing unsupported community and student-number questions

Expected answers, row projections, grouping, ordering, filters, and scope must be computed directly from PostgreSQL. Any mismatch exits non-zero.

Use an environment-provided benchmark principal with active grants for private cases. Add a preflight that fails clearly when the capability flag or grants are absent. Never mutate grants inside a benchmark.

## 12. Phase 1: build and qualify the opt-in path

### 12.1 Implementation order

1. Add configuration, provider metadata support, and the fake-provider extensions.
2. Add AI schemas, requirements, review envelopes, and schema tests.
3. Implement AI planner orchestration, prompts, binding, retries, and failures.
4. Add strict validation, requirement parity, predicate contracts, AI canonicalization, and response coherence.
5. Integrate dataset selection, other-list labels, memory filtering, and result propagation into the service/router.
6. Add traces, audit fields, API/SSE serialization, and frontend types.
7. Add the full test matrix.
8. Update benchmarks and database oracles.
9. Update documentation.
10. Run offline, database, and paid live verification; publish the Phase 1 report.

### 12.2 Phase 1 runtime state

- Default: `PLANNER_MODE=legacy`
- Opt-in: `PLANNER_MODE=ai`
- Self-review: on
- Review model: same as primary unless an explicitly measured override is configured
- Legacy modules remain present and tested

### 12.3 Phase 1 exit criteria

All must be true:

- existing legacy tests and all new AI tests pass
- lint and frontend build pass
- AI-mode live execution completes on files 49, 91, 93, and 94
- database-truth tests pass for all supported cases
- the complete Phase 1 metric set is collected
- a Phase 2 readiness report evaluates every promotion gate

Phase 1 completion does not automatically flip the default. If a Phase 2 gate fails, keep AI opt-in, retain artifacts, correct the implementation or prompt, and rerun the affected and full qualification suites.

## 13. Phase 2: AI default with legacy rollback

### 13.1 Promotion gates

Do not enter Phase 2 until all eight criteria pass:

1. AI is at least as good as legacy on the identical scoped golden suite.
2. There are zero dataset-scope violations.
3. There are zero unauthorized reads.
4. Every named condition-loss case and the three-condition case passes on every required run.
5. The complete database-truth suite passes.
6. All four datasets are exercised live.
7. `planner_unavailable` and `planner_invalid_output` are never rendered or audited as clarifications.
8. The qualification suite records zero invalid structured outputs at both primary and review stages. Any non-zero result blocks promotion and requires prompt/schema investigation.

Unauthorized-access qualification is asserted at four layers:

- no unauthorized file ID in a built `QueryPlan`
- no gateway call carrying an unauthorized file ID
- no returned rows/evidence from an unauthorized file
- no unauthorized citations

The gateway-call spy is the load-bearing assertion.

### 13.2 Default flip

The flip is recorded in `docs/phase-2-ai-planner-rollout.md` (2026-09-02). Gates 5 and 8 remain soak risks.

After written gate approval:

- change the application and deployment default to `PLANNER_MODE=ai`
- keep `PLANNER_MODE=legacy` fully functional as the emergency rollback
- keep self-review enabled
- deploy first to the normal pre-production environment and rerun smoke, scoped regression, database, and failure-injection checks
- deploy the AI default to production and start the continuous stability clock only after readiness and smoke tests pass

No legacy module or test is deleted in Phase 2.

The release owner is responsible for the mode flip and the application on-call owns rollback during the soak. The runbook must provide a one-step environment change back to `PLANNER_MODE=legacy`, the required redeploy/restart command, readiness checks, one public and one private smoke query, and confirmation that caches/settings were refreshed. Rolling back the mode must not delete AI traces, audit events, or failed-plan artifacts.

### 13.3 Monitoring and measurements

Publish dashboards or equivalent reports for:

- primary planner latency p50/p95
- review latency p50/p95
- total planner latency p50/p95
- end-to-end turn latency p50/p95
- mean tokens and cost per turn
- mean tokens and cost for reviewed two-call turns
- review correction, benefit, neutral, and false-positive rates
- validation rejection rate by reason
- clarification rate
- `planner_invalid_output` rate split by stage
- `planner_unavailable` rate split by stage and provider cause
- dataset-scope and authorization violations

Set the Phase 2 p95 and clarification operating bands from the Phase 1 report and record their numeric values in the deployment/runbook before the default flip.

Use these rules so the thresholds are reproducible rather than chosen ad hoc:

- qualification invalid-output threshold: zero events on the repeated promotion suite
- soak invalid-output warning: any event; rollback threshold: more than 1% of either stage over a rolling 100-call window or three consecutive events
- planner availability SLO: at least 99% successful primary/review provider calls over 24 hours, excluding explicit user cancellation
- p95 end-to-end target: no more than the greater of 500 ms or 20% above the Phase 1 AI p95 for the same scoped workload
- clarification band: no more than two percentage points or 20% relative above the qualified Phase 1 AI rate, whichever allowance is larger, unless the increase consists solely of newly correct unsupported-field refusals

Soak verification cadence:

- every deployment: unit/offline suite, failure injection, database smoke, and one live request for each dataset
- nightly: complete database-truth suite, named condition-loss canaries, and authorized/unauthorized scope canaries
- twice weekly during the 14-day window: the complete paid scoped golden suite, with every critical case graded individually
- continuously: stage-specific failure, latency, cost, clarification, scope, and authorization monitoring

If review latency is unacceptable, use this order and rerun all qualification gates after each change:

1. Set `PLANNER_REVIEW_MODEL` to a measured faster/cheaper compatible model.
2. Shorten the review prompt while retaining question, plan, and selected field names.
3. Re-measure.
4. Consider disabling review only through an explicit architecture decision backed by measured benefit and false-positive data.

Never introduce a plan-size review threshold.

### 13.4 Rollback triggers

Immediately restore `PLANNER_MODE=legacy` for:

- any dataset-scope violation
- any unauthorized gateway read
- any Sev-1 or Sev-2 planner incident
- recurrence of a named critical condition-loss failure
- database-truth failure attributable to planning

Rollback is also required when the documented Phase 2 operating band is breached persistently for planner invalid output, provider availability, p95 latency, or clarification rate.

Rollback changes only the mode. Preserve AI traces and benchmark artifacts for diagnosis, fix forward in opt-in mode, rerun the full promotion suite, and restart the Phase 2 stability clock after redeployment.

Any material change to the planner model, review model, prompt, AI-facing schema, requirement checker, review eligibility, validation policy, or canonicalization policy requires the full promotion suite again and resets the stability clock even when no production breach occurred.

## 14. Phase 3: remove legacy planning

### 14.1 Entry criterion: two continuously stable weeks

The AI default must satisfy all of the following continuously for 14 days:

- zero dataset-scope violations
- zero unauthorized reads
- zero named condition-loss regressions
- `planner_invalid_output` within the documented Phase 2 operating threshold at both stages
- `planner_unavailable` within the reasoning provider's SLO
- p95 turn latency within the Phase 1-derived target
- clarification rate within the Phase 2 band
- no Sev-1 or Sev-2 planner incident
- database-truth suite green on every scheduled run

Any breach resets the 14-day clock after remediation and redeployment.

Before legacy deletion, archive a dated stability report containing the exact model, prompt/schema revision, configured thresholds, scheduled-run results, dashboard/export locations, incidents and rollbacks, and named release approval.

### 14.2 Legacy removal

After the stability gate is signed off:

- remove the legacy branch from `plan_user_turn` and the service's legacy-only dataset heuristics
- remove `PLANNER_MODE` and `planner_mode`; AI becomes the only path
- remove unused compatibility parameters and legacy trace/result fields after verifying no external consumer
- delete legacy semantic-reader modules that have no remaining imports, including trusted overrides, analytic guards, deterministic/schema planners, question-rereading coverage, user-name interpretation, canonical-query fallback, turn interpreter, constrained LLM planner, semantic normalizer, and the legacy conversation-followup resolver
- retain deterministic catalog canonicalization, strict validation, QueryPlan building/validation, data gateway, executor, memory, retrieval, response rendering, voice, and security boundaries
- remove legacy provider/compiler caches and dead factory paths
- rewrite or remove tests whose only contract was zero model calls, trusted-fast-path source names, or deterministic language interpretation
- retain their underlying security, query-compilation, executor, and regression cases against the AI path
- remove legacy benchmark mode and rollback commands only after archiving the final A/B report
- remove the legacy flowchart and migration notes from active documentation while retaining historical reports

Archive the last Phase 2 release artifact and deployment configuration for 90 days. After the planner flag is deleted, emergency recovery is a deployment rollback to that artifact rather than an in-process semantic fallback. Smoke-test this deployment rollback once before merging the Phase 3 deletion.

Before deleting each module, use `rg` to prove that no production import, fixture, benchmark, or documentation generator still requires it.

### 14.3 Phase 3 verification and exit

Run the full test, lint, frontend build, migration, privilege, live regression, failure-injection, and database-truth suites again after deletion.

Phase 3 is complete only when:

- there is one planner path
- no `PLANNER_MODE` flag remains
- no legacy semantic reader is imported or reachable
- AI planner/review failures remain distinct
- every scope and authorization assertion remains green
- current docs describe only the final architecture

## 15. Documentation deliverables

Update:

- `docs/system-flowchart.md`: show AI mode as the active flow, preserve the 15-gate tree under a legacy heading through Phase 2, and remove it in Phase 3
- `docs/architecture.md`: add the AI-planner-first diagram, single-list invariant, failure states, and interpretation-versus-canonicalization boundary
- private regression notes: map former condition-loss and heuristic gaps to requirement parity, review, strict clarification, or unsupported behavior
- private database-validation report: describe planner-visible registered fields accurately for every authorized dataset
- `README.md`: remove claims that conflict with AI-mode model-call behavior and document mode selection
- `.env.example`: add planner settings and correct the outdated semantic-compiler comment
- `docs/system-function-inventory.md`: regenerate or update affected planner, provider, router, and benchmark entries
- benchmark documentation: explain scoped manifests, repeated-run grading, private-scope preflight, and review-benefit replay

Create a dated Phase 1 qualification report containing:

- repository revision or source snapshot identifier
- date, environment, provider, and model
- per-mode/per-dataset run summaries
- mean and worst-case scores
- critical-case results
- database-truth results
- latency, token, cost, correction, benefit, false-positive, failure, and rejection metrics
- all eight Phase 2 gate outcomes
- links or paths to sanitized JSON artifacts

Update the same rollout record with the Phase 2 start/end timestamps, operating thresholds, incidents/rollbacks, and final Phase 3 stability sign-off.

## 16. Verification commands and execution environment

Use the existing WSL2 Compose project without deleting volumes:

```sh
cd /mnt/c/Users/gad/Desktop/nia-standalone
docker compose --env-file .env -f infra/docker-compose.yml build migrate backend
docker compose --env-file .env -f infra/docker-compose.yml up -d postgres
docker compose --env-file .env -f infra/docker-compose.yml run --rm migrate
```

Local/static verification:

```sh
cd backend
python -m pytest ../tests -q
python -m ruff check app benchmarks ../tests

cd ../frontend
npm run build
```

AI smoke probes:

```sh
PLANNER_MODE=ai python -m benchmarks.probe "how many students are deceased"
PLANNER_MODE=ai python -m benchmarks.probe \
  "students from Garden River admitted after 1905 who died from tuberculosis"
```

Paid live A/B qualification:

```sh
for id in 49 91 93 94; do
  for mode in legacy ai; do
    backend/benchmarks/run_in_container.sh \
      docs/supplied_questions_pipeline_results.md \
      --live \
      --planner-mode "$mode" \
      --file-id "$id" \
      --runs 3 \
      --principal "$BENCHMARK_PRINCIPAL_ID" \
      --allow-private-files \
      --fail-on-gate \
      --json-out "/tmp/$mode-$id.json"
  done
done
```

The runner must select only applicable manifest cases for each file. Public cases must also be run without private capability; private cases require the seeded grant preflight.

Database truth:

```sh
PLANNER_MODE=ai python benchmarks/database_question_matrix.py
```

Failure injection:

- unset the key/provider and confirm `planner_unavailable`
- return malformed primary output twice and confirm two calls plus `planner_invalid_output`, stage `primary`
- return malformed review output and confirm no review retry plus stage `review`
- return a genuine clarification and verify it remains distinct
- use an unauthorized scope and verify zero calls carrying files 93/94

Manual end-to-end sequence in AI mode:

1. Select a list.
2. Ask a count.
3. Ask “list them.”
4. Ask “next.”
5. Ask “the second one.”
6. Say “hello.”
7. Ask for an unsupported field.
8. With Master selected, ask for Confirmed and verify the switch affordance starts a new conversation.
9. Without a private grant, ask for Potential and verify the generic response and zero gateway reads.

## 17. Final acceptance checklist

### Functional

- [ ] AI mode has one natural-language reader and no semantic fallback.
- [ ] Every AI query is bound to exactly the selected dataset.
- [ ] All current query semantics survive the AI-facing schema.
- [ ] Requirement parity and self-review both operate as designed.
- [ ] Corrected plans are fully revalidated and never recursively reviewed.
- [ ] General conversation does not trigger a second language-reading call.
- [ ] Mixed conversational prefixes survive deterministic and synthesized answers.

### Safety

- [ ] No model-visible or corrected schema contains a dataset ID.
- [ ] No question, model response, follow-up, or stored frame can widen scope.
- [ ] Unauthorized datasets are neither read nor disclosed.
- [ ] Gateway-call spies prove zero unauthorized access.
- [ ] Provider and malformed-output failures execute no query and never masquerade as clarifications.

### Quality and operations

- [ ] Legacy baseline remains green in Phase 1 and Phase 2.
- [ ] AI tests, lint, frontend build, migrations, privilege tests, and database truth pass.
- [ ] All four datasets are exercised live.
- [ ] Repeated-run mean, worst case, and every critical result are recorded.
- [ ] Review benefit and false-positive metrics are measured from original-versus-final execution.
- [ ] Phase 2 default flip occurs only after all eight gates pass.
- [ ] Phase 3 removal occurs only after 14 continuously stable days.
- [ ] Final architecture contains no permanent planner-mode flag or reachable legacy semantic reader.

## 18. Explicit exclusions

- No multi-dataset join, fan-out, or merged answer is introduced.
- No automatic backend dataset selection is introduced.
- No private dataset metadata is exposed to an unauthorized planner or user.
- No change is made to the fundamental QueryPlan/DAG, data-gateway privilege boundary, retrieval engine, voice transport, TTS, or STT beyond required integration and observability.
- No entity/name field receives article-stripping permission without a separate value-distribution audit.
- No Phase 2 or Phase 3 gate is waived because an aggregate benchmark score looks acceptable.
