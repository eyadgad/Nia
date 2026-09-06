"""Test defaults. Production/application default is PLANNER_MODE=ai (Phase 2).

Legacy planner tests stay on the rollback path unless a test opts into AI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings


@pytest.fixture(autouse=True)
def _legacy_planner_unless_ai_requested(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    wants_ai = "ai_settings" in request.fixturenames or request.node.get_closest_marker("planner_ai")
    monkeypatch.setenv("PLANNER_MODE", "ai" if wants_ai else "legacy")
    monkeypatch.setenv("LIVEKIT_API_KEY", "unit-test-key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "unit-test-livekit-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
