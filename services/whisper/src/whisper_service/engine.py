from __future__ import annotations

import asyncio
import logging
import os
import shutil
import struct
import tempfile
import time
import wave
from pathlib import Path
from typing import Protocol

from whisper_service.protocol import TranscriptResult

logger = logging.getLogger("nia.whisper")


DEFAULT_INITIAL_PROMPT = (
    "Nia (pronounced nee-uh) is a research assistant and is normally written Nia. "
    "Users may spell names and words one letter at a time."
)
DEFAULT_HOTWORDS = "Nia, hi, hello, hey"


class TranscriptionEngine(Protocol):
    name: str
    model: str

    async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult: ...


class ScriptedEngine:
    """Test/dev engine. Does not call a paid API or the main app."""

    name = "scripted"

    def __init__(self, partials: list[str] | None = None, final: str | None = None, model: str = "base.en") -> None:
        self.model = model
        self.partials = partials or ["How many", "How many students", "How many students have names starting with S"]
        self.final = final or "How many students have names starting with S"
        self._index = 0

    async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:
        duration_ms = _duration_ms(pcm, sample_rate)
        if not pcm or _rms(pcm) < 80:
            text = self.partials[min(self._index, len(self.partials) - 1)] if self._index else ""
            return TranscriptResult(text=text, speech=False, confidence=0.2, end_ms=duration_ms)
        text = self.partials[min(self._index, len(self.partials) - 1)]
        self._index = min(self._index + 1, len(self.partials))
        return TranscriptResult(text=text, speech=True, confidence=0.72, end_ms=duration_ms)

    def reset(self) -> None:
        self._index = 0


class FasterWhisperEngine:
    """Real local CPU transcription via faster-whisper (CTranslate2 whisper).

    Marked `heavy` so the session runs it once per finalized turn instead of on
    every 400ms hop — base.en on CPU is too slow for per-hop partials.
    """

    name = "faster-whisper"
    heavy = True

    def __init__(
        self,
        model_size: str = "small.en",
        compute_type: str = "int8",
        *,
        initial_prompt: str | None = DEFAULT_INITIAL_PROMPT,
        hotwords: str | None = DEFAULT_HOTWORDS,
        beam_size: int = 5,
        vad_filter: bool = False,
    ) -> None:
        from faster_whisper import WhisperModel

        self._model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
        self.model = model_size
        self.initial_prompt = initial_prompt
        self.hotwords = hotwords
        self.beam_size = max(1, beam_size)
        self.vad_filter = vad_filter

    async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:
        duration_ms = _duration_ms(pcm, sample_rate)
        if not pcm or _rms(pcm) < 60:
            return TranscriptResult(text="", speech=False, confidence=0.0, end_ms=duration_ms)

        def _run() -> str:
            import numpy as np

            audio = np.frombuffer(pcm, dtype=np.int16).astype("float32") / 32768.0
            segments, _info = self._model.transcribe(
                audio,
                language="en",
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,
                initial_prompt=self.initial_prompt,
                hotwords=self.hotwords,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()

        started_at = time.perf_counter()
        text = await asyncio.to_thread(_run)
        latency_ms = round((time.perf_counter() - started_at) * 1000)
        logger.info(
            "transcription completed model=%s audio_ms=%d latency_ms=%d speech=%s",
            self.model,
            duration_ms,
            latency_ms,
            bool(text),
        )
        return TranscriptResult(
            text=text,
            speech=bool(text),
            confidence=0.85 if text else 0.1,
            end_ms=duration_ms,
        )


class CliEngine:
    """Runs a local whisper.cpp binary. Never used by Assistant Core directly."""

    name = "whisper-cli"

    def __init__(self, binary: str, model_path: str) -> None:
        self.binary = binary
        self.model = Path(model_path).name
        self.model_path = model_path

    async def transcribe(self, pcm: bytes, sample_rate: int) -> TranscriptResult:
        if not pcm:
            return TranscriptResult(text="", speech=False, confidence=0.0)
        duration_ms = _duration_ms(pcm, sample_rate)
        with tempfile.TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "chunk.wav"
            _write_wav(wav_path, pcm, sample_rate)
            process = await asyncio.create_subprocess_exec(
                self.binary,
                "-m",
                self.model_path,
                "-f",
                str(wav_path),
                "-nt",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _stderr = await process.communicate()
        text = stdout.decode("utf-8", errors="ignore").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("[")]
        spoken = " ".join(lines)
        return TranscriptResult(
            text=spoken,
            speech=bool(spoken),
            confidence=0.8 if spoken else 0.1,
            end_ms=duration_ms,
        )


def build_engine() -> TranscriptionEngine:
    engine_pref = (os.environ.get("WHISPER_ENGINE") or "").strip().lower()
    if engine_pref in {"faster", "faster-whisper", "faster_whisper"}:
        try:
            initial_prompt = _optional_env("WHISPER_INITIAL_PROMPT", DEFAULT_INITIAL_PROMPT)
            hotwords = _optional_env("WHISPER_HOTWORDS", DEFAULT_HOTWORDS)
            return FasterWhisperEngine(
                model_size=os.environ.get("WHISPER_MODEL", "small.en"),
                initial_prompt=initial_prompt,
                hotwords=hotwords,
                beam_size=_int_env("WHISPER_BEAM_SIZE", 5),
                # LiveKit/Silero already provides one complete speech segment.
                # A second VAD pass can remove short utterances such as "hi".
                vad_filter=_bool_env("WHISPER_VAD_FILTER", False),
            )
        except Exception as exc:  # pragma: no cover - depends on optional dep
            print(f"faster-whisper unavailable ({exc}); falling back", flush=True)
    binary = os.environ.get("WHISPER_BIN") or shutil.which("whisper-cli") or shutil.which("whisper-cpp")
    model = os.environ.get("WHISPER_MODEL_PATH") or os.environ.get("WHISPER_MODEL")
    if binary and model and Path(model).exists():
        return CliEngine(binary, model)
    return ScriptedEngine(model=os.environ.get("WHISPER_MODEL", "base.en"))


def _optional_env(name: str, default: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip() or None


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _rms(pcm: bytes) -> int:
    if len(pcm) < 4:
        return 0
    count = len(pcm) // 2
    samples = struct.unpack("<" + "h" * count, pcm[: count * 2])
    mean_square = sum(sample * sample for sample in samples) / count
    return int(mean_square ** 0.5)


def _duration_ms(pcm: bytes, sample_rate: int) -> int:
    if sample_rate <= 0:
        return 0
    return int(len(pcm) / 2 / sample_rate * 1000)


def _write_wav(path: Path, pcm: bytes, sample_rate: int) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
