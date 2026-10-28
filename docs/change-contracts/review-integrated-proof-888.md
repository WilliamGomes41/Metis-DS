# Integrated Review verification — #888

Change class: B
Promise: Assess the integrated Review repair on authenticated user routes against the original performance and integrity budgets.
Proof: Matched native PostgreSQL/ASGI measurements, unchanged stored domain inputs, existing source oracle and negative/concurrency tests, explicit runtime evidence limits.
Touches lifecycle invariants: no
Rewrite risk: none

The existing production owners, requests, preparation, replay, review and
publication checks remain unchanged. This work adds an opt-in measurement and
comparison under `evidence/review-integrated-888/`, not a product runtime
component. Only disposable fixture setup and measurement output may change.
No schema, durable authority, job, production writer, deployment or migration is
introduced. Code/evidence revert is sufficient rollback.

The predeclared WP1 budgets, exact workload, sample protocol and limitations are
in that directory's README. Its benchmark uses the actual production composition,
named-reviewer login and native PostgreSQL. It observes all five Review routes
with complete/incomplete formation, short/long source, a filled batch and multiple
persisted documents. Incomplete matrix findings are synthetic; the existing real
failed-provider/recovery tests remain a separate requirement. Stored envelopes,
object history, bindings, review and command events must remain equal across GETs.

The integration diff retains the complete preoptimization source oracle and adds
integrity, window, freshness and writer-concurrency coverage. The only changed
older test helper selects explicit legacy import paths for a pinned rollback
checkout; assertions are retained. No replaced production probes or new runtime
debug statements were found. Historical benchmark scripts stay as reproducible
evidence, outside runtime composition.

The incomplete inventory's duplicate source-accountability projection is still
present. It includes current decisions; this patch neither caches approvals nor
substitutes a projection for domain authority. Faster local samples cannot prove
the original live complaint resolved. Current deployment identity, representative
live source, authorized logged-in production baseline and production latency
remain open under #695/#699/#680. Therefore #888/#884 must not be closed solely
on this patch or its local/CI results.
