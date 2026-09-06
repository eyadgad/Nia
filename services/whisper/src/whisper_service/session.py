from __future__ import annotations

from uuid import uuid4

from whisper_service.engine import TranscriptionEngine
from whisper_service.protocol import TranscriptEvent


class WhisperSession:
    """Incremental PCM windowing. Partial on hops, final on finalize_turn()."""

    def __init__(
        self,
        engine: TranscriptionEngine,
        *,
        sample_rate: int = 16000,
        hop_ms: int = 400,
        window_ms: int = 2000,
        session_id: str | None = None,
    ) -> None:
        self.engine = engine
        self.sample_rate = sample_rate
        self.hop_bytes = _ms_to_bytes(hop_ms, sample_rate)
        self.window_bytes = _ms_to_bytes(window_ms, sample_rate)
        self.session_id = session_id or str(uuid4())
        self._buffer = bytearray()
        self._since_hop = 0
        self._offset_ms = 0
        self._last_partial = ""

    async def push_pcm(self, pcm: bytes) -> list[TranscriptEvent]:
        if not pcm:
            return []
        self._buffer.extend(pcm)
        # Heavy engines (real whisper on CPU) transcribe once per finalized turn,
        # not on every hop, so the buffer just accumulates here.
        if getattr(self.engine, "heavy", False):
            return []
        self._since_hop += len(pcm)
        if self._since_hop < self.hop_bytes:
            return []
        self._since_hop = 0
        window = bytes(self._buffer[-self.window_bytes :])
        result = await self.engine.transcribe(window, self.sample_rate)
        self._last_partial = result.text
        end_ms = self._offset_ms + _bytes_to_ms(len(self._buffer), self.sample_rate)
        return [
            TranscriptEvent(
                type="partial",
                text=result.text,
                start_ms=self._offset_ms,
                end_ms=end_ms,
                confidence=result.confidence,
                speech=result.speech,
            )
        ]

    async def finalize_turn(self) -> TranscriptEvent:
        result = await self.engine.transcribe(bytes(self._buffer), self.sample_rate)
        text = result.text or self._last_partial
        end_ms = self._offset_ms + _bytes_to_ms(len(self._buffer), self.sample_rate)
        event = TranscriptEvent(
            type="final",
            text=text,
            start_ms=self._offset_ms,
            end_ms=end_ms,
            confidence=max(result.confidence, 0.8 if text else 0.0),
            speech=bool(text),
        )
        self.reset_session()
        return event

    def reset_session(self) -> None:
        self._offset_ms += _bytes_to_ms(len(self._buffer), self.sample_rate)
        self._buffer.clear()
        self._since_hop = 0
        self._last_partial = ""
        reset = getattr(self.engine, "reset", None)
        if callable(reset):
            reset()


def _ms_to_bytes(ms: int, sample_rate: int) -> int:
    return max(int(sample_rate * (ms / 1000) * 2), 2)


def _bytes_to_ms(length: int, sample_rate: int) -> int:
    if sample_rate <= 0:
        return 0
    return int(length / 2 / sample_rate * 1000)
