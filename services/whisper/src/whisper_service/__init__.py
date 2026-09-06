"""Independent local STT service. Do not import Assistant Core from here."""

from whisper_service.protocol import TranscriptEvent
from whisper_service.session import WhisperSession

__all__ = ["TranscriptEvent", "WhisperSession"]
