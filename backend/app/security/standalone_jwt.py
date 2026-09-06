from datetime import UTC, datetime, timedelta

import jwt

from app.config import Settings
from app.security.access_scope import AccessScope
from app.security.auth_adapter import AuthAdapter


class AuthError(Exception):
    pass


class StandaloneJwtAuthAdapter(AuthAdapter):
    """Phase 1 adapter. Issues and verifies standalone JWTs that carry AccessScope."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate_password(self, username: str, password: str) -> AccessScope:
        configured_username = self._settings.standalone_demo_username
        configured_password = self._settings.standalone_demo_password
        configured_principal = self._settings.standalone_demo_principal_id
        if (
            not configured_username
            or not configured_password
            or not configured_principal
            or username != configured_username
            or password != configured_password
        ):
            raise AuthError("invalid credentials")
        return AccessScope(
            principal_id=configured_principal,
            allowed_file_ids=tuple(self._settings.demo_allowed_file_ids),
            can_use_private_files=self._settings.standalone_demo_can_use_private_files,
            history_allowed=self._settings.standalone_demo_history_allowed,
            display_name=username,
        )

    def issue_token(self, scope: AccessScope) -> str:
        now = datetime.now(UTC)
        payload = {
            "iss": self._settings.jwt_issuer,
            "sub": scope.principal_id,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=self._settings.jwt_ttl_seconds)).timestamp()),
            "allowed_file_ids": list(scope.allowed_file_ids),
            "can_use_private_files": scope.can_use_private_files,
            "history_allowed": scope.history_allowed,
            "display_name": scope.display_name,
        }
        return jwt.encode(payload, self._settings.jwt_secret, algorithm="HS256")

    def resolve_scope(self, credentials: str) -> AccessScope:
        token = credentials.removeprefix("Bearer ").strip()
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=["HS256"],
                issuer=self._settings.jwt_issuer,
            )
        except jwt.PyJWTError as exc:
            raise AuthError("invalid token") from exc

        return AccessScope(
            principal_id=str(payload["sub"]),
            allowed_file_ids=tuple(payload.get("allowed_file_ids") or ()),
            can_use_private_files=bool(payload.get("can_use_private_files", False)),
            history_allowed=bool(payload.get("history_allowed", False)),
            display_name=str(payload["display_name"]) if payload.get("display_name") else None,
        )
