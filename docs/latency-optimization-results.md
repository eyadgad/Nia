# Latency optimization results

Date: 2026-09-07. Baseline run `2026-09-07T00:47:01Z`, sequential, `PLANNER_MODE=ai`, `PLANNER_REVIEW_MODE=always`. No image rebuild during the run. Container `nia-matrix-before` via `docker run --network infra_default` (not `compose run`, which had been restarting the stack).

Artifact: `docs/latency-baseline-before.json` and `docs/latency-baseline-before.stdout.txt`.

## Baseline quality

| | |
|---|---|
| Cases C | 74 |
| Repeats N | 3 |
| Observations O | 222 |
| Observation passes | 209 |
| p̂ | 209/222 = **94.14%** |
| SE_obs = √(p̂(1−p̂)/O) | **1.58 pp** (~3.5 observations) |
| SE_cases = √(p̂(1−p̂)/C) | **2.73 pp** (~2.0 cases) |
| Stable-pass K | **66** |
| Flaky | 7: A04, A05, D04, M05, M14, M21, P10 |
| Stable-fail | 1: A01 |
| planner_unavailable | 0 |
| review_status=corrected | **70 / 222 = 31.5%** of observations; **70 / 212 = 33.0%** of turns review actually ran on (`review_ms` n=212) |
| Matrix `final_response=llm_synthesis` | **0 / 222** |

## Baseline latency (happy-path; 0 unavailables in this run)

| Metric | p50 | p95 |
|---|---:|---:|
| e2e_ms | 3,290 | 10,003 |
| plan_ms | 1,797 | 6,980 |
| review_ms | 1,150 | 3,963 |
| catalog_ms | 13.0 | 25.5 |
| persist_ms | 12.089 | 17.7 |
| retrieval_ms | 22.4 | 658 |
| persist / e2e (p50/p50) | **0.367%** | — |
| persist / e2e (median of per-turn ratios) | 0.272% | — |
| catalog / e2e (p50/p50) | 0.396% | — |
| catalog / e2e (median of per-turn ratios) | 0.402% | — |
| review / e2e (p50/p50) | 35.0% | — |
| plan / e2e (p50/p50) | 54.6% | — |

TTFT equals e2e on this mix because deterministic answers emit one late `answer_delta`.

`cached_tokens` was null on this provider path. Not a lever.

## Decision gates (Phase 0)

| Item | Gate | Measured | Decision |
|---|---|---|---|
| 2 Conditional review | Ship only if review would change ~3% of ordinary turns; stay on always at ~15% | **31.5%** of observations (70/222), **33.0%** of reviewed turns (70/212) | **Do not ship.** Stay on `always`. A confidence&lt;0.75 trigger would also never fire: `validate_turn_plan(strict=True)` clarifies those plans and `only_clarification` returns before review. |
| Extra shadow run | Prerequisite if we were going to flip | Baseline already records review verdicts without applying a second 222-case shadow tax | **Skipped.** 31.5% is enough to refuse conditional. |
| 4 Catalog gather | catalog_ms p50 ≥ 2% e2e or &gt;4 datasets | 0.40% e2e (median per-turn ratio; 0.396% by p50 quotient), 4 datasets | **Skip gather.** |
| 4 Catalog cache | Always in the plan; 13 ms p50 | Permission-sensitive for 13 ms | **Skipped.** Not worth a stale `evidence_allowed` risk. |
| 5 Persist off path | persist_ms ≥ 5% e2e | **0.367%** p50/p50 (12.089 / 3290.017); 0.272% is the median of per-turn persist/e2e ratios in the JSON | **Do not build.** Both figures are far under 5%. |
| 6 Stream LLM synthesis | synthesis_rate ≥ 15% or TTFT complaint on synth turns | Matrix synthesis_rate **0%** | **Do not stream LLM prose.** Real `assistant.messages` mix was not sampled (Postgres was down when queried). |
| 7 Voice startup | voice_startup_ms p50 ≥ 500 ms | Not measured on the matrix | **Do not build** without a number. |
| 3 Planner model guardrail | Not percentage-gated | UI model was being passed into `plan_user_turn` | **Shipped.** Latency-neutral on the default model. |
| 8 Frontend refresh | Cheap, no matrix gate | `await refreshConversations()` held `busy` | **Shipped.** `void refreshConversations().catch(...)` + optimistic sidebar; server title wins. |

## What shipped (behaviour)

1. **Feature inventory** + five characterization tests (low-confidence clarify, verify_previous review-eligible, navigation-only skips review, evidence_allowed, empty registry fail-closed).
2. **Latency instrumentation** on `TurnResult.latency` (e2e, ttft, plan, review, catalog, retrieval, persist, attempts, cached_tokens).
3. **Matrix abort** on DB connection loss (exit 2, VOID). Run start timestamp. Sequential probe `benchmarks/latency_probe.py`.
4. **Planner/review model guardrail:** `plan_user_turn` uses the service default reasoner. `QueryRequest.model` is answer-only (`_reasoner_for` → `_turn_reasoner`, set and cleared per turn like `_latency_bag`). `PLANNER_MODEL` / `PLANNER_REVIEW_MODE=always` documented. `conditional`/`shadow` are rejected at settings load. Persist-off and text-streaming flags were **not** added: those features were not built.
5. **Non-blocking conversation list refresh.**

No planner prompt edits. No DAG/pool concurrency change. No conditional review. No persist-queue. No synthesis streaming. Legacy planner path retained.

## Quality after shipped code

The shipped items do not change plan construction or review. A second `--runs 3` was **not** repeated (would not isolate a latency delta; review still always-on). The 66 / 7 / 1 split is the before snapshot for any future change.

## Remaining bottleneck

Still one serial primary planner call (p50 1.8 s, p95 7.0 s) plus always-on review (p50 1.2 s, p95 4.0 s). Together they are ~89% of e2e p50. Retrieval and persist are not the story.

## Rollbacks

| Flag | Restores |
|---|---|
| `PLANNER_REVIEW_MODE=always` | Today’s review (already the default; implemented values are `always` and `off` only) |

`SYNC_AUDIT_WRITES` and `STREAM_TEXT_SYNTHESIS` are not settings. They will be added with items 5 and 6 if those are ever built.

## Inventory re-verify

See `docs/latency-feature-inventory.md`. After this work: planning/review/security/answering/voice/ops rows are unchanged except (a) UI model no longer selects the planner, (b) conversation sidebar refresh is non-blocking. Characterization tests still pass.
