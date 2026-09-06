"""OpenAI-compatible reasoning provider over plain HTTP.

The Cloudflare bridge speaks the same API as xAI -- same model ids, same request shapes,
and our planner schemas are accepted in strict mode unmodified -- but it serves REST, and
``xai-sdk`` is gRPC. Pointing that SDK at the bridge returns 403 on the HTTP/2 handshake, so
the transport is reimplemented here rather than reconfigured.

Everything above this file is unchanged: the five methods of ``ReasoningProvider`` are the
whole contract, and planning, retrieval and the gateway still import no vendor SDK.

httpx rather than the ``openai`` package: the only things needed are one POST, JSON-schema
structured output, and SSE, all of which were verified directly against the endpoint. httpx
is already a dependency; the SDK would be a new one for no additional capability.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.llm.base import StructuredOutputResult
from app.llm.schemas import PlannedQuery, SynthesisAnswer

_GLOBAL_SEMAPHORE: asyncio.Semaphore | None = None
_GLOBAL_SEMAPHORE_LIMIT: int | None = None


def _global_semaphore() -> asyncio.Semaphore:
    global _GLOBAL_SEMAPHORE, _GLOBAL_SEMAPHORE_LIMIT
    limit = max(1, get_settings().model_max_concurrency_global)
    if _GLOBAL_SEMAPHORE is None or _GLOBAL_SEMAPHORE_LIMIT != limit:
        _GLOBAL_SEMAPHORE = asyncio.Semaphore(limit)
        _GLOBAL_SEMAPHORE_LIMIT = limit
    return _GLOBAL_SEMAPHORE


class ReasoningProviderError(RuntimeError):
    """The provider answered, but not with something usable."""


class HttpReasoningProvider:
    """Chat-completions client for any OpenAI-compatible host."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_concurrency: int = 2,
        request_timeout_ms: int | None = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key if api_key is not None else settings.xai_api_key
        self._base_url = (base_url or settings.reasoning_base_url).rstrip("/")
        self._model = model or settings.reasoning_model
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._timeout_s = (
            request_timeout_ms
            if request_timeout_ms is not None
            else settings.xai_request_timeout_ms
        ) / 1000
        self.provider_name = "http"
        self.model_name = self._model
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------ transport

    def _http(self) -> httpx.AsyncClient:
        if not self._api_key:
            raise RuntimeError("XAI_API_KEY is not configured")
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=httpx.Timeout(self._timeout_s),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    def _body(self, *, system: str, user: str, **extra: Any) -> dict[str, Any]:
        settings = get_settings()
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": settings.model_temperature,
            **extra,
        }
        if settings.model_seed is not None:
            body["seed"] = settings.model_seed
        return body

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        client = self._http()
        async with _global_semaphore(), self._semaphore:
            response = await client.post("/v1/chat/completions", json=body)
        if response.status_code >= 400:
            raise ReasoningProviderError(
                f"{response.status_code} from reasoning provider: {response.text[:300]}"
            )
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise ReasoningProviderError(str(payload["error"])[:300])
        return payload

    # ------------------------------------------------------------------ the contract

    async def stream_answer(self, *, system: str, user: str) -> AsyncIterator[str]:
        client = self._http()
        body = self._body(system=system, user=user, stream=True)
        async with _global_semaphore(), self._semaphore:
            async with client.stream("POST", "/v1/chat/completions", json=body) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", "replace")
                    raise ReasoningProviderError(
                        f"{response.status_code} from reasoning provider: {detail[:300]}"
                    )
                async for line in response.aiter_lines():
                    delta = _delta_from_sse(line)
                    if delta:
                        yield delta

    async def answer_structured(self, *, system: str, user: str) -> SynthesisAnswer:
        parsed, _meta = await self._parse(SynthesisAnswer, system=system, user=user)
        return parsed

    async def plan_structured(self, *, system: str, user: str) -> PlannedQuery:
        parsed, _meta = await self._parse(PlannedQuery, system=system, user=user)
        return parsed

    async def structured_output(self, *, system: str, user: str, response_model):
        result = await self.structured_output_with_metadata(
            system=system, user=user, response_model=response_model
        )
        return result.value

    async def structured_output_with_metadata(
        self, *, system: str, user: str, response_model
    ) -> StructuredOutputResult:
        parsed, meta = await self._parse(response_model, system=system, user=user)
        return StructuredOutputResult(value=parsed, **meta)

    async def _parse(self, model_type: type[BaseModel], *, system: str, user: str):
        started = time.perf_counter()
        body = self._body(
            system=system,
            user=user,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": model_type.__name__,
                    "strict": True,
                    "schema": model_type.model_json_schema(),
                },
            },
        )
        payload = await self._post(body)
        content = _content_of(payload)
        try:
            parsed = model_type.model_validate_json(content)
        except Exception as exc:
            # The planner treats a malformed structured output as its own failure mode, so
            # say what came back rather than letting a validation error surface bare.
            raise ReasoningProviderError(
                f"{model_type.__name__} did not validate: {str(exc)[:200]}"
            ) from exc
        duration_ms = (time.perf_counter() - started) * 1000
        return parsed, _usage_metadata(payload, self.provider_name, self.model_name, duration_ms)


def _delta_from_sse(line: str) -> str:
    """The text of one server-sent chunk, or "" for anything that is not one."""
    if not line or not line.startswith("data:"):
        return ""
    data = line[len("data:") :].strip()
    if not data or data == "[DONE]":
        return ""
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return ""
    for choice in chunk.get("choices") or []:
        text = (choice.get("delta") or {}).get("content")
        if text:
            return str(text)
    return ""


def _content_of(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise ReasoningProviderError("reasoning provider returned no choices")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise ReasoningProviderError("reasoning provider returned an empty message")
    return str(content)


def _usage_metadata(
    payload: dict[str, Any], provider: str, model: str, duration_ms: float
) -> dict[str, Any]:
    usage = payload.get("usage") or {}
    prompt = _optional_int(usage.get("prompt_tokens") or usage.get("input_tokens"))
    completion = _optional_int(usage.get("completion_tokens") or usage.get("output_tokens"))
    total = _optional_int(usage.get("total_tokens"))
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return {
        "provider": provider,
        # What answered, not what was asked for: an alias resolves server-side, so
        # "grok-4.6" comes back as "grok-4.6-internal" and the trace should say so.
        "model": str(payload.get("model") or model),
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "cached_tokens": cached_tokens_of(payload),
        "cost_usd": None,
        "duration_ms": duration_ms,
    }


def cached_tokens_of(payload: dict[str, Any]) -> int:
    """Prompt tokens served from cache, which xAI never reported and this host does.

    Erratic in practice -- measured 0%, 1%, 0% then 99.5% across four identical calls -- so
    it is worth logging as a cost signal and not worth treating as a latency guarantee.
    """
    usage = payload.get("usage") or {}
    details = usage.get("prompt_tokens_details") or {}
    return _optional_int(details.get("cached_tokens")) or 0


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
