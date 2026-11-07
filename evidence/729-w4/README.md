# W4 — bounded database work during formation activation

The unchanged 130-task resume proof drops from **24.374409s to 9.555206s
median (60.8%)** across five alternating baseline/head pairs. All new runs are
below the predeclared 18s maximum (worst: 9.783557s); the median is below 15s.
Every run still exceeds five seconds. This is one background-processing slice
of #729/MET-36, not completion of the broader performance programme or a
production latency claim.

## Revisions and measurement boundary

- Baseline: `e6e008c671bfdaa780b1df6cd3b44a661643f7ce`, merged W1 main.
- Runtime implementation: `5df87a987764bbcd60e44b34402ffe52b558118a`.
- Both benchmark worktrees were clean. Later commits change explanation text,
  test evidence labels and this evidence only; they do not alter the measured
  writer or migration.
- Python 3.13.5, PostgreSQL 17.11, one local host. Each run gets a fresh isolated
  database. The deterministic provider makes no external model requests.
- Both checkouts use the byte-identical original
  `scripts/measure_source_task_reuse.py` (SHA-256
  `257a70dfa59186245b045b2a257879253585791cbdbd9e3218d14e53edb35474`).
- Time covers `execute_source_selection` after resume reservation. It excludes
  source upload, setup, reservation, post-run verification and browser paint.
  No tests or other benchmarks ran concurrently with these measurements.

| Pair | Baseline seconds | Head seconds |
|---|---:|---:|
| 1 | 24.907843 | 9.555206 |
| 2 | 24.068415 | 9.783557 |
| 3 | 24.374409 | 9.648111 |
| 4 | 24.755935 | 9.298082 |
| 5 | 24.186551 | 9.443391 |

[matched.json](matched.json) records revisions, environment and execution order;
[summary.json](summary.json) records the aggregate. All ten individual results
are retained. No samples were discarded. Each has 131 provider calls, including
the intentional second-call failure; the first committed task is never called
again and retains its exact result hash.

[verify_measurement.py](verify_measurement.py) wraps the original proof only to
check a fresh production runtime **after the timer stops**: all 261 ordered
objects, all 130 committed task results and source bytes remain exactly equal
within that run; the attempt succeeded and publication is still disallowed.
Each `*-restart.json` contains hashes/counts and those successful assertions.
Hashes retain run-specific identity; they are not normalized into a claim of
cross-run identity equality.

## Server-side cause and effect

The exploratory unprofiled baseline was 27.715238s. It selected the bottleneck
before the [contract](../../docs/change-contracts/729-w4-formation-database-work.md)
fixed acceptance and before product code changed. Separate instrumented runs
are diagnostic observations, not part of the latency sample above:

| Observation | Baseline | Head |
|---|---:|---:|
| Entire instrumented resume | 26.039772s | 9.579333s |
| Existing physical object writer | 16.140029s | 0.304127s |
| Generation-trigger invocations | 261 | 3 |
| Generation-trigger total time | 15.617s | 0.167s |
| Task-checkpoint method, 266 calls | 0.181005s | 0.176498s |

The 261 original INSERT statements took 16.027s in the client and 15.918s on
the server. Their generation updates alone took 15.611s. Rewriting the same
large document repeatedly ran its original identity/projection guards for
every inserted object. Driver transport and task-result commits did not
explain that group. Grouping only client calls would retain that trigger cost.

Migration033 preserves the exact per-row generation increment while updating
the document once per statement. The existing writer groups at most 128
adjacent new rows and checks every returned row; all per-row object guards and
epoch/fact triggers remain. This meets the separately fixed <=2s writer budget.
The native structural test proves <=4 document updates for 261 rows, exact
generation +261, exact ordered JSON and usable lineage certificates.

[profile-base.json](profile-base.json), [profile-head.json](profile-head.json)
and [profile_resume.py](profile_resume.py) contain client timings,
`pg_stat_statements`, `pg_stat_user_functions` and 25ms wait samples from a
separate local instrumented cluster. Query and nested function times overlap:
**do not sum them**. No sampled lock wait was observed; that does not prove
contention cannot occur. The base profile ran before implementation on the
baseline product files; the head profile ran on the clean runtime commit.

The remaining work includes 400 processing-attempt updates (1.645s client /
1.553s server in the head profile) and their nested projection checks. The
9.56s background job remains in the >5s inventory. Changing per-task durability
or attempt policy was excluded from W4 and is not justified by this evidence.

## Correctness, migration and recovery

The red regression was committed separately as `a5474899` before product code:
it verified the exact rows/counter, then failed because **261** document updates
exceeded the fixed maximum of four. The new native suite has 15 passing cases:
late-group suppression, changed payload/identity/position, hidden AFTER-trigger
writes, deferred COMMIT failure, exact multi-document INSERT/UPDATE/DELETE and
mixed UPSERT accounting, native0/empty writes, concurrency, stale checkpoint,
restricted legacy-writer rights, no optional review-card schema, repeatable
migration and rollback, and failure/restart/retry in both production compositions.

The restricted-role proof executes the old row trigger and then migration033
with **the same grants**; it needs no new runtime table grant or schema-create
permission. A test-fixture omission of the pre-existing `document_inputs`
SELECT grant was corrected before that final proof; product privileges were
not broadened. A deferred database COMMIT error is asserted at its actual
existing exception boundary, without changing application error handling.

A separate [adversarial self-review](../../docs/audit/w4-formation-database-review-2026-11-07.md)
traces alternate writers, fallback layouts, migration ordering, serialization,
recovery and exact SQL verification. In a disposable worktree, removing the
returned-payload comparison makes the later-group rewrite test fail with
`DID NOT RAISE`; restoring it passes. This is an implementer's adversarial pass,
not independent human approval.

Final test counts and required checks are recorded in [verification.json](verification.json).
The browser probe uses the existing real PostgreSQL/Chromium check, targeting
Documentopslag: 1440px and 390px, light/dark, keyboard and JavaScript disabled.
It waits for fragment navigation before assertion. No browser-harness change
was retained. The explanation links the composition diagram and W4 contract
at the runtime commit. Impeccable reported no findings.

## Reproduction

Provide a verified local test PostgreSQL DSN through `METIS_TEST_POSTGRES_DSN`
using `scripts/test_postgres.sh`. Do not record credentials in evidence.
Create clean worktrees for the baseline and runtime SHA above. From each
worktree, alternating baseline then head five times, run:

```sh
W4_RESTART_OUT=/absolute/output/1-head-restart.json \
  python /absolute/evidence/729-w4/verify_measurement.py \
  --counts 130 --output /absolute/output/1-head.json
```

Change output names for each pair; keep the original harness unchanged and run
no concurrent tests. For profiling, use an isolated server with
`pg_stat_statements` preloaded, `pg_stat_statements.track=all`,
`pg_stat_statements.track_planning=on` and `track_functions=all`. From the target
checkout set `W4_PROFILE_OUT=/absolute/output/profile` and run
`python /absolute/evidence/729-w4/profile_resume.py`. The wrapper creates the
extension in its disposable test database. It resets statement statistics for
the isolated cluster and function statistics for that database; do not point
the profiler at a shared or production server.

No schema change, deployment or production acceptance was executed. PostgreSQL
16 verification belongs to GitHub CI; Azure/network/model latency and the
broader end-to-end acceptance remain with #953/MET-44. MET-36 stays In Progress.
