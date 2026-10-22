# PostgreSQL schema-check connection cost

Change class: B
Promise: Document-store startup verifies the same provisioned tables and columns with fewer database connections; an incomplete schema still fails closed with the existing error.
Proof: Native schema-damage counterexamples, an observed connection budget, repeated unchanged console-portion timing, and full CI against the unchanged pinned baseline.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing path and bounded change

`console_asgi.build_app()` constructs the native stores and verifies them.
Document, review and remaining store verification inherit
`PostgresWorkflowDocumentStore.verify_schema()`. The same checks also run from
console initialization. The base verifier opens one connection for required
table names and a second connection for required topic columns.

The change runs those same SELECTs, in the same order, on one connection
owned by each verification call. Cutover, review and remaining verification use
the base verifier on that same connection before their existing extra checks.
The base helper has only this narrow schema-validation responsibility.
It caches no result and changes no schema,
privileges, authority, workflow state, transaction writer or lifecycle command.
Every subsequent startup still reads the database again.

Missing tables must fail before the column query; missing columns and database
errors must retain their existing named failures. Successful and rejected checks
must close their connection. No data may mutate. The existing native store and
production ASGI composition remain the execution path.

This is stateless startup validation. The stateful Class B overlay does not
apply. Rollback is a code revert; no data conversion or recovery step is needed.

## Evidence boundary

The unchanged 2x suite gate failed repeatedly on PR813 while PR814 varied across
the threshold. No threshold, baseline, suite selection, authentication cost,
durability setting or production route may be bypassed to make it green.
A local portion speedup is not a full-suite or CI completion claim.
