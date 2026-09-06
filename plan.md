# Build a Production-Ready Realtime Voice + Chat Data Assistant

You are a senior full-stack engineer, realtime-media engineer, retrieval engineer, and AI systems architect.

Your job is to **implement, run, test, and document** a production-ready web AI assistant that supports both:

1. normal text chat; and
2. ChatGPT-like realtime voice conversation.

The assistant primarily answers questions about **user-facing research datasets already stored in the existing PostgreSQL application database**. The inspected database is not a simple `people`/`documents` schema. Its research data is primarily represented through:

* `file` — dataset registry, current version, public/private status, labels, and dataset metadata;
* `data_config` — user-facing/dynamic dataset configuration and column metadata;
* `file_data` — authoritative raw dataset rows stored as JSONB;
* `file_data_normalized` — normalized/search-oriented representation of the same rows, including canonical fields, `search_text`, compact chat bundles, aliases/tokens, and provenance;
* approved reference data such as `communities`, `day_schools`, `indian_hospitals`, and `provinces`; and
* explicitly exposed, approved attachment/document metadata when the product enables that feature.

The assistant must **not** be given general access to the application database. Tables containing administrators, users, credentials, OTPs, logs, support operations, internal workflow state, system controls, and other non-user-facing information are outside the assistant's data boundary.

The system must be **retrieval-first and budget-conscious**.

The LLM must **never receive the entire database**.

For every user turn, the LLM should receive only:

* the current user question;
* a small amount of recent conversational state;
* compact structured session memory;
* the most relevant database records/passages;
* source identifiers/citations.

The only services we are willing to pay AI inference fees for are:

1. the reasoning LLM;
2. initial production TTS.

Everything else should be local/self-hosted where practical.


For the **test/initial paid-provider profile**, use:

```text
reasoning model: grok-4.20-0309-non-reasoning
TTS: xAI Text to Speech API
```

Keep provider interfaces configurable so the test model/TTS can be replaced without changing retrieval, planning, database, memory, or realtime-session logic.

A third non-negotiable principle is **critical-path latency minimization through bounded parallelism**. Independent work should run concurrently whenever doing so cannot change correctness, authorization, provenance, or user-visible ordering. The goal is not to create the largest possible number of tasks; it is to make the request's dependency DAG finish as quickly as possible without overloading PostgreSQL, whisper.cpp, the model provider, TTS, or the host.

A second non-negotiable principle is **least-privilege database access**:

```text
assistant runtime
    ↓
curated Assistant Data Gateway
    ↓
explicit allowlisted views/functions only
    ↓
user-facing research data
```

The assistant runtime must not have `SELECT` privileges on the general application schema. It must access research data only through a dedicated assistant-facing exposure layer that explicitly exposes approved fields and enforces dataset/version/privacy scope.

---

# 1. Mandatory technology stack

Use the following stack unless a concrete technical incompatibility forces a change.

## Frontend

Use:

* Next.js
* React
* TypeScript
* LiveKit React components where useful

Reference repository:

repositories/agent-starter-react

Use this as the primary frontend reference/starter.

The UI must support:

* normal text chat;
* voice-mode toggle;
* microphone input;
* realtime partial transcript;
* assistant text streaming;
* assistant audio streaming;
* live waveform;
* mic mute/unmute;
* interruption/barge-in;
* source citations;
* conversation history shared between text and voice;
* reconnect state;
* speaking/listening/thinking visual states.

---

# 2. Realtime voice runtime

Use LiveKit Agents as the primary realtime conversation framework.

Core repository:

repositories/agents

Python starter:

repositories/agent-starter-python

Self-hosted LiveKit server:

repositories/livekit

Do **not** require LiveKit Cloud.

The deployment should be capable of using a self-hosted LiveKit server so that LiveKit does not become an ongoing per-minute AI expense.

LiveKit should handle or coordinate:

* WebRTC;
* realtime audio transport;
* browser microphone streaming;
* browser speaker playback;
* sessions;
* turn-taking;
* endpointing;
* interruption;
* agent state;
* streamed output;
* reconnect behavior.

The realtime media path must remain separate from slower retrieval/database work.

---

# 3. Local speech-to-text

Do not use paid STT APIs.

Use:

repositories/whisper.cpp

Implement a local streaming transcription service around whisper.cpp.

The service must:

* continuously accept microphone audio;
* process audio incrementally;
* provide partial transcripts;
* provide final transcripts;
* expose timestamps where practical;
* support configurable Whisper model sizes;
* allow CPU inference initially;
* permit GPU acceleration later;
* be callable by the LiveKit agent/backend without a cloud API.

Prefer an independent service abstraction such as:

```text
WhisperService
    transcribe_stream()
    reset_session()
    finalize_turn()
```

Do not tightly couple whisper.cpp subprocess logic to the main application.

The system should allow replacing whisper.cpp later without changing the retrieval or reasoning layers.

---

# 4. Local voice activity detection

Use Silero VAD locally.

Reference:
repositories/silero-vad

Prefer LiveKit's Silero integration when it provides the necessary behavior.

Use VAD plus turn-detection logic to distinguish:

* short pauses;
* actual end of turn;
* interruptions;
* background noise;
* continuing speech.

Do not treat every 300–500 ms silence as the end of a user's thought.

Where supported, combine:

```text
Silero VAD
+
LiveKit semantic turn detection / endpointing
```

for more natural conversation.

---

# 5. Realtime conversation behavior

The system should feel substantially closer to ChatGPT Voice than to a simple:

```text
record
→ wait
→ transcribe
→ answer
→ play audio
```

pipeline.

Implement:

```text
continuous microphone stream
        ↓
partial transcription
        ↓
VAD / endpointing
        ↓
user turn finalized
        ↓
very fast retrieval
        ↓
streaming LLM generation
        ↓
sentence/phrase buffering
        ↓
streaming TTS
        ↓
audio begins before full answer finishes
```

The user must be able to interrupt the assistant.

---

# 6. Barge-in / interruption handling

Implement interruption as a first-class feature.

Every assistant generation should have a:

```text
generation_id
```

Track:

```text
session_id
conversation_id
turn_id
generation_id
tts_stream_id
```

If the user begins meaningful speech while assistant audio is playing:

1. immediately stop local assistant playback;
2. flush queued outgoing audio;
3. cancel the active TTS stream where supported;
4. cancel or stop unnecessary remaining LLM generation where practical;
5. mark the assistant message as interrupted;
6. record the portion of the assistant response that was actually delivered;
7. switch conversation state immediately back to listening;
8. transcribe the new user input.

The system must not continue speaking over the user.

State machine:

```text
IDLE
 ↓
LISTENING
 ↓
PROCESSING
 ↓
SPEAKING
 ↓
LISTENING
```

and interruption:

```text
SPEAKING
   ↓ user starts speaking
INTERRUPT
   ↓
cancel output
   ↓
LISTENING
```

---

# 7. Humanization requirements

Voice should not merely read chatbot text.

Implement a humanization layer.

It should support:

* conversational pacing;
* natural pauses;
* short acknowledgements when appropriate;
* interruption awareness;
* slightly shorter responses in voice mode;
* natural phrasing;
* adaptive speaking speed;
* pronunciation hints for names;
* continuity across follow-up questions;
* contextual greetings;
* awareness of the person/document currently being discussed.

Avoid unnecessary filler.

Do not make the assistant repeatedly say things such as:

```text
"Certainly!"
"Of course!"
"Great question!"
```

Voice answers should normally begin directly.

For voice mode:

* display citations visually;
* do not read ugly source IDs aloud;
* say things like "According to the 2025 project report..." when useful;
* keep the exact source IDs available in the UI.

---

# 8. Shared text + voice architecture

Do not build separate intelligence stacks for chat and voice.

Use:

```text
                        ASSISTANT CORE
                              ▲
                    ┌─────────┴─────────┐
                    │                   │
               Text Chat             Voice
                    │                   │
                    │               whisper.cpp
                    │                   │
                    └─────────┬─────────┘
                              │
                           question
                              │
                       retrieval core
                              │
                        evidence packet
                              │
                             LLM
                              │
                           answer text
                        ┌─────┴──────┐
                        │            │
                    chat UI          TTS
                                      │
                                    voice
```

The same:

* retrieval;
* history;
* memory;
* authentication;
* access control;
* citations;
* LLM;
* data policies

must be used by both chat and voice.

---

# 9. Backend/API and database-boundary layer

Use Python + FastAPI.

Reference:

repositories/fastapi

Use the official xAI Python SDK for reasoning calls and xAI's documented REST/WebSocket TTS API for speech synthesis:

repositories/xai-sdk-python

https://docs.x.ai/developers/models/grok-4.20-non-reasoning

https://docs.x.ai/developers/models/text-to-speech

https://docs.x.ai/developers/rest-api-reference/inference/voice

The backend must be split into **assistant logic** and a **restricted Assistant Data Gateway**. The reasoning/planning code must never open a general-purpose database connection that can inspect arbitrary application tables.

Recommended structure:

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── auth.py
│   │   ├── assistant.py
│   │   ├── conversations.py
│   │   ├── livekit_tokens.py
│   │   └── citations.py
│   │
│   ├── data_gateway/
│   │   ├── access_scope.py
│   │   ├── dataset_policy.py
│   │   ├── field_registry.py
│   │   ├── connection_pool.py
│   │   ├── current_records.py
│   │   ├── raw_records.py
│   │   ├── reference_data.py
│   │   ├── attachment_metadata.py
│   │   └── history.py
│   │
│   ├── realtime/
│   │   ├── agent.py
│   │   ├── session.py
│   │   ├── interruption.py
│   │   ├── turn_detection.py
│   │   └── audio_state.py
│   │
│   ├── stt/
│   │   ├── base.py
│   │   └── whisper_cpp.py
│   │
│   ├── planning/
│   │   ├── query_plan.py
│   │   ├── plan_schema.py
│   │   ├── deterministic_parser.py
│   │   ├── conversation_resolver.py
│   │   ├── plan_builder.py
│   │   ├── plan_validator.py
│   │   ├── dependency_graph.py
│   │   └── llm_planner.py
│   │
│   ├── concurrency/
│   │   ├── scheduler.py
│   │   ├── limits.py
│   │   ├── cancellation.py
│   │   ├── singleflight.py
│   │   └── timeouts.py
│   │
│   ├── execution/
│   │   ├── executor.py
│   │   ├── dag_scheduler.py
│   │   ├── structured_ops.py
│   │   ├── lexical_ops.py
│   │   ├── semantic_ops.py
│   │   ├── set_ops.py
│   │   ├── aggregate_ops.py
│   │   ├── temporal_ops.py
│   │   ├── comparison_ops.py
│   │   └── result_fusion.py
│   │
│   ├── retrieval/
│   │   ├── normalizer.py
│   │   ├── entity_resolver.py
│   │   ├── exact_search.py
│   │   ├── fulltext_search.py
│   │   ├── fuzzy_search.py
│   │   ├── vector_search.py
│   │   ├── ranker.py
│   │   ├── deduplicator.py
│   │   └── context_builder.py
│   │
│   ├── memory/
│   │   ├── session_memory.py
│   │   ├── conversation_memory.py
│   │   ├── query_frames.py
│   │   ├── result_sets.py
│   │   └── memory_updates.py
│   │
│   ├── llm/
│   │   ├── base.py
│   │   ├── xai_reasoner.py
│   │   └── structured_outputs.py
│   │
│   ├── tts/
│   │   ├── base.py
│   │   ├── xai_tts.py
│   │   └── kokoro_tts.py
│   │
│   ├── ingestion/
│   │   ├── attachment_fetcher.py
│   │   ├── parser.py
│   │   ├── ocr.py
│   │   ├── chunker.py
│   │   └── indexer.py
│   │
│   ├── db/
│   │   ├── assistant_models.py
│   │   ├── assistant_repository.py
│   │   ├── gateway_repository.py
│   │   └── migrations/
│   │
│   ├── security/
│   └── observability/
│
└── tests/
```

Maintain these boundaries:

```text
website authentication / authorization
        ↓
validated AccessScope
        ↓
Assistant Data Gateway
        ↓
conversation resolution
        ↓
planning
        ↓
validated execution
        ↓
result fusion
        ↓
evidence/context construction
        ↓
reasoning/response
```

The LLM and query planner do not choose database tables directly. They operate on semantic fields and allowed QueryPlan operations. Backend code maps those operations to the restricted exposure layer.

---


# 9A. Parallelism, concurrency, pipelining, and critical-path latency

Parallelism is a first-class architecture requirement. Every request should be represented as a dependency graph and the runtime should execute all **independent ready work concurrently**, subject to bounded resource limits and the immutable `AccessScope`.

The optimization target is:

```text
minimum end-to-end critical-path latency
```

not:

```text
maximum number of concurrent tasks
```

Unbounded concurrency can make the application slower by exhausting PostgreSQL connections, saturating CPU used by whisper.cpp, triggering provider rate limits, increasing context switching, or causing queue buildup. Therefore all concurrency must be **bounded, measured, cancellable, and backpressured**.

## 9A.1 Async-first backend

Use asynchronous I/O end-to-end for network/database-bound work:

```text
FastAPI async endpoints
async LiveKit callbacks
async PostgreSQL driver/pool
async xAI reasoning client
async xAI TTS WebSocket client
async Redis client when enabled
async background worker coordination
```

Do not use blocking HTTP/database calls on the event loop. Move unavoidable CPU/blocking work to:

```text
separate process
or
bounded worker thread/process pool
```

whisper.cpp should run as a separate local service/process so CPU-heavy transcription cannot block the FastAPI/LiveKit event loop.

## 9A.2 Per-turn concurrency graph

After a user turn is finalized and its immutable `AccessScope` is available, start independent preparation work concurrently.

Conceptual flow:

```text
FINAL TRANSCRIPT + ACCESS SCOPE
            │
            ├────────► load conversation state / active frame
            │
            ├────────► normalize question / local date parsing
            │
            ├────────► resolve aliases/reference candidates
            │
            └────────► load/cache relevant field-registry + dataset policy
                         │
                         └────────────┬──────────────┘
                                      ▼
                                  build plan
                                      │
                                      ▼
                             DAG READY-SET SCHEDULER
                                      │
                 ┌────────────────────┼────────────────────┐
                 ▼                    ▼                    ▼
              SQL branch          FTS branch         fuzzy/reference branch
                 │                    │                    │
                 └────────────────────┼────────────────────┘
                                      ▼
                                  result fusion
                                      │
                         ┌────────────┴────────────┐
                         ▼                         ▼
                   computed facts             evidence fetch
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                               final synthesis
                                      │
                              streamed text deltas
                                      │
                         ┌────────────┴─────────────┐
                         ▼                          ▼
                    frontend text             phrase TTS queue
                                                    │
                                                    ▼
                                              streamed audio
```

Only dependencies impose serialization.

## 9A.3 QueryPlan DAG scheduler

Implement `execution/dag_scheduler.py` so each step explicitly declares:

```text
step_id
dependencies[]
operation
resource_class
estimated_cost
scope
cancel_policy
timeout
idempotency_key
```

Execution algorithm:

1. validate the complete plan and `AccessScope` before data execution;
2. calculate in-degree/dependency counts;
3. place all dependency-free steps into the ready set;
4. execute ready steps concurrently using a bounded task group;
5. when a step completes, unlock dependent steps;
6. immediately schedule newly ready steps when resource limits allow;
7. propagate cancellation/errors according to dependency policy;
8. preserve deterministic output ordering separately from execution completion order.

Pseudo-code:

```python
while unfinished_steps:
    ready = dependency_graph.ready_steps()
    results = await bounded_gather(run_step(step) for step in ready)
    dependency_graph.commit(results)
```

Prefer Python 3.11+ `asyncio.TaskGroup` or equivalent structured concurrency instead of creating unmanaged background tasks.

## 9A.4 Parallel retrieval fan-out

For a retrieval node, run compatible methods concurrently when they provide independent signals:

```text
exact/canonical lookup ───────┐
metadata/JSONB filters ───────┤
PostgreSQL FTS ───────────────┼──► fusion/ranking/deduplication
pg_trgm lookup ───────────────┤
RapidFuzz/reference variants ─┘
```

Do not always wait for every branch if an exact, high-confidence result fully satisfies the operation. Support **early completion** policies such as:

```text
exact unique entity match found
→ cancel unnecessary fuzzy fallback
```

or:

```text
FTS already returns sufficient high-confidence evidence
→ skip optional semantic fallback
```

This saves latency and CPU while retaining correctness.

## 9A.5 PostgreSQL concurrency

Use an asynchronous connection pool. Independent SQL operations can execute concurrently only on separate database connections; do not attempt concurrent commands on one connection.

Use conservative configurable pool limits:

```text
DB_POOL_MIN=
DB_POOL_MAX=
DB_QUERY_CONCURRENCY=
DB_QUERY_TIMEOUT_MS=
```

Rules:

- authorization/data-scope checks must complete before protected row queries execute;
- independent reads may run concurrently;
- dependent joins/aggregates stay ordered according to the DAG;
- use one well-optimized SQL statement when PostgreSQL can perform the work more efficiently than multiple parallel round trips;
- use `EXPLAIN (ANALYZE, BUFFERS)` in performance testing before assuming fan-out is faster;
- cap concurrent queries per user/session and globally;
- cancel abandoned queries after barge-in/request cancellation when their results are no longer reusable;
- use statement timeouts;
- never hold transactions open while waiting on LLM/TTS/network operations.

## 9A.6 Parallel preparation during user speech

While the user is still speaking, perform only safe, non-sensitive preparation that does not require knowing the final intent:

```text
maintain VAD
stream partial whisper.cpp transcript
update UI transcript
keep session/conversation state warm
keep field registry and dataset policy cached
keep reference aliases cached
keep xAI TTS WebSocket warm for voice sessions
```

Optionally run **local speculative normalization** on partial transcripts, but do not fetch private/raw source rows based on an unfinished sentence and do not make paid reasoning calls speculatively.

When the final transcript arrives, discard stale partial-turn interpretations and execute only the finalized plan.

## 9A.7 Voice pipeline parallelism

The voice system should use pipeline parallelism rather than sequential stages wherever possible:

```text
microphone capture  ─────────────────────────────►
VAD                   ───────────────────────────►
whisper partial STT       ───────────────────────►
UI partial transcript      ──────────────────────►

final turn                    │
                              ▼
retrieval/planning             ███
model generation                  █████████████
display text                       █████████████
audio phrase buffering               ███████████
xAI streaming TTS                     ███████████
LiveKit playback                         █████████
```

The application must not wait for the full model answer before TTS begins.

Preserve spoken phrase order even if preparation is concurrent. Use a sequence number per TTS phrase and an ordered output queue.

## 9A.8 xAI TTS connection prewarming and reuse

For the xAI TTS test/initial profile, use its streaming WebSocket endpoint and establish the connection **before the first answer phrase is ready**, ideally when the voice session becomes active.

Reuse the WebSocket for multiple utterances in the same voice session when supported. This removes connection setup from the critical path of every answer.

Conceptual state:

```text
voice session opens
   ├── LiveKit/WebRTC ready
   ├── whisper.cpp worker ready
   └── xAI TTS WebSocket preconnected

answer phrase arrives
   ↓
text.delta immediately
   ↓
audio chunks immediately
```

## 9A.9 Reasoning-model concurrency

Use `grok-4.20-0309-non-reasoning` for the test reasoning profile.

Do not parallelize model calls that have logical dependencies. In particular:

```text
complex planning call
      ↓ must finish/validate first
plan execution
      ↓
final synthesis call
```

is necessarily sequential.

However, where a plan requires independent semantic classifications that cannot be done deterministically, the executor may submit **bounded parallel classification calls/batches** if that reduces latency and remains within the cost/rate-limit budget. Prefer batching candidate evidence into the smallest number of calls that preserves accuracy.

A single user turn must have a configurable paid-model concurrency budget so one complex request cannot consume the provider limit.

## 9A.10 Cancellation propagation

User interruption/cancellation must propagate immediately through the active request tree.

Example:

```text
USER BARGE-IN
   ↓
cancel playback
   ↓
cancel queued unsent TTS phrases
   ↓
cancel active TTS generation where possible
   ↓
cancel remaining model stream when no longer reusable
   ↓
cancel irrelevant retrieval/query branches
   ↓
preserve reusable completed facts/result-set IDs
   ↓
finalize trace/audit state asynchronously
```

Every task spawned for a turn must belong to the turn's structured concurrency scope so there are no orphaned tasks.

## 9A.11 Timeouts, hedging, retries, and backpressure

Every remote/local resource class needs explicit timeout and retry policy:

```text
DB_QUERY_TIMEOUT_MS
RETRIEVAL_BRANCH_TIMEOUT_MS
XAI_REQUEST_TIMEOUT_MS
XAI_TTS_FIRST_AUDIO_TIMEOUT_MS
WHISPER_TURN_FINALIZE_TIMEOUT_MS
```

Retry only idempotent operations automatically.

Do not blindly retry paid model/TTS calls after partial user-visible output. Use request/idempotency state so retries cannot create duplicated answers or overlapping speech.

Optional latency hedging may be used only for **local/cheap** operations where duplicate work is harmless; do not send duplicate paid model requests merely to race them.

Implement backpressure:

- bounded TTS phrase queue;
- bounded database pool;
- bounded model request semaphore;
- bounded whisper session workers;
- bounded background job workers;
- per-user/session concurrency limits;
- global concurrency limits.

When capacity is exhausted, queue briefly or degrade gracefully rather than spawning unlimited work.

## 9A.12 Singleflight/request coalescing

If multiple concurrent operations request the same immutable/cacheable resource, share one in-flight operation where practical.

Examples:

```text
field registry for file 49
reference aliases
same approved current-record metadata
same FTS query under identical AccessScope + source-version fingerprint
```

Implement `concurrency/singleflight.py` or Redis-backed request coalescing when horizontally scaled.

Never share a cached result across different authorization scopes unless the cached artifact is demonstrably public/non-sensitive.

## 9A.13 Background-worker parallelism

Offline work should use a bounded worker pool and `assistant.background_jobs` leases:

```text
attachment fetch
OCR
chunking
FTS rebuild
optional local embeddings
reference/alias rebuild
field-registry validation
maintenance/reconciliation of assistant-owned indexes
```

Independent files/jobs may execute in parallel. Steps for the same source should use idempotency keys and dependency ordering where required.

For PostgreSQL-backed job claiming, use transactional leasing such as `FOR UPDATE SKIP LOCKED` or an equivalent reliable queue design so multiple workers do not process the same job accidentally.

## 9A.14 Horizontal concurrency across users

The architecture must support many simultaneous sessions:

```text
multiple frontend clients
        ↓
LiveKit sessions
        ↓
multiple backend workers
        ↓
shared PostgreSQL / optional Redis
        ↓
local whisper worker pool
        ↓
xAI reasoning/TTS APIs
```

Conversation/query state must not depend solely on one process's memory if horizontal scaling is enabled. Persist authoritative state in the assistant schema; use Redis only as an acceleration/cache layer.

## 9A.15 Concurrency metadata in existing assistant tables

Do not create a new table merely for each concurrency mechanism. Extend existing reliability tables:

`assistant.query_runs` should additionally record:

```text
critical_path_ms
parallel_step_peak
queued_ms
cancel_reason
worker_id / instance_id
```

`assistant.query_step_runs` should additionally record:

```text
branch_group
ready_at
queued_at
started_at
completed_at
worker_id
attempt
idempotency_key
timeout_ms
cancelled
```

`assistant.background_jobs` already contains lease/heartbeat/retry state; also include:

```text
worker_id
lease_expires_at
idempotency_key
priority
resource_class
```

`assistant.voice_sessions` should track:

```text
xai_tts_connection_state
xai_tts_connected_at
first_audio_latency_ms
barge_in_cancel_latency_ms
```

## 9A.16 Parallelism correctness rules

Never parallelize across a required correctness/security dependency. These remain strict barriers:

```text
AccessScope validation
    BEFORE protected data retrieval

QueryPlan validation
    BEFORE data execution

current-version resolution
    BEFORE current-record facts are accepted

all required dependent facts
    BEFORE final synthesis that relies on them

citation authorization validation
    BEFORE citation display
```

Parallel completion order must not change deterministic answer semantics.

## 9A.17 Performance acceptance criteria

The implementation is not considered performance-complete until traces show:

- independent DAG steps overlap in time;
- compatible retrieval branches overlap in time;
- model text streaming overlaps with frontend rendering;
- TTS generation overlaps with continuing model generation;
- xAI TTS connection setup is normally outside the per-answer critical path;
- barge-in cancels unnecessary downstream work quickly;
- pool/semaphore saturation is observable;
- p50/p95/p99 stage and end-to-end latencies are measured;
- increasing concurrency does not cause database or CPU collapse under load.

Benchmark both sequential and parallel execution for representative queries. Keep parallel fan-out only where measurements show it improves the critical path.

---

# 10. Database architecture after inspection: explicit exposure, isolation, and assistant-owned tables

The inspected production database contains **33 application tables and 31,913 rows**, including user-facing research data as well as authentication, administration, logs, support workflows, review queues, and system state. The assistant must not receive access to that entire schema.

The database boundary is therefore part of the security architecture, not merely a coding convention.

## 10.1 Existing research-data model that the assistant is allowed to depend on

The existing application research model is:

```text
file
  │
  ├── data_config
  │
  ├── file_data                  authoritative raw JSONB rows
  │      │
  │      └── file_data_normalized normalized/search read model
  │
  └── approved reference / attachment metadata as explicitly exposed
```

The assistant data gateway may depend on the following existing tables, but only through curated views/functions and selected columns:

| Existing table | Status | Assistant use |
|---|---|---|
| `file` | **Required** | Dataset identity, current version, filename/title, description, row count metadata, `private`, and deletion/current-state filtering. |
| `data_config` | **Required** | User-facing dataset/column configuration and labels. Useful for planner schema discovery, but **not sufficient as the sole planner schema**. |
| `file_data` | **Required** | Authoritative raw JSONB row values. Used only after row IDs are selected, for exact raw evidence/citations or fields not represented in normalized bundles. |
| `file_data_normalized` | **Required** | Main current-record retrieval/search model: canonical fields, compact chat bundles, normalized aliases/tokens, `search_text`, source timestamps, and provenance. |
| `communities` | **Allowed reference** | Community/reserve entity resolution and fuzzy/voice correction. Use approved rows according to product policy. |
| `day_schools` | **Allowed reference** | School names and variants for entity resolution and voice/STT correction. |
| `indian_hospitals` | **Allowed reference** | Hospital names/variants for deterministic entity resolution. |
| `provinces` | **Allowed reference** | Province/location normalization and filtering. |
| `file_version` | **Feature-gated** | Only for explicit dataset-history/version questions. Expose safe version metadata only. |
| `file_edit_request_photos` | **Feature-gated through a sanitized view only** | Approved user-facing attachment/document/photo metadata. Do not expose reviewer/internal workflow columns. |

Do not grant the assistant runtime direct `SELECT` on any of these base tables. A dedicated gateway owner may read the necessary base tables to implement safe views/functions; the runtime role may use only the safe API layer.

## 10.2 Existing tables that are explicitly outside the assistant boundary

The normal assistant must have **no direct read access and no retrieval/indexing access** to these tables:

```text
users
roles
otps
logs

support_team_members
support_assignments
support_staff_availabilities
support_call_requests
support_calls
support_requests
support_schedule_settings
support_schedule_audit_logs

file_edit_request
file_edit_request_details
file_version_reconciliation_jobs
file_row_lineage
file_daily_honours
file_logo_content
file_access

form_file_mappings
form_submissions
form_submission_details
form_submission_uploads
```

These tables contain or may contain authentication data, administrator/user information, support contact information, internal notes, schedules, Zoom/passcode information, logs, workflow/review state, reconciliation internals, or other operational data that is not required for ordinary user-facing research questions.

`file_access` is not used by the assistant runtime to infer authorization because the inspected backup does not establish the full intended private-file policy. Authorization must come from the existing website's trusted authorization layer.

If a future administrative assistant is created, it must be a separate product mode, connection/role, policy set, and threat model. Do not broaden the research assistant's role.

## 10.3 Required current-version rule

Both `file_data` and `file_data_normalized` retain historical versions. The inspection found 8,672 normalized rows but only 2,942 current research rows; 66.1% are historical-version copies.

Every ordinary factual query must therefore be scoped to the current file version:

```text
record.file_id = file.id
AND record.version = file.version
AND file.is_delete = false
AND normalized.status = 'ready'
```

Historical records must be exposed only by an explicit history/version operation.

Never let individual query handlers remember this predicate independently. Encode it once in the assistant data-exposure layer.

## 10.4 Dedicated assistant database schema and roles

Create a dedicated schema, for example:

```text
assistant
assistant_api
```

Use separate PostgreSQL roles:

```text
assistant_gateway_owner   NOLOGIN
    owns safe views/functions
    SELECT only on the specific existing source tables required by those views/functions

assistant_runtime
    no SELECT on general application tables
    no direct SELECT on record-bearing gateway views that can contain private rows
    EXECUTE on scoped assistant_api data functions
    SELECT only on explicitly public/non-record metadata views where needed
    CRUD only on assistant-owned state tables

assistant_migrator
    schema migration role only; not used by the running web/voice process
```

Where possible, revoke `PUBLIC` privileges on assistant schemas and explicitly grant only what is required.

The website authentication layer must produce a validated `AccessScope` such as:

```json
{
  "principal_id": "opaque-user-key",
  "allowed_file_ids": [49, 91],
  "can_use_private_files": false,
  "history_allowed": false
}
```

Do not put user names, emails, password hashes, roles, OTPs, or administrator records into this object. The assistant only needs an opaque principal key plus the research-data scope it is allowed to query.

## 10.5 Safe assistant-facing exposure views/functions

Create a narrow data gateway. Suggested objects:

### `assistant_api.v_datasets`

Built from selected columns of `file` plus safe `data_config` metadata.

Expose only fields needed for user-facing dataset discovery/planning, for example:

```text
file_id
filename / display label
description
current_version
private
configured user-facing fields
assistant-enabled flag
```

Do not expose uploader/admin identifiers or unrelated operational metadata.

### `assistant_api.v_dataset_fields`

A safe union of curated `assistant.ai_field_registry` plus selected `data_config` labels. This is the schema seen by the planner.

The planner must not inspect the raw 352-column application schema.

### `assistant_api.v_current_records`

Current normalized research rows only:

```sql
SELECT
    n.id,
    n.source_row_id,
    n.file_id,
    n.version,
    n.row_data_normalized,
    n.search_text,
    n.canonical_name,
    n.canonical_community,
    n.canonical_school,
    n.source_created_at,
    n.source_updated_at,
    f.filename,
    f.private
FROM file_data_normalized n
JOIN file f
  ON f.id = n.file_id
 AND f.version = n.version
WHERE COALESCE(f.is_delete, false) = false
  AND n.status = 'ready';
```

This is an **internal gateway view**. Do not grant `assistant_runtime` unrestricted `SELECT` on it because it can contain private rows. Scoped gateway functions query this view and enforce dataset policy/grants before returning any record.

### `assistant_api.v_current_raw_records`

Current authoritative `file_data` rows only. It is used **after candidate/source IDs have been selected** when an exact raw field/value is needed for evidence or citation.

Never use it as a blanket context source.

### `assistant_api.v_reference_entities`

Curated union or separate views over approved `communities`, `day_schools`, `indian_hospitals`, and `provinces`, exposing only fields needed for lookup/variants.

### `assistant_api.v_approved_attachments` — optional

Sanitized projection of approved `file_edit_request_photos` rows if users are allowed to browse source documents/photos. Expose only user-facing metadata such as source row/file relationship, approved URL, display filename, media/document type, and safe caption/description fields.

Do not expose review/internal fields.

### Safe gateway functions

Prefer parameterized functions/repository methods such as:

```text
resolve_authorized_file_ids(principal_id)
list_datasets(principal_id)
get_dataset_fields(principal_id, file_id)
search_current_records(principal_id, requested_file_ids, query_plan_step)
get_current_records_by_ids(principal_id, source_row_ids, requested_fields)
get_raw_fields_by_ids(principal_id, source_row_ids, requested_keys)
resolve_reference_entity(principal_id, entity_type, text)
get_approved_attachments(principal_id, source_row_ids)
get_version_metadata(principal_id, file_id)       # feature-gated
```

Each record-bearing function must intersect the requested file IDs with:

```text
assistant.dataset_policy
+ file.private/current/deleted status
+ assistant.access_grants for the opaque principal when required
```

The application-level AccessScope and database-level grant projection provide defense in depth. The planner never gets a generic `query_database(sql)` tool.

## 10.6 Dataset policy based on the inspected data

The inspected current research datasets are:

| File ID | Dataset | Current rows | Private |
|---:|---|---:|---|
| 49 | Shingwauk And Wawanosh Students Master List | 2,781 | No |
| 91 | Confirmed- Shingwauk (Wawanosh) | 82 | No |
| 93 | Additional Deaths | 23 | Yes |
| 94 | Potential | 56 | Yes |

The assistant must never assume that `private=false/true` is the whole permission model. Files 93/94 require an authorization decision supplied by the website's existing trusted policy layer.

A product-level rule must also define what unqualified terms mean. In particular, the database has no global person table and a dataset row is not guaranteed to be a unique person across datasets.

Recommended policy:

```text
"students" / unqualified "people" → primary master-list scope (file 49), unless context says otherwise
"records"                         → records across all currently authorized datasets
"all datasets"                    → all datasets in AccessScope
cross-dataset unique people        → unsupported until a reviewed entity-link layer exists
```

Do not silently deduplicate people across datasets using names or student numbers.

## 10.7 Curated AI field registry

`data_config` is important user-facing metadata, but inspection showed it does not cover every raw research field and some normalization heuristic `role` labels are incorrect.

Create and maintain a curated `assistant.ai_field_registry` that is built from:

```text
data_config
+ observed raw field keys in file_data
+ canonical paths in file_data_normalized
+ normalized chat/search structures
+ curated aliases and semantic types
```

Each registry row should describe:

```text
semantic_field
human_label
aliases
file_id / dataset scope
canonical_json_path
raw_json_keys
semantic_type
allowed_operators
searchable
aggregatable
sortable
quoteable
sensitivity classification
exposure policy
validation rules
```

Examples:

```text
birth / born / date of birth
    → canonical.dates.birth

community / reserve / first nation
    → canonical.community

student number
    → canonical.student_number
```

The planner uses this registry rather than guessing field semantics.

## 10.8 Assistant-owned tables: complete initial inventory

The assistant must own its operational state in the dedicated `assistant` schema rather than adding fields to existing application tables.

### Required core tables

| Table | Purpose | Stored data |
|---|---|---|
| `assistant.dataset_policy` | Explicit allowlist of research datasets the assistant may use and product semantics for each dataset. | `file_id`, enabled flag, user-facing label, default-scope flags, history-enabled flag, attachment-enabled flag, private-policy mode, configuration version. No user PII. |
| `assistant.field_registry` | Authoritative semantic/planner schema described above. | Dataset-scoped semantic fields, aliases, canonical/raw paths, types, operators, exposure/sensitivity flags, validation rules. |
| `assistant.access_grants` | Narrow authorization projection used by scoped gateway functions for private research files. | Opaque principal ID, `file_id`, grant status, optional expiry, source/version of authorization decision. Never names, emails, passwords, OTPs, or role records. It is synchronized from the existing website authorization layer, which remains the source of truth. |
| `assistant.entity_aliases` | Stable aliases, STT corrections, and pronunciation hints not already represented by source/reference tables. | Entity type, canonical source/key, alias, normalized alias, optional phonetic/TTS hint, scope and confidence/verification flags. |
| `assistant.conversations` | Durable conversation container shared by text and voice. | Conversation ID, opaque principal ID, title/display metadata, created/updated timestamps, current mode/state flags. |
| `assistant.messages` | Finalized user/assistant message history. | Conversation ID, turn ID, role, final text/transcript, text/voice mode, interrupted flag, delivered-text boundary where known, timestamps. |
| `assistant.conversation_state` | Compact current memory without replaying full history. | Rolling summary, active entities, active dataset scope, active query state, last source IDs, pending references, state version. |
| `assistant.query_frames` | Multiple recoverable conversation topics/query contexts. | Conversation ID, frame key, topic/entities, logical constraints, recent result-set references, last-used timestamp. |
| `assistant.result_sets` | Lightweight durable references to previous ordered results for follow-ups. | Result-set ID, conversation/turn, entity/record type, ordered source IDs, sort metadata, dataset scope, expiry/retention metadata. Do not duplicate full source rows. |
| `assistant.query_plans` | Validated logical QueryPlan DAG used for a turn. | Turn ID, planner type (deterministic/LLM), plan JSON, schema version, validation status, plan hash, timestamps. No arbitrary SQL. |
| `assistant.query_runs` | Top-level execution trace for reliability/replay/debugging and critical-path analysis. | Plan ID, status, access-scope fingerprint, start/end times, latency, critical-path ms, peak parallel steps, queue time, worker/instance ID, cancellation/error category, result summary/counts, retry info. Avoid storing sensitive evidence payloads. |
| `assistant.query_step_runs` | Step-level execution/concurrency state for a QueryPlan DAG. | Query-run ID, step ID/op, dependency state, branch group, ready/queued/start/end timestamps, worker ID, attempt, idempotency key, timeout/cancel status, result count, safe result references, retry/error metadata. |
| `assistant.citations` | Stable answer-to-source provenance mapping. | Message/turn ID, claim/segment ID, `file_id`, version, source row ID, requested field/path or attachment/chunk ID, citation label and ordering. |
| `assistant.voice_sessions` | Realtime voice reliability state. | Conversation ID, LiveKit/session identifiers, connection lifecycle, generation/TTS IDs, interruption/reconnect timestamps, final session state. Do not store raw microphone audio by default. |
| `assistant.feedback` | Explicit user quality feedback. | Conversation/turn/message IDs, rating/category, optional user comment, timestamps. |
| `assistant.audit_events` | Assistant-specific security/operational audit trail, separate from application `logs`. | Opaque principal ID, event type, conversation/query IDs, dataset IDs touched, authorization outcome, model/provider action metadata, timestamp. Do not copy application logs or raw sensitive records. |
| `assistant.background_jobs` | Reliable queue/status tracking for parallel local indexing/rebuild/maintenance workers. | Job type, target dataset/source, resource class, priority, state, attempt count, idempotency key, worker ID, next retry, lease/heartbeat/lease expiry, error summary, created/started/completed timestamps. |

### Optional tables only when attachment-content Q&A is enabled

The backup contains attachment URLs/metadata but not actual binary file contents. If users need to ask what a PDF/image says, create:

| Table | Purpose | Stored data |
|---|---|---|
| `assistant.attachment_sources` | Safe record of external user-facing documents/photos selected for ingestion. | Source attachment ID, `file_id`, source row ID, approved URL/object key, media type, checksum, fetch status, source metadata. |
| `assistant.attachment_chunks` | Searchable/OCRed text chunks from ingested attachments. | Attachment source ID, page/section/chunk number, extracted text, FTS vector, optional local embedding, provenance offsets. |

`assistant.background_jobs` tracks fetch/OCR/indexing jobs; a separate ingestion-job table is unnecessary unless operational volume later justifies it.

### Optional future cross-dataset identity tables

Do **not** create these initially unless product requirements require unique-person analytics across datasets:

| Table | Purpose | Stored data |
|---|---|---|
| `assistant.person_entities` | Reviewed canonical person identity layer across dataset rows. | Internal person entity ID and minimal non-sensitive identity summary. |
| `assistant.person_record_links` | Auditable mapping from person entity to source rows. | Person entity ID, source row ID, `file_id`, match method, confidence, reviewer/verification state. |

Never populate these by name-only automatic deduplication.

## 10.9 Tables the assistant depends on vs. tables it owns

Keep the distinction explicit:

```text
EXISTING APPLICATION DATA (read only through gateway)
    file
    data_config
    file_data
    file_data_normalized
    approved reference data
    optional sanitized attachment/version metadata

ASSISTANT-OWNED STATE (CRUD in assistant schema)
    dataset_policy
    field_registry
    access_grants
    entity_aliases
    conversations/messages/state
    query frames/results/plans/runs
    citations/voice sessions/feedback/audit/jobs
    optional attachment chunks
```

The assistant must never modify `file`, `data_config`, `file_data`, or `file_data_normalized` through the question-answer path.

## 10.10 Indexes and extensions required for the assistant

The inspected database already has useful B-tree indexes but lacks a full-text GIN index over normalized search text and does not have `pg_trgm` installed.

Initial production additions should include:

```text
pg_trgm extension
GIN FTS index over the assistant current-record search vector
indexes on file_id + version + status
indexes on canonical_name/community/school where useful
indexes on assistant conversation/query foreign keys and timestamps
unique constraints for registry/grant/source identities
```

Do not require `pgvector` initially.

For the current corpus size, the initial retrieval stack is:

```text
parameterized SQL / JSONB
+ PostgreSQL FTS
+ pg_trgm
+ RapidFuzz
```

with local semantic retrieval added only after evaluation proves it necessary.

---

# 11. Hybrid query planning over the actual research-data model

Do **not** classify a user request as simply "SQL" or "RAG". A single user turn may combine dataset scoping, structured predicates, lexical/semantic retrieval, set operations, calculations, exact raw-field lookup, and final synthesis.

All QueryPlan fields must resolve through `assistant.field_registry`, and all data operations must execute through the Assistant Data Gateway from Section 10.

The planner sees semantic fields such as:

```text
student_name
first_name
last_name
indigenous_name
community
school
student_number
birth_date
admitted_date
discharged_date
death_date
deceased_status
cause_of_death
death_details
notes
additional_information
burial_location
```

It does **not** see or select raw application tables. The executor maps semantic fields to dataset-specific canonical/raw JSON paths.

## 11.1 QueryPlan scope is explicit

Every plan begins with a data scope derived from:

```text
validated AccessScope
+ conversation/query frame
+ explicit dataset wording
+ product defaults
```

Example:

```json
{
  "scope": {
    "file_ids": [49],
    "version_mode": "current",
    "authorized_only": true
  }
}
```

A plan may narrow this scope but never broaden it beyond the AccessScope.

Normal queries use current versions only. A plan can request historical/version data only through an explicit, feature-gated history operation.

## 11.2 QueryPlan as a DAG

Example mixed request:

```text
"How many students whose names start with S are recorded as deceased,
and what do their records say about causes of death?"
```

Possible logical plan:

```json
{
  "scope": {
    "file_ids": [49],
    "version_mode": "current"
  },
  "goals": ["exact_count", "cause_summary"],
  "steps": [
    {
      "id": "s_names",
      "op": "FILTER",
      "input": "current_records",
      "where": [
        {"field": "student_name", "operator": "STARTS_WITH", "value": "S"}
      ]
    },
    {
      "id": "deceased",
      "op": "FILTER",
      "input": "s_names",
      "where": [
        {"field": "deceased_status", "operator": "IS_TRUE"}
      ]
    },
    {
      "id": "count",
      "op": "COUNT",
      "input": "deceased"
    },
    {
      "id": "evidence",
      "op": "GET_EVIDENCE",
      "input": "deceased",
      "fields": ["student_name", "cause_of_death", "death_details"],
      "limit": 8
    }
  ]
}
```

The database/executor computes the exact count. The LLM receives the count plus only the selected cause/death evidence needed to answer the second part.

## 11.3 Simple deterministic plans

Example:

```text
"How many students have names starting with S?"
```

Plan:

```json
{
  "scope": {"file_ids": [49], "version_mode": "current"},
  "steps": [
    {
      "id": "matches",
      "op": "FILTER",
      "input": "current_records",
      "where": [
        {"field": "student_name", "operator": "STARTS_WITH", "value": "S"}
      ]
    },
    {"id": "result", "op": "COUNT", "input": "matches"}
  ]
}
```

This should use **zero reasoning-model calls** when the scope/field interpretation is unambiguous.

## 11.4 Cross-dataset plans without pretending rows are globally unique people

The database has no global person table. Cross-dataset plans must therefore be explicit about whether they operate on:

```text
records
canonical-name strings
verified person links (future optional feature)
```

For example:

```text
"Which names appear in both the student master list and confirmed-deaths dataset?"
```

may execute as:

```text
records from file 49 → PROJECT normalized student_name
records from file 91 → PROJECT normalized student_name
INTERSECT normalized name values
```

The answer must describe these as **matching names/records**, not proven unique-person identity, unless the optional reviewed person-link layer exists.

## 11.5 Supported operation vocabulary

The planner/executor may use only a constrained operation language.

### Scope/data-selection operations

```text
USE_DATASET
USE_CURRENT_VERSION
USE_HISTORY_VERSION       # feature-gated
USE_PREVIOUS_RESULT
USE_TOPIC_FRAME
```

### Structured operations

```text
FILTER
PROJECT
COUNT
COUNT_DISTINCT
SUM
AVG
MIN
MAX
SORT
LIMIT
GROUP_BY
EXISTS
DATE_RANGE
TOP_N
```

### Lexical/entity operations

```text
EXACT_LOOKUP
ALIAS_LOOKUP
REFERENCE_LOOKUP
FULL_TEXT_SEARCH
FUZZY_SEARCH
```

### Optional semantic operations

```text
SEMANTIC_SEARCH
SEMANTIC_CLASSIFY
```

These are local/open-model operations when enabled and are not a separate database path.

### Conversation operations

```text
RESOLVE_ENTITY
RESOLVE_PRONOUN
RESOLVE_ORDINAL
USE_PREVIOUS_RESULT
USE_ACTIVE_QUERY
USE_TOPIC_FRAME
APPLY_CONSTRAINT_EDIT
```

### Set operations

```text
INTERSECT
UNION
DIFFERENCE
EXCLUDE
```

### Calculation/comparison operations

```text
RATIO
PERCENTAGE
COMPARE
RANK
NORMALIZE
```

### Evidence operations

```text
GET_EVIDENCE
GET_RAW_FIELDS
GET_QUOTE
GET_PROVENANCE
CHECK_CONFLICTS
DEDUPLICATE
GET_APPROVED_ATTACHMENTS   # feature-gated
```

Do not allow arbitrary SQL generated by the LLM.

## 11.6 Deterministic parser first; constrained LLM planner only when needed

Use local deterministic parsing for obvious:

- dataset/file names;
- counts and aggregates;
- starts/ends/contains;
- equality/inequality;
- dates, years, ranges, before/after;
- known field aliases;
- reference entities;
- explicit limits/sorts;
- simple follow-up constraint changes.

A difficult request such as:

```text
"Among the records we were discussing, which communities seem to have
more evidence of repeated admissions, and what supports that?"
```

may use `grok-4.20-0309-non-reasoning` as a **constrained planner**.

The planning prompt contains:

```text
question
compact conversation/query state
allowed dataset descriptors
assistant.field_registry subset
allowed operation vocabulary
```

It does not contain database rows and does not contain forbidden application tables.

The LLM returns typed QueryPlan JSON, which must be validated before execution.

## 11.7 Iterative/dependent plans

Some plans require intermediate results before later steps.

Example:

```text
"Which communities have the highest proportion of records marked deceased?"
```

may require:

```text
1. choose authorized dataset scope
2. group all qualifying records by normalized community
3. count total records per community
4. count deceased-status records per community
5. calculate deceased / total
6. enforce minimum-denominator policy if configured
7. rank proportions
8. retrieve a small amount of supporting evidence only if explanation is requested
```

The executor passes intermediate IDs/counts between steps. Do not send thousands of rows to the LLM to perform the arithmetic.

## 11.8 Parallel execution of ready QueryPlan branches

The QueryPlan DAG is an execution graph, not merely a descriptive structure. Once validation completes, every step whose dependencies are satisfied should be scheduled immediately subject to the bounded concurrency rules in Section 9A.

Examples of naturally parallel branches include:

```text
independent dataset scans
independent numerator/denominator aggregates
exact + FTS + fuzzy retrieval signals
independent comparison-side evidence fetches
independent source/provenance checks
```

Examples that must remain sequential include:

```text
entity resolution → entity-specific query
semantic candidate classification → count of classified IDs
plan generation → plan validation → execution
retrieval/computed facts → final synthesis
```

Record branch timing in `assistant.query_step_runs` and expose the critical path in observability.

## 11.9 Retrieval hierarchy inside a plan

When a step needs text/entity retrieval, prefer:

```text
1. exact canonical/raw lookup through field registry
2. reference aliases/variants
3. structured JSONB predicates
4. PostgreSQL full-text search
5. pg_trgm / RapidFuzz
6. optional local semantic search
```

Compatible retrieval branches may run in parallel.

## 11.10 Result fusion

The executor produces two classes of output:

```text
COMPUTED FACTS
- exact record counts
- grouped counts
- dates/ranges
- percentages
- set intersections/differences
- rankings

EVIDENCE
- source row IDs
- selected canonical/default-bundle fields
- selected narrative/raw fields
- quotations
- approved attachment chunks
- provenance/conflict indicators
```

The final LLM never recomputes exact aggregates from prose when the executor has already produced them.

## 11.11 Required user scenarios

The planner, executor, memory, and response layer must support at least:

### A. Structured record queries

```text
"How many students have names starting with S?"
"How many records are from a particular community?"
"List records admitted before 1920."
```

### B. Text/narrative retrieval

```text
"Which records mention tuberculosis?"
"What do the notes say about this student?"
```

Use FTS/structured field retrieval first and optional local semantic retrieval only if needed.

### C. Mixed structured + narrative questions

```text
"How many students admitted before 1920 have notes mentioning illness,
and summarize the strongest evidence?"
```

### D. Multi-part questions

```text
"How many matching records are there, which communities occur most often,
and summarize the death-related evidence?"
```

Reuse intermediate result sets.

### E. Follow-up constraint edits

```text
"How many students were admitted in 1910?"
"What about 1911?"
"Only from Garden River."
"Exclude records with unknown discharge dates."
```

Modify the active query frame rather than treating each as unrelated.

### F. Pronouns/ordinals/result references

```text
"Tell me about the first one."
"What does that record say about parents?"
"Compare those two."
```

Resolve against structured result-set state.

### G. Ambiguous names / STT errors

Use canonical names, reference variants, `pg_trgm`, RapidFuzz, assistant aliases, and conversation context. Ask clarification when confidence is insufficient.

### H. Voice self-correction

```text
"Show records from 1912—sorry, 1913."
```

Prefer corrected constraints.

### I. Interruption/refinement

```text
Assistant: "There are ..."
User: "Only the confirmed dataset."
```

Cancel speech and re-run the prior plan with the narrowed dataset scope.

### J. Exact raw-value / quotation requests

```text
"What exactly is written in the Notes field?"
```

Use `GET_RAW_FIELDS`/`GET_QUOTE` after selecting authorized source rows.

### K. Comparison/ranking

```text
"Which communities have the most records?"
"Compare the admitted-date ranges for these two result sets."
```

Distinguish exact rankings from subjective/inference rankings.

### L. Negation/set operations

```text
"Records in community A but not community B."
"Names that occur in both the master list and confirmed-deaths dataset."
```

### M. Temporal/history questions

Use canonical date semantics for normal dates. Dataset version history is separately feature-gated through safe version metadata; do not mix historical copies into current factual answers.

### N. Derived facts/percentages

Execute numerator, denominator, and ratio exactly in the executor.

### O. Semantic classification feeding deterministic computation

For questions such as:

```text
"How many records contain evidence suggesting a particular theme?"
```

retrieve a narrowed candidate set first, classify only those candidates if necessary, then count matching source IDs. Never send the full dataset to a classifier prompt.

### P. Conflicting/duplicate evidence

Surface conflicts and deduplicate repeated evidence so copied text is not mistaken for independent corroboration.

### Q. Missing/unknown data

The Potential dataset is sparse. Distinguish missing/unknown from false/no, and never infer absent values.

### R. Explicit inference

If the user asks "why", "likely", "seems", or similar, label inference and cite the supporting record fields. Do not present inference as stored fact.

### S. Provenance/challenge

```text
"Where did you get that?"
"That's wrong—check again."
```

Use prior citation/result state; challenge paths re-retrieve/recompute rather than merely regenerate prose.

### T. Topic switching

Maintain multiple query frames so the user can say:

```text
"Going back to the confirmed-deaths records..."
```

### U. Access-controlled private datasets

Authorization is checked before retrieval. An unauthorized request for files 93/94 must not reveal names, counts, snippets, citation metadata, or search-hit existence.

### V. External attachment-content questions

Only supported after approved attachment files are ingested into `assistant.attachment_sources/chunks`. Before that, the assistant may expose only approved attachment metadata permitted by policy.

## 11.12 Planning cost policy

Preferred paths:

```text
simple exact query
→ local deterministic plan
→ gateway/database
→ deterministic formatter
→ 0 reasoning calls

normal synthesis query
→ local plan/retrieval
→ one reasoning call
→ answer

complex compositional query not reliably planned locally
→ constrained planning call
→ validated execution
→ final synthesis only if needed
```

A complex turn may legitimately require more than one reasoning interaction when correctness requires it, but never use an LLM simply to decide "SQL vs RAG."

## 11.13 Plan safety

Every QueryPlan must be:

1. schema/semantic-field validated against `assistant.field_registry`;
2. AccessScope validated;
3. dataset-policy validated;
4. operator allowlist validated;
5. dependency/DAG validated;
6. current/history mode validated;
7. resource-budget validated;
8. translated to parameterized gateway operations by backend code.

Reject or clarify unsafe/nonsensical plans. The planner cannot request forbidden application tables, arbitrary JSON paths, or arbitrary SQL.

---

# 12. Fuzzy/entity matching for the inspected data

Use RapidFuzz.

Reference:

repositories/RapidFuzz

Use it for user-facing research entities such as:

- student/person names and Indigenous names represented in research rows;
- communities/reserves;
- school names;
- Indian hospital names;
- province/location strings;
- safe user-facing dataset/file names;
- common whisper.cpp transcription errors.

Resolution order should combine:

```text
exact canonical value
   ↓
assistant.field_registry aliases
   ↓
reference-table variants
   ↓
normalized token match
   ↓
PostgreSQL pg_trgm
   ↓
RapidFuzz
   ↓
conversation/result-set context
   ↓
clarification if still ambiguous
```

Do not use application `users` or administrator/support tables as entity sources.

Do not automatically accept low-confidence or closely tied fuzzy matches.

---

# 13. PostgreSQL fuzzy search

Use PostgreSQL:

```text
pg_trgm
```

for database-side similarity matching.

Use:

* GIN/GiST indexes where appropriate;
* trigram similarity;
* normalized text columns.

RapidFuzz is complementary, not a replacement.

---

# 14. PostgreSQL full-text search

Use:

```text
tsvector
tsquery
GIN indexes
```

for text retrieval.

Precompute searchable vectors during ingestion.

Rank matches using PostgreSQL's full-text ranking capabilities plus your own metadata/entity weighting.

---

# 15. Ranking and result fusion for research records

Build deterministic ranking appropriate to the operation.

Possible lexical/entity score:

```text
final_score =
    exact_semantic_field_match_weight
  + exact_reference_alias_weight
  + metadata/canonical_match_weight
  + FTS_rank
  + trigram/fuzzy_weight
  + query-specific date/scope weight
```

Ranking rules depend on the question. Examples:

- exact canonical-name/reference matches outrank fuzzy matches;
- requested canonical field matches outrank incidental `search_text` mentions;
- evidence matching several requested semantic fields may outrank a single weak mention;
- current authorized rows always outrank/replace historical copies in ordinary queries;
- narrative evidence should not dominate merely because a row contains more text;
- private/unauthorized rows are removed **before** ranking, not given a low score;
- duplicate/near-duplicate evidence should be collapsed before LLM context construction.

For subjective rankings such as "strongest evidence", keep the basis visible and do not pretend it is an objective database field.

Return only useful top evidence, typically a small number of source rows/chunks, while exact aggregates can use the complete filtered set inside PostgreSQL without passing those rows to the LLM.

---

# 16. Context builder: field-specific evidence from current authorized records

The context builder is critical because the normalized research layer already contains compact answer-oriented representations. Do not send whole JSONB rows merely because they are available.

Input:

```text
question
validated AccessScope
resolved entities
QueryPlan computed facts
selected source_row_ids
conversation/query memory
```

Output:

```text
EvidencePacket
```

The evidence selection priority should be:

```text
1. executor-produced exact facts
2. compact canonical fields specifically requested by the plan
3. chat.default_bundle for concise identity/context
4. selected narrative fields only when the question requires them
5. exact raw file_data fields when provenance/quotation requires the authoritative source value
6. approved attachment chunks only when attachment-content ingestion is enabled
```

Do not automatically send:

```text
full row_data
full row_data_normalized
full search_text
all omitted/narrative fields
all fields from every matching record
```

Example:

```text
QUESTION
How many students whose names start with S were recorded as deceased,
and what do the records say about the causes of death?

SCOPE
Dataset: Shingwauk And Wawanosh Students Master List (file 49)
Access: authorized current version only

COMPUTED FACTS
Matching students: <exact executor count>
Matching deceased-status records: <exact executor count>

EVIDENCE
[file:49:v3:row:<id>]
Name: <canonical display name>
Deceased status: <canonical value>
Death/cause field: <requested safe field only>

[file:49:v3:row:<id>]
...
```

The LLM must never see unrelated rows, unauthorized datasets, application-admin tables, or operational metadata.

Enforce configurable budgets for:

```text
maximum evidence rows
maximum evidence tokens
maximum narrative characters per source
maximum sources per answer
```

Start around 1,500–4,000 evidence tokens and tune using evaluation.

---

# 17. Optional pgvector support

Support pgvector architecturally but keep it disabled by default.

Reference:

repositories/pgvector

Do not use a separate Pinecone/Qdrant/Milvus deployment initially.

If semantic search later becomes necessary:

```text
PostgreSQL
+
pgvector
```

should be sufficient for this dataset size.

Do not use a paid embedding API.

If vector retrieval is enabled later, use local/open embedding inference.

Semantic/vector search should be a fallback/secondary signal, not the default retrieval mechanism.

---

# 18. Preprocessing and attachment ingestion

The core research dataset is already normalized in `file_data_normalized`; do not rebuild or duplicate the full application dataset for every assistant deployment.

Initial preprocessing work should focus on:

```text
1. build/sync assistant.field_registry from data_config + observed normalized/raw keys + curated semantics
2. build safe current-record FTS indexes
3. build/sync reference aliases from communities/day_schools/indian_hospitals/provinces
4. validate canonical date values and mark outliers rather than silently trusting them
5. optionally cache derived search helpers that are safe and reproducible
```

### External attachment content

The inspected database contains attachment metadata/URLs but not the binary PDF/image contents. Only if product scope includes questions such as:

```text
"What does this document say?"
"Where in the certificate is this stated?"
```

implement an offline attachment pipeline:

```text
approved attachment metadata
      ↓
fetch external file
      ↓
verify checksum/type/size
      ↓
extract text
      ↓
OCR only when needed
      ↓
structure-aware chunking
      ↓
assistant.attachment_sources
assistant.attachment_chunks
      ↓
FTS / optional local embeddings
```

Rejected, pending, internal-review, or unauthorized attachments must never enter the factual retrieval index.

---

# 19. Chunking and provenance

Chunking applies primarily to separately ingested external documents/attachments, not to every `file_data` record.

For dataset rows, prefer field-level evidence from canonical/default/narrative bundles rather than arbitrary token chunks.

For external documents, prefer:

1. document structure;
2. page/section headings;
3. paragraphs;
4. reasonable token limits.

Preserve:

```text
attachment_source_id
file_id
source_row_id
page_number
section
chunk_number
source offsets where available
checksum/version
```

so every answer can map back to the user-facing source.

---

# 20. Conversation memory, active query state, dataset scope, and topic frames

Do not send the entire chat history to the LLM indefinitely.

Maintain structured conversational state that references user-facing research sources rather than nonexistent global person/document tables.

## 20.1 Active entity/source memory

Example:

```json
{
  "active_file_ids": [49],
  "active_source_rows": [12345, 12346],
  "active_names": ["<normalized display name>"],
  "active_communities": ["<community>"],
  "active_topics": ["admission history"],
  "last_source_ids": ["file:49:v3:row:12345"],
  "pending_references": {
    "that record": "file:49:v3:row:12345",
    "the second one": "result_set:rs_123:index:1"
  }
}
```

## 20.2 Active query state

Store logical constraints, not raw SQL:

```json
{
  "file_ids": [49],
  "version_mode": "current",
  "filters": [
    {"field": "admitted_date", "operator": "YEAR_EQUALS", "value": 1911},
    {"field": "community", "operator": "EQUALS", "value": "<community>"}
  ],
  "sort": null,
  "limit": null
}
```

This enables:

```text
"How many students were admitted in 1910?"
"What about 1911?"
"Only from <community>."
"Exclude records with unknown discharge date."
```

## 20.3 Previous result sets

Persist lightweight source references only:

```json
{
  "result_set_id": "rs_123",
  "record_type": "research_rows",
  "file_ids": [49],
  "ordered_source_ids": [
    "file:49:v3:row:12345",
    "file:49:v3:row:12346"
  ],
  "sort": "admitted_date ASC",
  "source_turn_id": "turn_17"
}
```

Do not copy full JSON rows into `assistant.result_sets`.

This supports:

```text
"Tell me about the second one."
"Compare the first two."
"Which one has the earlier admission date?"
```

## 20.4 Multiple topic/query frames

Maintain multiple frames such as:

```text
Frame A: master-list students from a community
Frame B: confirmed-deaths records for a school
Frame C: prior name-intersection query
```

"Going back to the confirmed-deaths records" should restore Frame B.

Each frame contains:

```text
frame_id
dataset scope
semantic entities
logical query constraints
recent result-set IDs
last source IDs
last_used_at
```

## 20.5 Recent conversational text

Keep separately:

```text
recent_turns: last 4–6 finalized user/assistant turns
rolling_summary: roughly 100–300 tokens
```

The planner/reasoner receives only relevant pieces of this state.

## 20.6 Corrections and interrupted turns

Store:

- finalized user transcript;
- corrected constraints;
- whether assistant speech was interrupted;
- delivered assistant text boundary where known;
- QueryPlan/result state produced before interruption.

An interruption should not erase useful query state.

---

# 21. Avoid separate memory-model calls

Do not add another paid LLM call after every response merely to update memory.

For turns that already require reasoning/synthesis, request the answer plus a compact structured memory update in the same response.

Example:

```json
{
  "answer": "...",
  "citations": [
    "file:49:v3:row:12345",
    "file:49:v3:row:12346:field:death_details"
  ],
  "memory_update": {
    "active_file_ids": [49],
    "active_source_rows": [12345, 12346],
    "active_topics": ["death records"],
    "last_source_ids": ["file:49:v3:row:12345"]
  }
}
```

Validate all returned source references before storing them.

For deterministic turns that skip the reasoning model, update query/source memory directly from the validated QueryPlan and executor result.

This keeps normal synthesis close to one reasoning call while preserving zero-call deterministic paths.

---

# 22. Optional Redis

Support Redis but do not require it for the smallest deployment.

Reference:

repositories/redis

PostgreSQL remains the durable source of truth.

Redis can later cache:

```text
session state
active entities
recent turns
retrieval results
popular answers
LiveKit session metadata
```

For the initial product it is acceptable to use:

```text
LiveKit worker memory
+
PostgreSQL
```

and add Redis when multiple backend workers or scale justify it.

---

# 23. Test reasoning model: xAI Grok 4.20 non-reasoning

For the test/initial provider profile use the exact model ID:

```text
grok-4.20-0309-non-reasoning
```

Official references:

https://docs.x.ai/developers/models/grok-4.20-non-reasoning

repositories/xai-sdk-python

Use the asynchronous xAI SDK client so reasoning/model network I/O does not block the realtime event loop.

This model should be used only where interpretation, constrained planning, comparison, semantic classification, or final synthesis is needed. It should not receive the whole database and it should never have general database credentials.

Use it for:

* reasoning over the compact EvidencePacket;
* comparing selected authorized records;
* final synthesis;
* difficult natural-language interpretation;
* constrained QueryPlan generation when deterministic/local planning is insufficient;
* structured memory updates;
* bounded semantic classification of already-retrieved candidate evidence when a deterministic method is insufficient.

Do not use it for:

* basic SQL/JSONB retrieval;
* exact counts, sorting, joins, percentages, or set operations;
* simple entity resolution;
* fuzzy string matching;
* document indexing;
* basic deterministic date parsing;
* vector generation;
* VAD;
* transcription;
* authorization decisions.

Design an abstraction:

```text
ReasoningProvider
    stream_answer()
    answer_structured()
    plan_structured()
```

Implement:

```text
XAIReasoningProvider
```

with asynchronous streaming and structured-output support.

The provider must accept configurable model IDs so later testing can compare another provider/model without changing the rest of the architecture.

For parallel execution, guard paid model calls with a bounded semaphore. Independent semantic sub-classification calls may execute concurrently only when the planner explicitly produces independent tasks and the configured paid-model concurrency budget allows it.

---

# 24. Reasoning prompt contract

The model should receive a strict system instruction similar to:

```text
You are a conversational assistant answering questions about the supplied evidence.

Use only evidence supplied in this request for factual claims about the database.

Do not invent missing records.

If evidence is insufficient or conflicting, clearly say so.

Prefer concise conversational answers.

Use source IDs internally for citations.

In voice mode, do not speak raw citation IDs unless asked.

Resolve follow-up wording using the supplied conversation memory.

Return the requested structured memory update.

Never assume access to records not included in the evidence block.

Treat executor-produced counts, dates, aggregates, rankings, and set results as authoritative computed facts; do not recompute them from prose.

Distinguish factual claims, explicit inference, and unknown information.

If evidence conflicts, report the conflict instead of silently resolving it unless a supplied source-reliability rule resolves it.

When the user requests an exact quotation, preserve the supplied source wording and citation rather than paraphrasing it.
```

---

# 25. Test/initial TTS: xAI Text to Speech

Use xAI Text to Speech for the test/initial paid TTS profile.

Official references:

https://docs.x.ai/developers/models/text-to-speech

https://docs.x.ai/developers/rest-api-reference/inference/voice

Use the streaming WebSocket form of the xAI TTS API for realtime voice output:

```text
wss://api.x.ai/v1/tts
```

Keep the voice configurable rather than hardcoding product behavior. For test defaults, `eve` may be used unless another voice is selected.

Create an abstraction:

```text
TTSProvider
    connect_session()
    synthesize_stream(text, voice_config)
    cancel_generation()
    close_session()
```

Implement:

```text
XAITTSProvider
```

It must support:

* bidirectional streaming;
* reusable/multi-utterance session connection when supported;
* cancellation/queue clearing for barge-in;
* configurable voice;
* configurable language and audio format;
* phrase/sentence input chunks;
* per-phrase sequence IDs so audio remains ordered;
* first-audio latency measurement;
* reconnect/failure handling.

Preconnect the xAI TTS WebSocket when voice mode becomes active so the TTS handshake is normally removed from the answer critical path.

Suggested speaking behavior:

```text
Speak naturally and conversationally.
Use a calm, warm, confident tone.
Do not sound like you are reading a formal report.
Use natural short pauses between ideas.
Keep responses concise in voice mode.
Pronounce names carefully.
Avoid excessive enthusiasm or filler.
```

Do not send source documents or database EvidencePackets to TTS. TTS receives only the final answer phrases selected for speech.

---

# 26. Stream TTS before the full answer is complete

Do not wait for the entire LLM response.

Pipeline:

```text
LLM token stream
       ↓
phrase/sentence boundary detector
       ↓
TTS queue
       ↓
xAI TTS WebSocket streaming
       ↓
LiveKit audio output
```

Example:

```text
LLM generates:

"John Smith joined the project in 2023.
He became technical lead in April 2024.
The final report..."

As soon as the first sentence is stable:

"John Smith joined the project in 2023."

        ↓

send to TTS

while LLM continues generating
```

This is necessary for low perceived latency.

Do not break text into tiny word fragments that sound unnatural.

Use short semantic phrases/sentences.

---

# 27. High-traffic TTS migration: Kokoro

When traffic makes cloud TTS cost substantial, switch TTS to Kokoro.

Primary model repository:

repositories/kokoro

Recommended API wrapper:

repositories/Kokoro-FastAPI

Kokoro should be self-hosted.

Implement:

```text
KokoroTTSProvider
```

with the same application interface as:

```text
XAITTSProvider
```

so switching should require configuration, not a rewrite.

Environment configuration example:

```text
TTS_PROVIDER=xai
```

or:

```text
TTS_PROVIDER=kokoro
```

Test/initial profile:

```text
xAI Text to Speech
```

High traffic:

```text
Kokoro
```

The rest of the architecture must remain unchanged.

---

# 28. Optional future local reasoning

Do not use this in the initial product, but design the reasoning-provider interface so local reasoning can later replace paid reasoning.

Reference:

repositories/gpt-oss

Possible future model:

```text
gpt-oss-20b
```

Do not deploy it initially unless requested.

The current objective is:

```text
paid reasoning API
+
local infrastructure
```

because that is likely more economical for a small application than maintaining a GPU server.

---

# 29. LiveKit RAG integration

Use LiveKit's user-turn completion hook or equivalent pre-LLM hook.

Reference documentation:

https://docs.livekit.io/agents/logic/external-data/

Important architecture:

```text
user finishes turn
       ↓
final transcript
       ↓
on_user_turn_completed()
       ↓
conversation-aware query builder
       ↓
database retrieval
       ↓
context builder
       ↓
LLM starts
```

Do **not** begin a factual response before retrieval completes.

This avoids:

```text
LLM guesses answer
→ context changes
→ throw generation away
→ regenerate
```

which wastes tokens.

---

# 30. Preemptive generation

Initially disable speculative/preemptive LLM answer generation if it starts before database retrieval has completed.

The retrieval path should be extremely fast.

Optimize:

```text
entity resolution
+
indexed PostgreSQL queries
+
context assembly
```

instead of paying for speculative generations that may need to be discarded.

After measuring production latency, optionally experiment with safe forms of pre-generation for generic acknowledgements only.

---

# 31. Chat history

Every user message and assistant answer should be persisted.

Voice messages should save:

```text
final transcript
mode = voice
timestamps
interrupted flag
```

Text messages:

```text
mode = text
```

Both should appear in the same conversation thread.

The user should be able to:

```text
type a question about a result set
↓
switch to voice
↓
say "what does the second record say in its Notes field?"
```

and the system must understand the reference using shared session memory.

---

# 32. Realtime partial transcript

During voice input:

```text
User audio:
"How many students admitted before..."
```

UI should display:

```text
How many students admitted before...
```

before the turn is final.

Clearly distinguish:

```text
partial transcript
```

from:

```text
final transcript
```

Only finalized text should normally be added as a permanent user message.

---

# 33. Assistant streaming text

The user should see answer text appear while it is generated.

Voice mode should therefore simultaneously provide:

```text
streaming assistant text
+
streaming assistant speech
```

This allows users to:

* read while listening;
* inspect names/numbers;
* see citations;
* interrupt if the answer goes in the wrong direction.

---

# 34. Citation and provenance handling

Every factual evidence item must have a stable source identifier tied to the existing research dataset, not a generic invented `person:` or `document:` identifier.

Recommended formats:

```text
file:49:v3:row:12345
file:91:v3:row:67890:field:cause_of_death
attachment:882:page:3:chunk:2
```

A citation record must contain enough information to re-check authorization and re-fetch the exact source without storing the whole source payload in assistant tables.

The reasoning model returns citation references only from the IDs included in its EvidencePacket.

The backend must validate that:

1. every cited source was actually supplied to the model;
2. the source was authorized for the current user at retrieval time;
3. the source row was current-version unless the query explicitly requested history;
4. quoted text came from the exact raw field/attachment chunk cited;
5. private-dataset citations do not leak source metadata to unauthorized users.

The frontend should make citations clickable and may show:

- dataset/file display name;
- safe record identity fields;
- the relevant field/excerpt;
- source version;
- approved attachment/page when applicable.

Do not expose internal database IDs, reviewer details, user/admin metadata, or arbitrary raw JSON unless explicitly approved for that view.

---

# 35. Security: database isolation, authorization, and least privilege

Authentication is mandatory for any non-public assistant session.

The assistant must **not** authenticate users by reading the `users`, `roles`, `otps`, or application session/log tables. Authentication and authorization remain responsibilities of the existing website.

The website passes the assistant a validated, minimal `AccessScope` containing only what is required to retrieve user-facing research data.

Security flow:

```text
website user/session
      ↓
existing website auth + authorization
      ↓
minimal signed/validated AccessScope
      ↓
assistant backend
      ↓
Assistant Data Gateway
      ↓
allowed datasets/fields only
```

Requirements:

- separate restricted database role for the assistant runtime;
- no direct `SELECT` on general application tables;
- no generic SQL execution tool;
- no raw schema discovery by the LLM;
- allowlisted assistant views/functions only;
- dataset policy checked before every query step;
- private files require explicit access grant;
- authorization applied **before** candidate retrieval, FTS, fuzzy matching, result fusion, and LLM context construction;
- current-version scoping applied in the data gateway;
- parameterized SQL generated by backend code only;
- secrets only on the server;
- no xAI API key in browser;
- secure LiveKit token issuance and short-lived tokens;
- encrypted HTTPS/WSS/WebRTC;
- audit assistant actions in `assistant.audit_events`, not by searching application `logs`;
- do not persist raw audio by default;
- do not copy sensitive source tables into assistant-owned tables.

Explicitly test that the assistant role cannot execute:

```sql
SELECT * FROM users;
SELECT * FROM otps;
SELECT * FROM logs;
SELECT * FROM support_requests;
```

and cannot enumerate unrelated application tables through information-schema/catalog access beyond what is strictly necessary.

The question-answer path is read-only with respect to existing research data. Future edit/write features require a separate permissioned workflow and must never reuse the normal retrieval executor.

---

# 36. Privacy and data minimization

The assistant should minimize data at four boundaries:

### Database boundary

Retrieve only authorized user-facing research fields from the safe exposure layer. Never retrieve application-admin/auth/support/log data merely to filter it later.

### Planner boundary

For complex LLM planning, provide:

```text
question
compact conversation/query state
assistant.field_registry subset
allowed operations
allowed dataset descriptors
```

Do **not** provide database rows during planning unless a later synthesis step requires evidence.

### Reasoning boundary

The reasoning model receives only:

```text
current question
compact memory
executor-produced exact facts
small authorized evidence packet
```

### TTS boundary

TTS receives only the finalized text to speak. It does not receive raw records, source JSON, database schemas, authorization data, or citation payloads.

Avoid unnecessary PII in assistant-owned state. Use opaque principal IDs rather than copying names/emails from the application's user system.

Retention periods must be configurable for:

- conversation messages;
- result sets;
- query-plan traces;
- audit events;
- user feedback;
- optional attachment-extracted text.

Support deletion/anonymization of assistant-owned conversation data without modifying the authoritative research datasets.

---

# 37. Observability

Instrument with OpenTelemetry-compatible tracing where practical.

Measure:

```text
session setup latency
WebRTC state
VAD timing
STT partial latency
STT final latency
turn-end detection latency
retrieval latency
retrieval result count
retrieval top scores
LLM first-token latency
LLM completion latency
TTS first-audio latency
barge-in cancellation latency
end-of-speech → first audible answer
database query duration
token counts
estimated reasoning cost
estimated TTS cost
errors
reconnects
```

For every turn generate a trace connecting:

```text
turn_id
→ transcription
→ retrieval
→ LLM
→ TTS
```

---

# 38. Retrieval and execution observability

Log enough metadata to diagnose retrieval quality without reproducing sensitive source payloads.

Per turn/query run, record:

```text
query plan ID/hash
normalized semantic intent
allowed dataset IDs
resolved entity references
planner type: deterministic or constrained-LLM
step operations
candidate counts
selected source IDs
retrieval scores
retrieval method
computed aggregate summaries
latency/error categories
```

Do not log:

```text
passwords / OTPs
application user records
support/contact records
raw private dataset payloads unless explicitly required for secured debugging
full evidence packets by default
raw microphone audio by default
```

Keep source-row IDs and access-scope fingerprints sufficient for controlled reinspection.

Retrieval quality will matter more than model size for this product, so query/execution traces should support offline evaluation and replay against test data.

---

# 39. Cost control

The system is explicitly budget-oriented.

The test/initial paid profile is xAI `grok-4.20-0309-non-reasoning` for reasoning when needed and xAI Text to Speech for spoken output. Local whisper.cpp, PostgreSQL retrieval, VAD, indexing, and deterministic execution remain unpaid/self-hosted components.

Cost rules:

1. no paid STT;
2. no paid embedding API;
3. no paid vector database;
4. no paid VAD;
5. no paid LLM merely to choose between "SQL vs RAG";
6. deterministic/local planning first;
7. allow the reasoning model as a constrained planner only when a complex natural-language request cannot be planned reliably using local rules;
8. skip the reasoning model entirely for safe deterministic answers when possible;
9. for normal synthesis questions, target one paid reasoning call;
10. complex compositional questions may use a planning interaction plus final synthesis if correctness requires it;
11. initial paid TTS only when voice mode is active;
12. no TTS cost for normal text-chat responses;
13. use deterministic memory/query-state updates where possible;
14. otherwise combine memory updates with the final reasoning response;
15. cache repeatable retrieval operations and safe deterministic results where useful;
16. reuse intermediate QueryPlan results instead of re-querying;
17. cap evidence tokens;
18. cap output length in voice mode;
19. never ask the LLM to count/sort/join records when PostgreSQL can do it exactly;
20. eventually migrate high-volume TTS to Kokoro.

The cost hierarchy should be:

```text
local parser / SQL / FTS / fuzzy / calculations
        ↓ preferred
optional local semantic retrieval
        ↓
paid reasoning only when interpretation/synthesis/planning is needed
        ↓
paid TTS only for spoken output
```

---

# 40. Example complete voice turn using the inspected database

Implement behavior equivalent to:

```text
User begins speaking
       ↓
browser streams WebRTC audio
       ↓
LiveKit session
       ↓
Silero VAD
       ↓
whisper.cpp partial transcripts

"How many students..."
"How many students have..."
"How many students have names starting with S?"
       ↓
final transcript
       ↓
conversation resolver
       ↓
product scope rule:
"students" → primary master-list dataset file 49
       ↓
AccessScope check
file 49 is allowed
       ↓
deterministic QueryPlan
FILTER canonical_name STARTS_WITH S
COUNT current authorized rows
       ↓
Assistant Data Gateway
assistant_api.v_current_records
       ↓
exact database count
       ↓
no reasoning call required
       ↓
template answer text
       ↓
xAI Text to Speech
       ↓
LiveKit audio
```

A mixed question may be:

```text
"How many students whose names start with S are recorded as deceased,
and what do the records say about the causes?"
```

Possible plan:

```text
1. restrict to AccessScope + file 49 + current version
2. FILTER canonical_name STARTS_WITH "S"
3. FILTER deceased_status according to curated field registry
4. COUNT matching records in PostgreSQL
5. PROJECT only source IDs + cause/death fields needed for evidence
6. rank/deduplicate evidence
7. send exact count + compact selected evidence to `grok-4.20-0309-non-reasoning`
8. stream response text and TTS
```

If the user interrupts:

```text
Assistant: "There are ..."
User: "Only records admitted before 1920."
```

cancel current TTS/generation, preserve prior query state, add the temporal constraint through the field registry, re-execute the plan, and continue naturally.

---

# 41. Frontend visual states

Implement clear states:

```text
Disconnected
Connecting
Ready
Listening
User speaking
Processing
Assistant speaking
Interrupted
Reconnecting
Error
```

Voice UI should show:

* microphone activity;
* waveform;
* partial transcript;
* listening indicator;
* assistant speaking state;
* stop/interrupt behavior;
* text response;
* citations.

Do not create a separate voice conversation page unless product design demands it.

Voice should feel like another mode of the same assistant.

---

# 42. Entity aliases and pronunciation dictionary

Because the user-facing data contains Indigenous/community/school/person names and voice transcription can produce spelling variations, combine existing reference data with assistant-curated aliases.

Primary deterministic sources:

```text
day_schools.name + variants
indian_hospitals.name + variants
communities
provinces
file_data_normalized canonical/tokens
assistant.entity_aliases
```

`assistant.entity_aliases` should store only safe research-entity aliases/pronunciation hints, for example:

```text
entity_type
source_file_id / source_row_id or reference key
canonical_display
alias
normalized_alias
phonetic_hint
tts_override
scope
verified
```

Before TTS, optionally transform difficult names into TTS-friendly pronunciation hints while keeping correct spelling in displayed text.

Do not use application users/admin names as an alias source.

---

# 43. Query normalization against a curated field registry

Implement locally:

- Unicode normalization;
- whitespace normalization;
- lowercase search representation;
- punctuation handling;
- basic date/year/range recognition;
- number and identifier normalization;
- correction phrases such as "sorry" / "actually" in voice input;
- entity alias lookup;
- reference-table variants;
- common raw-key aliases from `assistant.field_registry`.

Preserve the original question separately.

Do not hardcode raw JSON keys directly into natural-language parsing. For example, inspected datasets contain inconsistent raw keys such as spelling variants and trailing spaces. Resolve user language to a semantic field first, then let the field registry map it to the correct dataset-specific canonical/raw path.

Date operations must respect normalized date kinds such as exact date, year-only, range, and approximate year. Apply plausibility validation to obvious outliers before aggregate/date comparisons.

---

# 44. Follow-up resolution and conversational query evolution

The assistant must handle research-data follow-ups such as:

```text
"Show students admitted in 1911."
"Only from <community>."
"Which of those are recorded as deceased?"
"Tell me about the second one."
"What exactly do its notes say?"
```

and dataset-scope changes such as:

```text
"Search the master list."
"Now check the confirmed-deaths records."
"Which normalized names appear in both?"
```

Use:

```text
recent turns
active file/dataset scope
active semantic fields/entities
active query state
topic frames
last source IDs
previous result-set IDs
```

before using expensive reasoning.

When a follow-up changes one constraint, retain unaffected constraints.

A user may switch topics and later say:

```text
"Going back to the master-list results..."
```

Restore the matching query frame.

Never let a follow-up silently broaden the user's AccessScope or switch into private files without authorization.

---

# 45. Clarification and ambiguity behavior

Ask a concise clarification when the system cannot safely resolve:

- which dataset/file the user means;
- whether "people" means the primary student master list or records across authorized datasets;
- first name vs. last name vs. full/display name for prefix/suffix questions when product policy does not define a default;
- duplicate/similar student names;
- STT-corrected community/school/person name;
- pronoun/ordinal/result-set reference;
- date/time range;
- subjective ranking criterion;
- cross-dataset identity vs. matching-name semantics.

For example:

```text
"Do you want records from the student master list only, or all datasets you can access?"
```

or:

```text
"I found two close name matches. Which one did you mean?"
```

Do not ask unnecessary clarification when a high-confidence field-registry/reference resolution exists.

Store the answer in the current query frame so the same ambiguity is not repeatedly asked.

---

# 46. No-results, insufficient-evidence, conflict, and access behavior

Distinguish at least:

```text
NO MATCH
INSUFFICIENT EVIDENCE
MISSING / UNKNOWN FIELD
CONFLICTING EVIDENCE
AMBIGUOUS SCOPE/IDENTITY
HISTORY NOT AVAILABLE/ENABLED
ATTACHMENT CONTENT NOT INGESTED
ACCESS RESTRICTED
```

Do not turn missing fields into negative facts.

If normalized and raw source evidence conflict, preserve provenance and use the authoritative field/raw source according to configured rules; do not silently improvise.

If two authorized records disagree, report the conflict rather than choosing one unless a documented source-reliability rule applies.

For exact quotation requests, retrieve the selected raw field or approved attachment chunk and preserve the text faithfully.

For private/unauthorized data, do not reveal whether a particular person/name/record exists in the restricted dataset. Use a generic access response rather than a partial search result.

Do not fall back to general model knowledge for internal-database factual questions unless product policy explicitly permits and clearly labels general knowledge.

---

# 47. Deterministic fast paths inside the hybrid planner

Create deterministic fast paths, but keep them inside the same QueryPlan/execution architecture.

Example:

```text
"How many students have names starting with S?"
```

With the product default that "students" means file 49:

```text
USE_DATASET file 49
USE_CURRENT_VERSION
FILTER student_name STARTS_WITH "S"
COUNT
```

Example:

```text
"How many current records are in each authorized dataset?"
```

can execute:

```text
GROUP_BY file_id
COUNT
```

inside the AccessScope.

Common zero-reasoning operations include:

```text
COUNT / COUNT_DISTINCT over an explicitly defined record/value set
MIN / MAX
GROUP_BY
SORT / TOP_N
EXISTS
structured FILTER
DATE_RANGE
set operations over result IDs/normalized values
simple ratios/percentages
```

For safe deterministic plans:

```text
question
→ local planner
→ validated semantic QueryPlan
→ Assistant Data Gateway
→ exact result
→ deterministic formatter
```

Skip the reasoning LLM entirely when no interpretation/synthesis is needed.

---

# 48. Reasoning, planning, and synthesis paths

Use three composable capabilities.

## 48.1 Local deterministic planning

For straightforward questions:

```text
question
+ active query frame
+ assistant.field_registry
→ local QueryPlan
→ execute through gateway
```

No reasoning model is required.

## 48.2 Constrained reasoning-assisted planning

For difficult language:

```text
question
+ compact conversation/query state
+ allowed dataset descriptors
+ field-registry subset
+ allowed operation vocabulary
→ `grok-4.20-0309-non-reasoning`
→ typed QueryPlan
→ validator
→ gateway executor
```

The planning model receives **no source rows and no general application schema**.

## 48.3 Final synthesis

Use reasoning only when executor-produced facts/evidence need natural explanation, comparison, summarization, explicit inference, or conflict reporting.

Example:

```text
"Summarize what the selected records say about causes of death."
```

may use:

```text
selected source IDs
→ GET_EVIDENCE cause/death fields only
→ deduplicate/conflict check
→ `grok-4.20-0309-non-reasoning` synthesis
```

The final synthesis receives exact computed facts plus a small EvidencePacket, not the whole filtered result set.

Do not force every turn to pay for a final model call. A deterministic result such as an exact count may be formatted directly.

---

# 49. API contracts and AccessScope propagation

Create typed request/response schemas.

Text request example:

```text
POST /api/assistant/query
```

Request:

```json
{
  "conversation_id": "...",
  "question": "...",
  "mode": "text"
}
```

The browser must not be allowed to choose arbitrary `file_id` permissions. The server obtains a trusted access scope from the existing website session/authorization layer and attaches it internally:

```json
{
  "principal_id": "opaque-key",
  "allowed_file_ids": [49, 91],
  "history_allowed": false
}
```

Response stream should provide events such as:

```text
plan_started
plan_validated
retrieval_started
retrieval_completed
computed_fact
answer_delta
citation
memory_update
answer_completed
```

Voice uses LiveKit session/events for audio rather than duplicating audio over the text HTTP endpoint.

Every internal planning/execution request must carry the same immutable AccessScope for the turn. A plan may narrow scope but must never broaden it.

---

# 50. Provider abstractions

All model-dependent components must use interfaces.

```text
STTProvider
ReasoningProvider
TTSProvider
Retriever
MemoryStore
```

Implement:

```text
WhisperCppSTTProvider
XAIReasoningProvider
XAITTSProvider
KokoroTTSProvider
PostgresRetriever
PostgresMemoryStore
```

This prevents vendor lock-in.

---

# 51. Docker deployment

Provide Dockerfiles and Docker Compose for development.

Target services:

```text
frontend
backend
livekit
postgres              # existing DB or local restored development copy
whisper
kokoro                # optional profile initially
redis                 # optional profile
```

For local development, use a **sanitized/seed development database**, not a production dump containing administrator/auth/support data unless a secured environment explicitly requires it.

The backend must connect using `assistant_runtime`, not the existing application's privileged database user.

Example:

```text
docker compose up
```

should produce a usable local system after migrations create the `assistant` / `assistant_api` schemas, safe views/functions, indexes, and assistant-owned tables.

Use optional Docker Compose profiles for Kokoro and Redis.

---

# 52. Production deployment

Document:

- HTTPS and domain configuration;
- LiveKit WebRTC ports and TURN configuration;
- firewall rules;
- environment variables;
- database backups;
- xAI secret handling;
- horizontal backend scaling;
- recoverable voice-session considerations;
- assistant schema migrations;
- grants/privileges for `assistant_gateway_owner`, `assistant_runtime`, and `assistant_migrator`;
- synchronization of `assistant.dataset_policy`, `assistant.field_registry`, and private-file access grants;
- monitoring of background jobs and query-run failures.

Do not expose database ports publicly.

Do not run the assistant with the same database credentials as the main website application.

Production startup should include an automated privilege/self-test that fails closed if `assistant_runtime` can read a forbidden table.

---

# 53. Configuration

Use environment configuration similar to:

```text
ASSISTANT_DATABASE_URL=postgresql://assistant_runtime:.../...
ASSISTANT_SCHEMA=assistant
ASSISTANT_API_SCHEMA=assistant_api

LIVEKIT_URL=
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

XAI_API_KEY=
REASONING_PROVIDER=xai
REASONING_MODEL=grok-4.20-0309-non-reasoning

TTS_PROVIDER=xai
XAI_TTS_VOICE=eve
XAI_TTS_LANGUAGE=en
XAI_TTS_FORMAT=pcm
XAI_TTS_STREAMING=true

WHISPER_MODEL=
WHISPER_SERVICE_URL=

REDIS_URL=

MAX_EVIDENCE_TOKENS=
MAX_RETRIEVAL_RESULTS=
RECENT_TURN_COUNT=
RESULT_SET_RETENTION_HOURS=
QUERY_TRACE_RETENTION_DAYS=


# Parallelism / backpressure
QUERY_DAG_MAX_CONCURRENCY=8
RETRIEVAL_MAX_CONCURRENCY=6
DB_POOL_MIN=2
DB_POOL_MAX=12
DB_QUERY_CONCURRENCY=8
DB_QUERY_TIMEOUT_MS=2000
MODEL_MAX_CONCURRENCY_PER_TURN=2
MODEL_MAX_CONCURRENCY_GLOBAL=16
TTS_QUEUE_MAX_PHRASES=8
WHISPER_MAX_CONCURRENT_SESSIONS=
BACKGROUND_WORKER_CONCURRENCY=4
RETRIEVAL_BRANCH_TIMEOUT_MS=1500
XAI_REQUEST_TIMEOUT_MS=15000
XAI_TTS_FIRST_AUDIO_TIMEOUT_MS=4000

DEFAULT_PEOPLE_FILE_ID=49
ENABLE_HISTORY_QUERIES=false
ENABLE_ATTACHMENT_CONTENT=false
```

For high traffic:

```text
TTS_PROVIDER=kokoro
KOKORO_URL=http://kokoro:...
```

Do not configure forbidden application table names as runtime options. The source allowlist belongs in migrations/policy tables and the Assistant Data Gateway implementation.

---

# 54. Testing

Implement automated tests at several layers.

## Database-boundary tests

Verify the runtime database role:

- can use approved assistant views/functions;
- can CRUD assistant-owned tables according to intended permissions;
- cannot `SELECT` from `users`, `roles`, `otps`, `logs`, support tables, form/review workflow tables, reconciliation tables, or arbitrary application tables;
- cannot use a generic SQL execution function;
- cannot query historical `file_data`/`file_data_normalized` rows through ordinary current-record APIs;
- cannot read private file 93/94 rows without a matching trusted access grant;
- cannot broaden an AccessScope supplied for a turn.

## Source-data correctness tests

- `file` current version is always honored;
- current-record APIs return 2,942 rows for the inspected snapshot before authorization narrowing, not all 8,672 historical normalized rows;
- deleted/non-ready rows are excluded;
- `data_config` metadata is exposed only through safe selected structures;
- raw `file_data` is fetched only by selected row IDs/fields after retrieval;
- normalized field roles are not treated as authoritative when they conflict with the curated field registry;
- date outliers are flagged/handled according to validation policy;
- missing values remain unknown rather than false/no.

## Field-registry tests

- aliases resolve raw inconsistencies such as misspellings/trailing spaces;
- semantic fields map correctly per dataset;
- disallowed operators are rejected;
- fields not exposed by policy cannot appear in a plan;
- planner schemas never contain forbidden application tables.

## Retrieval/planning tests

- exact name/prefix;
- aliases/misspellings;
- community/school/reference variants;
- date filters;
- metadata/canonical filters;
- FTS;
- pg_trgm/RapidFuzz;
- zero results;
- ambiguous entity;
- set operations;
- multi-part hybrid plans;
- deterministic counts with zero reasoning calls;
- computed facts performed in PostgreSQL/executor rather than manually by the LLM.

## Conversation tests

Test follow-ups such as:

```text
How many students have names starting with S?
Which communities are most common among those records?
Only students admitted before 1920.
What about the first five?
Going back to the earlier count, how many are recorded as deceased?
```

Verify query state, result sets, dataset scope, and referents resolve correctly.

## Voice tests

- start session;
- local whisper.cpp partial/final transcript;
- semantic turn/endpoint detection;
- assistant generation;
- streaming TTS;
- user interruption;
- playback cancellation;
- query-state preservation after interruption;
- second turn after interruption;
- STT correction through reference/alias matching.

## Citation tests

- citation IDs map to current authorized source rows/fields;
- raw quotations match the cited raw field/attachment chunk;
- model cannot cite a source not in the EvidencePacket;
- private citations cannot leak metadata across access scopes.

## Cost tests

Verify:

- STT never calls paid APIs;
- FTS/fuzzy/indexing use local infrastructure;
- TTS is not called in text-only mode;
- deterministic questions can use zero reasoning calls;
- normal synthesis usually uses one reasoning call;
- attachment OCR/embeddings, when enabled, use local tools/models unless explicitly reconfigured.

## Parallelism/performance tests

Verify:

- independent QueryPlan steps overlap in trace timestamps;
- exact/FTS/fuzzy branches execute concurrently when enabled;
- dependent steps never start before prerequisites complete;
- immutable `AccessScope` is identical across every parallel branch;
- concurrent PostgreSQL reads use separate pooled connections and remain bounded;
- per-session/global semaphores prevent unbounded task creation;
- an exact unique match can cancel unnecessary fuzzy fallback work;
- barge-in cancels queued TTS, active xAI TTS, model stream, and irrelevant query branches promptly;
- model text streaming overlaps with frontend text rendering;
- xAI TTS audio generation overlaps with continuing model generation;
- xAI TTS WebSocket is prewarmed/reused across utterances when healthy;
- TTS phrase ordering remains correct despite concurrent upstream work;
- retry/idempotency logic never creates duplicate assistant messages or duplicate spoken output;
- load tests report p50/p95/p99 end-to-end latency, DB pool saturation, queue delay, and peak parallel steps;
- sequential-vs-parallel benchmark demonstrates that enabled fan-out actually lowers representative critical-path latency.

## Reliability/stability tests

- query run survives worker retry without duplicate final messages;
- background-job lease/retry semantics work;
- reconnect restores conversation/query state;
- partial failed query steps do not corrupt result sets;
- query/audit tables remain internally consistent after cancellation;
- failed privilege self-test prevents production startup.

---

# 55. Retrieval and query evaluation dataset

Create an evaluation framework using sanitized/non-sensitive fixtures derived from the real schema shape.

Each evaluation case should include:

```json
{
  "question": "How many students have names starting with S?",
  "access_scope": {"allowed_file_ids": [49]},
  "expected_plan_ops": ["FILTER", "COUNT"],
  "expected_dataset_ids": [49],
  "expected_reasoning_calls": 0,
  "expected_source_ids": []
}
```

For synthesis cases, include expected evidence source IDs/fields rather than entire source rows.

Measure:

```text
plan validity rate
unauthorized-source rate (must be zero)
current-version scoping accuracy
field-registry resolution accuracy
Recall@K
Precision@K
MRR where useful
entity resolution accuracy
citation correctness
aggregate correctness
fact-vs-inference correctness
reasoning-call count
critical-path latency
parallel-step overlap ratio
queue/saturation time
TTS first-audio latency
barge-in cancellation latency
latency
```

Do not evaluate only final prose quality. For this product, authorization, query scope, exact computation, evidence selection, and provenance are first-order correctness metrics.

---

# 56. Latency and parallelism goals

Optimize the **critical path**, not individual components in isolation.

Measure this voice path explicitly:

```text
user finishes speech
      ↓
final whisper.cpp transcript
      ↓
conversation/scope preparation + plan
      ↓
parallel DAG retrieval/execution
      ↓
required facts/evidence ready
      ↓
first Grok text delta
      ↓
first xAI TTS audio chunk
      ↓
first audible LiveKit playback
```

Also measure how much work overlaps:

```text
conversation-state load  ═══════
normalization             ═════
alias/reference lookup     ═══════

SQL branch                    ═══════
FTS branch                    ═════════
fuzzy branch                 ═════

Grok text generation                    ═════════════════
frontend text rendering                 ═════════════════
xAI TTS                                      ════════════
LiveKit playback                               ═══════════
```

Required telemetry:

```text
end_of_speech_to_final_transcript_ms
turn_prepare_ms
plan_ms
plan_queue_ms
dag_critical_path_ms
dag_total_work_ms
parallel_step_peak
retrieval_branch_overlap_ms
db_pool_wait_ms
model_queue_wait_ms
model_first_token_ms
tts_queue_wait_ms
xai_tts_connect_ms
xai_tts_first_audio_ms
first_audible_response_ms
barge_in_cancel_ms
```

Track p50/p95/p99, not only averages.

Set performance SLOs from measured deployment hardware/network rather than inventing unrealistic fixed numbers before benchmarking. The first performance milestone is that the parallel implementation must be measurably faster than the sequential baseline on representative multi-branch queries without reducing correctness, authorization safety, or stability.

Optimize in this order:

1. remove unnecessary work/calls;
2. move non-critical initialization out of the turn critical path;
3. parallelize independent DAG steps;
4. stream/pipeline dependent stages as soon as partial output is usable;
5. tune indexes/SQL;
6. tune connection/concurrency pools from load tests;
7. scale horizontally only after single-instance bottlenecks are measured.

Do not add slow autonomous-agent/tool layers unless measurement proves they are required.

---

# 57. Do not add unnecessary frameworks

Do not add by default:

* LangChain;
* LangGraph;
* MCP;
* Pinecone;
* Qdrant;
* Milvus;
* autonomous agents;
* multi-agent orchestration;
* paid embedding APIs.

This application has one primary task:

```text
resolve conversation
→ plan required operations
→ execute structured/retrieval operations
→ fuse computed facts + evidence
→ reason only where needed
→ answer
```

Keep it simple.

---

# 58. Repository/reference list

Use these sources as implementation references.

## Realtime voice

LiveKit Agents
repositories/agents

LiveKit Python Agent Starter
repositories/agent-starter-python

LiveKit React Agent Starter
repositories/agent-starter-react

LiveKit Server
repositories/livekit

LiveKit external data / RAG hook
https://docs.livekit.io/agents/logic/external-data/

## Backend

FastAPI
repositories/fastapi

## xAI reasoning and TTS

xAI Python SDK
repositories/xai-sdk-python

Grok 4.20 non-reasoning model
https://docs.x.ai/developers/models/grok-4.20-non-reasoning

xAI Text to Speech
https://docs.x.ai/developers/models/text-to-speech

xAI TTS REST/WebSocket API reference
https://docs.x.ai/developers/rest-api-reference/inference/voice

## Local STT

whisper.cpp
repositories/whisper.cpp

whisper.cpp realtime streaming example
repositories/whisper.cpp/tree/master/examples/stream

## VAD

Silero VAD
repositories/silero-vad

## Database retrieval

pgvector
repositories/pgvector

RapidFuzz
repositories/RapidFuzz

Redis
repositories/redis

## Local/high-volume TTS

Kokoro
repositories/kokoro

Kokoro FastAPI
repositories/Kokoro-FastAPI

## Optional future local reasoning

OpenAI gpt-oss
repositories/gpt-oss

---

# 59. Final target architecture after database inspection

Implement this architecture:

```text
                           WEB USER
                              │
                 ┌────────────┴────────────┐
                 │                         │
               CHAT                      VOICE
                 │                         │
                 │                  React / LiveKit
                 │                         │
                 │                       WebRTC
                 │                         │
                 │                  Self-hosted LiveKit
                 │                         │
                 │               ┌─────────┴─────────┐
                 │               │                   │
                 │          Silero VAD          whisper.cpp
                 │                                  local STT
                 └───────────────────┬─────────────────────┘
                                     │
                                FINAL USER TURN
                                     │
                                     ▼
                       WEBSITE AUTHORIZATION ADAPTER
                                     │
                              validated AccessScope
                                     │
                                     ▼
                         CONVERSATION RESOLVER
                         active entities / frames
                         prior result sets / edits
                                     │
                                     ▼
                          HYBRID QUERY PLANNER
                              QueryPlan DAG
                                     │
                                     ▼
                             PLAN VALIDATOR
                         field registry / operators
                         resource + scope validation
                                     │
                                     ▼
                          BOUNDED DAG SCHEDULER
                         ready-set / backpressure
                         cancellation / timeouts
                                     │
                                     ▼
                           ASSISTANT DATA GATEWAY
                                     │
                  ┌──────────────────┼──────────────────┐
                  │                  │                  │
                  ▼                  ▼                  ▼
              SAFE DATASET       CURRENT RECORD      REFERENCE
               METADATA             SEARCH             DATA
                  │                  │                  │
             data_config         file_data_norm     communities
             selected file       + current file     day_schools
                                  version            hospitals
                                                     provinces
                  │                  │                  │
                  └──────────────────┼──────────────────┘
                                     │
                                row/source IDs
                                     │
                       ┌─────────────┴──────────────┐
                       │    PARALLEL READY BRANCHES │
                       ▼                            ▼
                 COMPUTED FACTS                EVIDENCE FETCH
                 SQL/JSONB/FTS                 compact canonical
                 pg_trgm/RapidFuzz             default bundle
                 counts/sets/dates             selected narrative
                                               exact raw file_data
                                               optional attachments
                       │                            │
                       └─────────────┬──────────────┘
                                     ▼
                               CONTEXT BUILDER
                                     │
                         question + compact memory
                         + exact facts + small evidence
                                     │
                                     ▼
                           GROK-4.20-0309-NON-REASONING WHEN NEEDED
                               paid reasoning
                                     │
                       ┌─────────────┴─────────────┐
                       │                           │
                       ▼                           ▼
                    CHAT TEXT                  VOICE TEXT
                                                   │
                                      TEST/INITIAL: xAI TTS (STREAMING WS)
                                                   │
                                           high traffic?
                                                   │
                                                   ▼
                                             LOCAL KOKORO
                                                   │
                                                LiveKit
                                                   │
                                                SPEAKER

                 ───────── DATABASE ISOLATION ─────────

Existing application DB
  ├── exposed to gateway only:
  │      file
  │      data_config
  │      file_data
  │      file_data_normalized
  │      approved reference/sanitized optional sources
  │
  └── NOT exposed to assistant runtime:
         users / roles / otps / logs
         support_* / form_* / review queues
         reconciliation/system/admin tables

Assistant-owned schema
  ├── dataset/field/access policy
  ├── conversations/messages/state/frames/results
  ├── plans/runs/step-runs/citations
  ├── voice sessions/feedback/audit/jobs
  └── optional attachment sources/chunks
```

A single question may use several QueryPlan branches. There is no binary "SQL path" vs. "RAG path."

For safe deterministic plans, bypass `grok-4.20-0309-non-reasoning` entirely.

For complex planning, `grok-4.20-0309-non-reasoning` may produce only a constrained QueryPlan over assistant semantic fields; it never receives or selects arbitrary application tables and never generates executable SQL directly.

---

# 60. Non-negotiable design principles

The final implementation must preserve all of the following.

## 60.1 Database least privilege

```text
assistant runtime
≠
general application database access
```

The runtime can use only the Assistant Data Gateway and assistant-owned tables.

## 60.2 Existing source-table allowlist

The normal research assistant may derive data only from explicitly approved user-facing sources, centered on:

```text
file
data_config
file_data
file_data_normalized
approved reference data
optional sanitized approved attachment/version metadata
```

Everything else is denied unless a future separately designed feature explicitly adds it.

## 60.3 Current-version correctness

Ordinary queries operate on the current `file.version` only. Historical versions require explicit history intent.

## 60.4 LLM data minimization

```text
LLM INPUT
=
current question
+
compact conversation/query memory
+
executor-produced computed facts
+
small authorized field-specific evidence set
```

Never:

```text
LLM INPUT
=
entire database
+
entire conversation
+
question
```

## 60.5 No sensitive application data in assistant state

Do not copy application user/admin/auth/support/log data into assistant-owned tables. Use opaque principal IDs and research-data source references.

## 60.6 Deterministic execution first

PostgreSQL/local code performs exact filters, joins, counts, sets, dates, ratios, rankings, FTS, and fuzzy operations whenever possible. AI is for interpretation, difficult planning, and synthesis.

## 60.7 Correctness-bounded parallelism

Independent work should execute concurrently whenever possible, but security and dependency barriers are absolute. `AccessScope` validation, plan validation, current-version resolution, dependent computations, and citation authorization may not be bypassed for latency. All concurrency must be bounded, observable, cancellable, and backpressured.

## 60.8 Provenance

Every factual answer must be reproducible from authorized current research source IDs/fields or approved attachment chunks.

---

# 61. Deliverables

Do not stop after writing an architecture document.

Produce:

1. runnable frontend and backend;
2. LiveKit/self-hosted realtime configuration;
3. local whisper.cpp service;
4. Silero VAD integration;
5. xAI `grok-4.20-0309-non-reasoning` reasoning provider;
6. xAI streaming Text to Speech provider;
7. Kokoro provider with configuration switch;
8. PostgreSQL migrations creating `assistant` and `assistant_api` schemas;
9. restricted PostgreSQL roles/grants for gateway owner, runtime, and migrator;
10. safe views/functions over the explicitly approved source tables;
11. current-version-only research retrieval surface;
12. dataset policy table and seed for the four inspected datasets;
13. curated field registry table seeded from the inspected database plus manual corrections;
14. access-grant adapter/sync mechanism using opaque principal IDs;
15. assistant-owned core tables listed in Section 10.8;
16. FTS/pg_trgm indexes and migrations;
17. hybrid QueryPlan planner/validator/executor;
18. bounded QueryPlan DAG scheduler with cancellation/backpressure, pool limits, and critical-path tracing;
19. conversation/query/result-set memory;
20. citation/provenance system;
21. realtime interruption/reconnect state handling;
22. assistant-specific audit/query-run/background-job reliability tracking;
23. optional approved-attachment ingestion/chunking behind a feature flag;
24. Docker Compose and `.env.example`;
25. sanitized seed/demo database reflecting the real schema shape without production-sensitive tables/data;
26. automated security, retrieval, voice, cost, and reliability tests;
27. retrieval/query evaluation dataset;
28. README and architecture documentation;
29. production deployment and database-privilege instructions;
30. explicit table-access matrix documenting every existing source table as allowed, feature-gated, or denied;
31. migration rollback instructions.

Run the application locally and verify the complete flow end-to-end.
---

# 62. Definition of done

The project is complete only when all of the following are demonstrated.

## Core chat/voice behavior

1. Start the complete stack locally.
2. Open the website and start a normal text conversation.
3. Switch to voice in the same conversation.
4. See realtime partial whisper.cpp transcription.
5. Hear streaming TTS before the full final response has completed.
6. Interrupt the assistant and verify playback/generation stops quickly.
7. Verify conversation/query state survives the interruption and follow-up.
8. Restart/reconnect and verify durable assistant conversation state.
9. Switch TTS configuration from xAI Text to Speech to local Kokoro without changing retrieval/reasoning code.

## Database isolation/security

10. Verify `assistant_runtime` cannot select from `users`, `roles`, `otps`, `logs`, support tables, form/review workflow tables, reconciliation/internal tables, or arbitrary application tables.
11. Verify the runtime can access research data only through `assistant_api` safe views/functions.
12. Verify planning/reasoning code has no generic database-query tool and cannot emit executable SQL.
13. Verify authenticated website authorization produces an AccessScope without exposing application user/admin records.
14. Verify public files can be queried according to policy.
15. Verify private files 93/94 cannot be queried without an explicit trusted grant.
16. Verify a user without a grant cannot infer private-record counts, names, metadata, citations, or even candidate search hits through errors/timing/output.

## Current-record correctness

17. Verify ordinary retrieval uses `file.version` and excludes historical copies.
18. Against the inspected snapshot, verify the unrestricted current-record surface contains 2,942 research rows rather than 8,672 normalized historical rows.
19. Verify history/version queries are disabled or separately permissioned unless explicitly requested.
20. Verify deleted/non-ready rows are excluded.

## Data-model correctness

21. Verify `data_config`, `file`, `file_data`, and `file_data_normalized` are explicitly represented in the gateway architecture.
22. Verify `data_config` alone is not treated as the complete planner schema.
23. Verify the curated `assistant.field_registry` corrects raw-key/semantic inconsistencies and controls allowed operators.
24. Verify raw `file_data` values are fetched only for selected authorized source rows/fields, not sent wholesale to the model.
25. Verify `file_data_normalized` compact/default/canonical structures are preferred for evidence.
26. Verify missing/unknown fields are not converted to false/no.
27. Verify date outliers/approximate-year values are handled by validation/date semantics rather than blindly compared.
28. Verify cross-dataset record rows are not silently deduplicated into unique people by name/student number.

## Query planner scenarios

29. Ask "How many students have names starting with S?" and verify the plan can execute deterministically with zero reasoning calls.
30. Ask a mixed structured + text question and verify one QueryPlan combines filters/search/aggregation/synthesis as needed.
31. Ask a multi-part question and verify shared intermediate results are reused.
32. Apply follow-up constraint edits (year, dataset, exclusion, etc.) and verify active query state is modified rather than rebuilt incorrectly.
33. Demonstrate pronoun/ordinal resolution against prior result sets.
34. Demonstrate `INTERSECT`, `UNION`, and `DIFFERENCE` operations.
35. Demonstrate a percentage/derived-fact query and verify the executor performs the calculation.
36. Demonstrate comparison/ranking with explicit criteria and balanced evidence.
37. Demonstrate conflicting evidence and verify the conflict is surfaced with provenance.
38. Demonstrate an explicit inference request and verify inference is labeled as such.
39. Challenge an answer and verify retrieval/recalculation is re-run instead of merely regenerating prose.
40. Switch topics and say "Going back to ..."; verify the correct query frame is restored.

## Citations/privacy

41. Verify every citation maps to an authorized source row/field or approved attachment chunk.
42. Verify the model cannot cite a source not supplied in the EvidencePacket.
43. Verify TTS receives only answer text, not raw database evidence/schema/authorization data.
44. Verify assistant-owned state stores opaque principal IDs rather than copied application user profiles.
45. Verify application logs/OTP/support/user data never enter retrieval indexes, context, traces, or assistant-owned tables.

## Assistant-owned database state

46. Verify migrations create every required assistant-owned table from Section 10.8 with primary/foreign keys, uniqueness constraints, timestamps, and retention indexes where appropriate.
47. Verify query-run/query-step records remain consistent across success, cancellation, retry, and failure.
48. Verify background jobs support retry/lease/heartbeat semantics without duplicate ingestion/index state.
49. Verify result sets store only lightweight source references, not copied full source rows.
50. Verify retention/deletion procedures work for conversations, traces, result sets, feedback, and audit events.

## Cost

51. Confirm STT is local whisper.cpp.
52. Confirm VAD/turn handling is local/LiveKit infrastructure.
53. Confirm FTS/fuzzy/indexing uses local PostgreSQL/RapidFuzz.
54. Confirm deterministic queries can skip `grok-4.20-0309-non-reasoning`.
55. Confirm normal synthesis targets one paid reasoning call.
56. Confirm text mode does not call TTS.
57. Confirm the test/initial voice profile uses xAI Text to Speech and the high-traffic configuration can use local Kokoro.
58. Confirm the only paid AI categories in the initial configuration are reasoning when needed and TTS for spoken output.

Everything else must run locally or on infrastructure controlled by the application, and the assistant must remain unable to access unrelated sensitive/operational application data.

---



## Parallelism definition of done

Before declaring the realtime application performance-complete:

1. Demonstrate a multi-branch hybrid query whose independent QueryPlan nodes execute concurrently.
2. Demonstrate bounded exact/FTS/fuzzy retrieval fan-out and deterministic fusion.
3. Demonstrate that dependent nodes never violate DAG ordering.
4. Demonstrate no protected database query starts before AccessScope validation.
5. Demonstrate that PostgreSQL connection-pool and query concurrency limits are respected under load.
6. Demonstrate that Grok text streaming overlaps with UI rendering.
7. Demonstrate that xAI TTS starts from stable phrase chunks while Grok is still generating later text.
8. Demonstrate that the xAI TTS WebSocket is preconnected/reused for a healthy voice session.
9. Demonstrate immediate barge-in cancellation across playback, TTS queue, xAI TTS, model stream, and irrelevant query branches.
10. Demonstrate no orphan tasks remain after cancellation or disconnect.
11. Demonstrate background workers process independent jobs concurrently without duplicate processing.
12. Compare sequential and parallel traces for representative queries and show reduced critical-path latency.
13. Run concurrency/load tests and report p50/p95/p99 latency, queue delay, DB pool wait, model wait, first-audio latency, and cancellation latency.
14. Demonstrate that overload causes bounded queueing/backpressure rather than unbounded task creation.
