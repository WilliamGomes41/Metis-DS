# WP1–WP8 integrated acceptance

Change class: B
Promise: Assess the merged Review implementation against the existing authenticated GET, POST and lock budgets, without changing domain behavior.
Proof: Matched native PostgreSQL/ASGI workloads, exact input manifests, refusal/retry/rollback/concurrency controls and explicit remaining runtime gaps.
Touches lifecycle invariants: no
Rewrite risk: none

This is the continuation of #888 / MET-17, not another implementation or
acceptance authority. Production owners and code remain unchanged. Only opt-in
evidence, its integrity checks and the acceptance record may change. Reverting
the evidence commit is sufficient rollback. Disposable synthetic databases are
the only mutable domain state used by these runs.

## Predeclared proof and boundaries

| Claim | Failure to expose | Evidence / expected result | Limit |
| --- | --- | --- | --- |
| Integrated latency | Optimization shifts work to overview, detail or redirect | Same WP5 task-v1 32/128 source, two history candidates, depth two, current/stale bindings; authenticated five-route matrix, 303/400/409 and actual redirect GET. Overview ≤3000 ms, detail ≤5000 ms; POST ≤3000 ms, exclusive store-lock hold ≤250 ms, store transaction ≤500 ms. | Synthetic local engineering goals, not production SLO proof. |
| Matched comparison | Smaller inputs or missing requests manufacture improvement | Identical harness, Python, source identity, source/object/history/binding counts and request inventory; retain every sample and failure. | Before/after run on the same native server sequentially, without concurrent heavy tests. |
| Compact rollout | Green legacy run hides unavailable or stale compact cards | Explicit compact configuration, out-of-request preparation/check, live bindings/actor, no unknown card in a fully prepared workload; exact oracle, missing/stale, SQL mutation, restart and reader rollback controls. | No production preparation or reader switch. |
| Review integrity | Changed CAS, retries, authority or partial commits | Existing native WP5 matrix and WP6–WP8 tests, including binding-only legacy/task-v1, variant-specific retry, context, audit fault and deferred COMMIT fault, concurrency and publication race. | Distinct passage-generation, command-equality and disjoint-merge semantics remain distinct. |
| Unchanged source/publication | Small read becomes permission or loses source | Existing source oracle, root/membership/corruption, source outside passage, incomplete formation, canonical publication tests. | Complete closure remains owned by the existing domain kernel. |

Seven warm samples plus a first observation per route provide median/range only.
First observations use a fresh production composition, not flushed OS/database
caches. Neither a p95 nor guaranteed process/DB-cold latency is inferred. SQL,
fetch, JSON volume and inclusive diagnostic phases remain separate; overlapping
phases are never summed. Missing phase evidence is unknown, not zero.

The original #888 large-source ≥30% improvement and small-control ≤15% regression
budgets remain binding and separate from the WP5 POST goals. Historical misses
in RESULT.md and the current-* artifacts are retained. A new WP5 matched
comparison does not erase them or independently close those criteria.

## Runtime completion boundary

The integrated implementation under test starts at merged main
`e2e261d09b4e24427eed57aa3a72c95bc5dcde3b` (PR #925). The WP5 comparison starts at
`7adb588d957e9f5461f338349e11535654ea2d10`, whose benchmark is unchanged from that
merged tip. Every final measurement records its actual checkout and harness.
The exact configuration is retained separately for legacy and compact readers.

Current deployment identity, representative original production workload and
authorized logged-in live evidence belong to #695/#699/#680. This task does not
deploy, prepare production data, activate a reader or initiate production load.
MET-17/#888/#884 remain open whenever that evidence or another binding budget is
unproven. A passed native suite is not project completion.
