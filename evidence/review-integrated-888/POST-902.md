# MET-23 / #902 — native POST baseline and controlled lock probe

Change class: C
Promise: Reproduce completed Review POST and refusal responses through the real PostgreSQL/ASGI composition, with durable-state controls.
Proof: Opt-in companion scenario in the existing #888 harness and retained native CI artifacts. Execution results, not the presence of this harness, determine proof.
Touches lifecycle invariants: no
Rewrite risk: none

This is evidence work within #902. The execution verdict and remaining limits belong to the inspected native artifact and tracker acceptance record. No production code or domain contract changes.

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

The normal suite and existing CI entry now select three separate profiles: `initial`, `history`, and `history_incomplete`. The first is the unchanged initial-state request sequence. The other two seed four successor cycles for each candidate except the focal object and independent conflict control. Each cycle uses the real approval command, then the existing lineage helper and validated store to append a forced synthetic successor. Half the seeded objects receive a final approval. Reports count actual history rows, current objects, matching bindings and stale exact bindings; they assert both binding populations exist. No approval records are manufactured by direct SQL or fake audit events.

The incomplete profile adds an explicitly synthetic retained formation finding, as the existing GET matrix does. It asserts that the full passage response retains its incomplete-formation warning, while running the same POST sequence. It does not claim a genuine provider failure. No additional relation/context fixture is introduced in this increment.

For an opt-in comparison at greater object counts, set one profile explicitly:

```sh
REVIEW_PROOF_OUTPUT=/tmp/review-post-history.json REVIEW_POST_PROFILE=history \
  REVIEW_POST_SIZES=20,150 REVIEW_POST_HISTORY_DEPTH=4 \
  python -m pytest -q -p tests.conftest \
  evidence/review-integrated-888/benchmark.py -k native_review_post_baseline
```

The `history` profile holds the document row in a separate native PostgreSQL transaction before an independent control-object approval POST. A third, independent autocommit connection polls `pg_stat_activity` and `pg_blocking_pids`, with a statement timeout and 15-second observation deadline. It must observe exactly one actual `Lock` waiter executing a document-row locking SELECT, while the POST remains unfinished. The blocker always rolls back before the executor joins. The full POST must then complete with 303 and the existing exact-binding/durable-state assertions. A missing waiter, early completion or failed completion is a test failure. The exported probe contains only the fixed query category and wait event, never backend IDs, SQL, connection information or parameters. After the lock probe, the scenario renders a fresh focal form and measures its ordinary approval separately; the deliberate wait is not included in that approval sample. The initial profile remains the initial-state reference. Controlled-lock wall time includes the deliberate wait and must not be used as an ordinary latency/SLO sample.

This distinguishes an observed database lock from inference based on a `db_execute` label. It does not identify the incident's production SQL or rule out its other possible causes. Existing request diagnostics still separate execute/fetch, render and store-lock/transaction phases; they do not attribute every application statement to a query category.

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

The concurrency control appends a validated successor to the current append-order version using the same helper as history setup. It preserves every historical occurrence; selecting the first stored row would target an immutable predecessor after the control approval.

Reports include individual wall times, status, response size and existing aggregate diagnostic phases/counters. Phase trees may overlap or truncate; do not sum them or infer missing phases. `db_json_bytes` measures diagnostic JSON volume, not proven wire bytes. Reports contain no cookies, request identifiers, account IDs, SQL text, form values, original uploaded material or incident telemetry. The workload fingerprint is synthetic and reproducible. Neither one observation nor this small fixture supports p95 or production SLO claims.

## Completion matrix

The current [WP5 acceptance contract](ACCEPTANCE-902.md) specifies the complete native invocation, retry oracles, workload and technical budget definitions. `completion_902.py` adds binding-only legacy/task-v1 renewal, reject/revise/later retries, context retargeting and native context/single lock-cycle diagnosis. The existing CI entry also selects unchanged semantic-duplicate, second-review, batch/single lock-order, context/publication and disjoint storage-merge reference paths. Actual execution status is recorded in the retained JSON/JUnit and trackers; code presence alone is not proof.

The [writer/dependency/lock inventory](WRITERS-902.md) records the existing production compositions, command variants, explicit and derived invalidations, precondition differences and observed lock-order differences. It is static evidence, not a completed concurrency proof. Its first outstanding probe is context versus ordinary review across independent runtime locks.

The task-v1 dependency probes exercise two independent authorities. Revoking the reviewer's role after rendering a form must return 403 without changing document generation, objects, bindings or review/command audit; restoring the role allows the same form to proceed. Confirming literal source context after approval must reopen the target, invalidate its binding, advance generation, and make the pre-context form return 409 while preserving the committed context. Both the compact read package and HTTP page must include that context. These are sequential native dependency probes, not a complete writer inventory or proof of every concurrent authorization race. Their execution status is recorded in the PR/CI artifact.

The native suite also includes two task-v1 compatibility cases, complete and incomplete, using `tests.test_review_formation_problems.received/execute`. That existing helper runs receipt, reservation, bounded processing, persisted tasks and production activation with a deterministic provider transport. The new cases do not manually set a database flag or manufacture activated objects. They require `processing_storage_version=1` from PostgreSQL before Review, then require increasing `object_generation` after approval and a validated concurrent successor. Both cases exercise full passage GET, semantic refusal 400 with draft/state retention, approval 303 with an exact current binding, old-form retry 409, and generation-stale 409 without changes to the winner. Incomplete formation must remain incomplete after review. JSON evidence is appended to the existing CI artifact. This is a small compatibility proof, not a heavy task-v1 benchmark or a production incident replay.

Two further task-v1 cases inject actual PostgreSQL failures: a BEFORE INSERT trigger on review bindings (SQLSTATE P9021) and an initially deferred constraint trigger on review events that fails COMMIT (P9022). A transparent observer forwards the real review command unchanged and records only its native SQLSTATE cause. The HTTP responses follow the existing mappings (400 for wrapped binding-store failure, 500 for the unhandled COMMIT exception). Object histories, envelopes, bindings, review/command events and object generation must equal the pre-request state, including after a new production composition reads the same database. After removing the trigger, the same original form must succeed. This proves rollback and retry at those two boundaries; it does not assert draft retention on the generic database-error page or cover every batch/second-review/authorization race.

Task-v1 scale cases use 32/128 candidates and two native history cycles, with one first HTTP after a fresh production composition and two repeated GET/400 pairs. They retain actual object/history/binding/source counts and source/extraction identity. Transparent native cursor observation exports only fixed SQL categories, execute/fetch counts and time, fetched rows and affected write rows. Existing diagnostics retain JSON volume, source prepare/build, transaction and overlapping store-lock spans. Request/test progress inventories retain started but unfinished cases; JUnit owns the pass/fail/skip verdict. Engineering budget violations are baseline findings, not suppressed or confused with production SLO acceptance. The controlled SQL cause is separate from the unknown live incident cause.

## Local execution limitation

The initial authoring environment cannot start the repository's disposable PostgreSQL server: `scripts/test_postgres.sh` exits with `test_postgres_unavailable: OSError`. It exposes only a root UID/GID mapping and cannot change ownership to an unprivileged database user. Native execution must therefore be proved by the existing PostgreSQL CI environment or a permitted development database. Static checks are not native proof. This limitation says nothing about the production query's cause.
