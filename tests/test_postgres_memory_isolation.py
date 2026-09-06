import os
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.memory.postgres import PostgresMemoryStore, record_from_snapshot
from app.memory.types import ConversationRecord
from app.security.access_scope import AccessScope


class _AsyncContext:
    def __init__(self, value=None) -> None:
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


class _Pool:
    def __init__(self, connection) -> None:
        self.connection = connection

    def acquire(self):
        return _AsyncContext(self.connection)


class _Connection:
    def __init__(self, *, selected=None, saved_owner=None) -> None:
        self.selected = selected
        self.saved_owner = saved_owner
        self.executed: list[str] = []

    def transaction(self):
        return _AsyncContext()

    async def fetchrow(self, query, *_args):
        if "INSERT INTO assistant.conversations" in query:
            return self.saved_owner
        return self.selected

    async def execute(self, query, *_args):
        self.executed.append(query)


def _scope(principal_id: str) -> AccessScope:
    return AccessScope(principal_id=principal_id, allowed_file_ids=(49, 91))


@pytest.mark.asyncio
async def test_postgres_get_rejects_a_foreign_conversation():
    connection = _Connection(
        selected={
            "id": "00000000-0000-0000-0000-000000000001",
            "principal_id": "owner-a",
            "title": None,
            "rolling_summary": None,
            "active_query_state": {},
        }
    )
    store = PostgresMemoryStore(_Pool(connection))

    with pytest.raises(PermissionError):
        await store.get_or_create(
            _scope("owner-b"), "00000000-0000-0000-0000-000000000001"
        )

    assert connection.executed == []


@pytest.mark.asyncio
async def test_postgres_save_checks_owner_before_replacing_messages():
    connection = _Connection(saved_owner=None)
    store = PostgresMemoryStore(_Pool(connection))
    record = ConversationRecord(
        id="00000000-0000-0000-0000-000000000001",
        principal_id="owner-b",
        recent_turns=[{"role": "user", "text": "do not overwrite"}],
    )

    with pytest.raises(PermissionError):
        await store.save(record)

    assert not any("DELETE FROM assistant.messages" in query for query in connection.executed)


@pytest.mark.asyncio
async def test_postgres_save_upserts_stable_messages_without_rewriting_timestamps():
    connection = _Connection(saved_owner={"principal_id": "owner-a"})
    store = PostgresMemoryStore(_Pool(connection))
    record = ConversationRecord(
        id="00000000-0000-0000-0000-000000000001",
        principal_id="owner-a",
        recent_turns=[{"role": "user", "text": "first message"}],
    )

    await store.save(record)
    first_id = record.recent_turns[0]["message_id"]
    first_created_at = record.recent_turns[0]["created_at"]
    await store.save(record)

    assert record.recent_turns[0]["message_id"] == first_id
    assert record.recent_turns[0]["created_at"] == first_created_at
    assert not any("DELETE FROM assistant.messages" in query for query in connection.executed)
    message_upserts = [
        query for query in connection.executed if "INSERT INTO assistant.messages" in query
    ]
    assert len(message_upserts) == 2
    assert all("ON CONFLICT (id) DO UPDATE" in query for query in message_upserts)


def test_snapshot_cannot_change_the_validated_owner():
    restored = record_from_snapshot(
        {
            "id": "00000000-0000-0000-0000-000000000001",
            "principal_id": "attacker",
        },
        "validated-owner",
    )

    assert restored.principal_id == "validated-owner"


@pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="requires isolated local PostgreSQL")
@pytest.mark.asyncio
async def test_live_postgres_cannot_overwrite_another_principals_conversation():
    pool = await asyncpg.create_pool(dsn=os.environ["ASSISTANT_DATABASE_URL"])
    conversation_id = str(uuid4())
    store = PostgresMemoryStore(pool)
    try:
        original = ConversationRecord(
            id=conversation_id,
            principal_id="isolation-owner-a",
            recent_turns=[{"role": "user", "text": "owner A content"}],
        )
        await store.save(original)

        with pytest.raises(PermissionError):
            await store.get_or_create(_scope("isolation-owner-b"), conversation_id)

        restored = await store.get(_scope("isolation-owner-a"), conversation_id)
        assert restored is not None
        assert restored.recent_turns[0]["text"] == "owner A content"
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM assistant.conversations WHERE id = $1::uuid",
                conversation_id,
            )
        await pool.close()
