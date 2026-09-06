"""The REST reasoning provider, and the allowlist in front of it.

NIA's paid reasoning moved from the gRPC xai-sdk to an OpenAI-compatible HTTP host. The
five methods of ``ReasoningProvider`` are the whole contract everything above depends on,
so they are exercised here against a mock transport rather than the live endpoint.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.llm.http_reasoner import (  # noqa: E402
    HttpReasoningProvider,
    ReasoningProviderError,
    _content_of,
    _delta_from_sse,
    _usage_metadata,
    cached_tokens_of,
)
from app.llm.schemas import SynthesisAnswer  # noqa: E402


def _provider(handler) -> HttpReasoningProvider:
    provider = HttpReasoningProvider(api_key="test-key", model="grok-test")
    provider._client = httpx.AsyncClient(
        base_url="https://example.invalid", transport=httpx.MockTransport(handler)
    )
    return provider


def _completion(content: str, **usage) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "model": "grok-test-internal",
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, **usage},
        },
    )


# ---------------------------------------------------------------- structured output


def test_a_pydantic_model_round_trips_through_json_schema():
    answer = {"answer": "Two students.", "citations": [], "inference": False}
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _completion(json.dumps(answer))

    result = asyncio.run(
        _provider(handler).structured_output_with_metadata(
            system="s", user="u", response_model=SynthesisAnswer
        )
    )
    assert isinstance(result.value, SynthesisAnswer)
    assert result.value.answer == "Two students."

    fmt = captured["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "SynthesisAnswer"
    # Strict is what makes the host enforce the schema rather than merely suggest it.
    assert fmt["json_schema"]["strict"] is True
    assert fmt["json_schema"]["schema"]["type"] == "object"


def test_output_that_does_not_match_the_schema_is_a_provider_error():
    """The planner has a failure mode for this; a bare ValidationError is not it."""
    handler = lambda request: _completion('{"unexpected": true}')  # noqa: E731
    with pytest.raises(ReasoningProviderError, match="SynthesisAnswer"):
        asyncio.run(
            _provider(handler).answer_structured(system="s", user="u")
        )


def test_an_http_error_says_what_came_back():
    handler = lambda request: httpx.Response(429, text="slow down")  # noqa: E731
    with pytest.raises(ReasoningProviderError, match="429"):
        asyncio.run(_provider(handler).answer_structured(system="s", user="u"))


def test_an_empty_choice_list_is_an_error_not_an_empty_answer():
    handler = lambda request: httpx.Response(200, json={"choices": []})  # noqa: E731
    with pytest.raises(ReasoningProviderError, match="no choices"):
        asyncio.run(_provider(handler).answer_structured(system="s", user="u"))


# ---------------------------------------------------------------- request shape


def test_the_request_carries_the_system_and_user_turn_and_temperature():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _completion('{"answer":"ok","citations":[],"inference":false}')

    asyncio.run(_provider(handler).answer_structured(system="SYS", user="USR"))
    assert [m["role"] for m in captured["messages"]] == ["system", "user"]
    assert captured["messages"][0]["content"] == "SYS"
    assert captured["messages"][1]["content"] == "USR"
    assert captured["model"] == "grok-test"
    # Planning is structured extraction against a schema, so it does not sample.
    assert captured["temperature"] == get_settings().model_temperature


# ---------------------------------------------------------------- streaming


def test_streaming_yields_each_delta():
    frames = [
        'data: {"choices":[{"delta":{"content":"Two"}}]}',
        'data: {"choices":[{"delta":{"content":" students"}}]}',
        "data: [DONE]",
    ]
    handler = lambda request: httpx.Response(200, text="\n\n".join(frames))  # noqa: E731

    async def collect():
        return [chunk async for chunk in _provider(handler).stream_answer(system="s", user="u")]

    assert asyncio.run(collect()) == ["Two", " students"]


@pytest.mark.parametrize(
    "line",
    ["", ": keep-alive", "data: [DONE]", "data: not-json", 'data: {"choices":[]}'],
)
def test_frames_that_carry_no_text_are_skipped(line):
    assert _delta_from_sse(line) == ""


# ---------------------------------------------------------------- accounting


def test_usage_is_reported_and_totalled_when_the_host_omits_it():
    meta = _usage_metadata(
        {"model": "grok-test-internal", "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
        "http",
        "grok-test",
        12.5,
    )
    assert (meta["prompt_tokens"], meta["completion_tokens"], meta["total_tokens"]) == (10, 5, 15)
    # What answered, not what was asked for: aliases resolve server-side.
    assert meta["model"] == "grok-test-internal"


def test_cached_prompt_tokens_are_readable():
    """xAI never reported these; the bridge does, so caching stops being invisible."""
    payload = {"usage": {"prompt_tokens_details": {"cached_tokens": 12544}}}
    assert cached_tokens_of(payload) == 12544
    assert cached_tokens_of({"usage": {}}) == 0


def test_a_message_with_no_content_is_an_error():
    with pytest.raises(ReasoningProviderError, match="empty message"):
        _content_of({"choices": [{"message": {"content": ""}}]})


# ---------------------------------------------------------------- the allowlist


def test_the_offered_models_lead_with_the_default():
    from app.llm.factory import allowed_models

    models = allowed_models()
    assert models[0] == get_settings().reasoning_model
    assert len(set(models)) == len(models)


@pytest.mark.parametrize("requested", ["", None, "   "])
def test_no_choice_means_the_default(requested):
    from app.llm.factory import resolve_model

    assert resolve_model(requested) == get_settings().reasoning_model


def test_a_model_outside_the_allowlist_never_reaches_the_provider():
    """The name is passed straight to the host, which exposes hundreds of models."""
    from app.llm.factory import resolve_model

    assert resolve_model("grok-4.20-x-algo-reasoning") == get_settings().reasoning_model
    assert resolve_model("../../etc/passwd") == get_settings().reasoning_model


def test_an_offered_model_is_honoured():
    from app.llm.factory import allowed_models, resolve_model

    offered = allowed_models()[-1]
    assert resolve_model(offered) == offered


# ---------------------------------------------------------------- time budget


def test_a_direct_model_keeps_the_short_budget():
    from app.llm.factory import timeout_for

    assert timeout_for(get_settings().reasoning_model) == get_settings().xai_request_timeout_ms


def test_a_reasoning_model_gets_longer():
    """One ceiling cannot serve both: measured p95 87s against 21s.

    At the short budget the reasoning models did not merely lag, they failed -- the review
    call came back ReadTimeout and the turn was scored wrong.
    """
    from app.llm.factory import timeout_for

    settings = get_settings()
    assert timeout_for("grok-4.6") == settings.reasoning_request_timeout_ms
    assert timeout_for("grok-4.6") > timeout_for(settings.reasoning_model)


def test_every_offered_model_is_classified():
    """Adding a model to the picker means saying whether it reasons."""
    from app.llm.factory import allowed_models, timeout_for

    for model in allowed_models():
        assert timeout_for(model) > 0
