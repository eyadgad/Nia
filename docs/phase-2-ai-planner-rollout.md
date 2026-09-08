# Phase 2 AI planner rollout

Date: 2026-09-02  
Application default: `PLANNER_MODE=ai`  
Emergency rollback: `PLANNER_MODE=legacy`  
Self-review: on  
Legacy modules: retained until Phase 3

## Phase 1 review (what shipped)

Phase 1 built the opt-in AI path and left legacy as the default. In the repository that now means:

- `PlannedTurn` / `PlanReviewResponse` with `extra=forbid`, required `type`/`kind`/`verdict`
- `bind_scope` stamps the selected file; the model cannot emit dataset IDs
- Transport-only normalize; no semantic fallback after AI failure
- Review after bind + validate + QueryPlan build + predicate contract
- Requirement parity, predicate AND siblings, AI value expansion
- Observability on route, audit, and SSE
- Offline tests: 388 passed, 3 skipped (2026-09-02, after catalog-coerce/review-salvage)

Live database matrix on the rebuilt image (before the last coerce/review-salvage pass): **51/74**. Earlier un-rebuilt image: 42/74. Structural defects that were killing valid plans (schema-as-query-goal, `ReviewComplete` extras, ungrounded `dataset_not_selected`) are fixed in unit tests; the last coerce/review-salvage commit has not had a paid replay.

## Phase 2 promotion gates

| # | Gate | Outcome |
|---|---|---|
| 1 | AI at least as good as legacy on the scoped golden suite | **Partial.** Offline named-condition tests pass. Full paid scoped golden (`--runs 3 --fail-on-gate`) was not re-run after the last planner fixes. |
| 2 | Zero dataset-scope violations | **Pass** in unit/isolation tests. No live violation observed on the 51/74 run. |
| 3 | Zero unauthorized reads | **Pass** in privilege/isolation tests. Gateway spies remain the load-bearing assertion. |
| 4 | Named condition-loss + three-condition case on every required run | **Pass** offline (`test_ai_planner_named_conditions`, three-condition parity). Not replayed live ×3 after the last fix. |
| 5 | Complete database-truth suite | **Not green. 91.0%** (202/222 observations, `--runs 3`, 2026-09-06). 62 cases pass every run; 10 flaky; **2 fail every run** (A01, P10), down from 11 at the start of the day. Six full runs landed at 81.5 / 85.6 / 92.3 / 90.5 / 91.0 / 88.3 / 91.0 -- read the band, not the last figure. Gate is >= 95% with zero stable failures. |
| 6 | All four datasets exercised live | **Pass.** Files 49, 91, 93, 94 were on the 74-case matrix. |
| 7 | `planner_unavailable` / `planner_invalid_output` never rendered as clarifications | **Pass** in unit tests and response-policy contracts. |
| 8 | Zero invalid structured outputs at primary and review on the qualification suite | **Not green** on the 51/74 run (review extras, later treated as keep-plan). Needs a clean replay. |

Phase 2 is implemented because the default flip and rollback path are the remaining code/docs work. Gates 5 and 8 are recorded as open soak risks, not waived.

## Measuring a sampling planner (2026-09-05)

Gate 5 used to read "the database-truth suite is green". That is not reachable and the
criterion has been restated, because the planner samples:

- Ten cases, three identical runs, no code change between them: **four flipped**.
- The planner was sending **no `temperature` at all** for what is structured extraction
  against a schema. `MODEL_TEMPERATURE` now defaults to `0.0`. It stabilised several cases
  and did not remove the variance.
- A fixed `MODEL_SEED` was then measured over three runs. D20 and P09 still flipped, so the
  provider does not offer reproducibility here. The setting exists for pinning a replay;
  nothing depends on it.

`database_question_matrix.py --runs N` classifies each case as stable pass, flaky, or
stable fail. Two cautions on reading it:

1. **Flaky is not a soft pass.** If a case passes two runs in three, one user in three still
   gets a wrong answer. Flaky counts against the suite.
2. **At `--runs 3`, per-case classification is weak.** A case that passes half the time looks
   like a stable failure one time in eight. Measured directly: A02, A03 and A05 were "stable
   fail" in the full run and, re-run alone three times, came back A02 `PPF`, A05 `FPF`,
   A03 passing. Treat a stable-fail label as a lead worth diagnosing, not a verdict.

So the gate leans on the aggregate, which is a 222-sample statistic rather than a 3-sample
one: **observation pass rate ≥ 95%, and no case failing across a larger repeat count.**
Per-case classes are diagnostic guidance.

Baseline at the restatement: **181/222 = 81.5%**, 58 stable pass, 5 flaky, 11 stable fail.

After the category-matching work (migrations 057/058, `ai_catalog_coerce`,
`value_expansion`): **190/222 = 85.6%**, 60 stable pass, 6 flaky (A05, D01, D04, D08, M10,
P09), 8 stable fail (A01, A04, D18, D20, D24, M12, M23, P10). M04, M05, A02, A03 and D23
moved to passing.

Read the +4.1 points with the standard error in mind: on 222 observations around 85% it is
roughly 2.4 points, so a single measurement resolves this only weakly. What carries it is
that the movement has a mechanism -- M05's undercount and D23's family match are both
explained and unit-tested -- not that the number went up.

Of the 32 remaining failing observations, 24 are stable failures and 8 are flakiness. The
gap is mostly real defects, not sampling.

After withdrawing recorded_values from the planner prompt, excluding derived columns from
the oracle's "all information" projection, and declaring name_search a token index:
**205/222 = 92.3%**, 65 stable pass, 5 flaky (A03, D24, M11, M12, P07), 4 stable fail
(A01, A05, M05, P10). Stable failures have gone 11 -> 8 -> 4.

recorded_values was a measured trade, not a clean win. Showing a field's categories to the
planner fixed one case (P09) and broke four, because a list of values reads as a list of
conditions: "how many records are in the confirmed deaths list" came back 25 of 82. Removing
it recovered D01, D04, D18, D20, D24, M23, A04 and M12, and cost M05 and A05. The registry
still carries the values and the compiler still uses them; only the prompt stopped seeing
them.

Name correction (migration 060) is not visible in this suite: no case asks about a misspelt
name, so the capability it adds is unmeasured here and was verified by direct probe and unit
test instead. Its effect on the suite is neutral, which is the most the suite can say --
across the three runs the rate moved 92.3% -> 90.5% -> 91.0%, all inside the roughly two
point standard error, with stable failures at 3 or 4 throughout.

Stable failures over the day: 11 -> 8 -> 4 -> 2. What is left is A01 (file 93's label reads
as content rather than as the selected list) and P10 (binds "student number" to
student_name). The aggregate has stayed in an 88-92% band throughout, because the remaining
gap is dominated by flaky cases rather than by defects -- 10 of the 12 failing cases pass on
at least one run.

Field fill rate (migration 061) is the fix for answering from a field nobody filled in.
File 94's Nation is labelled for a place of origin and aliased "first nation", so binding
"from Garden River" to it is defensible from the catalog alone -- but it holds a value in 3
rows of 56, and those three are "community member", "not confirmed" and "Shingwauk". The
answer "0 records" was a claim about the people that the records do not support. The catalog
line now carries recorded=<filled>/<total>.

Deliberately a count and not a list of values, which is the difference between this and the
withdrawn recorded_values: a proportion is evidence for choosing a field, a vocabulary is an
invitation to filter on it.

A/B over five runs of the two cases it targets: **8/10 with it, 3/10 without** (P09 3/5 ->
5/5, P10 0/5 -> 3/5). At suite level it is invisible -- two cases cannot be resolved against
a two point standard error -- and a ten-case A/B came back 24/30 either way. Judge it on the
cases it addresses, not on the headline.

M05 is the price. "How many students have an unknown deceased status?" answers 15 (the
blank rows) rather than 665 (the rows recorded "unknown"). Both readings of the English are
defensible and the suite asserts the second. It is left failing rather than forced, because
the only change that made it pass was the one that cost four other cases.

## Reasoning moved to the Cloudflare bridge (2026-09-06)

Paid reasoning goes to an OpenAI-compatible REST host (`REASONING_BASE_URL`) through
`backend/app/llm/http_reasoner.py`, not to api.x.ai through `xai-sdk`. The bridge is faithful
at the API level -- same model ids, and our real `PlannedTurn` schema is accepted in
`strict: true` unmodified -- but `xai-sdk` is gRPC and gets 403 on the HTTP/2 handshake, so
the transport was reimplemented rather than reconfigured. `REASONING_PROVIDER=xai` still
selects the gRPC path and is the rollback.

**The cutover is accuracy-neutral: 202/222 = 91.0%, against 202/222 = 91.0% on xAI.** Same
number, 0.0 SE apart. 60 stable pass, 12 flaky, 2 stable fail (A01, P05; the baseline's were
A01, P10 -- P10 and P05 trade places between runs, which is what the flaky column is for).
Seven-probe turn latency 36.1s against 29.8s on xAI, inside the 29.8-43.2s range already
measured there.

### Model choice, and what the numbers do and do not say

The researcher picks the model; `Settings.reasoning_model_choices` is the allowlist, offered
on `GET /api/assistant/datasets`. Measured over 15 shape-spanning cases x 2 runs:

| model | pass rate | p50 | p95 |
|---|---|---:|---:|
| `grok-4.20-0309-non-reasoning` | 25/30 83.3% | 8.6s | 60.1s |
| `grok-4.6-fast` | 23/30 76.7% | 44.9s | 82.2s |
| `grok-4.6` | 22/30 73.3% | 46.5s | 89.9s |
| `grok-4.5` | 21/30 70.0% | 14.9s | 55.1s |

**The accuracy column cannot separate these models.** At n=30 the standard error is 7-8
points and the widest gap is 1.2 SE. The speed column can: 5x, with a mechanism -- the newer
models spend ~2,000 tokens reasoning first. So the default is the default for speed, not
because it answers better.

M23 fails or flakes on every model, and M10/P09 fail on all three reasoning models. Those are
properties of those questions, not of model quality.

Timeouts are per model -- 60s direct, 150s reasoning -- because at one shared 60s ceiling the
reasoning models returned `ai planner review provider failure: ReadTimeout` and were scored
wrong for a plumbing reason. `direct_answer_models` in config declares which is which.

Prompt caching is now measurable: `cached_tokens` rides on `StructuredOutputResult`. xAI
always reported 0; the bridge cached 12,544 of a repeated 12,606-token prefix. Hit rate is
node-dependent -- 0%, 1%, 0%, 99.5% across four identical calls -- so it is a cost signal,
not a latency guarantee.

## Operating bands (from Phase 1 live + plan §13.3)

| Metric | Warning | Rollback |
|---|---|---|
| Invalid structured output | any event | >1% of either stage over a rolling 100-call window, or 3 consecutive events |
| Provider availability | — | <99% successful primary/review calls / 24h (excluding user cancel) |
| End-to-end p95 | — | greater of 500 ms or 20% above the last qualified AI p95 for the same scoped suite |
| Clarification rate | — | more than +2 percentage points or +20% relative vs last qualified AI rate, unless the increase is only correct unsupported-field refusals |

Qualification invalid-output threshold remains **zero** on a repeated promotion suite.

## Default flip

Changed:

- `Settings.planner_mode` default `"ai"`
- `.env.example` and Compose `PLANNER_MODE=${PLANNER_MODE:-ai}`
- Docs: README, architecture, flowchart (AI active, 15-gate tree under legacy), deploy, this runbook

Unchanged: every legacy module and legacy test. Pytest pins `PLANNER_MODE=legacy` unless a test opts into AI.

Phase 2 start: 2026-09-02. Stability clock starts after production smoke, not at this commit.

## Rollback (on-call)

One step:

```bash
PLANNER_MODE=legacy docker compose --env-file .env -f infra/docker-compose.yml up -d backend agent
```

Or set `PLANNER_MODE=legacy` in `.env` and restart `backend` and `agent`. Do not reset `infra_nia_pg_data`. Do not delete traces or audit rows.

Readiness:

1. `GET /ready` on the backend
2. Public smoke, file 49: `How many records are in the master list?`
3. Private smoke, file 93, granted principal: `How many records are in additional deaths?`

Immediate rollback triggers: dataset-scope violation, unauthorized gateway read, Sev-1/2 planner incident, named condition-loss recurrence, database-truth failure caused by planning, or a persistent breach of the bands above.

Fix forward in opt-in mode (`PLANNER_MODE=ai` on a non-default process), rerun the promotion suite, and restart the 14-day Phase 3 clock after redeploy.

## Soak cadence

- Every deploy: unit/offline suite, failure injection, database smoke, one live question per dataset
- Nightly: full `database_question_matrix.py`, named condition-loss canaries, authorized/unauthorized scope canaries
- Twice weekly for 14 days: paid scoped golden, `--runs 3 --fail-on-gate`
- Continuously: stage-specific invalid/unavailable, latency, cost, clarification, scope, authorization

## Verification of this flip

Recorded in the implementing change:

- `Settings.planner_mode` default is `ai`
- `PLANNER_MODE=legacy` still produces a non-AI plan
- AI path still plans with the fake provider
- Offline pytest: 381 passed, 12 skipped (Postgres/LiveKit not in this environment)
- Ruff clean on the flipped config and new tests
- Frontend `npm run build` succeeded
- Compose/database live replay was not run from this environment (no Docker in the implementing shell)
