# NIA Standalone Assistant

Standalone text + voice research assistant with both demo authentication and a signed-token adapter for the existing NIA website.

## Layout

```text
frontend/          Next.js chat + voice UI
backend/           FastAPI Assistant Core
services/whisper/  local streaming STT (Phase C)
infra/             Docker Compose, self-hosted LiveKit, Postgres init
docs/              architecture and access matrix
tests/             cross-cutting security and eval tests
repositories/      reference clones only — do not edit
```

## Quick start

1. Copy `.env.example` to `.env` and set secrets.
2. Start the local stack:

```bash
docker compose -f infra/docker-compose.yml up --build
```

3. Open http://localhost:3000
4. Sign in with the standalone credentials configured in your untracked `.env` file.

Planning defaults to `PLANNER_MODE=ai`: one structured planner call, selected-list scope only, self-review on executable data, and no deterministic semantic fallback after an AI failure. Set `PLANNER_MODE=legacy` and restart to use the previous compiler path as an emergency rollback. See [docs/phase-2-ai-planner-rollout.md](docs/phase-2-ai-planner-rollout.md).

The backend talks to PostgreSQL as `assistant_runtime`. It never uses the website application role and never reads `users`, `roles`, `otps`, `logs`, or `support_*`. Production startup (`APP_ENV=production`) always runs the privilege self-test and refuses to boot if it fails.

Browser authentication uses an HttpOnly session cookie; JWTs are not stored in `localStorage`. In website mode, the existing website signs a short-lived HS256 token with `sub`, `allowed_file_ids`, `can_use_private_files`, and `history_allowed`, then calls `POST /api/auth/session` with that bearer token. Configure `AUTH_ADAPTER=website` plus `WEBSITE_JWT_SECRET`, `WEBSITE_JWT_ISSUER`, and `WEBSITE_JWT_AUDIENCE`. Password authentication remains outside the assistant.

`GET /health` is liveness-only. `GET /ready` verifies PostgreSQL, Whisper, LiveKit, and reasoning-provider configuration. Login, query, and LiveKit-token routes also have per-process rate limits; put a shared gateway limiter in front when running multiple replicas.

One-shot background job claim (retention, FTS rebuild, alias rebuild):

```bash
cd backend
uv run python -m app.observability.worker
```

To apply assistant schemas against an **existing** research database, set `APPLY_APP_STUBS=false` and point `ASSISTANT_MIGRATOR_DATABASE_URL` at a migrator role, then run:

```bash
cd backend
uv sync
uv run python -m app.db.migrate
uv run python -m app.db.privilege_selftest
```

## Paid providers

Only reasoning (`grok-4.20-0309-non-reasoning`) and spoken TTS (xAI, later Kokoro) are paid. STT is local whisper.cpp.

## Voice

Compose starts a self-hosted LiveKit server and an agent worker (`python -m app.realtime.worker start`). After sign-in, **Connect voice** mints a 15-minute room token that carries the signed `AccessScope` and dispatches `nia-research-assistant`. The agent transcribes with the local whisper service, uses Silero VAD for turns, and runs Assistant Core in `on_user_turn_completed` before any reply. Spoken phrases go through `TTSProvider` (xAI WebSocket by default). Set `TTS_PROVIDER=kokoro` to use self-hosted Kokoro-FastAPI — retrieval and reasoning do not change. Barge-in stops playback, flushes the phrase queue, and cancels unused model/DAG work without wiping query state. Text mode never starts TTS.

Text and voice share one conversation. Partial transcripts stay live in the thread until the turn is final. The voice bar has a waveform, mute, and interrupt. Reconnect reloads the durable conversation (Postgres when the pool is up).

xAI speech defaults to the male `rex` voice; `ara` is the female option. Users can switch naturally in either chat or speech (for example, “switch to female” or “use a man's voice”). The active voice reconnects before immediately greeting with the selected voice, and the preference is retained by the browser. Contextual xAI expression markup is added only at the TTS boundary; visible and stored conversation text remains tag-free. Expression is intentionally restrained and does not use cheerful or laughter effects.

```bash
cd backend
uv sync --extra voice
uv run python -m app.realtime.worker start
```

High-traffic TTS (Kokoro, no xAI speech cost):

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.kokoro.yml up --build
```

Terminal voice client (run from Windows or the host with the microphone):

```bash
pip install sounddevice numpy requests
python voice_cli.py
```

`voice_cli.py` authenticates through `/api/auth/login` using environment-backed credentials and can verify the returned principal before querying or synthesizing speech. It uses authenticated backend TTS (`rex` by default, `ara` after a female-voice request), so provider keys and expressive tags remain server-side. Configure `NIA_CLI_USER`, `NIA_CLI_PASSWORD`, and optionally `NIA_CLI_PRINCIPAL` in the untracked `.env` file. Use `--local-tts` only when an installed OS voice is preferred.

## Eval and docs

```bash
python -m pytest tests/test_eval_suite.py -q
```

| Doc | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Auth boundary, voice path, traces, eval gates |
| [docs/table-access-matrix.md](docs/table-access-matrix.md) | What `assistant_runtime` may touch |
| [docs/deploy.md](docs/deploy.md) | Production privilege self-test, Compose, paid vs local |
| [docs/rollback.md](docs/rollback.md) | Drop assistant schemas without touching research data |

Unauthorized-source rate on the eval suite must stay 0. Deterministic COUNT fixtures must keep zero reasoning calls.
