import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.data_gateway.memory import MemoryDataGateway
from app.execution.turn import AssistantTurnService
from app.llm.fake import FakeReasoningProvider
from app.memory.store import InMemoryMemoryStore
from app.planning.ai_catalog_coerce import coerce_planned_turn
from app.planning.ai_planner import (
    AIPlanner,
    authorized_dataset_options,
    bind_scope,
    planner_visible_labels,
    should_honor_dataset_not_selected,
)
from app.planning.ai_turn_schema import (
    PlannedConversationAction,
    PlannedQueryAction,
    PlannedTurn,
    PlanReviewResponse,
    ReviewComplete,
    ReviewCorrected,
    planned_turn_contains_dataset_id,
)
from app.planning.catalog import static_catalog
from app.planning.conversation_resolver import ConversationContext
from app.planning.plan_schema import FilterOperator, PlanScope, PlanStep, Predicate, QueryPlan
from app.planning.plan_validator import PlanValidationError
from app.planning.predicate_contract import validate_predicate_contract
from app.planning.query_plan_builder import build_query_plan
from app.planning.requirement_parity import check_requirement_parity
from app.planning.response_policy import resolve_final_response
from app.planning.turn_schema import (
    AggregateSpec,
    FilterSpec,
    ModifyPreviousAction,
    QueryAction,
    TurnPlan,
)
from app.planning.turn_validator import validate_turn_plan
from app.planning.value_expansion import expand_plan_values
from app.security.access_scope import AccessScope


def _ai_mode(monkeypatch):
    monkeypatch.setenv("PLANNER_MODE", "ai")
    get_settings.cache_clear()


def _scope() -> AccessScope:
    return AccessScope(principal_id="researcher", allowed_file_ids=(49, 91))


def _count_plan(goal="count", **kwargs) -> PlannedTurn:
    filters = kwargs.pop("filters", [])
    requirements = [
        {
            "kind": "goal",
            "action_index": 0,
            "text": f"goal {goal}",
            "goal": goal,
        }
    ]
    for spec in filters:
        requirements.append(
            {
                "kind": "filter",
                "action_index": 0,
                "text": f"{spec['field']} {spec['operator']} {spec.get('value')}",
                "collection": "filters",
                "field": spec["field"],
                "operator": spec["operator"],
                "value": spec.get("value"),
            }
        )
    return PlannedTurn.model_validate(
        {
            "normalized_request": kwargs.pop("normalized_request", "count records"),
            "actions": [
                {
                    "type": "query",
                    "goal": goal,
                    "filters": filters,
                    **kwargs,
                }
            ],
            "stated_requirements": requirements,
            "final_response": "deterministic",
            "confidence": 0.9,
        }
    )


@pytest.fixture
def ai_settings(monkeypatch):
    _ai_mode(monkeypatch)
    yield
    monkeypatch.delenv("PLANNER_MODE", raising=False)
    get_settings.cache_clear()


def test_planned_turn_rejects_datasets_field():
    with pytest.raises(ValidationError):
        PlannedQueryAction.model_validate({"goal": "count", "datasets": [49]})


def test_provider_json_schema_requires_union_discriminators():
    planned_schema = PlannedTurn.model_json_schema()
    action_schemas = [
        item
        for item in planned_schema["$defs"].values()
        if "type" in item.get("properties", {})
    ]
    assert action_schemas
    assert all("type" in item.get("required", []) for item in action_schemas)
    assert "kind" in planned_schema["$defs"]["GoalRequirement"]["required"]
    review_schema = PlanReviewResponse.model_json_schema()
    assert "verdict" in review_schema["$defs"]["ReviewComplete"]["required"]


def test_planned_turn_preserves_query_semantics():
    planned = PlannedTurn.model_validate(
        {
            "actions": [
                {
                    "type": "query",
                    "goal": "stats",
                    "search_text": "tuberculosis",
                    "secondary_group_value_part": "year",
                    "having_min_count": 2,
                    "stats_value_part": "year",
                    "verify_previous": True,
                    "filters": [{"field": "community", "operator": "EQUALS", "value": "Garden River"}],
                }
            ],
            "stated_requirements": [
                {"kind": "goal", "action_index": 0, "text": "stats", "goal": "stats"}
            ],
            "final_response": "deterministic",
            "confidence": 0.9,
        }
    )
    action = planned.query_actions()[0]
    assert action.search_text == "tuberculosis"
    assert action.secondary_group_value_part == "year"
    assert action.having_min_count == 2
    assert action.stats_value_part == "year"
    assert action.verify_previous is True
    bound = bind_scope(planned, 49)
    assert bound.query_actions()[0].datasets == [49]
    assert planned_turn_contains_dataset_id(planned.model_dump()) is False


def test_extra_fields_rejected_on_envelopes():
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {
                "actions": [{"type": "clarify", "question": "Which?"}],
                "final_response": "compiler_response",
                "file_id": 49,
            }
        )
    with pytest.raises(ValidationError):
        ReviewComplete.model_validate({"verdict": "complete", "extra": True})


def test_illegal_review_states_rejected():
    with pytest.raises(ValidationError):
        PlanReviewResponse.model_validate({"verdict": "corrected"})
    with pytest.raises(ValidationError):
        PlanReviewResponse.model_validate({"verdict": "needs_clarification"})
    parsed = PlanReviewResponse.model_validate({"verdict": "complete"})
    assert isinstance(parsed.root, ReviewComplete)


def test_review_complete_strips_leftover_correction_fields():
    parsed = PlanReviewResponse.model_validate(
        {
            "verdict": "complete",
            "missing": ["use cause_of_death for confirmed deaths"],
            "plan": {
                "actions": [{"type": "query", "goal": "count"}],
                "final_response": "deterministic",
                "confidence": 0.9,
            },
        }
    )
    assert isinstance(parsed.root, ReviewComplete)


def test_conversational_plan_drops_query_requirements():
    planned = PlannedTurn.model_validate(
        {
            "actions": [{"type": "respond", "intent": "describe_available_data", "response": ""}],
            "stated_requirements": [
                {"kind": "goal", "action_index": 0, "text": "fields", "goal": "distinct"}
            ],
            "final_response": "compiler_response",
            "confidence": 0.9,
        }
    )
    assert planned.stated_requirements == []
    assert planned.respond_actions()[0].intent == "describe_available_data"


def test_general_conversation_requires_response():
    with pytest.raises(ValidationError):
        PlannedConversationAction.model_validate(
            {"intent": "general_conversation", "response": ""}
        )
    PlannedConversationAction.model_validate({"intent": "dataset_not_selected", "response": ""})


def test_requirement_index_and_compare_branch_validation():
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {
                "actions": [{"type": "query", "goal": "count"}],
                "stated_requirements": [
                    {"kind": "goal", "action_index": 3, "text": "count", "goal": "count"}
                ],
                "final_response": "deterministic",
            }
        )
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {
                "actions": [{"type": "query", "goal": "compare", "compare": []}],
                "stated_requirements": [
                    {
                        "kind": "filter",
                        "action_index": 0,
                        "text": "community",
                        "collection": "compare",
                        "field": "community",
                        "operator": "EQUALS",
                        "value": "Garden River",
                    }
                ],
                "final_response": "deterministic",
            }
        )


def test_requirement_parity_one_to_one():
    planned = _count_plan(
        filters=[
            {"field": "community", "operator": "EQUALS", "value": "Garden River"},
            {"field": "admitted_date", "operator": "AFTER", "value": 1905},
        ]
    )
    bound = bind_scope(planned, 49)
    check_requirement_parity(planned, bound)
    planned.stated_requirements.append(
        planned.stated_requirements[1].model_copy(update={"text": "duplicate garden river"})
    )
    with pytest.raises(PlanValidationError) as exc:
        check_requirement_parity(planned, bound)
    assert exc.value.code == "dropped_requirement"


def test_bind_scope_never_reads_model_file_ids():
    planned = _count_plan()
    bound = bind_scope(planned, 91)
    assert bound.query_actions()[0].datasets == [91]


@pytest.mark.asyncio
async def test_primary_retries_validation_error_only():
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        {"actions": [{"type": "query"}], "final_response": "deterministic"},
        _count_plan(),
        {"verdict": "complete"},
    ]
    planner = AIPlanner(provider)
    result = await planner.plan(
        "How many students?",
        catalog=static_catalog().for_scope(_scope()),
        selected_file_id=49,
        authorized_options=authorized_dataset_options(static_catalog().for_scope(_scope())),
        context=ConversationContext(),
    )
    assert result.status == "planned"
    assert result.planner_attempts == 2
    assert result.planner_retry_count == 1
    assert result.planner_total_model_calls == 2
    assert result.review_status == "skipped"
    assert provider.structured_log[1]["user"].startswith("SCHEMA-VALIDATION RETRY")


@pytest.mark.asyncio
async def test_no_retry_on_provider_failure():
    provider = FakeReasoningProvider()
    provider.structured_queue = [TimeoutError("xai timeout")]
    planner = AIPlanner(provider)
    result = await planner.plan(
        "How many students?",
        catalog=static_catalog().for_scope(_scope()),
        selected_file_id=49,
        authorized_options=authorized_dataset_options(static_catalog().for_scope(_scope())),
        context=ConversationContext(),
    )
    assert result.status == "planner_unavailable"
    assert result.planner_failure_stage == "primary"
    assert result.planner_attempts == 1
    assert result.planner_total_model_calls == 1


@pytest.mark.asyncio
async def test_malformed_primary_twice():
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        {"actions": [{"type": "query"}], "final_response": "deterministic"},
        {"actions": [{"type": "query"}], "final_response": "deterministic"},
    ]
    planner = AIPlanner(provider)
    result = await planner.plan(
        "How many students?",
        catalog=static_catalog().for_scope(_scope()),
        selected_file_id=49,
        authorized_options=authorized_dataset_options(static_catalog().for_scope(_scope())),
        context=ConversationContext(),
    )
    assert result.status == "planner_invalid_output"
    assert result.planner_failure_stage == "primary"
    assert result.planner_attempts == 2
    assert result.review_attempts == 0


@pytest.mark.asyncio
async def test_greeting_skips_review(ai_settings):
    provider = FakeReasoningProvider()
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(_scope(), "hello", selected_file_id=49)
    assert result.status == "answered"
    assert result.planner_total_model_calls == 1
    assert result.review_status == "skipped"
    assert result.reasoning_calls == 1


@pytest.mark.asyncio
async def test_data_request_reviews_even_with_zero_filters(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        _count_plan(goal="list", normalized_request="show students admitted after 1905"),
        ReviewComplete(),
    ]
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(
        _scope(),
        "Show students admitted after 1905",
        selected_file_id=49,
    )
    assert result.review_attempts == 1
    assert result.planner_total_model_calls == 2


@pytest.mark.asyncio
async def test_review_correction_not_reviewed_again(ai_settings):
    corrected = _count_plan(
        filters=[{"field": "community", "operator": "EQUALS", "value": "Garden River"}]
    )
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        _count_plan(),
        ReviewCorrected(missing=["community Garden River"], plan=corrected),
        ReviewComplete(),
    ]
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(_scope(), "How many from Garden River?", selected_file_id=49)
    assert result.review_status == "corrected"
    assert result.planner_total_model_calls == 2
    assert provider.structured_calls == 2


@pytest.mark.asyncio
async def test_dataset_selection_required(ai_settings):
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=FakeReasoningProvider()
    )
    result = await service.answer(_scope(), "How many students are there?")
    assert result.status == "dataset_selection_required"
    assert result.planner_total_model_calls == 0


@pytest.mark.asyncio
async def test_pin_conflict_before_planner(ai_settings):
    store = InMemoryMemoryStore()
    service = AssistantTurnService(MemoryDataGateway(), store=store, reasoner=FakeReasoningProvider())
    first = await service.answer(_scope(), "How many students?", selected_file_id=49)
    second = await service.answer(
        _scope(),
        "How many records?",
        conversation_id=first.conversation_id,
        selected_file_id=91,
    )
    assert second.status == "dataset_scope_conflict"
    assert second.suggested_file_id == 91


@pytest.mark.asyncio
async def test_authorized_other_list_suggestion(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        PlannedTurn.model_validate(
            {
                "actions": [
                    {
                        "type": "respond",
                        "intent": "dataset_not_selected",
                        "response": "Confirmed deaths",
                    }
                ],
                "stated_requirements": [],
                "final_response": "compiler_response",
                "confidence": 0.95,
            }
        )
    ]
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(
        _scope(),
        "How many records are in confirmed deaths?",
        selected_file_id=49,
    )
    assert result.status == "dataset_not_selected"
    assert result.suggested_file_id == 91
    assert "Confirmed deaths" in result.answer
    assert result.plan is None


@pytest.mark.asyncio
async def test_unauthorized_list_is_not_disclosed(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        PlannedTurn.model_validate(
            {
                "actions": [
                    {"type": "respond", "intent": "dataset_not_selected", "response": "Potential records"}
                ],
                "final_response": "compiler_response",
                "confidence": 0.9,
            }
        )
    ]
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(_scope(), "Search the potential list", selected_file_id=49)
    assert result.suggested_file_id is None
    assert "Potential" not in result.answer
    assert result.plan is None


@pytest.mark.asyncio
async def test_no_fan_out_in_ai_mode(ai_settings):
    provider = FakeReasoningProvider()
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider)
    result = await service.answer(
        _scope(),
        "Compare the master list and confirmed deaths.",
        selected_file_id=49,
    )
    assert result.selected_file_id == 49
    assert result.status != "dataset_mismatch"


def test_strict_validation_no_orphan_promotion():
    turn = TurnPlan(
        actions=[ModifyPreviousAction(changes=[FilterSpec(field="community", operator="EQUALS", value="Garden River")])],
        final_response="deterministic",
        confidence=0.9,
    )
    validated = validate_turn_plan(
        turn,
        scope=_scope(),
        catalog=static_catalog().for_scope(_scope()),
        has_active_query=False,
        strict=True,
    )
    assert validated.clarify_actions()
    assert not validated.query_actions()


def test_predicate_and_or_contract():
    and_plan = QueryPlan(
        planner_type="ai_planner",
        goals=["count"],
        scope=PlanScope(file_ids=(49,)),
        steps=[
            PlanStep(
                id="f",
                op="FILTER",
                input="current_records",
                where=[
                    Predicate(
                        op="and",
                        items=[
                            Predicate(field="community", operator=FilterOperator.EQUALS, value="Garden River"),
                            Predicate(field="community", operator=FilterOperator.EQUALS, value="Sault Ste. Marie"),
                        ],
                    )
                ],
            )
        ],
    )
    with pytest.raises(PlanValidationError):
        validate_predicate_contract(and_plan)
    or_plan = QueryPlan(
        planner_type="ai_planner",
        goals=["count"],
        scope=PlanScope(file_ids=(49,)),
        steps=[
            PlanStep(
                id="f",
                op="FILTER",
                input="current_records",
                where=[
                    Predicate(
                        op="or",
                        items=[
                            Predicate(field="community", operator=FilterOperator.EQUALS, value="Garden River"),
                            Predicate(field="community", operator=FilterOperator.EQUALS, value="Sault Ste. Marie"),
                        ],
                    )
                ],
            )
        ],
    )
    validate_predicate_contract(or_plan)


def test_ai_canonicalization_does_not_reassign_fields():
    catalog = static_catalog().for_scope(_scope())
    plan = QueryPlan(
        planner_type="ai_planner",
        goals=["count"],
        scope=PlanScope(file_ids=(49,)),
        steps=[
            PlanStep(
                id="f",
                op="FILTER",
                input="current_records",
                where=[Predicate(field="notes", operator=FilterOperator.CONTAINS, value="the school.")],
            )
        ],
    )
    expanded = expand_plan_values(plan, catalog, profile="ai")
    leaf = expanded.steps[0].where[0]
    assert leaf.field == "notes"
    assert leaf.value == "school"


def test_sibling_predicates_are_anded_for_contradictions():
    and_plan = QueryPlan(
        planner_type="ai_planner",
        goals=["count"],
        scope=PlanScope(file_ids=(49,)),
        steps=[
            PlanStep(
                id="f",
                op="FILTER",
                input="current_records",
                where=[
                    Predicate(field="community", operator=FilterOperator.EQUALS, value="Garden River"),
                    Predicate(field="community", operator=FilterOperator.EQUALS, value="Sault Ste. Marie"),
                ],
            )
        ],
    )
    with pytest.raises(PlanValidationError) as exc:
        validate_predicate_contract(and_plan)
    assert exc.value.code == "op_contract"


def test_transport_normalize_keeps_fillers_and_polite_wrappers():
    from app.planning.input_normalizer import normalize_transport, normalize_user_turn

    text = "um please could you tell me how many students, sorry, records"
    transport = normalize_transport(text)
    legacy = normalize_user_turn(text)
    assert "um" in transport.normalized_text.lower()
    assert "please" in transport.normalized_text.lower()
    assert "um" not in legacy.normalized_text.lower()


def test_modify_parity_includes_limit_and_presentation():
    from app.planning.requirement_parity import extract_expressed
    from app.planning.turn_schema import ModifyPreviousAction, ResultWindow

    turn = TurnPlan(
        actions=[
            ModifyPreviousAction(
                goal="list",
                limit=10,
                offset=5,
                sort_by="student_name",
                sort_direction="desc",
                sample=False,
                requested_fields=["student_name"],
                window=ResultWindow(anchor="start", size=10, cursor=0),
                exhaustive=True,
                presentation="table",
            )
        ],
        final_response="deterministic",
        confidence=0.9,
    )
    kinds = {item.kind: item for item in extract_expressed(turn) if item.kind == "modify_edit"}
    edits = {item.edit for item in extract_expressed(turn) if item.kind == "modify_edit"}
    assert edits >= {
        "goal",
        "limit",
        "offset",
        "sort_by",
        "sort_direction",
        "sample",
        "requested_fields",
        "window",
        "exhaustive",
        "presentation",
    }
    del kinds


def test_missing_requirement_kind_is_rejected():
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {
                "actions": [{"type": "query", "goal": "count"}],
                "stated_requirements": [
                    {"action_index": 0, "text": "count", "goal": "count"}
                ],
                "final_response": "deterministic",
                "confidence": 0.9,
            }
        )


def test_out_of_range_requirement_is_rejected():
    with pytest.raises(ValidationError):
        PlannedTurn.model_validate(
            {
                "actions": [{"type": "query", "goal": "count"}],
                "stated_requirements": [
                    {"kind": "goal", "action_index": 0, "text": "count", "goal": "count"},
                    {"kind": "goal", "action_index": 4, "text": "ghost", "goal": "list"},
                ],
                "final_response": "deterministic",
                "confidence": 0.9,
            }
        )


def test_mode_aggregate_compiles_to_stats_instead_of_crashing():
    turn = TurnPlan(
        actions=[
            QueryAction(
                datasets=[49],
                goal="aggregate",
                aggregate=AggregateSpec(function="mode", field="age"),
            )
        ],
        final_response="deterministic",
        confidence=0.9,
    )
    plan = build_query_plan(turn, scope=_scope(), catalog=static_catalog())
    assert plan.op_names() == ["USE_CURRENT_VERSION", "STATS"]


def test_ai_does_not_strip_articles_on_community():
    catalog = static_catalog().for_scope(_scope())
    plan = QueryPlan(
        planner_type="ai_planner",
        goals=["count"],
        scope=PlanScope(file_ids=(49,)),
        steps=[
            PlanStep(
                id="f",
                op="FILTER",
                input="current_records",
                where=[Predicate(field="community", operator=FilterOperator.EQUALS, value="The Pas")],
            )
        ],
    )
    expanded = expand_plan_values(plan, catalog, profile="ai")
    assert expanded.steps[0].where[0].value == "The Pas"


def test_planner_visible_labels_exclude_file_ids():
    dataset = static_catalog().dataset(49)
    labels = planner_visible_labels(dataset)
    assert all("file 49" not in label.lower() for label in labels)
    assert "Student master list" in labels


def test_response_contract_rejects_suppressed_query():
    turn = TurnPlan(
        actions=[QueryAction(datasets=[49], goal="count")],
        final_response="compiler_response",
        confidence=0.9,
    )
    with pytest.raises(PlanValidationError) as exc:
        resolve_final_response(turn)
    assert exc.value.code == "response_contract"


@pytest.mark.asyncio
async def test_source_actions_drops_stale_active_frame(ai_settings):
    from app.execution.turn import AssistantTurnService
    from app.memory.types import ConversationRecord, QueryFrame, QueryState
    from app.planning.input_normalizer import NormalizedTurn
    from app.planning.plan_validator import PlanValidationError
    from app.planning.router import PlanRouteResult
    from app.planning.turn_schema import ModifyPreviousAction, TurnPlan

    conversation = ConversationRecord(
        id="00000000-0000-0000-0000-000000000099",
        principal_id="researcher",
        selected_file_id=49,
        frames={
            "old": QueryFrame(
                frame_key="old",
                topic="old",
                query=QueryState(file_ids=(91,), goal="count"),
            )
        },
        active_frame_key="old",
    )
    route = PlanRouteResult(
        plan=None,
        status="planned",
        source="ai_planner",
        normalized_turn=NormalizedTurn(raw_text="next", normalized_text="next"),
        turn_plan=TurnPlan(
            actions=[ModifyPreviousAction(page="next")],
            final_response="deterministic",
            confidence=0.9,
        ),
    )
    service = AssistantTurnService(MemoryDataGateway(), store=InMemoryMemoryStore())
    try:
        compiled = service._source_actions(
            route, _scope(), static_catalog().for_scope(_scope()), conversation
        )
    except PlanValidationError:
        compiled = {}
    assert all(getattr(query, "datasets", [49]) == [49] for query in compiled.values())


@pytest.mark.asyncio
async def test_schema_question_uses_selected_catalog_text(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        {
            "actions": [{"type": "respond", "intent": "describe_available_data", "response": ""}],
            "stated_requirements": [
                {"kind": "goal", "action_index": 0, "text": "fields", "goal": "distinct"}
            ],
            "final_response": "compiler_response",
            "confidence": 0.9,
        }
    ]
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider
    )
    result = await service.answer(
        _scope(),
        "What fields are available in the master list?",
        selected_file_id=49,
    )
    assert result.status == "answered"
    assert result.plan is None
    assert "student name" in result.answer.casefold()
    assert result.review_status == "skipped"


@pytest.mark.asyncio
async def test_ungrounded_dataset_not_selected_retries(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        {
            "actions": [
                {"type": "respond", "intent": "dataset_not_selected", "response": ""}
            ],
            "final_response": "compiler_response",
            "confidence": 0.9,
        },
        _count_plan(),
        ReviewComplete(),
    ]
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider
    )
    result = await service.answer(
        _scope(),
        "How many students were admitted between 1940 and 1945?",
        selected_file_id=49,
    )
    assert result.status == "answered"
    assert result.planner_attempts == 2
    assert result.planner_retry_count == 1
    assert provider.structured_log[0]["user"].find("SCHEMA-VALIDATION RETRY") == -1
    assert provider.structured_log[1]["user"].startswith("SCHEMA-VALIDATION RETRY")


@pytest.mark.asyncio
async def test_review_prompt_lists_only_selected_fields(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        _count_plan(),
        ReviewComplete(),
    ]
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider
    )
    await service.answer(_scope(), "How many students?", selected_file_id=49)
    review_prompt = provider.structured_log[1]["user"]
    assert "SELECTED FIELDS:" in review_prompt
    assert "cause_of_death" not in review_prompt


def test_dataset_not_selected_requires_named_other_source():
    action = PlannedConversationAction(intent="dataset_not_selected", response="")
    options = authorized_dataset_options(static_catalog().for_scope(_scope()))
    assert (
        should_honor_dataset_not_selected(
            action,
            question="How many students were admitted between 1940 and 1945?",
            selected_file_id=49,
            options=options,
        )
        is False
    )
    assert (
        should_honor_dataset_not_selected(
            action,
            question="How many records are in confirmed deaths?",
            selected_file_id=49,
            options=options,
        )
        is True
    )


@pytest.mark.asyncio
async def test_malformed_review_has_no_retry(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        _count_plan(),
        {"verdict": "corrected"},
    ]
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider
    )
    result = await service.answer(_scope(), "How many students?", selected_file_id=49)
    assert result.status == "answered"
    assert result.review_status == "invalid_output"
    assert result.review_attempts == 1
    assert result.plan is not None
    assert provider.structured_calls == 2


def test_boolean_equals_is_coerced_to_is_true():
    planned = _count_plan(
        filters=[{"field": "deceased_status", "operator": "EQUALS", "value": "deceased"}]
    )
    coerced = coerce_planned_turn(planned, static_catalog().for_scope(_scope()), 49)
    spec = coerced.query_actions()[0].filters[0]
    assert spec.operator == "IS_TRUE"
    assert spec.value is None
    assert coerced.stated_requirements[1].operator == "IS_TRUE"


def test_projection_requirement_accepts_long_field_list():
    fields = [
        "student_name",
        "cause_of_death",
        "death_factor",
        "birth_date",
        "death_date",
        "burial_date",
        "first_admitted_date",
        "discharged_date",
        "death_registration_date",
        "age_at_death",
        "gender",
        "nation",
        "community",
        "school",
        "place_of_death",
        "location_of_death",
        "place_of_burial",
        "student_number",
        "indigenous_name",
        "parents_names",
        "ancestry_information",
        "admission_method",
        "reason_for_discharge",
        "documentation",
        "investigative_notes",
        "specific_file_notes",
        "information_shared_with",
        "death_registration_number",
        "other_schools",
        "other_links",
        "other_information",
        "census_documents_used",
        "census_year",
        "nia_comments",
    ]
    planned = PlannedTurn.model_validate(
        {
            "actions": [
                {
                    "type": "query",
                    "goal": "list",
                    "requested_fields": fields,
                    "filters": [
                        {"field": "student_name", "operator": "CONTAINS", "value": "Albert"}
                    ],
                }
            ],
            "stated_requirements": [
                {"kind": "goal", "action_index": 0, "text": "list", "goal": "list"},
                {
                    "kind": "projection",
                    "action_index": 0,
                    "text": "project " + ", ".join(fields),
                    "requested_fields": fields,
                },
            ],
            "final_response": "deterministic",
            "confidence": 0.9,
        }
    )
    bound = bind_scope(planned, 91)
    check_requirement_parity(planned, bound)


def test_review_corrected_uses_verdict_discriminator():
    corrected = _count_plan()
    parsed = PlanReviewResponse.model_validate(
        {
            "verdict": "corrected",
            "missing": ["use cause_of_death"],
            "plan": corrected.model_dump(mode="json"),
        }
    )
    assert parsed.root.verdict == "corrected"


@pytest.mark.asyncio
async def test_unknown_field_review_can_correct(ai_settings):
    provider = FakeReasoningProvider()
    provider.structured_queue = [
        _count_plan(filters=[{"field": "deceased_status", "operator": "IS_UNKNOWN"}]),
        ReviewCorrected(
            missing=["deceased_status is not on this list"],
            plan=_count_plan(
                filters=[{"field": "gender", "operator": "IS_UNKNOWN"}]
            ),
        ),
    ]
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=provider
    )
    result = await service.answer(
        AccessScope(principal_id="researcher", allowed_file_ids=(91,)),
        "How many confirmed death records have no recorded gender?",
        selected_file_id=91,
    )
    assert result.review_status == "corrected"
    assert result.status in {"answered", "clarification"}
    if result.plan is not None:
        fields = [leaf.field for step in result.plan.steps for leaf in step.where if leaf.field]
        assert "deceased_status" not in fields


def test_application_default_is_ai():
    from app.config import Settings

    assert Settings.model_fields["planner_mode"].default == "ai"


@pytest.mark.asyncio
async def test_legacy_rollback_still_plans(monkeypatch):
    monkeypatch.setenv("PLANNER_MODE", "legacy")
    get_settings.cache_clear()
    assert get_settings().planner_mode == "legacy"
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=FakeReasoningProvider()
    )
    result = await service.answer(_scope(), "How many students are there?", selected_file_id=49)
    assert result.status == "answered"
    assert result.plan is not None
    assert result.planner_type != "ai_planner"


@pytest.mark.planner_ai
@pytest.mark.asyncio
async def test_ai_default_path_plans_with_fake_provider(ai_settings):
    service = AssistantTurnService(
        MemoryDataGateway(), store=InMemoryMemoryStore(), reasoner=FakeReasoningProvider()
    )
    result = await service.answer(_scope(), "How many students are there?", selected_file_id=49)
    assert result.status == "answered"
    assert result.planner_type == "ai_planner"


@pytest.mark.asyncio
async def test_three_condition_parity_reaches_plan(ai_settings):
    planned = _count_plan(
        filters=[
            {"field": "community", "operator": "EQUALS", "value": "Garden River"},
            {"field": "admitted_date", "operator": "AFTER", "value": 1905},
            {"field": "cause_of_death", "operator": "CONTAINS", "value": "tuberculosis"},
        ]
    )
    # cause_of_death is not on file 49; use 91 for this semantic check via bind+parity only
    planned = _count_plan(
        filters=[
            {"field": "community", "operator": "EQUALS", "value": "Garden River"},
            {"field": "admitted_date", "operator": "AFTER", "value": 1905},
            {"field": "deceased_status", "operator": "IS_TRUE"},
        ]
    )
    bound = bind_scope(planned, 49)
    check_requirement_parity(planned, bound)
    fields = {leaf.field for spec in bound.query_actions()[0].filters for leaf in [spec]}
    assert fields == {"community", "admitted_date", "deceased_status"}
