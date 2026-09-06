import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.api.assistant import QueryRequest, _memory_store, _stream_query, _turn_service
from app.data_gateway.memory import MemoryDataGateway
from app.execution.turn import AssistantTurnService, TurnResult
from app.llm.fake import FakeReasoningProvider
from app.main import create_app
from app.memory.store import InMemoryMemoryStore
from app.security.access_scope import AccessScope
from app.security.deps import get_access_scope
from app.security.auth_adapter import get_auth_adapter
from app.security.standalone_jwt import StandaloneJwtAuthAdapter
from app.config import Settings
from app.tts.base import ensure_no_tts_in_text_mode
from fastapi.testclient import TestClient


def _client(store: InMemoryMemoryStore | None = None) -> TestClient:
    app = create_app()
    memory = store or InMemoryMemoryStore()

    def scope() -> AccessScope:
        return AccessScope(principal_id="principal-researcher", allowed_file_ids=(49, 91))

    def service() -> AssistantTurnService:
        return AssistantTurnService(MemoryDataGateway(), store=memory, reasoner=FakeReasoningProvider())

    app.dependency_overrides[get_access_scope] = scope
    app.dependency_overrides[_memory_store] = lambda: memory
    app.dependency_overrides[_turn_service] = service
    return TestClient(app)


def test_query_golden_path_json():
    response = _client().post(
        "/api/assistant/query",
        json={"question": "How many students have names starting with S?", "mode": "text"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reasoning_calls"] == 0
    assert body["plan"]["scope"]["file_ids"] == [49]
    assert body["facts"][0]["value"] == 2


def test_list_query_returns_structured_rows_and_range_metadata():
    response = _client().post(
        "/api/assistant/query",
        json={"question": "List the last 3 students", "mode": "text"},
    )
    assert response.status_code == 200
    body = response.json()
    result = body["list_results"][0]
    assert result["window"] == {"anchor": "end", "size": 3, "count": 3, "cursor": 0}
    assert result["offset"] == 2
    assert result["has_more"] is False
    assert result["fields"][0] == {"name": "student_name", "label": "Student name"}
    assert result["rows"][0]["values"]["student_name"] == "Samuel A"


def test_query_requires_auth():
    app = create_app()
    client = TestClient(app)
    response = client.post("/api/assistant/query", json={"question": "How many students?"})
    assert response.status_code == 401


def test_cookie_authenticated_mutation_rejects_untrusted_browser_origin():
    settings = Settings(
        jwt_secret="unit-test-secret",
        standalone_demo_username="test-user",
        standalone_demo_password="unit-test-password",
        standalone_demo_principal_id="test-principal",
    )
    adapter = StandaloneJwtAuthAdapter(settings)
    app = create_app()
    app.dependency_overrides[get_auth_adapter] = lambda: adapter

    with TestClient(app) as client:
        signed_in = client.post(
            "/api/auth/login",
            json={"username": "test-user", "password": "unit-test-password"},
        )
        response = client.post(
            "/api/assistant/query",
            headers={"Origin": "https://attacker.invalid", "Sec-Fetch-Site": "cross-site"},
            json={"question": "How many students?"},
        )

    assert signed_in.status_code == 200
    assert response.status_code == 403


def test_query_sse_emits_required_events():
    response = _client().post(
        "/api/assistant/query",
        json={"question": "How many students have names starting with S?", "mode": "text"},
        headers={"Accept": "text/event-stream"},
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    for event in ("plan_started", "plan_validated", "computed_fact", "answer_delta", "answer_completed"):
        assert f"event: {event}" in body
    assert body.count("event: plan_started") == 1
    assert "event: citation" not in body or "file:93" not in body


def test_sse_starts_before_assistant_computation_finishes():
    class DelayedService:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def answer(self, *_args, **_kwargs):
            self.started.set()
            await self.release.wait()
            return TurnResult(status="answered", answer="Finished")

    async def run():
        service = DelayedService()
        stream = _stream_query(QueryRequest(question="wait"), _client_scope(), service)

        first = await stream.__anext__()
        assert "event: plan_started" in first
        assert not service.started.is_set()

        next_event = asyncio.create_task(stream.__anext__())
        await service.started.wait()
        assert not next_event.done()
        service.release.set()
        assert "event: answer_delta" in await next_event
        await stream.aclose()

    asyncio.run(run())


def test_turn_service_emits_execution_progress_in_order():
    async def run():
        events: list[str] = []

        async def capture(event: str, _data: dict) -> None:
            events.append(event)

        service = AssistantTurnService(
            MemoryDataGateway(),
            store=InMemoryMemoryStore(),
            reasoner=FakeReasoningProvider(),
        )
        await service.answer(
            _client_scope(),
            "How many students have names starting with S?",
            on_progress=capture,
        )
        assert events.index("plan_validated") < events.index("retrieval_completed")
        assert events.index("retrieval_completed") < events.index("computed_fact")
        assert events.index("computed_fact") < events.index("answer_delta")

    asyncio.run(run())


def test_closing_sse_cancels_inflight_turn(monkeypatch):
    import app.api.assistant as assistant_api

    class NeverFinishes:
        def __init__(self) -> None:
            self.cancellation = None

        async def answer(self, *_args, cancellation=None, **_kwargs):
            self.cancellation = cancellation
            await asyncio.Event().wait()

    async def run():
        service = NeverFinishes()
        stream = _stream_query(QueryRequest(question="wait"), _client_scope(), service)
        await stream.__anext__()
        assert await stream.__anext__() == ": keep-alive\n\n"
        await stream.aclose()
        assert service.cancellation is not None
        assert service.cancellation.cancelled
        assert service.cancellation.reason == "client_disconnected"

    monkeypatch.setattr(assistant_api, "_SSE_HEARTBEAT_SECONDS", 0.001)
    asyncio.run(run())


def test_synthesis_sse_includes_citations():
    response = _client().post(
        "/api/assistant/query",
        json={
            "question": "Summarize what the records say about causes of death.",
            "mode": "text",
            "selected_file_id": 91,
        },
        headers={"Accept": "text/event-stream"},
    )
    assert "event: citation" in response.text
    assert "event: answer_delta" in response.text
    assert "file:93" not in response.text


def test_conversation_list_and_get():
    store = InMemoryMemoryStore()
    client = _client(store)
    asked = client.post(
        "/api/assistant/query",
        json={"question": "How many students have names starting with S?", "mode": "text"},
    )
    conversation_id = asked.json()["conversation_id"]
    listed = client.get("/api/assistant/conversations")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["conversations"]}
    assert conversation_id in ids
    detail = client.get(f"/api/assistant/conversations/{conversation_id}")
    assert detail.status_code == 200
    roles = [turn["role"] for turn in detail.json()["turns"]]
    assert "user" in roles and "assistant" in roles


def test_text_mode_never_starts_tts():
    ensure_no_tts_in_text_mode("text")
    source = Path(__file__).resolve().parents[1] / "backend" / "app" / "api" / "assistant.py"
    text = source.read_text(encoding="utf-8")
    assert "ensure_no_tts_in_text_mode" in text
    assert "synthesize_stream" not in text


def _client_scope() -> AccessScope:
    return AccessScope(principal_id="principal-researcher", allowed_file_ids=(49, 91))
