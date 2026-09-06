from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TranscriptEvent(BaseModel):
    type: Literal["partial", "final"]
    text: str
    start_ms: int = 0
    end_ms: int = 0
    confidence: float = 0.0
    speech: bool = True


class TranscriptResult(BaseModel):
    text: str
    speech: bool = True
    confidence: float = 0.7
    start_ms: int = 0
    end_ms: int = 0


class ControlMessage(BaseModel):
    type: Literal["reset", "finalize", "config"]
    sample_rate: int | None = Field(default=None, ge=8000, le=48000)
    language: str | None = None
