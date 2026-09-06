# NIA Standalone: exhaustive source-symbol inventory

Generated from first-party runtime source during the system-flow review. This lists every named Python class/function/method (including private and nested helpers), every named TypeScript/TSX function/class or function-valued local captured by the source patterns, and the SQL objects declared by runtime migrations. Anonymous callbacks and test/benchmark symbols are outside this runtime inventory.

Inventory size: **1175 named symbols across 112 files**.

Phase 2 routing: `plan_user_turn` in `backend/app/planning/router.py` defaults to
`plan_user_turn_ai` when `Settings.planner_mode` is `ai`. Legacy readers
(`trusted_overrides`, `deterministic_parser`, `schema_query`, `semantic_compiler`)
remain imported on the `PLANNER_MODE=legacy` rollback path.

## `backend/app\api\assistant.py`

- Line 29: `class QueryRequest(BaseModel):`
- Line 36: `def _gateway() -> DataGateway:`
- Line 48: `def _memory_store():`
- Line 52: `def _turn_service(`
- Line 63: `def _serialize_turn(result: TurnResult) -> dict[str, Any]:`
- Line 93: `async def list_conversations(`
- Line 120: `async def get_conversation(`
- Line 146: `async def list_datasets(`
- Line 171: `async def query(`
- Line 195: `async def _stream_query(`
- Line 207: `async def on_progress(event: str, data: dict[str, Any]) -> None:`
- Line 271: `async def _as_sse(`
- Line 322: `def _answer_chunks(text: str) -> list[str]:`
- Line 338: `def _public_turn(turn: dict[str, Any]) -> dict[str, Any]:`
- Line 351: `def _sse(event: str, data: dict[str, Any]) -> str:`
- Line 355: `def _dataset_label(catalog, file_id: int | None) -> str | None:`
- Line 362: `def _supported_operations(fields: list[dict[str, Any]]) -> list[str]:`
- Line 384: `def _starter_prompts(`

## `backend/app\api\auth.py`

- Line 13: `class LoginRequest(BaseModel):`
- Line 18: `class SessionResponse(BaseModel):`
- Line 25: `def _serialize(scope: AccessScope) -> SessionResponse:`
- Line 34: `def _set_session_cookie(response: Response, adapter: AuthAdapter, scope: AccessScope) -> None:`
- Line 48: `def _clear_session_cookie(response: Response) -> None:`
- Line 61: `async def login(`
- Line 75: `async def exchange_website_session(`
- Line 86: `async def browser_session(`
- Line 107: `async def me(`
- Line 117: `async def logout(response: Response) -> None:`

## `backend/app\api\health.py`

- Line 15: `async def health() -> dict:`
- Line 30: `async def readiness():`
- Line 60: `async def _check_database() -> dict[str, object]:`
- Line 69: `async def _check_http(url: str, timeout_ms: int) -> dict[str, object]:`

## `backend/app\api\livekit_tokens.py`

- Line 20: `class TokenRequest(BaseModel):`
- Line 26: `class TokenResponse(BaseModel):`
- Line 37: `async def create_token(`

## `backend/app\api\speech.py`

- Line 20: `class SpeechRequest(BaseModel):`
- Line 25: `def _tts_provider() -> TTSProvider:`
- Line 30: `async def synthesize_speech(`
- Line 58: `async def audio() -> AsyncIterator[bytes]:`

## `backend/app\concurrency\cancellation.py`

- Line 6: `class CancellationToken:`
- Line 9: `def __init__(self) -> None:`
- Line 13: `def cancel(self, reason: str = "cancelled") -> None:`
- Line 18: `def cancelled(self) -> bool:`
- Line 21: `def raise_if_cancelled(self) -> None:`

## `backend/app\concurrency\limits.py`

- Line 10: `class ResourceLimits:`
- Line 17: `def from_settings(cls) -> "ResourceLimits":`
- Line 30: `class ResourceGate:`
- Line 31: `def __init__(self, limits: ResourceLimits | None = None) -> None:`
- Line 38: `def semaphore(self, resource_class: str) -> asyncio.Semaphore:`
- Line 41: `async def acquire(self, resource_class: str) -> None:`
- Line 49: `def release(self, resource_class: str) -> None:`

## `backend/app\concurrency\singleflight.py`

- Line 10: `class Singleflight:`
- Line 13: `def __init__(self) -> None:`
- Line 17: `async def do(self, key: str, factory: Callable[[], Awaitable[T]]) -> T:`

## `backend/app\concurrency\timeouts.py`

- Line 9: `class StepTimeoutError(TimeoutError):`
- Line 10: `def __init__(self, step_id: str, timeout_ms: int) -> None:`
- Line 16: `async def with_timeout(awaitable: Awaitable[T], timeout_ms: int, step_id: str) -> T:`

## `backend/app\config.py`

- Line 7: `class Settings(BaseSettings):`
- Line 129: `def cors_origin_list(self) -> list[str]:`
- Line 133: `def demo_allowed_file_ids(self) -> list[int]:`
- Line 142: `def get_settings() -> Settings:`
- Line 146: `def validate_production_settings(settings: Settings) -> None:`

## `backend/app\data_gateway\memory.py`

- Line 29: `def seed_records() -> list[dict[str, Any]]:`
- Line 158: `class MemoryDataGateway:`
- Line 161: `def __init__(`
- Line 171: `async def list_datasets(self, scope: AccessScope) -> list[dict[str, Any]]:`
- Line 186: `async def get_dataset_fields(self, scope: AccessScope, file_id: int) -> list[dict[str, Any]]:`
- Line 191: `async def load_catalog(self, scope: AccessScope) -> FieldCatalog:`
- Line 194: `async def count_records(`
- Line 202: `async def count_records_by_file(`
- Line 214: `async def group_values(`
- Line 232: `def _display(self, row: dict[str, Any], field: str) -> str | None:`
- Line 240: `async def group_values_multi(`
- Line 291: `async def field_stats(`
- Line 330: `async def duplicate_values(`
- Line 367: `async def record_completeness(`
- Line 401: `async def interval_rows(`
- Line 447: `async def interval_stats(`
- Line 490: `async def list_records(`
- Line 524: `async def list_records_window(`
- Line 564: `async def sample_records(`
- Line 587: `async def sample_records_page(`
- Line 617: `async def retrieve_candidates(`
- Line 632: `async def get_raw_fields(`
- Line 657: `async def get_records_by_source_ids(`
- Line 670: `def _allowed_file_ids(self, scope: AccessScope, file_ids: tuple[int, ...]) -> set[int]:`
- Line 679: `async def save_query_run(`

## `backend/app\data_gateway\protocol.py`

- Line 15: `class GroupRow:`
- Line 25: `class FieldStats:`
- Line 37: `class DuplicateGroup:`
- Line 46: `class CompletenessRow:`
- Line 56: `class IntervalRow:`
- Line 67: `def is_impossible(self) -> bool:`
- Line 77: `class IntervalStats:`
- Line 88: `class RecordPage:`
- Line 100: `class DataGateway(Protocol):`
- Line 101: `async def list_datasets(self, scope: AccessScope) -> list[dict[str, Any]]: ...`
- Line 103: `async def get_dataset_fields(self, scope: AccessScope, file_id: int) -> list[dict[str, Any]]: ...`
- Line 105: `async def load_catalog(self, scope: AccessScope) -> FieldCatalog: ...`
- Line 107: `async def count_records(`
- Line 114: `async def count_records_by_file(`
- Line 121: `async def group_values(`
- Line 129: `async def group_values_multi(`
- Line 145: `async def field_stats(`
- Line 155: `async def duplicate_values(`
- Line 169: `async def record_completeness(`
- Line 179: `async def interval_rows(`
- Line 193: `async def interval_stats(`
- Line 205: `async def list_records(`
- Line 217: `async def list_records_window(`
- Line 231: `async def sample_records(`
- Line 240: `async def sample_records_page(`
- Line 249: `async def retrieve_candidates(`
- Line 258: `async def get_raw_fields(`
- Line 265: `async def get_records_by_source_ids(`
- Line 271: `async def save_query_run(`

## `backend/app\data_gateway\repository.py`

- Line 29: `def _filters_payload(predicates: list[Predicate]) -> list[dict[str, Any]]:`
- Line 34: `def _optional_float(value: Any) -> float | None:`
- Line 38: `def _members(value: Any) -> list[str]:`
- Line 59: `def _gateway_row(row: Any) -> dict[str, Any]:`
- Line 74: `class AssistantDataGateway:`
- Line 81: `def __init__(self, pool: asyncpg.Pool) -> None:`
- Line 84: `async def list_datasets(self, scope: AccessScope) -> list[dict[str, Any]]:`
- Line 94: `async def get_dataset_fields(self, scope: AccessScope, file_id: int) -> list[dict[str, Any]]:`
- Line 107: `async def load_catalog(self, scope: AccessScope) -> FieldCatalog:`
- Line 122: `async def count_records(`
- Line 138: `async def count_records_by_file(`
- Line 154: `async def group_values(`
- Line 180: `async def group_values_multi(`
- Line 225: `async def field_stats(`
- Line 261: `async def duplicate_values(`
- Line 303: `async def record_completeness(`
- Line 338: `async def interval_rows(`
- Line 384: `async def interval_stats(`
- Line 423: `async def list_records(`
- Line 452: `async def list_records_window(`
- Line 512: `async def sample_records(`
- Line 535: `async def sample_records_page(`
- Line 570: `async def retrieve_candidates(`
- Line 594: `async def get_raw_fields(`
- Line 617: `async def get_records_by_source_ids(`
- Line 638: `async def save_query_run(`
- Line 653: `def to_wall(value: float | None) -> datetime | None:`

## `backend/app\db\migrate.py`

- Line 14: `async def apply_migrations() -> None:`
- Line 48: `def main() -> None:`

## `backend/app\db\pool.py`

- Line 10: `async def init_pool() -> asyncpg.Pool:`
- Line 23: `def get_pool() -> asyncpg.Pool:`
- Line 29: `async def close_pool() -> None:`

## `backend/app\db\privilege_selftest.py`

- Line 30: `async def assert_runtime_isolation(dsn: str | None = None) -> None:`
- Line 75: `def main() -> None:`

## `backend/app\execution\dag_scheduler.py`

- Line 16: `class ScheduledStep:`
- Line 30: `class StepResult:`
- Line 39: `class StepTrace:`
- Line 56: `def duration_ms(self) -> float:`
- Line 63: `class RunTrace:`
- Line 74: `def latency_ms(self) -> float:`
- Line 83: `class DagScheduler:`
- Line 86: `def __init__(`
- Line 98: `async def run(`
- Line 123: `def mark_ready() -> None:`
- Line 183: `async def _run_one(`
- Line 198: `async def invoke() -> StepResult:`
- Line 216: `def _cancel_group(`
- Line 240: `def _critical_path_ms(steps: list[ScheduledStep], traces: dict[str, StepTrace]) -> float:`
- Line 244: `def walk(step_id: str) -> float:`

## `backend/app\execution\derivations.py`

- Line 26: `def value_part(value: Any, part: str | None) -> str | None:`
- Line 50: `def numeric_value(value: Any, part: str | None = None) -> float | None:`
- Line 63: `def parse_date(value: Any) -> date | None:`
- Line 83: `def date_precision(value: Any) -> str | None:`
- Line 99: `def _safe_date(year: int, month: int, day: int) -> date | None:`

## `backend/app\execution\executor.py`

- Line 32: `class ComputedFact:`
- Line 39: `class ActionResult:`
- Line 81: `class ExecutionResult:`
- Line 96: `class PlanExecutionError(ValueError):`
- Line 132: `class QueryExecutor:`
- Line 135: `def __init__(`
- Line 146: `async def execute(`
- Line 168: `async def _run_step(`
- Line 685: `def _counts_from_groups(groups: list[GroupRow]) -> dict[str, int]:`
- Line 696: `def _count_from_dep(dep: str, prior: dict[str, StepResult]) -> int | None:`
- Line 706: `def _to_scheduled(plan: QueryPlan, fingerprint: str) -> list[ScheduledStep]:`
- Line 736: `def _inputs(step: PlanStep) -> list[str]:`
- Line 744: `def _collect_predicates(step: PlanStep, prior: dict[str, StepResult], plan: QueryPlan) -> list[Predicate]:`
- Line 755: `def _hits_from_dep(dep: str, prior: dict[str, StepResult]) -> list[RetrievalHit]:`
- Line 762: `def _collect_hits(`
- Line 775: `def _collect_sort(step: PlanStep, prior: dict[str, StepResult]) -> tuple[str | None, str | None]:`
- Line 785: `def _typed_aggregate_value(value: Any, semantic_type: str) -> int | float | str | None:`
- Line 801: `def _collect_limit(step: PlanStep, prior: dict[str, StepResult], plan: QueryPlan) -> int | None:`
- Line 809: `def _collect_offset(step: PlanStep, prior: dict[str, StepResult], plan: QueryPlan) -> int | None:`
- Line 819: `def _collect_paging(step: PlanStep, prior: dict[str, StepResult]) -> dict[str, Any]:`
- Line 831: `def _resolve_window(`
- Line 847: `def _categorical_value(row: dict[str, Any], field_name: str) -> str | None:`
- Line 863: `def _collect_value_counts(`
- Line 876: `def _grouped_by_file(step: PlanStep, prior: dict[str, StepResult]) -> bool:`
- Line 885: `def hit_from_row(row: dict[str, Any]) -> RetrievalHit:`
- Line 899: `def _reduce(plan: QueryPlan, outputs: dict[str, StepResult], trace: RunTrace) -> ExecutionResult:`
- Line 942: `def _accumulate(bucket: ActionResult, value: dict[str, Any]) -> None:`
- Line 1023: `def _merge_rows(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:`

## `backend/app\execution\filters.py`

- Line 11: `def extract_field_value(record: dict[str, Any], spec: FieldSpec) -> Any:`
- Line 47: `def _walk(row: Any, path: str) -> Any:`
- Line 56: `def predicate_matches(record: dict[str, Any], predicate: Predicate, spec: FieldSpec) -> bool:`
- Line 133: `def _terms(value: Any) -> list[str]:`
- Line 139: `def _negative_match(value: Any, predicate: Predicate) -> bool:`
- Line 152: `def matches_predicate_tree(`
- Line 174: `def apply_predicates(`
- Line 193: `def _as_bool(value: Any) -> bool | None:`
- Line 206: `def _year(value: Any) -> int | None:`
- Line 213: `def _number(value: Any) -> float | None:`

## `backend/app\execution\formatter.py`

- Line 9: `def _row_name(row: dict, catalog: FieldCatalog) -> str:`
- Line 16: `def format_spoken_answer(`
- Line 46: `def _spoken_action(action: ActionResult, plan: QueryPlan, catalog: FieldCatalog) -> str | None:`
- Line 85: `def _spoken_list(values: list[str]) -> str:`
- Line 94: `def format_deterministic_answer(`
- Line 116: `def _format_action(`
- Line 193: `def _format_page(`
- Line 258: `def _humanize(field: str | None) -> str:`
- Line 262: `def _format_number(value: float | None, digits: int = 2) -> str:`
- Line 279: `def _format_numeric_aggregates(`
- Line 300: `def _format_ranked(action: ActionResult, scope_text: str) -> str:`
- Line 336: `def _format_stats(action: ActionResult, scope_text: str) -> str:`
- Line 360: `def _format_percentage(action: ActionResult, scope_text: str, constraint: str) -> str:`
- Line 374: `def _format_duplicates(action: ActionResult, scope_text: str) -> str:`
- Line 399: `def _format_completeness(action: ActionResult, scope_text: str) -> str:`
- Line 414: `def _format_intervals(action: ActionResult, scope_text: str) -> str:`
- Line 445: `def _scope_text(`
- Line 459: `def _format_distinct(field: str, values: list[str], scope_text: str) -> str:`
- Line 470: `def _format_distinct_count(field: str, count: int, scope_text: str) -> str:`
- Line 479: `def _format_value_counts(field: str, counts: dict[str, int], scope_text: str) -> str:`
- Line 498: `def _format_grouped(grouped: dict[int, int], catalog: FieldCatalog) -> str:`
- Line 506: `def _compact_subject(predicates: list[Predicate], noun: str, *, plural: bool) -> str:`
- Line 516: `def _compact_list_heading(predicates: list[Predicate]) -> str:`
- Line 526: `def _community(predicates: list[Predicate]) -> str | None:`
- Line 533: `def _starts_with(predicates: list[Predicate]) -> str | None:`
- Line 540: `def format_access_denied() -> str:`
- Line 544: `def format_unplanned(detail: str) -> str:`
- Line 551: `def _constraint_text(predicates: list[Predicate]) -> str:`

## `backend/app\execution\row_projection.py`

- Line 16: `def semantic_value(`
- Line 58: `def public_projected_row(`
- Line 72: `def field_descriptors(`
- Line 89: `def display_value(value: Any) -> str:`
- Line 99: `def _first_spec(`
- Line 111: `def _read_path(payload: Any, path: str) -> Any:`

## `backend/app\execution\turn.py`

- Line 58: `class TurnResult:`
- Line 85: `class AssistantTurnService:`
- Line 88: `def __init__(`
- Line 106: `async def answer(`
- Line 147: `async def _answer(`
- Line 371: `async def _answer_fan_out(`
- Line 468: `async def _run_plan(`
- Line 608: `def _semantic_compiler(self) -> SemanticCompiler | UnavailableSemanticCompiler:`
- Line 628: `def _source_actions(`
- Line 653: `async def _direct_reply(`
- Line 713: `async def _answer_general(`
- Line 747: `async def _reasoned_plan_and_answer(`
- Line 797: `async def _planning_catalog(self, scope: AccessScope) -> FieldCatalog:`
- Line 808: `def _should_synthesize(`
- Line 825: `async def _synthesize(`
- Line 867: `async def _answer_reference(`
- Line 946: `async def _answer_ordinal(`
- Line 1007: `async def _persist(`
- Line 1037: `async def _record_query_run(`
- Line 1055: `async def _emit_phrases(text: str, cancel: CancellationToken, on_spoken_phrase: SpokenPhraseFn) -> None:`
- Line 1061: `async def _emit_progress(`
- Line 1070: `def _public_rows(execution: ExecutionResult, catalog: FieldCatalog) -> list[dict[str, Any]]:`
- Line 1081: `def _public_row_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:`
- Line 1095: `def _display_name(row: dict[str, Any]) -> Any:`
- Line 1105: `def _display_community(row: dict[str, Any]) -> Any:`
- Line 1112: `def _public_list_results(`
- Line 1153: `def _public_evidence(execution: ExecutionResult) -> list[dict[str, Any]]:`
- Line 1166: `def _route_trace(route: PlanRouteResult) -> list[dict[str, Any]]:`
- Line 1246: `def _direct_status(route: PlanRouteResult) -> str:`
- Line 1263: `def _fallback_reply(route: PlanRouteResult, mode: str = "text") -> str:`
- Line 1284: `def _is_unintelligible(route: PlanRouteResult) -> bool:`
- Line 1288: `def _resolve_selected_dataset(`
- Line 1312: `def _other_list_for_question(`
- Line 1331: `def _specific_label(`
- Line 1350: `def select_dataset_for_question(`
- Line 1425: `def _wrong_list_for_question(`
- Line 1476: `def is_person_summary(question: str) -> bool:`
- Line 1482: `def _question_for_dataset(question: str, catalog: FieldCatalog, file_id: int) -> str:`
- Line 1511: `def _fan_out_datasets(`
- Line 1544: `def _field_dataset_suggestion(`
- Line 1594: `def _conversation_context(conversation: ConversationRecord) -> ConversationContext:`
- Line 1616: `def _verify_preface(conversation: ConversationRecord, execution: ExecutionResult) -> str:`
- Line 1640: `def _filter_specs(predicates) -> list[FilterSpec]:`
- Line 1658: `def _active_query_from_frame(frame) -> ActiveQuery | None:`
- Line 1692: `def _frame_payload(frame) -> dict[str, Any]:`
- Line 1715: `def _memory_text(conversation: ConversationRecord) -> str:`
- Line 1722: `def _memory_text_for_general(conversation: ConversationRecord) -> str:`
- Line 1733: `def _is_unclear_single_word(question: str) -> bool:`
- Line 1740: `def _looks_like_list_page(text: str) -> bool:`
- Line 1744: `def _describe_predicate(predicate) -> str:`
- Line 1755: `def _packet_for_synthesis(question: str, execution: ExecutionResult) -> EvidencePacket:`

## `backend/app\llm\base.py`

- Line 13: `class ReasoningProvider(Protocol):`
- Line 16: `async def stream_answer(self, *, system: str, user: str) -> AsyncIterator[str]: ...`
- Line 18: `async def answer_structured(self, *, system: str, user: str) -> SynthesisAnswer: ...`
- Line 20: `async def plan_structured(self, *, system: str, user: str) -> PlannedQuery: ...`
- Line 22: `async def structured_output(self, *, system: str, user: str, response_model: type[T]) -> T: ...`

## `backend/app\llm\citations.py`

- Line 8: `def allowed_source_ids(packet: EvidencePacket) -> set[str]:`
- Line 15: `def validate_synthesis(`
- Line 36: `def render_evidence_block(packet: EvidencePacket) -> str:`
- Line 65: `def _append_item(lines: list[str], item) -> None:`

## `backend/app\llm\factory.py`

- Line 15: `def _xai_provider(`
- Line 31: `def reasoning_unavailable_reason() -> str | None:`
- Line 47: `def describe_reasoning() -> dict[str, Any]:`
- Line 59: `def get_reasoning_provider() -> ReasoningProvider | None:`

## `backend/app\llm\fake.py`

- Line 10: `class FakeReasoningProvider:`
- Line 13: `def __init__(self) -> None:`
- Line 21: `async def stream_answer(self, *, system: str, user: str) -> AsyncIterator[str]:`
- Line 36: `async def structured_output(self, *, system: str, user: str, response_model):`
- Line 45: `async def plan_structured(self, *, system: str, user: str) -> PlannedQuery:`
- Line 96: `async def answer_structured(self, *, system: str, user: str) -> SynthesisAnswer:`
- Line 118: `def _payload(user: str) -> dict:`
- Line 126: `def _utterance(user: str) -> tuple[str, str, dict]:`
- Line 138: `def _catalog_ids(parsed: dict) -> list[int]:`
- Line 150: `def _default_dataset(parsed: dict) -> int:`
- Line 159: `def _dataset_for_label(parsed: dict, text: str) -> int | None:`
- Line 171: `def _turn_plan_payload(user: str) -> dict:`
- Line 541: `def _followup_plan(`
- Line 676: `def _find_frame(phrase: str, frames: list) -> dict | None:`
- Line 693: `def _extract_filters(text: str) -> list[dict]:`
- Line 730: `def _extract_search(text: str) -> str | None:`
- Line 746: `def _respond(normalized: str, response: str, confidence: float, *, intent: str) -> dict:`
- Line 755: `def _is_identity(text: str) -> bool:`
- Line 770: `def _is_audio(text: str) -> bool:`
- Line 785: `def _action_reference(text: str) -> dict | None:`
- Line 807: `def _ordinal_selector(text: str) -> str | None:`
- Line 826: `def _is_catalog(text: str) -> bool:`
- Line 843: `def _canonical_payload(user: str) -> dict:`
- Line 872: `def _extract_source_ids(user: str) -> list[str]:`
- Line 888: `def _extract_names(user: str) -> list[str]:`
- Line 896: `def _extract_causes(user: str) -> list[str]:`
- Line 904: `def _extract_facts(user: str) -> list[str]:`

## `backend/app\llm\prompts.py`

- Line 51: `def planner_user_prompt(`
- Line 79: `def synthesis_user_prompt(`

## `backend/app\llm\schemas.py`

- Line 8: `class PlannedPredicate(BaseModel):`
- Line 14: `class PlannedStep(BaseModel):`
- Line 25: `class PlannedQuery(BaseModel):`
- Line 34: `class MemoryUpdate(BaseModel):`
- Line 40: `class SynthesisAnswer(BaseModel):`

## `backend/app\llm\xai_reasoner.py`

- Line 13: `def _global_semaphore() -> asyncio.Semaphore:`
- Line 22: `class XAIReasoningProvider:`
- Line 25: `def __init__(`
- Line 45: `async def stream_answer(self, *, system: str, user: str) -> AsyncIterator[str]:`
- Line 63: `async def answer_structured(self, *, system: str, user: str) -> SynthesisAnswer:`
- Line 67: `async def plan_structured(self, *, system: str, user: str) -> PlannedQuery:`
- Line 70: `async def structured_output(self, *, system: str, user: str, response_model):`
- Line 78: `async def _parse(self, model_type, *, system: str, user: str):`
- Line 91: `def _client(self):`

## `backend/app\main.py`

- Line 21: `async def lifespan(_: FastAPI):`
- Line 53: `def create_app() -> FastAPI:`

## `backend/app\memory\followups.py`

- Line 46: `class FollowUpResolution:`
- Line 55: `def is_followup_utterance(text: str) -> bool:`
- Line 68: `def _plan_from_state(state: QueryState, scope: AccessScope, catalog: FieldCatalog) -> QueryPlan:`
- Line 79: `def resolve_listed_ordinal(`
- Line 113: `def _resolve_action_frame(`
- Line 144: `def resolve_followup(`
- Line 227: `def _upsert(filters: list[Predicate], incoming: Predicate) -> list[Predicate]:`
- Line 233: `def _find_frame(conversation: ConversationRecord, phrase: str, catalog: FieldCatalog) -> QueryFrame | None:`

## `backend/app\memory\postgres.py`

- Line 14: `class PostgresMemoryStore:`
- Line 17: `def __init__(self, pool: asyncpg.Pool) -> None:`
- Line 20: `async def get_or_create(self, scope: AccessScope, conversation_id: str | None) -> ConversationRecord:`
- Line 33: `async def save(self, record: ConversationRecord) -> None:`
- Line 109: `async def list_for_principal(self, scope: AccessScope) -> list[ConversationRecord]:`
- Line 124: `async def get(self, scope: AccessScope, conversation_id: str) -> ConversationRecord | None:`
- Line 158: `def snapshot_record(record: ConversationRecord) -> dict[str, Any]:`
- Line 162: `def record_from_snapshot(payload: dict[str, Any], principal_id: str) -> ConversationRecord:`
- Line 166: `def _new_id() -> str:`
- Line 172: `def _validated_id(value: str) -> str:`
- Line 179: `def _current_mode(record: ConversationRecord) -> str:`
- Line 185: `def _last_source_ids(record: ConversationRecord) -> list[str]:`
- Line 190: `def _snapshot(record: ConversationRecord) -> dict[str, Any]:`
- Line 207: `def _from_row(row: dict[str, Any], principal_id: str) -> ConversationRecord:`
- Line 227: `def _from_snapshot(payload: dict[str, Any], principal_id: str) -> ConversationRecord:`
- Line 252: `def _prepare_turns(record: ConversationRecord) -> None:`
- Line 271: `def _as_datetime(value: Any) -> datetime:`
- Line 281: `def _enrich_turns(record: ConversationRecord, stored: Any) -> None:`

## `backend/app\memory\store.py`

- Line 9: `class MemoryStore(Protocol):`
- Line 10: `async def get_or_create(self, scope: AccessScope, conversation_id: str | None) -> ConversationRecord: ...`
- Line 12: `async def save(self, record: ConversationRecord) -> None: ...`
- Line 14: `async def list_for_principal(self, scope: AccessScope) -> list[ConversationRecord]: ...`
- Line 16: `async def get(self, scope: AccessScope, conversation_id: str) -> ConversationRecord | None: ...`
- Line 19: `class InMemoryMemoryStore:`
- Line 22: `def __init__(self) -> None:`
- Line 25: `async def get_or_create(self, scope: AccessScope, conversation_id: str | None) -> ConversationRecord:`
- Line 35: `async def save(self, record: ConversationRecord) -> None:`
- Line 38: `async def list_for_principal(self, scope: AccessScope) -> list[ConversationRecord]:`
- Line 41: `async def get(self, scope: AccessScope, conversation_id: str) -> ConversationRecord | None:`
- Line 53: `def default_memory_store() -> MemoryStore:`

## `backend/app\memory\types.py`

- Line 12: `class QueryState(BaseModel):`
- Line 36: `class ResultSet(BaseModel):`
- Line 57: `class QueryFrame(BaseModel):`
- Line 68: `class ConversationRecord(BaseModel):`
- Line 86: `def active_frame(self) -> QueryFrame | None:`
- Line 92: `def new_conversation_id() -> str:`
- Line 96: `def frame_key_for(file_ids: tuple[int, ...]) -> str:`
- Line 108: `def parse_source_id(source_id: str) -> tuple[int, int] | None:`
- Line 119: `def make_source_id(file_id: int, version: int, source_row_id: int) -> str:`

## `backend/app\memory\updates.py`

- Line 18: `def update_memory_from_turn(`
- Line 70: `def _append_turn(`
- Line 95: `def extract_query_state(plan: QueryPlan) -> QueryState:`
- Line 121: `def extract_action_query_state(`
- Line 165: `def _persist_action_frames(`
- Line 209: `def _write_frame(`
- Line 254: `def _rows(execution: ExecutionResult | None) -> list[dict]:`
- Line 260: `def _source_ids(execution: ExecutionResult | None) -> list[str]:`
- Line 264: `def _source_ids_from_rows(rows: list[dict]) -> list[str]:`
- Line 275: `def _topic(state: QueryState) -> str:`
- Line 283: `def _summary(conversation: ConversationRecord) -> str:`

## `backend/app\observability\audit.py`

- Line 10: `class AuditEvent:`
- Line 22: `class MemoryAuditor:`
- Line 25: `def __init__(self) -> None:`
- Line 28: `async def record(`
- Line 52: `class PostgresAuditor:`
- Line 53: `def __init__(self, pool) -> None:`
- Line 56: `async def record(`
- Line 100: `def get_auditor() -> MemoryAuditor:`
- Line 104: `def reset_auditor() -> None:`
- Line 108: `def default_auditor():`
- Line 117: `def _safe_metadata(payload: dict[str, Any]) -> dict[str, Any]:`

## `backend/app\observability\jobs.py`

- Line 33: `class Job:`
- Line 48: `class MemoryJobQueue:`
- Line 51: `def __init__(self) -> None:`
- Line 55: `async def enqueue(`
- Line 79: `async def claim(self, worker_id: str, *, lease_seconds: int = 30) -> Job | None:`
- Line 98: `async def complete(self, job_id: str) -> None:`
- Line 103: `async def fail(self, job_id: str, error: str, *, retry: bool = True) -> None:`
- Line 110: `class PostgresJobQueue:`
- Line 111: `def __init__(self, pool) -> None:`
- Line 114: `async def enqueue(`
- Line 151: `async def claim(self, worker_id: str, *, lease_seconds: int = 30) -> Job | None:`
- Line 168: `async def complete(self, job_id: str) -> None:`
- Line 179: `async def fail(self, job_id: str, error: str, *, retry: bool = True) -> None:`

## `backend/app\observability\retention.py`

- Line 18: `class RetentionPolicy:`
- Line 26: `class PurgeReport:`
- Line 34: `def should_purge(created_at: datetime, *, max_age: timedelta, now: datetime | None = None) -> bool:`
- Line 42: `class RetentionService:`
- Line 45: `def __init__(self, policy: RetentionPolicy | None = None) -> None:`
- Line 48: `def purge_local(`
- Line 96: `async def purge_postgres(self, pool) -> PurgeReport:`
- Line 147: `async def delete_conversation(self, pool, conversation_id: str, principal_id: str) -> bool:`
- Line 160: `def _as_dt(value: Any) -> datetime:`

## `backend/app\observability\tracing.py`

- Line 26: `def _safe_attrs(attributes: dict[str, Any]) -> dict[str, Any]:`
- Line 30: `def _otel_tracer():`
- Line 38: `def _otel_error_status():`
- Line 44: `def _otel_value(value: Any) -> Any:`
- Line 51: `class Span:`
- Line 61: `def duration_ms(self) -> float:`
- Line 67: `class Tracer:`
- Line 70: `def __init__(self) -> None:`
- Line 75: `def span(self, name: str, **attributes: Any) -> Iterator[Span]:`
- Line 98: `def by_name(self, name: str) -> list[Span]:`
- Line 101: `def reset(self) -> None:`
- Line 108: `def get_tracer() -> Tracer:`
- Line 112: `def reset_tracer() -> None:`

## `backend/app\observability\worker.py`

- Line 13: `async def handle_job(job, queue) -> None:`
- Line 39: `async def run_once(queue, worker_id: str = "nia-job-1") -> bool:`
- Line 50: `def main() -> None:`
- Line 54: `async def _main() -> None:`

## `backend/app\planning\analytic_guards.py`

- Line 87: `def is_analytic_question(question: str) -> bool:`
- Line 105: `def apply_analytic_guards(turn: TurnPlan, question: str, catalog: FieldCatalog) -> TurnPlan:`
- Line 118: `def _guard_action(action: QueryAction, question: str, catalog: FieldCatalog) -> QueryAction:`
- Line 198: `def _merge_same_field_alternatives(`
- Line 237: `def _correct_presence_polarity(`
- Line 266: `def _negated_before(`
- Line 287: `def _breakdown_bucket_updates(`
- Line 312: `def _person_summary_updates(`
- Line 336: `def _name_from_filters(action: QueryAction) -> str | None:`
- Line 373: `def _event_rank(semantic_field: str) -> int | None:`
- Line 380: `def _mentions_event(question: str, semantic_field: str) -> bool:`
- Line 390: `def _date_fields_by_rank(action: QueryAction, catalog: FieldCatalog) -> dict[int, str]:`
- Line 407: `def _infer_interval_fields(`
- Line 447: `def _sanitize_goal_requirements(`
- Line 505: `def _drop_unresolvable_fields(`
- Line 529: `def _bucket_part(question: str) -> str | None:`
- Line 537: `def _grouping_field(action: QueryAction, question: str, catalog: FieldCatalog) -> str | None:`
- Line 569: `def _stats_target(action: QueryAction, catalog: FieldCatalog) -> str | None:`
- Line 581: `def _name_part_update(`
- Line 612: `def _expand_synonyms(`
- Line 649: `def _family_for(families: dict, value: str) -> list[str] | None:`
- Line 662: `def _spec(name: str, datasets: list[int], catalog: FieldCatalog) -> FieldSpec | None:`

## `backend/app\planning\canonical_query.py`

- Line 14: `class TurnType(StrEnum):`
- Line 21: `class CanonicalGoal(StrEnum):`
- Line 29: `class RetrievalMode(StrEnum):`
- Line 36: `class CanonicalFilter(BaseModel):`
- Line 44: `class CanonicalSort(BaseModel):`
- Line 51: `class CanonicalQuery(BaseModel):`
- Line 91: `def _ids(cls, value: Any) -> tuple[int, ...]:`
- Line 97: `def spoken_or_direct_text(self) -> str | None:`
- Line 106: `class CanonicalQueryError(ValueError):`
- Line 110: `def canonical_query_to_plan(`
- Line 231: `def _append_retrieval(`
- Line 257: `def _default_projection(file_ids: tuple[int, ...], catalog: FieldCatalog) -> list[str]:`
- Line 265: `def _field_exists_on_all(file_ids: tuple[int, ...], field: str, catalog: FieldCatalog) -> bool:`
- Line 269: `def _require_field_on_all(file_ids: tuple[int, ...], field: str, catalog: FieldCatalog) -> None:`
- Line 275: `def _evidence_allowed_on_any(file_ids: tuple[int, ...], field: str, catalog: FieldCatalog) -> bool:`

## `backend/app\planning\catalog.py`

- Line 12: `class FieldSpec(BaseModel):`
- Line 33: `class DatasetSpec(BaseModel):`
- Line 45: `class FieldCatalog(BaseModel):`
- Line 54: `def dataset(self, file_id: int) -> DatasetSpec | None:`
- Line 57: `def fields_for(self, file_id: int) -> list[FieldSpec]:`
- Line 60: `def resolve_field(self, file_id: int, name: str) -> FieldSpec | None:`
- Line 69: `def resolve_dataset_ids(self, text: str) -> list[int]:`
- Line 78: `def for_scope(self, scope: Any) -> FieldCatalog:`
- Line 100: `def dataset_match_labels(dataset: DatasetSpec) -> tuple[str, ...]:`
- Line 117: `def static_catalog() -> FieldCatalog:`
- Line 272: `def _comprehensive_public_fields() -> tuple[FieldSpec, ...]:`
- Line 403: `def catalog_from_rows(`

## `backend/app\planning\conversation_resolver.py`

- Line 31: `class ConversationContext:`
- Line 45: `class ConversationResolution:`
- Line 52: `def resolve_conversation_followup(`
- Line 113: `def _looks_like_short_followup(text: str, value: str) -> bool:`
- Line 119: `def _is_date_predicate(`
- Line 128: `def _edit_unique_predicate(`

## `backend/app\planning\deterministic_parser.py`

- Line 150: `class ParseResult:`
- Line 163: `class ConstraintExtraction:`
- Line 170: `def parse_deterministic(`
- Line 373: `def needs_synthesis(text: str) -> bool:`
- Line 377: `def _fallback(`
- Line 397: `def _coverage(text: str, consumed_spans: list[tuple[int, int]]) -> tuple[float, tuple[str, ...]]:`
- Line 432: `def _dataset_spans(text: str, catalog: FieldCatalog) -> list[tuple[int, int]]:`
- Line 455: `def _distinct_field(text: str) -> str | None:`
- Line 463: `def _schema_distinct_field(`
- Line 498: `def build_distinct_plan(`
- Line 516: `def build_distinct_count_plan(*, file_ids: tuple[int, ...], field: str) -> QueryPlan:`
- Line 533: `def build_structured_plan(`
- Line 613: `def _resolve_file_ids(`
- Line 634: `def _constraints(`

## `backend/app\planning\input_normalizer.py`

- Line 31: `class NormalizationCorrection:`
- Line 38: `class NormalizedTurn:`
- Line 55: `def changed(self) -> bool:`
- Line 59: `def normalize_user_turn(text: str) -> NormalizedTurn:`
- Line 72: `def _apply_simple_correction(match: re.Match[str]) -> str:`

## `backend/app\planning\llm_planner.py`

- Line 12: `class ConstrainedPlanner:`
- Line 13: `def __init__(self, provider: ReasoningProvider, catalog: FieldCatalog) -> None:`
- Line 17: `async def plan(`
- Line 31: `def planned_query_to_plan(drafted: PlannedQuery, scope: AccessScope) -> QueryPlan:`

## `backend/app\planning\plan_coverage.py`

- Line 53: `def plan_covers_question(plan: QueryPlan, question: str, catalog: FieldCatalog) -> bool:`
- Line 71: `def _covered(token: str, vocabulary: set[str]) -> bool:`
- Line 76: `def _catalog_vocabulary(plan: QueryPlan, catalog: FieldCatalog) -> set[str]:`
- Line 88: `def _plan_vocabulary(plan: QueryPlan) -> set[str]:`
- Line 107: `def normalize_question(question: str) -> str:`
- Line 113: `def _label_pattern(label: str) -> str:`
- Line 131: `def field_mentions(`
- Line 168: `def specific_field_mentions(`
- Line 188: `def plan_field_references(plan: QueryPlan) -> set[str]:`

## `backend/app\planning\plan_schema.py`

- Line 7: `class PlanOp(StrEnum):`
- Line 63: `class FilterOperator(StrEnum):`
- Line 149: `class PlanScope(BaseModel):`
- Line 158: `def _ids(cls, value: Any) -> tuple[int, ...]:`
- Line 162: `class Predicate(BaseModel):`
- Line 179: `def _leaf_or_group(self) -> "Predicate":`
- Line 188: `def is_group(self) -> bool:`
- Line 191: `def leaves(self) -> list["Predicate"]:`
- Line 200: `def payload(self) -> dict[str, Any]:`
- Line 211: `def all_of(*items: Predicate) -> Predicate:`
- Line 215: `def any_of(*items: Predicate) -> Predicate:`
- Line 219: `def not_(item: Predicate) -> Predicate:`
- Line 223: `class PlanStep(BaseModel):`
- Line 259: `def _ids(cls, value: Any) -> tuple[int, ...] | None:`
- Line 266: `def _input(cls, value: Any) -> str | list[str] | None:`
- Line 272: `class QueryPlan(BaseModel):`
- Line 288: `def _unique_step_ids(self) -> "QueryPlan":`
- Line 296: `def op_names(self) -> list[str]:`
- Line 299: `def step_map(self) -> dict[str, PlanStep]:`

## `backend/app\planning\plan_validator.py`

- Line 11: `class PlanValidationError(ValueError):`
- Line 12: `def __init__(self, message: str, *, code: str = "invalid_plan") -> None:`
- Line 51: `def validate_query_plan(`
- Line 73: `def _reject_structural_injection(plan: QueryPlan) -> None:`
- Line 94: `def _validate_budgets(plan: QueryPlan, settings) -> None:`
- Line 116: `def _validate_scope(plan: QueryPlan, scope: AccessScope) -> None:`
- Line 144: `def _validate_dag(plan: QueryPlan) -> None:`
- Line 159: `def _validate_ops_and_fields(`
- Line 209: `def _validate_op_contract(step: PlanStep) -> None:`
- Line 253: `def _validate_aggregate_capability(op: PlanOp, spec) -> None:`
- Line 274: `def _validate_predicate(field: str, operator: str, file_ids: tuple[int, ...], catalog: FieldCatalog) -> None:`
- Line 283: `def _validate_field(field: str, file_ids: tuple[int, ...], catalog: FieldCatalog):`
- Line 294: `def _inputs(value: str | list[str] | None) -> list[str]:`

## `backend/app\planning\query_plan_builder.py`

- Line 69: `class QueryPlanBuildError(ValueError):`
- Line 73: `class UnsupportedFieldsError(QueryPlanBuildError):`
- Line 74: `def __init__(`
- Line 92: `def compiled_query_actions(`
- Line 109: `def query_action_from_state(state) -> QueryAction:`
- Line 117: `def _query_action_from_fields(state) -> QueryAction:`
- Line 154: `def reconstruct_query_action(`
- Line 255: `def build_query_plan(`
- Line 299: `def _stamp(steps: list[PlanStep], *, action_id: str, action_goal: str) -> list[PlanStep]:`
- Line 309: `def _is_data_action(action) -> bool:`
- Line 313: `def _effective_query(`
- Line 433: `def _source_query(`
- Line 457: `def _apply_changes(existing: list[FilterSpec], changes: list[FilterSpec]) -> list[FilterSpec]:`
- Line 471: `def _compile_single(`
- Line 499: `def _compile_parallel(`
- Line 531: `def _compile_branch(`
- Line 948: `def _all_projectable_fields(file_ids: tuple[int, ...], catalog: FieldCatalog) -> list[str]:`
- Line 961: `def _all_evidence_fields(file_ids: tuple[int, ...], catalog: FieldCatalog) -> list[str]:`
- Line 969: `def _stats_field(query: QueryAction, file_ids: tuple[int, ...], catalog: FieldCatalog) -> str:`
- Line 980: `def _interval_fields(`
- Line 993: `def _compile_compare(`
- Line 1036: `def _compile_aggregate(`
- Line 1071: `def _append_retrieval(`
- Line 1094: `def _append_evidence(`
- Line 1122: `def _resolve_datasets(datasets: list[int], scope: AccessScope, catalog: FieldCatalog) -> tuple[int, ...]:`
- Line 1141: `def _predicates_for(`
- Line 1153: `def _to_predicate(spec: FilterSpec, file_ids: tuple[int, ...], catalog: FieldCatalog) -> Predicate:`
- Line 1168: `def _canonical_field(name: str, file_ids: tuple[int, ...], catalog: FieldCatalog) -> str:`
- Line 1176: `def _default_list_sort(file_ids: tuple[int, ...], catalog: FieldCatalog) -> str | None:`
- Line 1183: `def _default_projection(file_ids: tuple[int, ...], catalog: FieldCatalog) -> list[str]:`
- Line 1190: `def _requested_projection(`
- Line 1218: `def _common_field_labels(file_ids: tuple[int, ...], catalog: FieldCatalog) -> list[str]:`
- Line 1229: `def _evidence_allowed(file_ids: tuple[int, ...], field: str, catalog: FieldCatalog) -> bool:`
- Line 1234: `def _quoteable(file_ids: tuple[int, ...], field: str, catalog: FieldCatalog) -> bool:`

## `backend/app\planning\response_policy.py`

- Line 31: `def decide_final_response(turn: TurnPlan) -> str:`
- Line 62: `def only_clarification(turn: TurnPlan) -> bool:`
- Line 66: `def only_general_conversation(turn: TurnPlan | None) -> bool:`
- Line 75: `def only_direct_response(turn: TurnPlan) -> bool:`
- Line 81: `def only_reference(turn: TurnPlan) -> bool:`
- Line 86: `def acknowledgement(turn: TurnPlan, *, mode: str = "text") -> str | None:`
- Line 93: `def canned_response(`
- Line 147: `def _first_sentence(text: str | None) -> str:`
- Line 158: `def _naturalize_assistant_name(text: str) -> str:`

## `backend/app\planning\router.py`

- Line 43: `class PlanRouteResult:`
- Line 63: `async def plan_user_turn(`
- Line 442: `def _no_deterministic_plan():`
- Line 449: `def _route_validated_turn(`
- Line 567: `def _compiler_response_text(`
- Line 595: `def describe_available_data(catalog: FieldCatalog, file_ids: tuple[int, ...] = ()) -> str:`
- Line 616: `def _unsupported_fields_text(exc: UnsupportedFieldsError) -> str:`
- Line 628: `def _humanize_field(value: str) -> str:`
- Line 632: `def _unplanned_clarification(input_mode: Literal["text", "voice"]) -> str:`
- Line 644: `def _looks_like_incomplete_utterance(text: str) -> bool:`
- Line 649: `def _compiler_unavailable_text(`
- Line 657: `def _frame_map(context: ConversationContext) -> dict:`

## `backend/app\planning\schema_query.py`

- Line 78: `class FieldMention:`
- Line 85: `def is_schema_priority(text: str) -> bool:`
- Line 101: `def parse_schema_query(`
- Line 245: `def _field_mentions(text: str, specs: list[FieldSpec]) -> list[FieldMention]:`
- Line 269: `def _phrase_variants(phrase: str) -> set[str]:`
- Line 284: `def _word_number_variants(word: str) -> set[str]:`
- Line 299: `def _unique_specs(mentions: list[FieldMention]) -> list[FieldSpec]:`
- Line 309: `def _operation_field(`
- Line 328: `def _best_token_overlap(text: str, specs: list[FieldSpec]) -> FieldSpec | None:`
- Line 334: `def _token_overlap(text: str, spec: FieldSpec) -> int:`
- Line 347: `def _singular(token: str) -> str:`
- Line 351: `def _predicates(`
- Line 450: `def _exact_value(text: str, mentions: list[FieldMention], spec: FieldSpec) -> str | None:`
- Line 496: `def _modifier_target(match: re.Match[str] | None, mentions: list[FieldMention]) -> str | None:`
- Line 514: `def _field_context(text: str, mentions: list[FieldMention], spec: FieldSpec) -> str:`
- Line 523: `def _contains_value(text: str, mentions: list[FieldMention], spec: FieldSpec) -> str | None:`
- Line 550: `def _clean_value(value: str) -> str:`
- Line 555: `def _dedupe_predicates(items: list[Predicate]) -> list[Predicate]:`
- Line 566: `def _person_name(text: str) -> str | None:`
- Line 576: `def _projection(text: str, mentioned: list[FieldSpec], specs: list[FieldSpec]) -> list[str]:`
- Line 586: `def _list_controls(`
- Line 616: `def _value_part(text: str, spec: FieldSpec) -> str | None:`
- Line 620: `def _plain_dataset_count(text: str) -> bool:`
- Line 626: `def _semantic(specs: list[FieldSpec], name: str) -> FieldSpec | None:`
- Line 630: `def _phrase_in(text: str, phrase: str) -> bool:`
- Line 634: `def _scope_step(file_id: int) -> PlanStep:`
- Line 638: `def _filtered_steps(file_id: int, predicates: list[Predicate]) -> tuple[list[PlanStep], str]:`
- Line 647: `def _count_plan(file_id: int, predicates: list[Predicate]) -> QueryPlan:`
- Line 653: `def _aggregate_plan(file_id: int, spec: FieldSpec, op: PlanOp, predicates: list[Predicate]) -> QueryPlan:`
- Line 659: `def _group_plan(`
- Line 685: `def _list_plan(`
- Line 731: `def _plan(file_id: int, goals: list[str], steps: list[PlanStep]) -> QueryPlan:`

## `backend/app\planning\semantic_compiler.py`

- Line 162: `class TurnStructuredCall(Protocol):`
- Line 163: `async def __call__(`
- Line 173: `class CompilerResult:`
- Line 184: `def as_layer(self) -> dict[str, Any]:`
- Line 200: `class SemanticCompiler:`
- Line 201: `def __init__(`
- Line 212: `async def compile(`
- Line 293: `class UnavailableSemanticCompiler:`
- Line 294: `def __init__(self, reason: str) -> None:`
- Line 299: `async def compile(`
- Line 328: `def compiler_user_prompt(`
- Line 355: `def catalog_payload(catalog: FieldCatalog) -> dict[str, Any]:`
- Line 382: `def _active_query_payload(active: ActiveQuery | None) -> dict[str, Any] | None:`

## `backend/app\planning\semantic_normalizer.py`

- Line 31: `class CanonicalStructuredCall(Protocol):`
- Line 32: `async def __call__(`
- Line 41: `class SemanticNormalizerProtocol(Protocol):`
- Line 42: `async def normalize(`
- Line 53: `class LLMSemanticNormalizer:`
- Line 61: `def __init__(self, structured_call: CanonicalStructuredCall) -> None:`
- Line 64: `async def normalize(`
- Line 90: `def semantic_normalizer_user_prompt(`
- Line 106: `def _catalog_payload(catalog: FieldCatalog) -> dict:`

## `backend/app\planning\timing.py`

- Line 14: `class PlanningTimings:`
- Line 19: `def as_dict(self) -> dict[str, float]:`
- Line 22: `def get(self, name: str, default: float = 0.0) -> float:`
- Line 29: `def total_ms(self) -> float:`
- Line 33: `def slowest(self) -> tuple[str, float] | None:`
- Line 39: `class TimingRecorder:`
- Line 46: `def __init__(self) -> None:`
- Line 50: `def measure(self, name: str) -> Iterator[None]:`
- Line 58: `def record(self, name: str, elapsed_ms: float) -> None:`
- Line 61: `def finish(self) -> PlanningTimings:`

## `backend/app\planning\trusted_overrides.py`

- Line 121: `def apply_trusted_overrides(`
- Line 289: `def trusted_fast_turn(`
- Line 336: `def _apply_random_sample(`
- Line 383: `def _enforce_cause_summary(turn: TurnPlan, text: str) -> TurnPlan | None:`
- Line 401: `def _unavailable_catalog_field(text: str, *, catalog: FieldCatalog | None) -> str | None:`
- Line 419: `def _requested_sample_size(text: str) -> int:`
- Line 429: `def _reset_implicit_paging(turn: TurnPlan) -> TurnPlan:`
- Line 443: `def _bare_research_dump(turn: TurnPlan) -> bool:`
- Line 466: `def _offers_next_page(last_assistant_text: str) -> bool:`
- Line 471: `def _extract_result_window(text: str) -> ResultWindow | None:`
- Line 482: `def _apply_result_window(`
- Line 539: `def _extract_requested_fields(text: str) -> list[str]:`
- Line 557: `def _apply_requested_fields(`
- Line 605: `def _all_public_fields(catalog: FieldCatalog) -> list[str]:`
- Line 613: `def _respond(turn: TurnPlan, intent: str, response: str = "") -> TurnPlan:`
- Line 627: `def _replace(turn: TurnPlan, actions) -> TurnPlan:`

## `backend/app\planning\turn_interpreter.py`

- Line 16: `class CanonicalStructuredCall(Protocol):`
- Line 17: `async def __call__(`
- Line 27: `class InterpreterResult:`
- Line 40: `def as_layer(self) -> dict[str, Any]:`
- Line 56: `class TurnInterpreterProtocol(Protocol):`
- Line 60: `async def interpret(`
- Line 72: `class LLMTurnInterpreter:`
- Line 79: `def __init__(`
- Line 90: `async def interpret(`
- Line 164: `class UnavailableTurnInterpreter:`
- Line 167: `def __init__(self, reason: str) -> None:`
- Line 172: `async def interpret(`
- Line 203: `def _public_canonical(canonical: CanonicalQuery) -> dict[str, Any]:`

## `backend/app\planning\turn_schema.py`

- Line 135: `def _reject_forbidden_identifier(value: str, *, label: str) -> str:`
- Line 143: `class FilterSpec(BaseModel):`
- Line 152: `def _field(cls, value: str) -> str:`
- Line 160: `def _operator(cls, value: str) -> str:`
- Line 167: `class AggregateSpec(BaseModel):`
- Line 177: `def _field(cls, value: str | None) -> str | None:`
- Line 183: `class CompareBranch(BaseModel):`
- Line 191: `class ResultWindow(BaseModel):`
- Line 201: `class QueryAction(BaseModel):`
- Line 242: `def _group_by(cls, value: list[str]) -> list[str]:`
- Line 247: `def _sort_by(cls, value: str | None) -> str | None:`
- Line 254: `def _requested_fields(cls, value: list[str]) -> list[str]:`
- Line 262: `class ModifyPreviousAction(BaseModel):`
- Line 281: `def _has_an_edit(self) -> "ModifyPreviousAction":`
- Line 302: `def _requested_fields(cls, value: list[str] | None) -> list[str] | None:`
- Line 312: `class VerifyPreviousAction(BaseModel):`
- Line 321: `class ClarifyAction(BaseModel):`
- Line 328: `class ConversationAction(BaseModel):`
- Line 349: `class ReferenceAction(BaseModel):`
- Line 371: `class ActiveQuery(BaseModel):`
- Line 408: `class TurnPlan(BaseModel):`
- Line 424: `def _consistent_actions(self) -> "TurnPlan":`
- Line 429: `def query_actions(self) -> list[QueryAction]:`
- Line 432: `def modify_actions(self) -> list[ModifyPreviousAction]:`
- Line 435: `def clarify_actions(self) -> list[ClarifyAction]:`
- Line 438: `def respond_actions(self) -> list[ConversationAction]:`
- Line 441: `def reference_actions(self) -> list[ReferenceAction]:`
- Line 444: `def verify_actions(self) -> list[VerifyPreviousAction]:`
- Line 447: `def public_dict(self) -> dict[str, Any]:`

## `backend/app\planning\turn_validator.py`

- Line 43: `def validate_turn_plan(`
- Line 142: `def _drop_orphan_followups(`
- Line 189: `def _mixes_general_conversation_with_research(turn: TurnPlan) -> bool:`
- Line 201: `def _trusted_conversation(turn: TurnPlan) -> bool:`
- Line 207: `def action_datasets(action: QueryAction | ModifyPreviousAction, catalog: FieldCatalog) -> list[int]:`
- Line 216: `def _clarification_turn(turn: TurnPlan, question: str, *, unresolved: list[str]) -> TurnPlan:`
- Line 228: `def _validate_query_action(`
- Line 277: `def _validate_filter(spec: FilterSpec, datasets: list[int], catalog: FieldCatalog) -> None:`
- Line 294: `def _validate_aggregate(action: QueryAction, catalog: FieldCatalog) -> None:`
- Line 336: `def _require_field_on_every_dataset(name: str, datasets: list[int], catalog: FieldCatalog) -> None:`
- Line 345: `def _validate_evidence_request(turn: TurnPlan, catalog: FieldCatalog) -> None:`
- Line 361: `def _reject_structural_injection(turn: TurnPlan) -> None:`

## `backend/app\planning\user_name.py`

- Line 77: `def extract_introduced_name(text: str) -> str | None:`
- Line 88: `def is_user_name_question(text: str) -> bool:`
- Line 92: `def is_assistant_identity_question(text: str) -> bool:`
- Line 96: `def is_conversational_correction(text: str) -> bool:`
- Line 118: `def is_speak_request(text: str) -> bool:`
- Line 122: `def is_bare_affirmation(text: str) -> bool:`
- Line 126: `def is_confusion(text: str) -> bool:`
- Line 130: `def is_explicit_row_reference(text: str) -> bool:`
- Line 142: `def extract_followup_name(text: str) -> str | None:`
- Line 152: `def is_named_record_followup(text: str) -> bool:`
- Line 156: `def looks_like_research(text: str) -> bool:`

## `backend/app\planning\value_expansion.py`

- Line 35: `def expand_plan_values(plan: QueryPlan, catalog: FieldCatalog) -> QueryPlan:`
- Line 50: `def _rewrite(`
- Line 103: `def _unknown_terms(spec: FieldSpec) -> list[str]:`
- Line 114: `def _field_owning_value(`
- Line 138: `def _owns(spec: FieldSpec, needles: set[str]) -> bool:`
- Line 150: `def _family_terms(families: dict, value: object) -> list[str] | None:`
- Line 168: `def _lookup(families: dict, value: str) -> list[str] | None:`
- Line 181: `def _spec(name: str, file_ids: tuple[int, ...], catalog: FieldCatalog) -> FieldSpec | None:`

## `backend/app\realtime\agent.py`

- Line 31: `class ResearchVoiceAgent:`
- Line 34: `def __init__(`
- Line 50: `def _new_turn_cancel(self) -> CancellationToken:`
- Line 58: `async def handle_final_transcript(`
- Line 90: `async def speak(phrase: str) -> None:`
- Line 131: `async def handle_voice_preference(`
- Line 185: `async def publish_transcript(self, text: str, *, final: bool) -> None:`
- Line 196: `async def interrupt(self, reason: str = "barge-in") -> None:`
- Line 203: `def mark_speaking(self) -> None:`
- Line 207: `def mark_listening(self) -> None:`
- Line 214: `def mark_interrupted(self) -> None:`
- Line 218: `async def _emit(self, payload: dict[str, Any]) -> None:`
- Line 224: `def session_options() -> dict[str, Any]:`
- Line 241: `async def build_turn_service() -> AssistantTurnService:`
- Line 269: `def message_transcript(new_message: Any) -> str:`
- Line 279: `async def _agent_entry(ctx: Any) -> None:`
- Line 296: `async def notify(payload: dict[str, Any]) -> None:`
- Line 317: `async def switch_voice(preference: VoicePreference) -> None:`
- Line 344: `class CoreAgent(Agent):`
- Line 345: `def __init__(self) -> None:`
- Line 353: `async def on_user_turn_completed(self, turn_ctx, new_message) -> None:`
- Line 356: `async def speak_phrase(phrase: str) -> None:`
- Line 389: `def _on_user_state(ev) -> None:`
- Line 395: `def _on_transcript(ev) -> None:`
- Line 401: `def _on_data(*args: Any) -> None:`
- Line 421: `async def apply_voice_preference() -> None:`
- Line 422: `async def speak_phrase(phrase: str) -> None:`
- Line 444: `def run_livekit_worker() -> None:`

## `backend/app\realtime\states.py`

- Line 6: `class VoiceState(StrEnum):`
- Line 59: `class VoiceStateMachine:`
- Line 60: `def __init__(self) -> None:`
- Line 63: `def transition(self, target: VoiceState) -> VoiceState:`

## `backend/app\realtime\turn_hook.py`

- Line 15: `class TurnHookResult:`
- Line 22: `class AssistantTurnHook:`
- Line 28: `async def on_user_turn_completed(`

## `backend/app\retrieval\context_builder.py`

- Line 12: `def estimate_tokens(text: str) -> int:`
- Line 16: `def build_evidence_packet(`
- Line 61: `def _compact_fields(`

## `backend/app\retrieval\deduplicator.py`

- Line 7: `def dedupe_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:`

## `backend/app\retrieval\entity_resolver.py`

- Line 14: `class ReferenceAlias:`
- Line 21: `class ResolvedEntity:`
- Line 39: `def resolve_entity(`

## `backend/app\retrieval\exact_search.py`

- Line 9: `def score_exact(record: dict[str, Any], query: str) -> RetrievalHit | None:`
- Line 27: `def _hit(record: dict[str, Any], method: str, score: float, field_name: str) -> RetrievalHit:`

## `backend/app\retrieval\fulltext_search.py`

- Line 9: `def score_fts(record: dict[str, Any], query: str) -> RetrievalHit | None:`
- Line 44: `def _snippet(text: str, token: str, radius: int = 48) -> str:`

## `backend/app\retrieval\fuzzy_search.py`

- Line 14: `def score_fuzzy(record: dict[str, Any], query: str) -> RetrievalHit | None:`

## `backend/app\retrieval\hybrid.py`

- Line 17: `class CandidateSource(Protocol):`
- Line 18: `async def retrieve_candidates(`
- Line 29: `class HybridRetrievalResult:`
- Line 36: `class HybridRetriever:`
- Line 39: `def __init__(self, source: CandidateSource) -> None:`
- Line 42: `async def retrieve(`
- Line 74: `async def run(method: str) -> list[RetrievalHit]:`
- Line 98: `async def _branch(`
- Line 116: `def _unique_exact(hits: list[RetrievalHit]) -> bool:`

## `backend/app\retrieval\normalizer.py`

- Line 11: `def normalize_search_text(value: str | None) -> str:`
- Line 20: `def tokens(value: str | None) -> list[str]:`

## `backend/app\retrieval\ranker.py`

- Line 14: `def rank_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:`
- Line 15: `def key(hit: RetrievalHit) -> tuple[float, float, str]:`

## `backend/app\retrieval\types.py`

- Line 10: `class RetrievalHit(BaseModel):`
- Line 25: `def source_id(self) -> str:`
- Line 28: `def identity(self) -> tuple[int, int]:`
- Line 32: `class EvidenceItem(BaseModel):`
- Line 43: `class EvidenceBranch(BaseModel):`
- Line 54: `class EvidencePacket(BaseModel):`

## `backend/app\retrieval\vector_search.py`

- Line 6: `def score_vector(*_args: object, **_kwargs: object) -> list[RetrievalHit]:`

## `backend/app\security\access_scope.py`

- Line 6: `class AccessScope(BaseModel):`
- Line 24: `def _tuple_ids(cls, value: Any) -> tuple[int, ...]:`
- Line 29: `def allows_file(self, file_id: int, *, private: bool = False) -> bool:`
- Line 36: `def narrow(self, requested_file_ids: list[int] | tuple[int, ...] | None) -> "AccessScope":`
- Line 49: `def fingerprint(self) -> str:`

## `backend/app\security\auth_adapter.py`

- Line 8: `class AuthAdapter(ABC):`
- Line 18: `async def authenticate_password(self, username: str, password: str) -> AccessScope:`
- Line 22: `def issue_token(self, scope: AccessScope) -> str:`
- Line 26: `def resolve_scope(self, credentials: str) -> AccessScope:`
- Line 30: `def build_auth_adapter(settings: Settings | None = None) -> AuthAdapter:`
- Line 43: `def get_auth_adapter() -> AuthAdapter:`

## `backend/app\security\deps.py`

- Line 11: `def get_access_scope(`
- Line 29: `def _validate_cookie_origin(request: Request) -> None:`

## `backend/app\security\livekit_token.py`

- Line 18: `def principal_room_prefix(scope: AccessScope) -> str:`
- Line 23: `def assigned_room_name(`
- Line 39: `def mint_livekit_token(`
- Line 79: `def decode_livekit_token(token: str) -> dict:`
- Line 89: `def metadata_dict(metadata: str | dict | None) -> dict:`
- Line 99: `def scope_from_metadata(metadata: str | dict | None) -> AccessScope:`
- Line 109: `def conversation_id_from_metadata(metadata: str | dict | None) -> str | None:`
- Line 115: `def selected_file_id_from_metadata(metadata: str | dict | None) -> int | None:`

## `backend/app\security\rate_limit.py`

- Line 12: `class RateLimitMiddleware:`
- Line 19: `def __init__(self, app, *, settings: Settings) -> None:`
- Line 32: `async def __call__(self, scope, receive, send) -> None:`
- Line 65: `def _client_address(scope, *, trust_proxy: bool) -> str:`

## `backend/app\security\standalone_jwt.py`

- Line 10: `class AuthError(Exception):`
- Line 14: `class StandaloneJwtAuthAdapter(AuthAdapter):`
- Line 17: `def __init__(self, settings: Settings) -> None:`
- Line 20: `async def authenticate_password(self, username: str, password: str) -> AccessScope:`
- Line 34: `def issue_token(self, scope: AccessScope) -> str:`
- Line 48: `def resolve_scope(self, credentials: str) -> AccessScope:`

## `backend/app\security\website_adapter.py`

- Line 9: `class WebsiteAuthAdapter(AuthAdapter):`
- Line 17: `def __init__(self, settings: Settings) -> None:`
- Line 21: `async def authenticate_password(self, username: str, password: str) -> AccessScope:`
- Line 24: `def issue_token(self, scope: AccessScope) -> str:`
- Line 27: `def resolve_scope(self, credentials: str) -> AccessScope:`

## `backend/app\stt\base.py`

- Line 9: `class TranscriptEvent(BaseModel):`
- Line 18: `class STTProvider(Protocol):`
- Line 21: `async def transcribe_stream(`
- Line 28: `async def reset_session(self) -> None: ...`
- Line 30: `async def finalize_turn(self) -> TranscriptEvent | None: ...`

## `backend/app\stt\livekit_adapter.py`

- Line 9: `class LiveKitWhisperAdapter:`
- Line 16: `def __init__(self, provider: STTProvider) -> None:`
- Line 19: `def to_livekit_payload(self, event: TranscriptEvent) -> dict[str, Any]:`
- Line 33: `async def stream_events(self, audio: AsyncIterator[bytes], *, sample_rate: int = 16000) -> AsyncIterator[dict[str, Any]]:`
- Line 38: `class LiveKitStreamPump:`
- Line 41: `def __init__(self, provider: STTProvider) -> None:`
- Line 45: `async def push(self, pcm: bytes) -> list[dict[str, Any]]:`
- Line 52: `async def flush(self) -> list[dict[str, Any]]:`
- Line 59: `def create_livekit_stt(provider: STTProvider):`
- Line 76: `def _speech_event(payload: dict[str, Any]):`
- Line 101: `class WhisperCppLiveKitSTT(stt.STT):`
- Line 102: `def __init__(self) -> None:`
- Line 108: `def model(self) -> str:`
- Line 112: `def provider(self) -> str:`
- Line 115: `async def _recognize_impl(self, buffer, *, language=NOT_GIVEN, conn_options=DEFAULT_API_CONNECT_OPTIONS):`

## `backend/app\stt\whisper_cpp.py`

- Line 11: `class WhisperCppSTTProvider:`
- Line 14: `def __init__(self, base_url: str | None = None, client: httpx.AsyncClient | None = None) -> None:`
- Line 21: `async def _http(self) -> httpx.AsyncClient:`
- Line 26: `async def _ensure_session(self) -> str:`
- Line 35: `async def push_audio(self, chunk: bytes) -> list[TranscriptEvent]:`
- Line 42: `async def transcribe_stream(`
- Line 58: `async def reset_session(self) -> None:`
- Line 64: `async def finalize_turn(self) -> TranscriptEvent | None:`
- Line 72: `async def aclose(self) -> None:`

## `backend/app\tts\base.py`

- Line 7: `class TTSProvider(Protocol):`
- Line 8: `async def connect_session(self) -> None: ...`
- Line 10: `async def synthesize_stream(`
- Line 14: `async def cancel_generation(self) -> None: ...`
- Line 16: `async def close_session(self) -> None: ...`
- Line 19: `def ensure_no_tts_in_text_mode(mode: str) -> None:`

## `backend/app\tts\expressive.py`

- Line 57: `def strip_voice_tags(text: str) -> str:`
- Line 65: `def add_contextual_voice_tags(text: str) -> str:`

## `backend/app\tts\factory.py`

- Line 11: `def get_tts_provider(name: str | None = None) -> TTSProvider:`

## `backend/app\tts\fake.py`

- Line 6: `class FakeTTSProvider:`
- Line 9: `def __init__(self) -> None:`
- Line 16: `async def connect_session(self) -> None:`
- Line 20: `async def synthesize_stream(`
- Line 32: `async def cancel_generation(self) -> None:`
- Line 35: `async def close_session(self) -> None:`

## `backend/app\tts\humanize.py`

- Line 28: `def humanize_for_speech(text: str, *, max_chars: int | None = MAX_SPOKEN_CHARS) -> str:`
- Line 44: `def _trim_to_sentences(text: str, max_chars: int) -> str:`

## `backend/app\tts\kokoro.py`

- Line 11: `class KokoroTTSProvider:`
- Line 14: `def __init__(`
- Line 32: `async def connect_session(self) -> None:`
- Line 40: `def voice(self) -> str:`
- Line 43: `async def set_voice(self, voice: str) -> None:`
- Line 48: `async def synthesize_stream(`
- Line 59: `async def _synthesize_inner(`
- Line 87: `async def cancel_generation(self) -> None:`
- Line 91: `async def close_session(self) -> None:`
- Line 97: `async def _http(self) -> httpx.AsyncClient:`

## `backend/app\tts\livekit_adapter.py`

- Line 12: `def prepare_speech_text(text: str, *, expressive: bool = False) -> str:`
- Line 20: `def create_livekit_tts(provider: TTSProvider):`
- Line 25: `class ProviderChunkedStream(tts.ChunkedStream):`
- Line 26: `async def _run(self, output_emitter) -> None:`
- Line 41: `class ProviderLiveKitTTS(tts.TTS):`
- Line 42: `def __init__(self) -> None:`
- Line 50: `def model(self) -> str:`
- Line 54: `def provider(self) -> str:`
- Line 57: `def synthesize(`
- Line 62: `def prewarm(self) -> None:`

## `backend/app\tts\phrases.py`

- Line 12: `class SpokenPhrase:`
- Line 18: `class PhraseBuffer:`
- Line 21: `def __init__(self, *, min_chars: int = 12) -> None:`
- Line 27: `def start(self, generation_id: str) -> None:`
- Line 32: `def push(self, delta: str) -> list[SpokenPhrase]:`
- Line 38: `def flush(self) -> list[SpokenPhrase]:`
- Line 41: `def _drain(self, *, flush: bool) -> list[SpokenPhrase]:`
- Line 59: `def _next(self, text: str) -> SpokenPhrase:`
- Line 64: `class PhraseQueue:`
- Line 67: `def __init__(self, max_phrases: int = 8) -> None:`
- Line 74: `def start_generation(self) -> str:`
- Line 80: `def put(self, phrase: SpokenPhrase) -> bool:`
- Line 89: `def pop(self) -> SpokenPhrase | None:`
- Line 97: `def flush(self) -> list[SpokenPhrase]:`
- Line 103: `def __len__(self) -> int:`
- Line 106: `def pending_texts(self) -> list[str]:`
- Line 110: `def split_phrases(text: str) -> list[str]:`
- Line 118: `def _sentence_end(text: str) -> int:`

## `backend/app\tts\session.py`

- Line 13: `class SpeechSession:`
- Line 16: `def __init__(`
- Line 35: `async def connect(self) -> None:`
- Line 39: `def begin_turn(self) -> str:`
- Line 46: `async def enqueue_text(self, text: str) -> list[SpokenPhrase]:`
- Line 59: `async def feed_delta(self, delta: str) -> list[SpokenPhrase]:`
- Line 71: `async def finish_input(self) -> list[SpokenPhrase]:`
- Line 83: `async def play(self) -> AsyncIterator[bytes]:`
- Line 101: `async def speak(self, text: str) -> AsyncIterator[bytes]:`
- Line 107: `async def interrupt(self, reason: str = "barge-in") -> None:`
- Line 113: `async def close(self) -> None:`
- Line 118: `class BargeInController:`
- Line 121: `def __init__(self, speech: SpeechSession, cancellation: CancellationToken) -> None:`
- Line 127: `async def interrupt(self, reason: str = "barge-in") -> None:`

## `backend/app\tts\silent.py`

- Line 6: `class SilentTTSProvider:`
- Line 15: `def __init__(self, sample_rate: int = 24000) -> None:`
- Line 20: `async def connect_session(self) -> None:`
- Line 24: `async def synthesize_stream(`
- Line 39: `async def cancel_generation(self) -> None:`
- Line 42: `async def close_session(self) -> None:`

## `backend/app\tts\voice_control.py`

- Line 20: `def requested_voice_preference(text: str) -> VoicePreference | None:`

## `backend/app\tts\xai_tts.py`

- Line 18: `class XAITTSProvider:`
- Line 23: `def __init__(`
- Line 53: `def voice(self) -> str:`
- Line 56: `async def set_voice(self, voice: str) -> None:`
- Line 64: `async def connect_session(self) -> None:`
- Line 80: `async def synthesize_stream(`
- Line 94: `async def _synthesize_inner(self, text: str) -> AsyncIterator[bytes]:`
- Line 117: `async def cancel_generation(self) -> None:`
- Line 129: `async def close_session(self) -> None:`
- Line 141: `async def _send(self, payload: dict[str, Any]) -> None:`
- Line 147: `async def _recv(self) -> str | bytes | None:`
- Line 155: `async def _open_websockets(url: str, headers: dict[str, str], timeout: float):`

## `backend/app\value_normalization.py`

- Line 7: `def json_object(value: Any) -> dict[str, Any]:`
- Line 20: `def semantic_scalar(value: Any) -> Any:`

## `frontend/app\layout.tsx`

- Line 9: `export default function RootLayout({ children }: { children: React.ReactNode }) {`

## `frontend/app\page.tsx`

- Line 52: `export default function HomePage() {`
- Line 141: `async function restoreSession() {`
- Line 153: `function expireSession(message = "Your session expired. Sign in again.") {`
- Line 158: `async function refreshConversations() {`
- Line 168: `async function onLogin(event: FormEvent) {`
- Line 179: `function signOut() {`
- Line 196: `function startNewConversation() {`
- Line 209: `async function openConversation(id: string) {`
- Line 228: `async function restoreConversation(id: string) {`
- Line 243: `async function toggleVoice() {`
- Line 255: `async function connectVoiceSession(): Promise<VoiceSession | null> {`
- Line 304: `function applyVoiceMessage(message: VoiceMessage) {`
- Line 390: `async function toggleMute() {`
- Line 396: `async function interruptVoice() {`
- Line 401: `async function sendQuestion(event?: FormEvent) {`
- Line 516: `function onQuestionChange(event: ChangeEvent<HTMLTextAreaElement>) {`
- Line 522: `function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {`
- Line 534: `function switchDataset(fileId: number) {`
- Line 549: `function useSuggestion(text: string) {`
- Line 899: `function ChatMessage({`
- Line 977: `function StructuredListResult({ result }: { result: QueryListResult }) {`
- Line 1016: `function displayResultValue(value: unknown): string {`
- Line 1023: `function starterPrompts(datasetLabel?: string | null) {`
- Line 1049: `function defaultDatasetId(datasets: Dataset[]): number | null {`
- Line 1053: `function shortDatasetLabel(dataset: Dataset): string {`
- Line 1060: `function compactDatasetLabel(dataset: Dataset): string {`
- Line 1066: `function citationLabel(fields: Record<string, unknown> | undefined, index: number) {`
- Line 1072: `function citationHeading(citation: { source_id: string; fields?: Record<string, unknown> }) {`
- Line 1076: `function welcomeLine(): ChatLine {`
- Line 1084: `function turnToLine(turn: ConversationTurn): ChatLine {`
- Line 1095: `function upsertLine(lines: ChatLine[], next: ChatLine): ChatLine[] {`
- Line 1101: `function updateLineProgress(lines: ChatLine[], id: string, progress: string): ChatLine[] {`
- Line 1107: `function initials(value: string) {`
- Line 1112: `function NiaMark({ compact = false }: { compact?: boolean }) {`
- Line 1120: `function NiaGlyph() {`
- Line 1128: `function MenuIcon() { return <Icon path="M4 7h16M4 12h16M4 17h16" />; }`
- Line 1129: `function CloseIcon() { return <Icon path="M6 6l12 12M18 6L6 18" />; }`
- Line 1130: `function ComposeIcon() { return <Icon path="M12 5v14M5 12h14" />; }`
- Line 1131: `function ChevronIcon() { return <Icon path="M9 10l3 3 3-3" className="h-4 w-4" />; }`
- Line 1132: `function VoiceIcon() { return <Icon path="M12 15a3 3 0 003-3V7a3 3 0 10-6 0v5a3 3 0 003 3zm5-3a5 5 0 01-10 0M12 17v3M9 20h6" />; }`
- Line 1133: `function ArrowUpIcon() { return <Icon path="M12 19V5M6.5 10.5L12 5l5.5 5.5" className="h-4 w-4" />; }`
- Line 1134: `function ArrowDiagonalIcon() { return <Icon path="M8 16L16 8M10 8h6v6" className="h-4 w-4" />; }`
- Line 1135: `function SourceIcon() { return <Icon path="M7 7h10v10H7zM10 10h8v8h-8z" className="h-3.5 w-3.5" />; }`
- Line 1136: `function PanelIcon({ collapsed = false }: { collapsed?: boolean }) {`
- Line 1139: `function Icon({ path, className = "h-5 w-5" }: { path: string; className?: string }) {`
- Line 1147: `function TypingIndicator() {`
- Line 1157: `function LoadingDots() {`

## `frontend/components\voice-bar.tsx`

- Line 13: `export function VoiceBar({ state, muted, level, error, onMute, onInterrupt, onDisconnect }: VoiceBarProps) {`

## `frontend/lib\api.ts`

- Line 41: `export class AuthExpiredError extends Error {`
- Line 48: `async function authorizedFetch(path: string, init: RequestInit = {}): Promise<Response> {`
- Line 59: `export async function login(username: string, password: string): Promise<Session> {`
- Line 72: `export async function fetchSession(): Promise<Session | null> {`
- Line 83: `export async function logout(): Promise<void> {`
- Line 90: `export async function fetchDatasets(): Promise<Dataset[]> {`
- Line 109: `export async function fetchLivekitToken(`
- Line 127: `export async function health(): Promise<{ status: string }> {`
- Line 195: `export async function fetchConversations(): Promise<ConversationSummary[]> {`
- Line 212: `export async function fetchConversation(`
- Line 230: `export async function streamQuery(`
- Line 281: `function parseSseBlock(block: string): QueryEvent | null {`

## `frontend/lib\voice.ts`

- Line 54: `export async function connectVoice(details: LivekitToken, handlers: VoiceHandlers): Promise<VoiceSession> {`
- Line 70: `const setState = (state: VoiceUiState) => handlers.onState(state);`
- Line 72: `const attachAudio = (track: { kind?: string; attach: () => HTMLMediaElement }) => {`
- Line 83: `const detachAudio = () => {`
- Line 205: `export function requestedVoicePreference(text: string): VoicePreference | null {`
- Line 217: `async function waitForVoiceInput(subscription: Promise<void>, timeoutMs: number): Promise<void> {`
- Line 234: `function startLevelMeter(room: { localParticipant: { audioTrackPublications?: Map<unknown, { audioTrack?: { mediaStream?: MediaStream } }> } }, onLevel?: (level: number) => void) {`
- Line 242: `const tick = () => {`

## `services/whisper/src/whisper_service\__main__.py`

- Line 8: `def main() -> None:`

## `services/whisper/src/whisper_service\engine.py`

- Line 26: `class TranscriptionEngine(Protocol):`
- Line 30: `async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult: ...`
- Line 33: `class ScriptedEngine:`
- Line 38: `def __init__(self, partials: list[str] | None = None, final: str | None = None, model: str = "base.en") -> None:`
- Line 44: `async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:`
- Line 53: `def reset(self) -> None:`
- Line 57: `class FasterWhisperEngine:`
- Line 67: `def __init__(`
- Line 86: `async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:`
- Line 91: `def _run() -> str:`
- Line 124: `class CliEngine:`
- Line 129: `def __init__(self, binary: str, model_path: str) -> None:`
- Line 134: `async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:`
- Line 163: `def build_engine() -> TranscriptionEngine:`
- Line 187: `def _optional_env(name: str, default: str) -> str | None:`
- Line 194: `def _int_env(name: str, default: int) -> int:`
- Line 201: `def _bool_env(name: str, default: bool) -> bool:`
- Line 208: `def _rms(pcm: bytes) -> int:`
- Line 217: `def _duration_ms(pcm: bytes, sample_rate: int) -> int:`
- Line 223: `def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:`

## `services/whisper/src/whisper_service\protocol.py`

- Line 8: `class TranscriptEvent(BaseModel):`
- Line 17: `class TranscriptResult(BaseModel):`
- Line 25: `class ControlMessage(BaseModel):`

## `services/whisper/src/whisper_service\server.py`

- Line 20: `def _default_max_sessions() -> int:`
- Line 31: `def _default_session_ttl_seconds() -> float:`
- Line 42: `class WhisperService:`
- Line 43: `def __init__(`
- Line 58: `async def get_session(self, session_id: str | None = None) -> WhisperSession:`
- Line 71: `async def touch(self, session_id: str) -> None:`
- Line 76: `async def session_count(self) -> int:`
- Line 81: `async def drop(self, session_id: str) -> None:`
- Line 86: `def _drop_expired_locked(self) -> None:`
- Line 94: `def create_app(service: WhisperService | None = None) -> Starlette:`
- Line 97: `async def health(_request: Request) -> JSONResponse:`
- Line 107: `async def transcribe(request: Request) -> JSONResponse:`
- Line 113: `async def open_session(_request: Request) -> JSONResponse:`
- Line 117: `async def push_audio(request: Request) -> JSONResponse:`
- Line 122: `async def finalize(request: Request) -> JSONResponse:`
- Line 127: `async def reset(request: Request) -> JSONResponse:`
- Line 132: `async def close_session(request: Request) -> JSONResponse:`
- Line 137: `async def stream(websocket: WebSocket) -> None:`
- Line 180: `async def _require_session(service: WhisperService, session_id: str) -> WhisperSession:`

## `services/whisper/src/whisper_service\session.py`

- Line 9: `class WhisperSession:`
- Line 12: `def __init__(`
- Line 31: `async def push_pcm(self, pcm: bytes) -> list[TranscriptEvent]:`
- Line 58: `async def finalize_turn(self) -> TranscriptEvent:`
- Line 73: `def reset_session(self) -> None:`
- Line 83: `def _ms_to_bytes(ms: int, sample_rate: int) -> int:`
- Line 87: `def _bytes_to_ms(length: int, sample_rate: int) -> int:`

## `voice_cli.py`

- Line 66: `def _configuration() -> dict[str, str]:`
- Line 81: `def _first_config(config: dict[str, str], *names: str, default: str = "") -> str:`
- Line 88: `class AssistantClient:`
- Line 91: `def __init__(`
- Line 107: `def login(self) -> dict:`
- Line 125: `def synthesize(self, text: str, preference: str):`
- Line 143: `def ask(self, question: str, *, mode: str = "text", trace: bool = True) -> dict:`
- Line 194: `class WhisperClient:`
- Line 197: `def __init__(self, base_url: str) -> None:`
- Line 200: `def health(self) -> dict:`
- Line 205: `def transcribe(self, pcm: bytes, sample_rate: int = SAMPLE_RATE) -> str:`
- Line 220: `def _rms(block: bytes) -> float:`
- Line 231: `class Microphone:`
- Line 232: `def __init__(self) -> None:`
- Line 249: `def read_block(self) -> bytes:`
- Line 253: `def close(self) -> None:`
- Line 260: `def calibrate(self, seconds: float = 1.0) -> tuple[float, float]:`
- Line 270: `def listen_utterance(`
- Line 310: `class Speaker:`
- Line 321: `def __init__(`
- Line 367: `def available(self) -> bool:`
- Line 370: `def describe(self) -> str:`
- Line 382: `def set_preference(self, preference: str) -> None:`
- Line 389: `def _select_pyttsx3_voice(self) -> None:`
- Line 414: `def say(self, text: str) -> None:`
- Line 440: `def _speak_sapi5(self, text: str) -> None:`
- Line 458: `def _ensure_sapi5_process(self) -> subprocess.Popen:`
- Line 496: `def close(self) -> None:`
- Line 506: `class BackendSpeaker:`
- Line 509: `def __init__(`
- Line 530: `def available(self) -> bool:`
- Line 533: `def describe(self) -> str:`
- Line 541: `def set_preference(self, preference: str) -> None:`
- Line 544: `def say(self, text: str) -> None:`
- Line 572: `def close(self) -> None:`
- Line 579: `def _short_json(value: Any, *, max_chars: int = 3000) -> str:`
- Line 589: `def _trace_value(data: dict, *names: str) -> Any:`
- Line 596: `def print_layer_trace(data: dict, *, raw_response: bool = False) -> None:`
- Line 688: `def print_answer(data: dict, *, trace: bool = True, raw_response: bool = False) -> None:`
- Line 708: `def handle_voice_control(text: str, speaker) -> bool:`
- Line 724: `def run_wav(args, assistant: AssistantClient, whisper: WhisperClient, speaker: Speaker) -> None:`
- Line 749: `def run_text(args, assistant: AssistantClient, speaker: Speaker) -> None:`
- Line 767: `def run_voice(args, assistant: AssistantClient, whisper: WhisperClient, speaker: Speaker) -> None:`
- Line 778: `def _handle_utterance(pcm, assistant, whisper, speaker, *, trace: bool = True, raw_response: bool = False) -> None:`
- Line 815: `def _loop_vad(args, mic, assistant, whisper, speaker) -> None:`
- Line 833: `def _loop_push_to_talk(args, mic, assistant, whisper, speaker) -> None:`
- Line 843: `def _wait_enter() -> None:`
- Line 859: `def main() -> None:`

## SQL migration object declarations

Inventory size: **171 SQL object/grant declarations across 27 migration files**. Repeated function/view names show later replacement migrations that evolve the same database API.

### `backend/app/db/migrations\003_app_stubs.sql`

- Line 4: `CREATE TABLE IF NOT EXISTS public.file (`
- Line 16: `CREATE TABLE IF NOT EXISTS public.data_config (`
- Line 24: `CREATE TABLE IF NOT EXISTS public.file_data (`
- Line 33: `CREATE TABLE IF NOT EXISTS public.file_data_normalized (`
- Line 48: `CREATE TABLE IF NOT EXISTS public.communities (`
- Line 54: `CREATE TABLE IF NOT EXISTS public.day_schools (`
- Line 60: `CREATE TABLE IF NOT EXISTS public.indian_hospitals (`
- Line 66: `CREATE TABLE IF NOT EXISTS public.provinces (`
- Line 74: `CREATE TABLE IF NOT EXISTS public.users (`
- Line 79: `CREATE TABLE IF NOT EXISTS public.roles (`
- Line 83: `CREATE TABLE IF NOT EXISTS public.otps (`
- Line 87: `CREATE TABLE IF NOT EXISTS public.logs (`
- Line 91: `CREATE TABLE IF NOT EXISTS public.support_requests (`
- Line 95: `CREATE TABLE IF NOT EXISTS public.file_access (`
- Line 100: `CREATE TABLE IF NOT EXISTS public.file_edit_request (`
- Line 104: `CREATE TABLE IF NOT EXISTS public.form_submissions (`

### `backend/app/db/migrations\004_assistant_tables.sql`

- Line 1: `CREATE SCHEMA IF NOT EXISTS assistant;`
- Line 2: `CREATE SCHEMA IF NOT EXISTS assistant_api;`
- Line 7: `CREATE TABLE IF NOT EXISTS assistant.dataset_policy (`
- Line 20: `CREATE TABLE IF NOT EXISTS assistant.field_registry (`
- Line 40: `CREATE TABLE IF NOT EXISTS assistant.access_grants (`
- Line 52: `CREATE TABLE IF NOT EXISTS assistant.entity_aliases (`
- Line 68: `CREATE TABLE IF NOT EXISTS assistant.conversations (`
- Line 77: `CREATE TABLE IF NOT EXISTS assistant.messages (`
- Line 89: `CREATE TABLE IF NOT EXISTS assistant.conversation_state (`
- Line 101: `CREATE TABLE IF NOT EXISTS assistant.query_frames (`
- Line 114: `CREATE TABLE IF NOT EXISTS assistant.result_sets (`
- Line 126: `CREATE TABLE IF NOT EXISTS assistant.query_plans (`
- Line 137: `CREATE TABLE IF NOT EXISTS assistant.query_runs (`
- Line 156: `CREATE TABLE IF NOT EXISTS assistant.query_step_runs (`
- Line 176: `CREATE TABLE IF NOT EXISTS assistant.citations (`
- Line 190: `CREATE TABLE IF NOT EXISTS assistant.voice_sessions (`
- Line 208: `CREATE TABLE IF NOT EXISTS assistant.feedback (`
- Line 219: `CREATE TABLE IF NOT EXISTS assistant.audit_events (`
- Line 231: `CREATE TABLE IF NOT EXISTS assistant.background_jobs (`
- Line 250: `CREATE TABLE IF NOT EXISTS assistant.attachment_sources (`
- Line 262: `CREATE TABLE IF NOT EXISTS assistant.attachment_chunks (`
- Line 273: `CREATE TABLE IF NOT EXISTS assistant.schema_migrations (`
- Line 278: `CREATE INDEX IF NOT EXISTS idx_field_registry_file ON assistant.field_registry (file_id);`
- Line 279: `CREATE INDEX IF NOT EXISTS idx_access_grants_principal ON assistant.access_grants (principal_id);`
- Line 280: `CREATE INDEX IF NOT EXISTS idx_conversations_principal ON assistant.conversations (principal_id, updated_at DESC);`
- Line 281: `CREATE INDEX IF NOT EXISTS idx_messages_conversation ON assistant.messages (conversation_id, created_at);`
- Line 282: `CREATE INDEX IF NOT EXISTS idx_query_frames_last_used ON assistant.query_frames (conversation_id, last_used_at DESC);`
- Line 283: `CREATE INDEX IF NOT EXISTS idx_result_sets_expiry ON assistant.result_sets (expires_at);`
- Line 284: `CREATE INDEX IF NOT EXISTS idx_query_runs_started ON assistant.query_runs (started_at DESC);`
- Line 285: `CREATE INDEX IF NOT EXISTS idx_audit_created ON assistant.audit_events (created_at DESC);`
- Line 286: `CREATE INDEX IF NOT EXISTS idx_jobs_state ON assistant.background_jobs (state, priority, created_at);`

### `backend/app/db/migrations\005_assistant_api.sql`

- Line 3: `CREATE OR REPLACE VIEW assistant_api.v_current_records AS`
- Line 25: `CREATE OR REPLACE VIEW assistant_api.v_current_raw_records AS`
- Line 39: `CREATE OR REPLACE VIEW assistant_api.v_datasets AS`
- Line 53: `CREATE OR REPLACE VIEW assistant_api.v_dataset_fields AS`
- Line 71: `CREATE OR REPLACE VIEW assistant_api.v_reference_entities AS`
- Line 80: `CREATE OR REPLACE FUNCTION assistant_api._authorized_file_ids(`
- Line 113: `CREATE OR REPLACE FUNCTION assistant_api.list_datasets(`
- Line 149: `CREATE OR REPLACE FUNCTION assistant_api.get_dataset_fields(`
- Line 169: `CREATE OR REPLACE FUNCTION assistant_api.search_current_records(`
- Line 215: `CREATE OR REPLACE FUNCTION assistant_api.get_current_records_by_ids(`
- Line 252: `CREATE OR REPLACE FUNCTION assistant_api.get_raw_fields_by_ids(`
- Line 285: `CREATE OR REPLACE FUNCTION assistant_api.resolve_reference_entity(`

### `backend/app/db/migrations\006_grants.sql`

- Line 25: `ALTER FUNCTION assistant_api._authorized_file_ids(TEXT, INTEGER[], BOOLEAN) OWNER TO assistant_gateway_owner;`
- Line 26: `ALTER FUNCTION assistant_api.list_datasets(TEXT, INTEGER[], BOOLEAN) OWNER TO assistant_gateway_owner;`
- Line 27: `ALTER FUNCTION assistant_api.get_dataset_fields(TEXT, INTEGER, INTEGER[], BOOLEAN) OWNER TO assistant_gateway_owner;`
- Line 28: `ALTER FUNCTION assistant_api.search_current_records(TEXT, INTEGER[], BOOLEAN, TEXT, INTEGER) OWNER TO assistant_gateway_owner;`
- Line 29: `ALTER FUNCTION assistant_api.get_current_records_by_ids(TEXT, INTEGER[], BOOLEAN, BIGINT[]) OWNER TO assistant_gateway_owner;`
- Line 30: `ALTER FUNCTION assistant_api.get_raw_fields_by_ids(TEXT, INTEGER[], BOOLEAN, BIGINT[], TEXT[]) OWNER TO assistant_gateway_owner;`
- Line 31: `ALTER FUNCTION assistant_api.resolve_reference_entity(TEXT, TEXT, TEXT) OWNER TO assistant_gateway_owner;`

### `backend/app/db/migrations\007_seed.sql`

- Line 93: `CREATE INDEX IF NOT EXISTS idx_fdn_file_version_status`
- Line 95: `CREATE INDEX IF NOT EXISTS idx_fdn_canonical_name`
- Line 97: `CREATE INDEX IF NOT EXISTS idx_fdn_search_trgm`
- Line 99: `CREATE INDEX IF NOT EXISTS idx_fdn_search_fts`

### `backend/app/db/migrations\010_structured_query.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api._field_text(`
- Line 28: `CREATE OR REPLACE FUNCTION assistant_api._apply_op(`
- Line 82: `CREATE OR REPLACE FUNCTION assistant_api._record_matches(`
- Line 116: `CREATE OR REPLACE FUNCTION assistant_api.structured_count(`
- Line 138: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 184: `ALTER FUNCTION assistant_api._field_text(INTEGER, JSONB, TEXT, TEXT, TEXT, TEXT) OWNER TO assistant_gateway_owner;`
- Line 185: `ALTER FUNCTION assistant_api._apply_op(TEXT, TEXT, TEXT) OWNER TO assistant_gateway_owner;`
- Line 186: `ALTER FUNCTION assistant_api._record_matches(INTEGER, JSONB, TEXT, TEXT, TEXT, JSONB) OWNER TO assistant_gateway_owner;`
- Line 187: `ALTER FUNCTION assistant_api.structured_count(TEXT, INTEGER[], BOOLEAN, JSONB) OWNER TO assistant_gateway_owner;`
- Line 188: `ALTER FUNCTION assistant_api.structured_list(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT, TEXT, INTEGER) OWNER TO assistant_gateway_owner;`

### `backend/app/db/migrations\011_retrieval.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.retrieve_candidates(`
- Line 59: `ALTER FUNCTION assistant_api.retrieve_candidates(TEXT, INTEGER[], BOOLEAN, TEXT, TEXT, INTEGER)`

### `backend/app/db/migrations\012_is_known.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api._apply_op(`
- Line 58: `ALTER FUNCTION assistant_api._apply_op(TEXT, TEXT, TEXT) OWNER TO assistant_gateway_owner;`

### `backend/app/db/migrations\015_field_registry_inspected.sql`

- Line 1: `ALTER TABLE assistant.field_registry`
- Line 3: `ALTER TABLE assistant.field_registry`
- Line 21: `CREATE OR REPLACE FUNCTION assistant_api._field_text(`

### `backend/app/db/migrations\016_list_offset.sql`

- Line 3: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 51: `ALTER FUNCTION assistant_api.structured_list(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT, TEXT, INTEGER, INTEGER)`

### `backend/app/db/migrations\017_structured_sort.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 93: `ALTER FUNCTION assistant_api.structured_list(`

### `backend/app/db/migrations\018_random_sampling.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.structured_sample(`
- Line 50: `ALTER FUNCTION assistant_api.structured_sample(`

### `backend/app/db/migrations\019_single_scan_sampling.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.structured_sample_page(`
- Line 64: `ALTER FUNCTION assistant_api.structured_sample_page(`

### `backend/app/db/migrations\020_resolved_sample_filters.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.structured_sample_page(`
- Line 107: `ALTER FUNCTION assistant_api.structured_sample_page(`

### `backend/app/db/migrations\021_resolved_count_list_filters.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api._field_text_at_path(`
- Line 23: `CREATE OR REPLACE FUNCTION assistant_api.structured_count(`
- Line 91: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 229: `ALTER FUNCTION assistant_api._field_text_at_path(JSONB, TEXT, TEXT, TEXT, TEXT)`
- Line 231: `ALTER FUNCTION assistant_api.structured_count(TEXT, INTEGER[], BOOLEAN, JSONB)`
- Line 233: `ALTER FUNCTION assistant_api.structured_list(`

### `backend/app/db/migrations\022_exact_group_aggregates.sql`

- Line 1: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_count(`
- Line 71: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_values(`
- Line 166: `ALTER FUNCTION assistant_api.structured_group_count(TEXT, INTEGER[], BOOLEAN, JSONB)`
- Line 168: `ALTER FUNCTION assistant_api.structured_group_values(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT)`

### `backend/app/db/migrations\023_dataset_scoped_conversations.sql`

- Line 1: `ALTER TABLE assistant.conversations`
- Line 4: `ALTER TABLE assistant.voice_sessions`
- Line 7: `CREATE INDEX IF NOT EXISTS idx_conversations_dataset`
- Line 10: `CREATE INDEX IF NOT EXISTS idx_voice_sessions_dataset`

### `backend/app/db/migrations\024_comprehensive_public_fields.sql`

- Line 87: `CREATE OR REPLACE FUNCTION assistant_api._apply_op(`
- Line 177: `ALTER FUNCTION assistant_api._apply_op(TEXT, TEXT, TEXT) OWNER TO assistant_gateway_owner;`

### `backend/app/db/migrations\025_typed_semantic_values.sql`

- Line 7: `CREATE OR REPLACE FUNCTION assistant_api._semantic_text(p_value JSONB)`
- Line 32: `CREATE OR REPLACE FUNCTION assistant_api._field_text_at_path(`
- Line 94: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 253: `CREATE OR REPLACE FUNCTION assistant_api.structured_sample_page(`
- Line 347: `ALTER FUNCTION assistant_api._semantic_text(JSONB) OWNER TO assistant_gateway_owner;`
- Line 348: `ALTER FUNCTION assistant_api._field_text_at_path(JSONB, TEXT, TEXT, TEXT, TEXT)`
- Line 350: `ALTER FUNCTION assistant_api.structured_list(`
- Line 353: `ALTER FUNCTION assistant_api.structured_sample_page(`

### `backend/app/db/migrations\027_catalog_validation_rules.sql`

- Line 5: `CREATE OR REPLACE VIEW assistant_api.v_dataset_fields AS`

### `backend/app/db/migrations\028_semantic_date_sort.sql`

- Line 10: `CREATE OR REPLACE FUNCTION assistant_api._date_sort_key(p_value TEXT)`
- Line 73: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`

### `backend/app/db/migrations\030_display_values.sql`

- Line 10: `CREATE OR REPLACE FUNCTION assistant_api._field_display_at_path(`
- Line 44: `CREATE OR REPLACE FUNCTION assistant_api._field_display(`
- Line 70: `CREATE OR REPLACE FUNCTION assistant_api._parse_date_value(p_value TEXT)`
- Line 130: `CREATE OR REPLACE FUNCTION assistant_api._date_precision(p_value TEXT)`
- Line 163: `CREATE OR REPLACE FUNCTION assistant_api._value_part(p_value TEXT, p_part TEXT)`
- Line 207: `CREATE OR REPLACE FUNCTION assistant_api._numeric_value(p_value TEXT, p_part TEXT)`
- Line 235: `ALTER FUNCTION assistant_api._field_display_at_path(JSONB, TEXT, TEXT, TEXT, TEXT)`
- Line 237: `ALTER FUNCTION assistant_api._field_display(INTEGER, JSONB, TEXT, TEXT, TEXT, TEXT)`
- Line 239: `ALTER FUNCTION assistant_api._parse_date_value(TEXT) OWNER TO assistant_gateway_owner;`
- Line 240: `ALTER FUNCTION assistant_api._date_precision(TEXT) OWNER TO assistant_gateway_owner;`
- Line 241: `ALTER FUNCTION assistant_api._value_part(TEXT, TEXT) OWNER TO assistant_gateway_owner;`
- Line 242: `ALTER FUNCTION assistant_api._numeric_value(TEXT, TEXT) OWNER TO assistant_gateway_owner;`

### `backend/app/db/migrations\031_filter_groups.sql`

- Line 14: `CREATE OR REPLACE FUNCTION assistant_api._apply_op(`
- Line 155: `CREATE OR REPLACE FUNCTION assistant_api._field_text(`
- Line 179: `CREATE OR REPLACE FUNCTION assistant_api._matches_group(`
- Line 292: `CREATE OR REPLACE FUNCTION assistant_api._record_matches(`
- Line 311: `ALTER FUNCTION assistant_api._matches_group(INTEGER, JSONB, TEXT, TEXT, TEXT, JSONB)`
- Line 316: `CREATE OR REPLACE FUNCTION assistant_api.structured_count(`
- Line 345: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_count(`
- Line 378: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_values(`
- Line 434: `CREATE OR REPLACE FUNCTION assistant_api.structured_sample_page(`
- Line 492: `CREATE OR REPLACE FUNCTION assistant_api.structured_list(`
- Line 620: `ALTER FUNCTION assistant_api.structured_count(TEXT, INTEGER[], BOOLEAN, JSONB)`
- Line 622: `ALTER FUNCTION assistant_api.structured_group_count(TEXT, INTEGER[], BOOLEAN, JSONB)`
- Line 624: `ALTER FUNCTION assistant_api.structured_group_values(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT)`
- Line 626: `ALTER FUNCTION assistant_api.structured_sample_page(TEXT, INTEGER[], BOOLEAN, JSONB, INTEGER)`
- Line 628: `ALTER FUNCTION assistant_api.structured_list(`

### `backend/app/db/migrations\032_analytics.sql`

- Line 13: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_values2(`
- Line 107: `CREATE OR REPLACE FUNCTION assistant_api.structured_stats(`
- Line 177: `CREATE OR REPLACE FUNCTION assistant_api.structured_duplicates(`
- Line 277: `CREATE OR REPLACE FUNCTION assistant_api.structured_completeness(`
- Line 364: `CREATE OR REPLACE FUNCTION assistant_api.structured_interval(`
- Line 463: `CREATE OR REPLACE FUNCTION assistant_api.structured_interval_stats(`
- Line 510: `ALTER FUNCTION assistant_api.structured_group_values2(`
- Line 513: `ALTER FUNCTION assistant_api.structured_stats(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT, TEXT)`
- Line 515: `ALTER FUNCTION assistant_api.structured_duplicates(`
- Line 518: `ALTER FUNCTION assistant_api.structured_completeness(TEXT, INTEGER[], BOOLEAN, JSONB, TEXT, INTEGER)`
- Line 520: `ALTER FUNCTION assistant_api.structured_interval(`
- Line 523: `ALTER FUNCTION assistant_api.structured_interval_stats(`

### `backend/app/db/migrations\033_domain_metadata.sql`

- Line 11: `CREATE OR REPLACE VIEW assistant_api.v_dataset_fields AS`
- Line 30: `CREATE OR REPLACE FUNCTION assistant.set_value_synonyms(`

### `backend/app/db/migrations\034_dataset_aliases.sql`

- Line 6: `ALTER TABLE assistant.dataset_policy`
- Line 38: `CREATE OR REPLACE VIEW assistant_api.v_datasets AS`
- Line 55: `CREATE OR REPLACE FUNCTION assistant_api.list_datasets(`
- Line 93: `ALTER FUNCTION assistant_api.list_datasets(TEXT, INTEGER[], BOOLEAN)`

### `backend/app/db/migrations\035_case_folded_grouping.sql`

- Line 9: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_values(`
- Line 66: `CREATE OR REPLACE FUNCTION assistant_api.structured_group_values2(`

