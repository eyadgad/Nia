"""Where a tester's report goes.

The testing build asks people to click Report, write their name and what they saw, and
submit. This is the only writer of assistant.feedback, which had sat unused since the early
tables.

Same shape as the conversation store above it: a Postgres implementation for the running
stack and a process-local one for tests, chosen the same way, so a report is never lost to a
missing pool during a test run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.security.access_scope import AccessScope

# A report is written by hand, so the ceilings are about keeping a stray paste out of the
# database rather than about what anyone is likely to type.
MAX_NAME = 120
MAX_COMMENT = 4000


@dataclass(frozen=True)
class FeedbackReport:
    comment: str
    reporter_name: str = ""
    conversation_id: str | None = None
    principal_id: str = ""
    app_version: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class FeedbackStore(Protocol):
    async def record(self, scope: AccessScope, report: FeedbackReport) -> None: ...


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self.reports: list[FeedbackReport] = []

    async def record(self, scope: AccessScope, report: FeedbackReport) -> None:
        self.reports.append(report)


class PostgresFeedbackStore:
    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def record(self, scope: AccessScope, report: FeedbackReport) -> None:
        """Store one report, keeping the conversation link only when it is the writer's own.

        An unrecognised or someone else's conversation id is dropped rather than refused:
        the finding is the point, and losing it to a bad link would be the wrong trade. The
        foreign key would reject it anyway, taking the report with it.
        """
        conversation_id = report.conversation_id or None
        if conversation_id is not None:
            async with self._pool.acquire() as conn:
                owned = await conn.fetchval(
                    """
                    SELECT 1 FROM assistant.conversations
                    WHERE id = $1::uuid AND principal_id = $2
                    """,
                    conversation_id,
                    scope.principal_id,
                )
            if not owned:
                conversation_id = None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO assistant.feedback
                    (conversation_id, comment, reporter_name, principal_id, app_version,
                     category, rating)
                VALUES ($1::uuid, $2, $3, $4, $5, 'tester_report', NULL)
                """,
                conversation_id,
                report.comment,
                report.reporter_name or None,
                scope.principal_id,
                report.app_version or None,
            )


_DEFAULT_FEEDBACK_STORE = InMemoryFeedbackStore()


def default_feedback_store() -> FeedbackStore:
    try:
        from app.db.pool import get_pool

        return PostgresFeedbackStore(get_pool())
    except Exception:
        return _DEFAULT_FEEDBACK_STORE
