# MET-23 / #902 — initial native POST baseline

Change class: C
Promise: Reproduce completed Review POST and refusal responses through the real PostgreSQL/ASGI composition, with durable-state controls.
Proof: Opt-in companion scenario in the existing #888 harness and retained native CI artifacts. Execution results, not the presence of this harness, determine proof.
Touches lifecycle invariants: no
Rewrite risk: none

This is an initial increment of #902, not completion of its workload or SQL-isolation requirements. No production code or domain contract changes.

## Run

Use the pinned development dependencies and PostgreSQL 16 with CREATEDB rights. First check the real database boundary:

```sh
export METIS_TEST_POSTGRES_DSN="$(bash scripts/test_postgres.sh)"
REVIEW_PROOF_OUTPUT=/tmp/review-post-902.json REVIEW_POST_SIZES=20,150 \
  python -m pytest -q -p tests.conftest \
  evidence/review-integrated-888/benchmark.py -k native_review_post_baseline \
  --junitxml=/tmp/review-post-902.xml
```

Use a new output path for each run; the harness appends cases. The existing CI characterization job runs size 20 and retains JSON and JUnit in `review-post-902`. Never count PostgreSQL skips, missing artifacts, timeouts or incomplete responses as passes. A failed or interrupted case may have JUnit without JSON; retain that outcome and rerun only with its reason recorded. No latency sample exists for an unfinished request.

## Scenario and authority

The fixture ingests synthetic HTML using deterministic fixture selections and the production candidate creator, source preparation, lifecycle projection, stores, login, HTTP handler and review command. It does not substitute a fake kernel or lifecycle projection. Each full response is consumed with redirects disabled, so POST cost excludes the redirected GET. Snapshot tokens come from actual rendered forms.

| Action | Expected response | Durable control |
| --- | --- | --- |
| Passage GET | 200 | Whole source/review state unchanged |
| Approve with reported missing source context | 400 and retained draft | Whole state unchanged |
| Valid approval | 303 | Approved focal version and valid exact binding |
| Replay original form | 409 | Committed winner unchanged |
| Fresh form after independent object write | 409 | Concurrent state unchanged |

The semantic refusal reaches the real review command and uses its existing rule that a discrepancy precludes approval. It is not a simulated database failure. The concurrent write is deliberate synthetic fixture setup using the existing store path, outside the measured request. These cases do not establish retry behavior for reject, revise, defer, second review or batch.

Reports include individual wall times, status, response size and existing aggregate diagnostic phases/counters. Phase trees may overlap or truncate; do not sum them or infer missing phases. `db_json_bytes` measures diagnostic JSON volume, not proven wire bytes. Reports contain no cookies, request identifiers, account IDs, SQL text, form values, original uploaded material or incident telemetry. The workload fingerprint is synthetic and reproducible. Neither one observation nor this small fixture supports p95 or production SLO claims.

## Remaining MET-23 work

- Populate representative append-order histories, valid and stale exact bindings, relation context and incomplete formation; record their actual counts and contract versions.
- Separate validation before versus inside a transaction using observed native phases. Add deterministic native fault/lock probes with independent connections and bounded deadlines.
- Attribute safe SQL categories and execute/fetch/lock wait separately, without exporting query parameters or incident identifiers. A controlled local lock proves observability only; production SQL cause remains unknown without corresponding live evidence.
- Build the mutation/invalidation dependency fixture and writer/lock inventory for later work packages. Preserve the distinctions between passage generation, command equality and storage three-way merge, including binding-only and legacy writes.
- Collect comparable completed runs at the agreed workload sizes. Keep failures and unfinished requests in the run inventory. Do not close #902 from this initial baseline.

## Local execution limitation

The initial authoring environment cannot start the repository's disposable PostgreSQL server: `scripts/test_postgres.sh` exits with `test_postgres_unavailable: OSError`. It exposes only a root UID/GID mapping and cannot change ownership to an unprivileged database user. Native execution must therefore be proved by the existing PostgreSQL CI environment or a permitted development database. Static checks are not native proof. This limitation says nothing about the production query's cause.
