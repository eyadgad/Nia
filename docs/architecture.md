# Architecture

```text
Standalone UI
    ↓
StandaloneJwtAuthAdapter
    ↓
immutable AccessScope
    ↓
Assistant Core
    ↓
assistant_runtime
    ↓
assistant_api views/functions
    ↓
allowed research data only
```

Website integration replaces only the identity source:

```text
Existing NIA Website → WebsiteAuthAdapter → same AccessScope → same Assistant Core
```

The website token is exchanged at `POST /api/auth/session`. It contains only an opaque `sub` and research-data permissions. The assistant never reads website authentication tables. Browsers then use an HttpOnly assistant session cookie.

These layers must not import standalone JWT or website session types:

- query planning
- retrieval
- database gateway
- conversation memory
- citations
- LiveKit
- whisper.cpp
- Grok reasoning (REST, `REASONING_BASE_URL`)
- xAI TTS
- Kokoro

Reasoning goes over an OpenAI-compatible REST host set by `REASONING_BASE_URL`, through
`backend/app/llm/http_reasoner.py`. `REASONING_PROVIDER=xai` selects the older gRPC
`xai-sdk` path instead and is the one-variable rollback; the two are interchangeable behind
the five-method `ReasoningProvider` protocol, and nothing above the boundary imports either.

The model is chosen per turn by the researcher from `Settings.reasoning_model_choices`, an
allowlist -- the name is passed straight to the host, which exposes hundreds of models. The
choices reach the UI on `GET /api/assistant/datasets`; an unrecognised name falls back to the
default rather than failing the turn. The models are not equivalent: the default answers
directly, the newer ones reason first, which is several seconds a call.

Voice path (Phase C):

```text
browser microphone
    ↓
self-hosted LiveKit (WebRTC)
    ↓
agent worker (Silero VAD + whisper.cpp STT)
    ↓
on_user_turn_completed
    ↓
Assistant Core (same AccessScope as text)
    ↓
phrase buffer → TTSProvider (xAI WS or Kokoro-FastAPI)
    ↓
LiveKit playback (barge-in cancels queue + TTS + unused LLM/DAG)
    ↓
same conversation snapshot (text + voice)
```

`POST /api/livekit/token` is authenticated. The JWT embeds the caller's AccessScope and can only join a room namespaced to that principal. Preemptive generation is off so retrieval finishes before any reply starts.

Observability (Phase D):

```text
turn span
  ├── stt
  ├── retrieval
  ├── llm
  └── tts
```

Audit events land in `assistant.audit_events` whenever the database pool is available; isolated tests fall back to the in-process log. Background jobs use `FOR UPDATE SKIP LOCKED` leases. Retention deletes assistant-owned traces/result sets/audit rows only — never research tables. Production startup always runs the privilege self-test.

## Eval gates

`tests/eval_fixtures.py` + `tests/test_eval_suite.py` require:

- every fixture plan that the local parser emits is valid against the field registry and AccessScope;
- unauthorized-source rate is **0** (`file:93:` / `file:94:` never appear in citations or evidence);
- COUNT fixtures match seed aggregates (2 students starting with S; 1 admitted in 1910);
- synthesis uses exactly the expected reasoning-call count and stripped citations;
- follow-ups edit the active frame instead of opening a new topic;
- a multi-branch hybrid query has a shorter wall-clock latency when DAG concurrency > 1 than when it is forced sequential.

See [deploy.md](deploy.md) for privilege, Compose, and paid-vs-local notes.

## Planner (Phase 2: AI default)

Application default is `PLANNER_MODE=ai`. `PLANNER_MODE=legacy` remains a one-step emergency rollback. Legacy semantic readers are not deleted until Phase 3.

```text
final user input
    -> transport-only normalization
    -> empty-input / selected-dataset / pin-conflict guards
    -> primary structured PlannedTurn
    -> bind selected dataset (trusted; model cannot name file IDs)
    -> strict TurnPlan validation + requirement parity
    -> QueryPlan build + predicate contract
    -> self-review (complete | corrected once | needs_clarification)
    -> registry value canonicalization + QueryPlan validation
    -> deterministic execution
    -> deterministic answer or evidence-backed synthesis
```

Invariants:

- The planner sees fields from exactly one selected list, plus labels of other authorized lists.
- A question never changes scope, fans out, or silently substitutes another list.
- Provider failure and malformed output are operational failures, not clarifications.
- There is no deterministic semantic fallback after an AI failure.

Interpretation (what the user asked) is the model's job. Canonicalization (synonyms, article strip on marked note fields, boolean/gender coercions) is trusted code after parse. The two are not interchangeable.

Failure states: `planner_unavailable`, `planner_invalid_output`, `dataset_not_selected`, `unsupported_fields`, `clarification`, `dataset_selection_required`, `dataset_scope_conflict`.

See [ai-planner-end-to-end-plan.md](ai-planner-end-to-end-plan.md) and [phase-2-ai-planner-rollout.md](phase-2-ai-planner-rollout.md).
