# #718 — refuse partial workflow storage before startup

Change class: B
Promise: the composition root admits only a complete PostgreSQL workflow with canonical publication storage, or an all-file local harness; invalid configurations cannot open storage or credentials.
Proof: exhaustive 30 partial combinations, unknown values, Azure/local and CLI rejection; native R+ startup/restart and unchanged A08/R2 assertions.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing mechanism and change

`console_asgi.build_app` selected identity-only, review-without-remaining and complete workflow consoles. Only the documents-without-review combination was checked before constructors. Store factories could verify schema before later prerequisites failed. A local PG workflow could omit canonical publication storage.

Extend the existing environment-only check, preserving the #665 refusal code. Validate five existing settings before credentials, Blob, stores, bootstrap or reconciliation. All five must be `postgres` or all empty (the latter local only). Canonical-only plus file workflow is also refused: it is a mixed deployment, not the all-file harness. No new mode flag, writer or persistence abstraction. Delete the identity-only and review-only branches/imports from `build_app`.

The documented `serve-console` local harness remains available. Its guard reuses the composition validator and refuses a complete PG configuration rather than silently ignoring it. Direct intermediate constructors and `create_console_app(None)` are #719/#722, not protected by this composition-only change. The class chain is not collapsed (#721).

## State and failure

This is stateless admission. Existing PostgreSQL stores remain authoritative; this change does not mutate schema, domain objects, review permissions, publication rules or commit/mirror behavior. An invalid startup produces a stable error without storage calls. Correcting config is not a data migration: an existing mixed installation must have its data location checked before configuration changes. No automatic import or fallback. Code rollback restores old admission behavior, not data; this patch performs no data conversion.

## Tests and review boundary

First commit contains rejection tests. On base `26a0901`, 28 failed and 9 passed: failures reached the trapped storage/credential boundary; #665 cases already rejected correctly. The final matrix retains every case, adds valid composition/CLI checks and native startup/restart. Tests accepting tier R in A08/R2 and other workflow behavior fixtures are moved to R+; old direct-constructor introspection in #665 remains intentional pending #719. Existing rollback/concurrency assertions are retained. The complete fixture uses the production fast-badge class, a remaining store, canonical store and shared transaction binding.

The separate `workflow-topology-proof` CI job supplies native PostgreSQL 16. Local PostgreSQL installation was unavailable due filesystem permissions; skipped native tests are not acceptance evidence. Overall test count is recorded at final verification. No deployment or production data operations.

Separate review checks: all 32 presence/absence combinations; normalized casing; unknown values; old tier-D error priority; canonical-only rejection; local CLI bypass; unchanged Azure Blob requirement; removed construction branches; no schema or writer changes; existing tests preserved. Direct construction, route fallback and global backend registration remain separately tracked, not claimed fixed.
