# Deploy and privilege notes

## Environments

| `APP_ENV` | Privilege self-test | Postgres down |
|---|---|---|
| `development` | runs if `FAIL_CLOSED_ON_PRIVILEGE_ERROR=true` | API still boots for UI work |
| `test` | skipped | n/a |
| `production` | **always** runs | process exits |

Production must use `assistant_runtime` only. Never point `ASSISTANT_DATABASE_URL` at a website/app role.

Production startup rejects missing or unsafe authentication, LiveKit, and cookie settings. Populate all secret values through the deployment environment or a secret manager. At minimum:

```text
APP_ENV=production
AUTH_COOKIE_SECURE=true
JWT_SECRET=<secret-manager reference>
LIVEKIT_API_SECRET=<secret-manager reference>
AUTH_ADAPTER=website
WEBSITE_JWT_SECRET=<separate secret-manager reference>
WEBSITE_JWT_ISSUER=<configured issuer>
WEBSITE_JWT_AUDIENCE=<configured audience>
```

Keep `CORS_ORIGINS` restricted to the browser origin. Cookie-authenticated browser mutations validate that origin. Only enable `TRUST_PROXY_HEADERS` behind a trusted proxy that overwrites forwarded headers.

```bash
cd backend
uv sync
uv run python -m app.db.migrate
uv run python -m app.db.privilege_selftest
```

Against an existing research database:

```bash
APPLY_APP_STUBS=false
ASSISTANT_MIGRATOR_DATABASE_URL=<secret-manager DSN>
ASSISTANT_DATABASE_URL=<secret-manager DSN>
```

## Compose

Reasoning uses `REASONING_PROVIDER=http` against `REASONING_BASE_URL`. Set
`REASONING_PROVIDER=xai` to fall back to the gRPC SDK against api.x.ai, which needs an
api.x.ai key rather than the bridge token.

Run these from the repository root. `--env-file .env` is not optional: `-f infra/...` makes
`infra/` the project directory, so compose looks for `infra/.env` when it interpolates
`${POSTGRES_PASSWORD}` and friends. Without it the stack stops at `required variable
POSTGRES_PASSWORD is missing a value` before building anything.

Default stack (xAI TTS when `XAI_API_KEY` is set):

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

High-traffic local TTS:

```bash
docker compose --env-file .env -f infra/docker-compose.yml -f infra/docker-compose.kokoro.yml up --build
```

Open http://localhost:3000 and sign in with the standalone credentials stored in your untracked `.env` file.

Planning defaults to `PLANNER_MODE=ai`. To roll back to the previous compiler path:

```bash
PLANNER_MODE=legacy
```

Restart backend and the LiveKit agent so cached settings reload. Do not reset the Postgres volume. See [phase-2-ai-planner-rollout.md](phase-2-ai-planner-rollout.md).

The LiveKit agent entrypoint must stay a **module-level** function (`app.realtime.agent._agent_entry`). Nested closures cannot be pickled by the worker process pool.

On WSL2, set `infra/livekit.yaml` `rtc.node_ip` to the current VM address (`ip -4 addr show eth0`) and recreate the LiveKit container if voice connects but has no media. Rebuild `agent` and `migrate` after backend changes; those images are not bind-mounted.

## Paid vs local

| Path | Provider |
|---|---|
| Reasoning when needed | `grok-4.20-0309-non-reasoning` |
| Spoken TTS (default) | xAI WebSocket |
| Spoken TTS (high traffic) | Kokoro-FastAPI (`TTS_PROVIDER=kokoro`) |
| STT | local whisper.cpp |
| VAD / turns | Silero + LiveKit (self-hosted) |
| Retrieval | PostgreSQL FTS / `pg_trgm` / RapidFuzz |

Text mode never starts TTS.

## Eval

```bash
python -m pytest tests/test_eval_suite.py tests/test_privilege_boundary.py -q
```

`RUN_DB_TESTS=1` enables the live privilege self-test against an isolated `assistant_runtime` database.

## Rollback

See [rollback.md](rollback.md). Dropping `assistant` / `assistant_api` does not modify research rows.
