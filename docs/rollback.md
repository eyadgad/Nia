# Rollback and privilege recovery

## Planner mode rollback (Phase 2)

The application default is `PLANNER_MODE=ai`. Restore the legacy compiler without deleting AI traces:

```bash
# WSL / Compose — one step
PLANNER_MODE=legacy docker compose --env-file .env -f infra/docker-compose.yml up -d backend agent
```

Or set `PLANNER_MODE=legacy` in `.env` and restart `backend` and `agent`. Confirm `GET /ready` is healthy, then run one public smoke (`How many records are in the master list?` on file 49) and one private smoke (`How many records are in additional deaths?` on file 93 with a granted principal). Settings are process-cached: a restart is required.

Rolling the mode back must not drop `assistant.query_traces`, `assistant.audit_events`, or benchmark JSON artifacts.

Immediate rollback triggers: any dataset-scope violation, unauthorized gateway read, Sev-1/2 planner incident, recurrence of a named condition-loss failure, or a database-truth failure attributable to planning.

# Privilege recovery

Privilege self-test (`python -m app.db.privilege_selftest`) must fail closed in production if `assistant_runtime` can `SELECT` `users`, `otps`, `logs`, `support_*`, or the raw `file` / `file_data` tables. Fix grants, then re-run the self-test before serving traffic.

# Migration rollback

Assistant objects live in `assistant` and `assistant_api`. They do not alter application research rows.

To remove the assistant layer from a database:

```sql
DROP SCHEMA IF EXISTS assistant_api CASCADE;
DROP SCHEMA IF EXISTS assistant CASCADE;
DROP TABLE IF EXISTS public.assistant_schema_migrations;
```

Do not drop `assistant_runtime` until no application process uses that role. Local stub tables in `public` should only exist in the compose development database.

Assistant-owned retention (result sets, query traces, audit events) can be purged without touching research data:

```bash
cd backend
uv run python -c "import asyncio; from app.observability.jobs import MemoryJobQueue; from app.observability.worker import handle_job; q=MemoryJobQueue(); asyncio.run(q.enqueue('retention'));"
```

Prefer `python -m app.observability.worker` against a live pool so `RetentionService.purge_postgres` runs.
