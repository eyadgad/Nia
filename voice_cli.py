#!/usr/bin/env python3
"""Terminal voice agent for the NIA assistant — no browser, no LiveKit, no UI.

Speak into your microphone; this transcribes your speech with the local whisper
service and answers via the Assistant Core HTTP API, printing the exchange in
your terminal. It reuses the running Docker stack — nothing else to start.

PREREQS
    The stack must be running so these are reachable from this machine:
        whisper   http://localhost:8090   (STT)
        backend   http://localhost:8000    (Assistant Core)
    Start it with:  docker compose -f infra/docker-compose.yml up

    Install client deps once (run this on the machine with the microphone):
        pip install sounddevice numpy requests

    Answers are SPOKEN BY DEFAULT through authenticated backend TTS, using the
    same contextual expression and rex/ara voices as the web voice agent. The
    xAI key never leaves the backend. Use --local-tts for an OS voice instead.
    Run on the machine with the speakers/microphone — inside WSL there is
    usually no audio device or mic, so run this from Windows directly.

USAGE
    python voice_cli.py                 # hands-free: talk, pause, hear the answer
    python voice_cli.py --voice-test    # verify you can hear audio, then exit
    python voice_cli.py --push-to-talk  # press Enter to start/stop each utterance
    python voice_cli.py --no-speak      # print answers only, stay silent
    python voice_cli.py --local-tts --tts-voice David  # installed OS voice
    python voice_cli.py --text          # type questions instead (no mic)
    python voice_cli.py --wav clip.wav  # transcribe one 16 kHz mono WAV and answer

    Ctrl+C to quit.

This is a client tool. It never touches the database directly — it only calls
the same authenticated HTTP endpoints the web UI uses, so the AccessScope and
data boundary are identical.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency 'requests'. Install with: pip install requests")

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))
from app.tts.voice_control import requested_voice_preference  # noqa: E402

SAMPLE_RATE = 16000
BLOCK_MS = 20
BLOCK_FRAMES = SAMPLE_RATE * BLOCK_MS // 1000  # 320 frames / 20 ms


def _configuration() -> dict[str, str]:
    """Read CLI identity settings without exposing or embedding credentials."""
    values: dict[str, str] = {}
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip().strip('"').strip("'")
    values.update({key: value for key, value in os.environ.items() if value})
    return values


def _first_config(config: dict[str, str], *names: str, default: str = "") -> str:
    return next((config[name] for name in names if config.get(name)), default)


# --------------------------------------------------------------------------- #
# HTTP clients for the running services
# --------------------------------------------------------------------------- #
class AssistantClient:
    """Talks to the Assistant Core over HTTP, exactly like the web UI."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        *,
        expected_principal: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._expected_principal = expected_principal
        self._http = requests.Session()
        self._authenticated = False
        self.conversation_id: str | None = None

    def login(self) -> dict:
        resp = self._http.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self._username, "password": self._password},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        principal = str(data.get("principal_id") or "")
        if self._expected_principal and principal != self._expected_principal:
            self._http.cookies.clear()
            raise RuntimeError(
                "authenticated principal mismatch: "
                f"expected {self._expected_principal!r}, received {principal!r}"
            )
        self._authenticated = True
        return data

    def synthesize(self, text: str, preference: str):
        """Open an authenticated streaming PCM response from backend TTS."""
        if not self._authenticated:
            self.login()
        resp = self._http.post(
            f"{self.base_url}/api/voice/speech",
            json={"text": text, "preference": preference},
            stream=True,
            timeout=(10, 120),
        )
        if not resp.ok:
            body = resp.text.strip()
            resp.close()
            raise RuntimeError(
                f"speech HTTP {resp.status_code}: {body or resp.reason}"
            )
        return resp

    def ask(self, question: str, *, mode: str = "text", trace: bool = True) -> dict:
        """Send one final user turn to Assistant Core.

        `mode` is important: voice turns must be sent as ``voice`` so the backend
        can choose spoken wording after the turn interpreter classifies the
        utterance.  ``debug=true`` and ``X-NIA-Debug-Trace`` are intentionally
        harmless if the backend does not implement tracing yet, while allowing a
        trace-enabled backend to return each planning/execution layer.
        """
        if not self._authenticated:
            self.login()

        headers = {}
        params: dict[str, str] = {}
        if trace:
            headers["X-NIA-Debug-Trace"] = "1"
            params["debug"] = "true"

        started = time.perf_counter()
        resp = self._http.post(
            f"{self.base_url}/api/assistant/query",
            headers=headers,
            params=params,
            json={
                "question": question,
                "mode": mode,
                "conversation_id": self.conversation_id,
            },
            timeout=60,
        )
        http_ms = (time.perf_counter() - started) * 1000.0

        if not resp.ok:
            # Include the backend body because FastAPI 422/500 details are much
            # more useful than a generic requests exception during development.
            body = resp.text.strip()
            raise RuntimeError(
                f"assistant HTTP {resp.status_code} after {http_ms:.1f} ms: {body or resp.reason}"
            )

        data = resp.json()
        if data.get("conversation_id"):
            self.conversation_id = data["conversation_id"]

        # Client-only diagnostics use a leading underscore so they cannot be
        # confused with server-generated planning fields.
        data["_client_http_ms"] = round(http_ms, 3)
        data["_client_mode"] = mode
        return data


class WhisperClient:
    """Sends raw PCM to the local whisper service for one-shot transcription."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict:
        resp = requests.get(f"{self.base_url}/health", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def transcribe(self, pcm: bytes, sample_rate: int = SAMPLE_RATE) -> str:
        resp = requests.post(
            f"{self.base_url}/v1/transcribe",
            params={"sample_rate": sample_rate},
            data=pcm,
            headers={"Content-Type": "application/octet-stream"},
            timeout=120,
        )
        resp.raise_for_status()
        return (resp.json().get("text") or "").strip()


# --------------------------------------------------------------------------- #
# Microphone capture with a simple auto-calibrated energy VAD
# --------------------------------------------------------------------------- #
def _rms(block: bytes) -> float:
    import numpy as np

    if len(block) < 2:
        return 0.0
    samples = np.frombuffer(block, dtype=np.int16).astype("float32")
    if samples.size == 0:
        return 0.0
    return float((samples**2).mean() ** 0.5)


class Microphone:
    def __init__(self) -> None:
        try:
            import sounddevice as sd  # noqa: F401
        except Exception as exc:  # pragma: no cover
            sys.exit(
                "Microphone capture needs 'sounddevice' and 'numpy'.\n"
                "  pip install sounddevice numpy\n"
                f"(import error: {exc})"
            )
        import sounddevice as sd

        self._sd = sd
        self._stream = sd.RawInputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK_FRAMES
        )
        self._stream.start()

    def read_block(self) -> bytes:
        data, _overflow = self._stream.read(BLOCK_FRAMES)
        return bytes(data)

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass

    def calibrate(self, seconds: float = 1.0) -> tuple[float, float]:
        """Measure ambient noise and derive start/stop speech thresholds."""
        blocks = max(1, int(seconds * 1000 / BLOCK_MS))
        floor = 0.0
        for _ in range(blocks):
            floor = max(floor, _rms(self.read_block()))
        start = max(floor * 2.2, 380.0)
        stop = max(floor * 1.5, 240.0)
        return start, stop

    def listen_utterance(
        self,
        start_thresh: float,
        stop_thresh: float,
        *,
        silence_ms: int = 1400,
        min_ms: int = 300,
        max_ms: int = 20000,
    ) -> bytes:
        """Block until speech starts, then return PCM up to the trailing pause."""
        silence_blocks = silence_ms // BLOCK_MS
        min_blocks = min_ms // BLOCK_MS
        max_blocks = max_ms // BLOCK_MS
        speaking = False
        quiet = 0
        collected: list[bytes] = []
        while True:
            block = self.read_block()
            level = _rms(block)
            if not speaking:
                if level >= start_thresh:
                    speaking = True
                    collected.append(block)
                    quiet = 0
                continue
            collected.append(block)
            if level < stop_thresh:
                quiet += 1
            else:
                quiet = 0
            if quiet >= silence_blocks and len(collected) >= min_blocks:
                break
            if len(collected) >= max_blocks:
                break
        return b"".join(collected)


# --------------------------------------------------------------------------- #
# Optional local text-to-speech (offline, no API key)
# --------------------------------------------------------------------------- #
class Speaker:
    """Speaks answers aloud using whatever the OS already provides.

    Backends are tried in order and the chosen one is reported at startup, so
    "I hear nothing" is always distinguishable from "TTS failed". Windows SAPI5
    is driven through PowerShell, which needs no pip install at all.

    Failures are reported once rather than swallowed — silent degradation is
    indistinguishable from a broken microphone from the user's side.
    """

    def __init__(
        self,
        enabled: bool = True,
        *,
        voice: str | None = None,
        rate: int = 0,
        preference: str = "male",
    ) -> None:
        self.backend: str | None = None
        self._engine = None
        self._voice = voice
        self._rate = rate
        self.preference = preference
        self._warned = False
        self._proc: subprocess.Popen | None = None
        if not enabled:
            self.backend = "off"
            return

        # 1. pyttsx3 if the user installed it (cross-platform, in-process).
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            # pyttsx3 rate is words-per-minute (~200 default); map the same
            # -10..10 scale used for SAPI5 onto a sensible wpm.
            self._engine.setProperty("rate", 200 + int(rate) * 20)
            self._select_pyttsx3_voice()
            self.backend = "pyttsx3"
            return
        except Exception:
            self._engine = None

        # 2. Built-in OS voices — no dependency required.
        if sys.platform == "win32" and shutil.which("powershell"):
            self.backend = "sapi5"
        elif sys.platform == "darwin" and shutil.which("say"):
            self.backend = "say"
        elif shutil.which("spd-say"):
            self.backend = "spd-say"
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            self.backend = "espeak"
        else:
            self.backend = None

    @property
    def available(self) -> bool:
        return self.backend not in (None, "off")

    def describe(self) -> str:
        if self.backend == "off":
            return "speech off (--no-speak)"
        if self.backend is None:
            hint = (
                "pip install pyttsx3"
                if sys.platform != "win32"
                else "PowerShell not found on PATH"
            )
            return f"no speech backend available ({hint})"
        return f"local {self.preference} speech via {self.backend}"

    def set_preference(self, preference: str) -> None:
        self.preference = "female" if preference == "female" else "male"
        if self._engine is not None:
            self._select_pyttsx3_voice()
        if self._proc is not None:
            self.close()

    def _select_pyttsx3_voice(self) -> None:
        if self._engine is None:
            return
        voices = list(self._engine.getProperty("voices") or [])
        if self._voice:
            selected = next(
                (
                    item
                    for item in voices
                    if self._voice.lower() in (getattr(item, "name", "") or "").lower()
                ),
                None,
            )
        else:
            selected = next(
                (
                    item
                    for item in voices
                    if self.preference in str(getattr(item, "gender", "")).lower()
                ),
                None,
            )
        if selected is not None:
            self._engine.setProperty("voice", selected.id)

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text or not self.available:
            return
        try:
            if self.backend == "pyttsx3":
                self._engine.say(text)
                self._engine.runAndWait()
            elif self.backend == "sapi5":
                self._speak_sapi5(text)
            elif self.backend == "say":
                voice = "Samantha" if self.preference == "female" else "Alex"
                subprocess.run(["say", "-v", voice, text], check=False)
            elif self.backend == "spd-say":
                subprocess.run(["spd-say", "-w", text], check=False)
            elif self.backend == "espeak":
                binary = shutil.which("espeak-ng") or "espeak"
                voice = "en+f3" if self.preference == "female" else "en+m3"
                subprocess.run([binary, "-v", voice, text], check=False)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if not self._warned:
                self._warned = True
                print(f"[speech failed via {self.backend}: {exc}]")

    def _speak_sapi5(self, text: str) -> None:
        """Windows built-in voices via one long-lived PowerShell process.

        Spawning PowerShell per utterance costs ~170ms; this keeps a single
        synthesizer warm and streams one line of text per turn. Newlines are
        escaped so a multi-line answer stays a single message.
        """
        proc = self._ensure_sapi5_process()
        payload = text.replace("\r", " ").replace("\n", " ").strip()
        proc.stdin.write(payload + "\n")
        proc.stdin.flush()
        # The worker echoes a sentinel once playback finishes, so turns stay
        # ordered and the next prompt does not talk over the answer.
        while True:
            line = proc.stdout.readline()
            if not line or line.strip() == "__SPOKEN__":
                break

    def _ensure_sapi5_process(self) -> subprocess.Popen:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        select_voice = ""
        if self._voice:
            select_voice = (
                f"try {{ $s.SelectVoice((($s.GetInstalledVoices() | "
                f"Where-Object {{ $_.VoiceInfo.Name -like '*{self._voice}*' }} | "
                f"Select-Object -First 1).VoiceInfo.Name)) }} catch {{}};"
            )
        else:
            gender = "Female" if self.preference == "female" else "Male"
            select_voice = (
                f"try {{ $v = $s.GetInstalledVoices() | Where-Object {{ "
                f"$_.VoiceInfo.Gender -eq '{gender}' }} | Select-Object -First 1; "
                "if ($v) { $s.SelectVoice($v.VoiceInfo.Name) } } catch {};"
            )
        script = (
            "Add-Type -AssemblyName System.Speech;"
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
            f"$s.Rate = {int(self._rate)};"
            f"{select_voice}"
            "while (($line = [Console]::In.ReadLine()) -ne $null) {"
            "  if ($line.Trim()) { $s.Speak($line) }"
            "  [Console]::Out.WriteLine('__SPOKEN__');"
            "  [Console]::Out.Flush();"
            "}"
        )
        self._proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        return self._proc

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.stdin.close()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.kill()
        self._proc = None


class BackendSpeaker:
    """Play authenticated xAI/Kokoro PCM while credentials stay on the backend."""

    def __init__(
        self,
        assistant: AssistantClient,
        enabled: bool = True,
        *,
        preference: str = "male",
    ) -> None:
        self.assistant = assistant
        self.preference = "female" if preference == "female" else "male"
        self.backend = "backend" if enabled else "off"
        self._warned = False
        self._sounddevice = None
        if enabled:
            try:
                import sounddevice as sd

                self._sounddevice = sd
            except Exception:
                self.backend = None

    @property
    def available(self) -> bool:
        return self.backend == "backend" and self._sounddevice is not None

    def describe(self) -> str:
        if self.backend == "off":
            return "speech off (--no-speak)"
        if not self.available:
            return "backend speech unavailable (install sounddevice)"
        voice = "ara" if self.preference == "female" else "rex"
        return f"authenticated backend speech via {voice} ({self.preference})"

    def set_preference(self, preference: str) -> None:
        self.preference = "female" if preference == "female" else "male"

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text or not self.available:
            return
        try:
            with self.assistant.synthesize(text, self.preference) as response:
                sample_rate = int(response.headers.get("X-Audio-Sample-Rate", "24000"))
                with self._sounddevice.RawOutputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                ) as output:
                    pending = b""
                    for chunk in response.iter_content(chunk_size=4096):
                        if not chunk:
                            continue
                        audio = pending + chunk
                        aligned = len(audio) - (len(audio) % 2)
                        if aligned:
                            output.write(audio[:aligned])
                        pending = audio[aligned:]
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if not self._warned:
                self._warned = True
                print(f"[backend speech failed: {exc}]")

    def close(self) -> None:
        return None


# --------------------------------------------------------------------------- #
# Output helpers
# --------------------------------------------------------------------------- #
def _short_json(value: Any, *, max_chars: int = 3000) -> str:
    try:
        rendered = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except Exception:
        rendered = repr(value)
    if len(rendered) > max_chars:
        rendered = rendered[:max_chars] + f"\n... <truncated {len(rendered) - max_chars} chars>"
    return rendered


def _trace_value(data: dict, *names: str) -> Any:
    for name in names:
        if name in data and data[name] not in (None, "", [], {}):
            return data[name]
    return None


def print_layer_trace(data: dict, *, raw_response: bool = False) -> None:
    """Print backend layer outputs when present.

    The function deliberately accepts several field names so it works while the
    backend trace contract is evolving.  A trace-enabled backend can either send
    a list under ``debug_trace``/``trace``/``layers`` or expose the common
    planning fields individually.
    """
    print("  ── layer trace ─────────────────────────────────────────")
    print(f"  client.mode: {_trace_value(data, '_client_mode') or 'unknown'}")
    if data.get("_client_http_ms") is not None:
        print(f"  client.backend_http_ms: {float(data['_client_http_ms']):.3f}")

    # Preferred contract: an ordered list of layer records.
    ordered = _trace_value(data, "debug_trace", "trace", "layers", "pipeline_trace")
    if isinstance(ordered, list):
        for i, layer in enumerate(ordered, 1):
            if isinstance(layer, dict):
                name = layer.get("layer") or layer.get("name") or layer.get("stage") or f"layer_{i}"
                ms = layer.get("duration_ms")
                status = layer.get("status")
                heading = f"  [layer:{name}]"
                if status:
                    heading += f"  status={status}"
                if ms is not None:
                    heading += f"  time={ms} ms"
                print(heading)
                payload = {
                    k: v for k, v in layer.items()
                    if k not in {"layer", "name", "stage", "duration_ms", "status"}
                }
                if payload:
                    for line in _short_json(payload, max_chars=2200).splitlines():
                        print("      " + line)
            else:
                print(f"  [{i}] {_short_json(layer, max_chars=1000)}")
        print("  ───────────────────────────────────────────────────────")
        if raw_response:
            print("  raw backend response:")
            for line in _short_json({k: v for k, v in data.items() if not k.startswith('_')}, max_chars=12000).splitlines():
                print("    " + line)
        return

    # Backward-/forward-compatible flat/nested fields.
    fields = [
        ("normalized input", ("normalized_turn", "normalized_text", "normalized_input")),
        ("conversation resolver", ("conversation_resolution", "resolved_turn", "conversation")),
        ("turn router", ("route", "route_source", "source", "turn_type")),
        ("deterministic parser", ("deterministic", "deterministic_result", "parse_result")),
        ("semantic normalizer", ("canonical_query", "semantic_normalizer", "canonical")),
        ("query plan", ("query_plan", "plan")),
        ("plan validation", ("validation", "validated_plan")),
        ("executor", ("execution", "execution_result", "executor")),
        ("planning timings", ("timings", "planning_timings")),
    ]
    found = False
    for label, aliases in fields:
        value = _trace_value(data, *aliases)
        if value is None:
            continue
        found = True
        print(f"  {label}:")
        for line in _short_json(value, max_chars=2500).splitlines():
            print("    " + line)

    # Always show the high-level route metadata we already receive today.
    summary = {
        key: data.get(key)
        for key in (
            "status", "planner_type", "source", "route_source",
            "reasoning_calls", "conversation_id"
        )
        if data.get(key) is not None
    }
    if summary:
        found = True
        print("  backend summary:")
        for line in _short_json(summary, max_chars=1500).splitlines():
            print("    " + line)

    if not found:
        print("  (backend returned no internal layer trace fields)")
        print("  The CLI requested tracing with ?debug=true and X-NIA-Debug-Trace: 1.")
        print("  Wire the backend to return debug_trace/timings to see internal layers here.")

    if raw_response:
        print("  raw backend response:")
        for line in _short_json({k: v for k, v in data.items() if not k.startswith('_')}, max_chars=12000).splitlines():
            print("    " + line)
    print("  ───────────────────────────────────────────────────────")


def print_answer(data: dict, *, trace: bool = True, raw_response: bool = False) -> None:
    answer = data.get("answer") or "(no answer)"
    print(f"\nAssistant: {answer}")
    citations = data.get("citations") or []
    if citations:
        print("  sources: " + ", ".join(str(c) for c in citations))
    meta = []
    if data.get("planner_type"):
        meta.append(str(data["planner_type"]))
    elif data.get("source"):
        meta.append(str(data["source"]))
    meta.append(f"{data.get('reasoning_calls', 0)} reasoning call(s)")
    if data.get("_client_http_ms") is not None:
        meta.append(f"HTTP {float(data['_client_http_ms']):.1f} ms")
    print("  [" + " · ".join(meta) + "]")
    if trace:
        print_layer_trace(data, raw_response=raw_response)
    print()


def handle_voice_control(text: str, speaker) -> bool:
    """Apply a voice instruction locally without spending a reasoning call."""
    preference = requested_voice_preference(text)
    if preference is None:
        return False
    speaker.set_preference(preference)
    greeting = "Hi, I'm here."
    print(f"\nAssistant: {greeting}")
    print(f"  [voice switched to {preference}]\n")
    speaker.say(greeting)
    return True


# --------------------------------------------------------------------------- #
# Run modes
# --------------------------------------------------------------------------- #
def run_wav(args, assistant: AssistantClient, whisper: WhisperClient, speaker: Speaker) -> None:
    with wave.open(args.wav, "rb") as w:
        rate = w.getframerate()
        pcm = w.readframes(w.getnframes())
    if rate != SAMPLE_RATE:
        print(f"[warning: {args.wav} is {rate} Hz; whisper expects 16000 Hz mono]")
    stt_started = time.perf_counter()
    transcript = whisper.transcribe(pcm, sample_rate=rate)
    stt_ms = (time.perf_counter() - stt_started) * 1000.0
    if not args.no_trace:
        seconds = len(pcm) / 2 / rate if rate else 0.0
        print(f"  [layer:stt] audio={seconds:.3f}s · latency={stt_ms:.3f} ms")
    print(f"\nYou (from {args.wav}): {transcript or '(nothing recognized)'}")
    if not transcript:
        print('Assistant: Sorry, I didn\'t catch that.')
        speaker.say("Sorry, I didn't catch that.")
        return
    if handle_voice_control(transcript, speaker):
        return
    data = assistant.ask(transcript, mode="voice", trace=not args.no_trace)
    data["_client_stt_ms"] = round(stt_ms, 3)
    print_answer(data, trace=not args.no_trace, raw_response=args.raw_response)
    speaker.say(data.get("spoken_text") or data.get("answer") or "")


def run_text(args, assistant: AssistantClient, speaker: Speaker) -> None:
    print("Type a question (blank line or Ctrl+C to quit).")
    while True:
        try:
            question = input("\nYou: ").strip()
        except EOFError:
            break
        if not question:
            break
        if handle_voice_control(question, speaker):
            continue
        # Input is typed, but this remains a voice client: request the concise,
        # citation-free spoken form while still printing the full answer.
        data = assistant.ask(question, mode="voice", trace=not args.no_trace)
        print_answer(data, trace=not args.no_trace, raw_response=args.raw_response)
        speaker.say(data.get("spoken_text") or data.get("answer") or "")


def run_voice(args, assistant: AssistantClient, whisper: WhisperClient, speaker: Speaker) -> None:
    mic = Microphone()
    try:
        if args.push_to_talk:
            _loop_push_to_talk(args, mic, assistant, whisper, speaker)
        else:
            _loop_vad(args, mic, assistant, whisper, speaker)
    finally:
        mic.close()


def _handle_utterance(pcm, assistant, whisper, speaker, *, trace: bool = True, raw_response: bool = False) -> None:
    seconds = len(pcm) / 2 / SAMPLE_RATE
    print(f"[heard {seconds:.1f}s, transcribing…]")

    turn_started = time.perf_counter()
    stt_started = time.perf_counter()
    transcript = whisper.transcribe(pcm)
    stt_ms = (time.perf_counter() - stt_started) * 1000.0

    if trace:
        print(f"  [layer:stt] audio={seconds:.3f}s · latency={stt_ms:.3f} ms")
    if not transcript:
        print("You: (nothing recognized)")
        print('Assistant: Sorry, I didn\'t catch that.')
        speaker.say("Sorry, I didn't catch that.")
        return

    print(f"You: {transcript}")
    if handle_voice_control(transcript, speaker):
        return
    if trace:
        print(f"  [layer:stt.output] {transcript!r}")
        print("  [layer:assistant.input] mode='voice' → POST /api/assistant/query")

    data = assistant.ask(transcript, mode="voice", trace=trace)
    data["_client_stt_ms"] = round(stt_ms, 3)
    data["_client_turn_ms"] = round((time.perf_counter() - turn_started) * 1000.0, 3)
    print_answer(data, trace=trace, raw_response=raw_response)
    if trace:
        print(
            "  [client timing] "
            f"stt={stt_ms:.1f} ms · backend={float(data.get('_client_http_ms', 0.0)):.1f} ms · "
            f"turn={float(data.get('_client_turn_ms', 0.0)):.1f} ms\n"
        )
    speaker.say(data.get("spoken_text") or data.get("answer") or "")


def _loop_vad(args, mic, assistant, whisper, speaker) -> None:
    print("Calibrating ambient noise (stay quiet ~1s)…")
    start_thresh, stop_thresh = mic.calibrate()
    if args.threshold:
        start_thresh = float(args.threshold)
        stop_thresh = start_thresh * 0.65
    print(
        f"Ready. Speak, then pause. (start≈{start_thresh:.0f}, stop≈{stop_thresh:.0f} RMS)  "
        "Ctrl+C to quit.\n"
    )
    while True:
        pcm = mic.listen_utterance(start_thresh, stop_thresh, silence_ms=args.silence_ms)
        _handle_utterance(
            pcm, assistant, whisper, speaker,
            trace=not args.no_trace, raw_response=args.raw_response,
        )


def _loop_push_to_talk(args, mic, assistant, whisper, speaker) -> None:
    print("Push-to-talk. Press Enter to start recording, Enter again to stop. Ctrl+C to quit.\n")
    while True:
        input("[Enter to start] ")
        print("Recording… press Enter to stop.")
        collected: list[bytes] = []
        import threading

        stop = threading.Event()

        def _wait_enter() -> None:
            try:
                input()
            except EOFError:
                pass
            stop.set()

        threading.Thread(target=_wait_enter, daemon=True).start()
        while not stop.is_set():
            collected.append(mic.read_block())
        _handle_utterance(
            b"".join(collected), assistant, whisper, speaker,
            trace=not args.no_trace, raw_response=args.raw_response,
        )


def main() -> None:
    config = _configuration()
    parser = argparse.ArgumentParser(description="Terminal voice agent for the NIA assistant.")
    parser.add_argument("--api", default="http://localhost:8000", help="Assistant backend base URL")
    parser.add_argument("--whisper", default="http://localhost:8090", help="Whisper service base URL")
    parser.add_argument(
        "--user",
        default=_first_config(config, "NIA_CLI_USER", "STANDALONE_DEMO_USERNAME"),
        help="Login username (configured through the environment when omitted)",
    )
    parser.add_argument(
        "--password",
        default=_first_config(config, "NIA_CLI_PASSWORD", "STANDALONE_DEMO_PASSWORD"),
        help="Login password (prefer NIA_CLI_PASSWORD; prompts when unavailable)",
    )
    parser.add_argument(
        "--principal",
        default=_first_config(
            config,
            "NIA_CLI_PRINCIPAL",
            "STANDALONE_DEMO_PRINCIPAL_ID",
        ),
        help="Expected authenticated principal (optional environment-backed check)",
    )
    parser.add_argument("--push-to-talk", action="store_true", help="Enter-gated capture instead of VAD")
    parser.add_argument("--text", action="store_true", help="Type questions instead of speaking")
    # This is a voice agent, so answers are spoken by default when the OS can.
    parser.add_argument(
        "--speak",
        action="store_true",
        help="(default) speak answers through authenticated backend TTS",
    )
    parser.add_argument("--no-speak", action="store_true", help="Print answers only, stay silent")
    parser.add_argument(
        "--local-tts",
        action="store_true",
        help="Use an installed OS voice instead of authenticated backend TTS",
    )
    parser.add_argument("--tts-voice", help="Installed voice substring; implies --local-tts")
    parser.add_argument(
        "--tts-rate", type=int, default=0,
        help="Speaking rate -10..10 (default 0 = natural pace; try 2-3 for faster answers)",
    )
    parser.add_argument(
        "--voice-test",
        action="store_true",
        help="Speak a test sentence to verify audio output, then exit",
    )
    parser.add_argument("--wav", help="Transcribe one 16 kHz mono WAV file and answer, then exit")
    parser.add_argument("--threshold", type=float, help="Override VAD start threshold (RMS)")
    parser.add_argument(
        "--silence-ms",
        type=int,
        default=1400,
        help="Trailing pause that ends a turn (default 1400; 800 chopped natural speech)",
    )
    parser.add_argument(
        "--no-trace", action="store_true",
        help="Hide per-layer development trace output",
    )
    parser.add_argument(
        "--raw-response", action="store_true",
        help="With tracing enabled, also print the complete backend JSON response",
    )
    args = parser.parse_args()

    if not args.user:
        args.user = input("Username: ").strip()
    if not args.user:
        parser.error("a username is required through --user or the environment")
    if not args.password:
        args.password = getpass.getpass(f"Password for {args.user}: ")

    assistant = AssistantClient(
        args.api,
        args.user,
        args.password,
        expected_principal=args.principal,
    )
    whisper = WhisperClient(args.whisper)

    # Fail fast with clear guidance if the stack isn't reachable.
    try:
        info = assistant.login()
    except Exception as exc:
        sys.exit(
            f"Could not authenticate {args.user} at {args.api}: {exc}\n"
            "Is the stack up?  docker compose -f infra/docker-compose.yml up"
        )
    files = ", ".join(str(f) for f in info.get("allowed_file_ids", []))
    print(
        f"Signed in as {args.user} ({info.get('principal_id')}) — "
        f"authorized files: {files or 'none'}"
    )

    if args.no_speak:
        speaker = Speaker(False)
    elif args.local_tts or args.tts_voice:
        speaker = Speaker(
            True,
            voice=args.tts_voice,
            rate=args.tts_rate,
            preference="male",
        )
    else:
        speaker = BackendSpeaker(assistant, True, preference="male")
        if not speaker.available:
            print("[backend audio unavailable; falling back to an installed OS voice]")
            speaker = Speaker(True, rate=args.tts_rate, preference="male")

    if args.voice_test:
        print(f"Speech backend: {speaker.describe()}")
        if not speaker.available:
            sys.exit(
                "No speech backend. Install sounddevice for backend audio, or "
                "use --local-tts with an available OS voice."
            )
        print("Speaking a test sentence - you should hear it now...")
        speaker.say("Voice output is working. I am the Nia research assistant.")
        print("Done. If you heard nothing, check your output device and volume.")
        speaker.close()
        return

    if not args.text:
        try:
            h = whisper.health()
            print(f"Whisper: {h.get('engine')} / {h.get('model')}")
            if h.get("engine") == "scripted":
                print("[note: whisper is the scripted stub — rebuild the whisper image for real transcription]")
        except Exception as exc:
            sys.exit(f"Could not reach whisper at {args.whisper}: {exc}")

    print(f"Speech: {speaker.describe()}")
    if not speaker.available and not args.no_speak:
        print("[answers will be printed only — run with --voice-test to diagnose audio]")

    if not args.no_trace:
        print("Trace: ON (use --no-trace to hide layer output; --raw-response for full backend JSON)")
    print()
    try:
        if args.wav:
            run_wav(args, assistant, whisper, speaker)
        elif args.text:
            run_text(args, assistant, speaker)
        else:
            run_voice(args, assistant, whisper, speaker)
    except KeyboardInterrupt:
        print("\nBye.")
    finally:
        speaker.close()


if __name__ == "__main__":
    main()
