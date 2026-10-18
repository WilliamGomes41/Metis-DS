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

Separate review checks: all 32 presence/absence combinations; normalized casing; unknown values; unknown-value precedence followed by the tier-D error; canonical-only rejection; local CLI bypass; unchanged Azure Blob requirement; removed construction branches; no schema or writer changes; existing tests preserved. Direct construction, route fallback and global backend registration remain separately tracked, not claimed fixed.

## Local verification, 17 October 2026

- Base collection: 5,449. Final collection: 5,498 (49 added, none removed).
- Final #718 tests: 47 passed; two native startup/restart cases skipped locally because no test PostgreSQL is available.
- Broader local suite on the initial implementation, before the final account-CLI guard and native-case additions: 4,941 passed, 5 failed, 541 skipped, 6 xfailed (581.68 seconds).
- All five failures reproduce on unchanged base `26a0901`: `test_t13_l2_psql_argv_carries_no_password`, `test_parent_process_death_terminates_transport_worker`, and the three pinned-HTTPS/redirect SSRF cases in `test_security_harden_wave3.py`. They do not establish a regression from #718. Native skips and these environment-dependent failures still prevent claiming a wholly green local suite.
- Repository preflight, release-control preflight, compilation, architecture boundaries and six architecture invariant tests passed.
- Separate pass found the `console-account` local writer also ignored PG/Azure settings. It now shares the local-command guard with `serve-console`; six refusal cases cover both commands. The existing local commands remain supported.
- CI and mandatory Sherlock/Argos review are still required. No merge, deployment or issue closure is claimed by this evidence record.


## First native run and test-fixture correction

GitHub run 39066411438: 322 passed, 3 failed, zero skipped. Both complete startup variants reached the login page; the new restart assertion incorrectly read `_accounts`, which the PostgreSQL identity implementation does not populate. Replace it with real authentication after restart and compare the durable account ID. The migrated A08 published rejection scenario only marked the envelope as published; R+ correctly asks the canonical store. Seed the existing canonical release/audit fixture as well, retaining the rejection and zero-write assertions. No production behavior is changed to accommodate these tests. A fresh native run is required before acceptance.


## PR #744 review corrections

- Both direct `OperationsConsole` CLI commands already had a guard at head `6195270`; retain their six rejection cases. Move their validator into `workflow_store_configuration`, with a subprocess proof that ASGI can be unavailable.
- Unknown settings now produce their exact `unsupported_*` code before checking prerequisites. The #665 explicit `file` case expects that exact error; missing review still has its original tier-D error.
- Share the five authority names across admission, credential selection, worker topology, refusal storage and the test matrix. Remove unreachable factory prerequisite checks and the Azure file branch.
- Restore the original seven-migration `workflow_postgres` fixture. Only full-composition cases use `complete_postgres`, which creates and finally drops its own UUID-named database. It never drops schemas in the supplied database and passes the isolated DSN to subprocesses. Test-server CREATEDB rights are required; creation failure is not converted to a skip.
- Restore actual Azure `build_app()` path assertions with native PG, including runtime/source paths outside a simulated wwwroot. Restart authentication uses a new empty data root. Explicit teardown restores the rebound AuditRegistry global.
- Use `complete_console` consistently, bind four stores once, and name the actual R+ class in introspection/type assertions. Publication unit tests explicitly retain their MemoryCanonicalStore double; native composition/restart uses real canonical PG storage.
- Local review verification: 118 passed / 25 native skips, plus 53 passed / 89 native skips. The previously baseline-reproduced psql-availability test is excluded from the second run (psql is absent). Collection succeeds: 5,499 tests. Native CI on the updated head remains required; these skips do not prove PostgreSQL behavior.
- Additional ASGI/navigation/logging coverage: 83 passed. Final admission-only rerun: 48 passed, two native skips. Repository/release preflights, compilation and architecture checks pass.
