# W1 — complete source-resolution evidence

Issue #729 / MET-36; existing project and parent #959 / MET-45.
Local run on 7 November 2026, Python 3.13.5, PostgreSQL 17.11.
No production or deployment claim. The CI PostgreSQL 16 environment remains a
separate check.

## Comparison

All 20 W1 corrections completed below five seconds, including the full HTTP
navigation chain; all 20 baseline corrections exceeded five seconds. Every
sample also met the W1 POST (3s), outer-lock (250ms), transaction (500ms) and
complete-action (5s) budgets.

| Metric (p95, 20 observations/version) | Baseline | W1 |
|---|---:|---:|
| Correction POST | 6.932s | 0.759s |
| Complete correction action | 9.086s | 2.962s |
| Outer write lock | 3,913ms | 169ms |
| Native write transaction | 3,913ms | 169ms |
| SQL queries per correction | 1,087 | 86 |
| Decoded JSON per correction (decimal MB) | 259.90 | 11.16 |
| Physical connections per correction | 36 | 12 |

Correction POST p95 fell by 89.1%. W1's slowest correction POST was 0.795s,
its slowest complete action 3.041s, and its longest lock 190ms. Ordinary
approval p95 was 0.567s before and 0.565s after; its SQL and JSON counters
were unchanged (69 queries, 5.85 MB). This sample shows no approval regression.

The baseline is `c4db3bd84bfe722ab235eff67d2ccf69b60a785b`; the final functional
implementation is `37d35f09d7e679050140d95a06f091e8b7e4c9e0`. Later commits only
record evidence. Five alternating pairs (AB, BA, AB, BA, AB), four observations
per operation per run, produce 20 observations per version for correction and
20 for ordinary approval. The fixture has 923 paragraphs, 924 raw source
fragments and 92 candidates. Every operation uses a real HTTPS request against
the production application composition in a fresh ordinary Gunicorn worker;
default 30-second timeout and garbage collection remain enabled.

POST time is client wall time through the 303 response. The complete correction
action separately includes form GET, POST, redirect GET and reopening the
source-selection page. It excludes login, user think time, browser paint and
production network latency. Lock and transaction time come from the existing
request diagnostics; SQL and decoded JSON counters cover the POST. Both
versions use identical instrumentation and fixtures. No other test or benchmark
ran concurrently. The p95 is observation 19 of 20 (nearest rank); all samples,
including outliers, are retained. This small controlled local sample does not
estimate a production service-level objective.

Every run also checks exact approval bindings, three recorded assessment
answers, four new open corrected versions, unchanged untargeted objects,
unchanged source files and canonical store, and persistence after restarting
the runtime. [summary.json](summary.json), [manifest.json](manifest.json),
[execution-order.jsonl](execution-order.jsonl) and all `base-*.json` / `head-*.json`
contain the counters, worker identities and successful proof results.
Raw worker configurations, credentials, TLS keys and request logs are excluded.

## Correctness and compatibility

The red HTTP regression was committed separately in `f0a243d7` before product
code: the original full repair ran with the outer lock and SQL transaction
active. On the final implementation it runs in the existing SQL-free preparation
scope. Native tests exercise both production console compositions, exact
whole-object-set stale replay, current actor/roster/policy/source races,
unrelated and retained-version writes, immutable selected arguments,
same-baseline equivalence to the original serial kernel, final audit and
deferred-COMMIT rollback, retry and restart. Historical source records without
prepared extraction and unprepared history retain the original serial route.

The full parallel suite completed with **8,315 passed, 7 failed, 45 skipped and
3 expected failures**. Four failures came from missing history in the shallow
checkout; fetching full history resolved them. Two exposed the historical
Docling compatibility path, which was fixed. One race fixture attempted SQL
inside pure preparation; it now injects the competing write at the real commit
boundary. **All seven reruns passed**, followed by **152 affected source-repair
and shared-review tests**, plus **eight architecture/explanation tests**.
The full suite was not repeated after that bounded fix. No PostgreSQL test was
skipped; skips concern opt-in browsers, real Docling models or optional Bend.
[verification.json](verification.json) records counts, exact commands, skip
reasons and limitations. Local pytest-xdist was used for the full suite; no
runtime or repository dependency was added.

The separate [adversarial self-review](../../docs/audit/w1-source-resolution-review-2026-11-07.md)
records the discovered mutable-selection and historical-source issues and their
fixes. Removing the public precondition check makes stale replay succeed and
fails the rollback/retry proof; the mutation was restored. This is an
implementer's adversarial pass, not independent human approval.

The document-storage explanation passed the existing Chromium check adapted
locally to its model: desktop 1440px, mobile 390px, light/dark and JavaScript
disabled. The probe waited for fragment navigation before assertion; no harness
change was retained. Impeccable's detector reported no findings.

Repository preflight, release-control preflight against `origin/main`, source
compilation and architecture boundaries passed. The Class A/high-risk PR
contract and exact-head Linear handoff are validated before PR creation.
See [checks.json](checks.json) for the recorded local checks.

`origin/main` advanced to `d8e223b5d9b730580e454db7f39f689807801f2d` during this
work (saved-review discovery). A merge-tree check found no conflict. The
comparison keeps the original pinned baseline to isolate W1; the newer main's
changes are not included in these performance claims. PR checks must verify
the integrated result.

## Reproduction

Use clean detached worktrees at the two commits above, the repository's Python
dependencies and a disposable native PostgreSQL database verified through
`scripts/test_postgres.sh`. Supply its DSN via `METIS_TEST_POSTGRES_DSN`; never
commit it. Create a private tools directory containing a local TLS `server.crt`
and `server.key` valid for 127.0.0.1. Keep it outside the repository. Run:

```sh
python evidence/729-w1/run_comparison.py --base /path/to/base --head /path/to/head --out /path/to/new-results --tools /path/to/private-tools
python evidence/729-w1/summarize_comparison.py /path/to/new-results
```

The runner copies the frozen baseline server harness and extends its existing
probe with navigation and phase timing. It refuses dirty/moved worktrees and
records both probe hashes. Temporary probe files are removed after each run.
Only the allowlisted JSON results and scripts are suitable for publication;
the result directory also contains private worker configurations and logs.
