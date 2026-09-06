from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Callable

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute
from starlette.websockets import WebSocket

from whisper_service.engine import TranscriptionEngine, build_engine
from whisper_service.protocol import ControlMessage
from whisper_service.session import WhisperSession


def _default_max_sessions() -> int:
    raw = os.environ.get("WHISPER_MAX_CONCURRENT_SESSIONS", "8")
    try:
        return max(1, int(raw))
    except ValueError:
        return 8


MAX_SESSIONS = _default_max_sessions()


def _default_session_ttl_seconds() -> float:
    raw = os.environ.get("WHISPER_SESSION_TTL_SECONDS", "300")
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 300.0


SESSION_TTL_SECONDS = _default_session_ttl_seconds()


class WhisperService:
    def __init__(
        self,
        engine: TranscriptionEngine | None = None,
        max_sessions: int = MAX_SESSIONS,
        session_ttl_seconds: float = SESSION_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.engine = engine or build_engine()
        self.max_sessions = max_sessions
        self.session_ttl_seconds = max(1.0, session_ttl_seconds)
        self._clock = clock
        self.sessions: dict[str, WhisperSession] = {}
        self._last_seen: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, session_id: str | None = None) -> WhisperSession:
        async with self._lock:
            self._drop_expired_locked()
            if session_id and session_id in self.sessions:
                self._last_seen[session_id] = self._clock()
                return self.sessions[session_id]
            if len(self.sessions) >= self.max_sessions:
                raise RuntimeError("whisper session capacity reached")
            session = WhisperSession(self.engine, session_id=session_id)
            self.sessions[session.session_id] = session
            self._last_seen[session.session_id] = self._clock()
            return session

    async def touch(self, session_id: str) -> None:
        async with self._lock:
            if session_id in self.sessions:
                self._last_seen[session_id] = self._clock()

    async def session_count(self) -> int:
        async with self._lock:
            self._drop_expired_locked()
            return len(self.sessions)

    async def drop(self, session_id: str) -> None:
        async with self._lock:
            self.sessions.pop(session_id, None)
            self._last_seen.pop(session_id, None)

    def _drop_expired_locked(self) -> None:
        cutoff = self._clock() - self.session_ttl_seconds
        expired = [session_id for session_id, seen in self._last_seen.items() if seen < cutoff]
        for session_id in expired:
            self.sessions.pop(session_id, None)
            self._last_seen.pop(session_id, None)


def create_app(service: WhisperService | None = None) -> Starlette:
    svc = service or WhisperService()

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "engine": svc.engine.name,
                "model": svc.engine.model,
                "sessions": await svc.session_count(),
            }
        )

    async def transcribe(request: Request) -> JSONResponse:
        pcm = await request.body()
        sample_rate = int(request.query_params.get("sample_rate", "16000"))
        result = await svc.engine.transcribe(pcm, sample_rate)
        return JSONResponse(result.model_dump())

    async def open_session(_request: Request) -> JSONResponse:
        session = await svc.get_session()
        return JSONResponse({"session_id": session.session_id})

    async def push_audio(request: Request) -> JSONResponse:
        session = await _require_session(svc, request.path_params["session_id"])
        events = await session.push_pcm(await request.body())
        return JSONResponse({"events": [event.model_dump() for event in events]})

    async def finalize(request: Request) -> JSONResponse:
        session = await _require_session(svc, request.path_params["session_id"])
        event = await session.finalize_turn()
        return JSONResponse(event.model_dump())

    async def reset(request: Request) -> JSONResponse:
        session = await _require_session(svc, request.path_params["session_id"])
        session.reset_session()
        return JSONResponse({"ok": True, "session_id": session.session_id})

    async def close_session(request: Request) -> JSONResponse:
        session_id = request.path_params["session_id"]
        await svc.drop(session_id)
        return JSONResponse({"ok": True, "session_id": session_id})

    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        session = await svc.get_session()
        await websocket.send_text(json.dumps({"type": "ready", "session_id": session.session_id}))
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                await svc.touch(session.session_id)
                if message.get("bytes"):
                    for event in await session.push_pcm(message["bytes"]):
                        await websocket.send_text(event.model_dump_json())
                    continue
                text = message.get("text")
                if not text:
                    continue
                control = ControlMessage.model_validate_json(text)
                if control.type == "config" and control.sample_rate:
                    session.sample_rate = control.sample_rate
                elif control.type == "reset":
                    session.reset_session()
                    await websocket.send_text(json.dumps({"type": "reset", "session_id": session.session_id}))
                elif control.type == "finalize":
                    event = await session.finalize_turn()
                    await websocket.send_text(event.model_dump_json())
        finally:
            await svc.drop(session.session_id)

    return Starlette(
        routes=[
            Route("/health", health),
            Route("/v1/transcribe", transcribe, methods=["POST"]),
            Route("/v1/session", open_session, methods=["POST"]),
            Route("/v1/session/{session_id}/audio", push_audio, methods=["POST"]),
            Route("/v1/session/{session_id}/finalize", finalize, methods=["POST"]),
            Route("/v1/session/{session_id}/reset", reset, methods=["POST"]),
            Route("/v1/session/{session_id}", close_session, methods=["DELETE"]),
            WebSocketRoute("/v1/stream", stream),
        ]
    )


async def _require_session(service: WhisperService, session_id: str) -> WhisperSession:
    return await service.get_session(session_id)


app = create_app()
