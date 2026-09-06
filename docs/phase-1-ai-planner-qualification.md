# Phase 1 AI planner qualification

Date: 2026-09-02 (updated after blocking-findings fix)  
Mode default: `PLANNER_MODE=legacy`  
Opt-in: `PLANNER_MODE=ai`  
Self-review: on, after bind + strict validation + QueryPlan build + predicate contract

## Fixes in this revision

- Review no longer runs before dataset binding or validation.
- Top-level sibling predicates are treated as AND for contradiction checks.
- Transport-only normalization in AI mode (no filler/polite/correction rewriting).
- Requirement parity covers remaining modify edits, interval max-only, and compare-branch search labels.
- `_source_actions` discards a stale active frame that is not the selected dataset.
- Planner provider/model/token/cost metadata is on the route, audit event, and SSE payload.
- Trace layer order is normalize → planner → validator → builder → predicate → review → expansion → plan validator.
- Missing `kind`/`type` discriminators are coerced; out-of-range requirement indexes are dropped.
- Regression CLI: `--runs`, `--suite`, `--allow-private-files`, `--fail-on-gate`, review-benefit replay.
- Database matrix includes files 93 and 94 plus unsupported-field refusals.
- Named Q20/Q37/Q44/Q57/Q62/Q73/Q75 compilation tests added.

## Offline verification

| Check | Result |
|---|---|
| Full pytest | 360 passed, 12 skipped |
| AI planner + named-condition tests | included in the 360 |
| Phase-related Ruff on touched modules | run after this revision |
| Frontend production build | previously passed; types only gained optional fields |

## Phase 2

Default flip is documented in [phase-2-ai-planner-rollout.md](phase-2-ai-planner-rollout.md). Application default is now `PLANNER_MODE=ai`. Rollback is `PLANNER_MODE=legacy`.

Re-run live after rebuilding the backend image:

```sh
docker compose -f infra/docker-compose.yml build backend
docker compose -f infra/docker-compose.yml run --rm -e PLANNER_MODE=ai \
  -v /mnt/c/Users/gad/Desktop/nia-standalone/backend/benchmarks:/app/benchmarks:ro \
  backend python /app/benchmarks/database_question_matrix.py
```

Scoped golden:

```sh
python -m benchmarks.regression --suite ../docs/ai-planner-scoped-suite.json \
  --planner-mode ai --runs 3 --allow-private-files --fail-on-gate --json-out /tmp/ai-phase1.json
```

## Rollback

`PLANNER_MODE=legacy` and restart. AI traces are retained.
