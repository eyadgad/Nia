import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import Settings
from app.main import create_app
from app.security.auth_adapter import get_auth_adapter
from app.security.standalone_jwt import AuthError, StandaloneJwtAuthAdapter
from app.security.website_adapter import WebsiteAuthAdapter


def test_standalone_login_issues_scope_and_token():
    settings = Settings(
        jwt_secret="unit-test-secret",
        standalone_demo_username="test-user",
        standalone_demo_password="unit-test-password",
        standalone_demo_principal_id="test-principal",
        standalone_demo_allowed_file_ids="49,91",
    )
    adapter = StandaloneJwtAuthAdapter(settings)
    scope = asyncio.run(adapter.authenticate_password("test-user", "unit-test-password"))
    assert scope.allowed_file_ids == (49, 91)
    token = adapter.issue_token(scope)
    resolved = adapter.resolve_scope(f"Bearer {token}")
    assert resolved.principal_id == scope.principal_id
    assert resolved.allowed_file_ids == (49, 91)
    assert scope.display_name == "test-user"
    assert resolved.display_name == "test-user"


def test_standalone_rejects_bad_password():
    adapter = StandaloneJwtAuthAdapter(
        Settings(
            jwt_secret="unit-test-secret",
            standalone_demo_username="test-user",
            standalone_demo_password="unit-test-password",
            standalone_demo_principal_id="test-principal",
        )
    )
    try:
        asyncio.run(adapter.authenticate_password("test-user", "nope"))
    except AuthError:
        return
    raise AssertionError("expected AuthError")


def test_standalone_rejects_login_when_credentials_are_unconfigured():
    adapter = StandaloneJwtAuthAdapter(
        Settings(
            jwt_secret="unit-test-secret",
            standalone_demo_username="",
            standalone_demo_password="",
            standalone_demo_principal_id="",
        )
    )
    with pytest.raises(AuthError):
        asyncio.run(adapter.authenticate_password("", ""))


def test_website_adapter_validates_signed_access_scope_and_issues_session():
    settings = Settings(
        jwt_secret="assistant-session-secret-that-is-long-enough",
        website_jwt_secret="website-signing-secret-that-is-long-enough",
        website_jwt_issuer="test-website",
        website_jwt_audience="test-assistant",
    )
    adapter = WebsiteAuthAdapter(settings)
    now = datetime.now(UTC)
    website_token = jwt.encode(
        {
            "iss": "test-website",
            "aud": "test-assistant",
            "sub": "opaque-user-25",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "allowed_file_ids": [49, 91],
            "can_use_private_files": False,
            "history_allowed": False,
        },
        settings.website_jwt_secret,
        algorithm="HS256",
    )

    scope = adapter.resolve_scope(f"Bearer {website_token}")
    session_token = adapter.issue_token(scope)
    restored = adapter.resolve_scope(session_token)

    assert scope.principal_id == "opaque-user-25"
    assert restored == scope


def test_website_adapter_rejects_password_login():
    adapter = WebsiteAuthAdapter(Settings())
    try:
        asyncio.run(adapter.authenticate_password("anyone", "x"))
    except AuthError:
        return
    raise AssertionError("website mode must not authenticate against assistant tables")


def test_browser_login_uses_http_only_cookie_instead_of_response_token():
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
        response = client.post(
            "/api/auth/login",
            json={"username": "test-user", "password": "unit-test-password"},
        )
        restored = client.get("/api/auth/me")

    assert response.status_code == 200
    assert "token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert restored.status_code == 200
    assert restored.json()["principal_id"] == settings.standalone_demo_principal_id


def test_first_browser_visit_has_an_anonymous_session_response_without_401():
    response = TestClient(create_app()).get("/api/auth/session")

    assert response.status_code == 204
