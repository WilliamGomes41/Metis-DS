# #708 — refuse reprocessing without a Storeopdracht owner

Change class: B
Promise: R+ reprocessing refuses an enclosing raw workflow transaction without a Storeopdracht before reload, row locking, domain mutation or mirror writes.
Proof: native PostgreSQL rejection test red on main `3b64ae2`, plus accepted standalone/nested commands, foreign-owner rejection, mirror spies and rollback/commit-failure tests on the production R+ class.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing mechanism and smallest change

The review mixin's `_reprocessing_transaction` calls `_store_command_applies`.
That method accepts an owned command, refuses a foreign command, and returns
false for an active raw workflow transaction without a command. The false branch
currently delegates to the documents mixin: it enters a savepoint and reloads,
which writes the bindings mirror before the enclosing transaction commits.

Replace that reprocessing-only fallback with the stable ConsoleError code
`reprocessing_store_command_required`. Keep the shared admission method, command
owner, participant savepoints, locks and recovery mechanisms unchanged. The
caller still owns its enclosing raw transaction and may catch the refusal;
the rejected reprocessing body does not run. No retry or domain audit event is
created by this refusal.

The caller review found no supported route that needs raw-owner reprocessing.
Participation, decision and source-context raw owners call `_commit_prepared_store`,
whose compatibility behavior is unchanged. Successor parent checking opens its
raw transaction inside reprocessing, rather than wrapping reprocessing in it.
The remaining raw owners and general compatibility removal remain #741/#742.

## State and failure boundaries

PostgreSQL remains authoritative. The guard adds no durable state, schema, data
migration, new writer or lifecycle rule. The existing Storeopdracht still owns
the transaction and recovery. A rejected call changes no domain data or mirrors;
valid calls retain their revision checks, idempotency and serialization.
Code rollback is a revert; no data conversion is needed.

The native tests create and finally drop their own UUID-named database. The
supplied METIS_TEST_POSTGRES_DSN must identify a test server with CREATEDB rights;
creation errors fail rather than becoming skips. The shared transaction fixture
and supplied database schemas are not changed by these new tests.

## Evidence and completion boundary

First commit `b195ce5` contains the regression tests: 1 failed (missing refusal),
6 passed, zero skips on PostgreSQL 16 against unmodified main `3b64ae2`.
The accepted cases now cover both FastBadgePostgresCompleteWorkflowDurablePublicationConsole
and FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole with
real identity, documents, review, remaining and canonical stores. Immutable
source bytes use an existing in-memory test adapter; Azure is not contacted.
Rollback cases make real object/authorization/event/envelope changes and cover
an outer exception, a caught participant exception, and a deferred foreign-key
violation on the actual outer COMMIT. All four mirrors are compared with PG;
spies prohibit mirror writes while the workflow transaction is active.

The ledger's use of buffered committed events remains unchanged. The explicit
B1 question in #708 must be resolved separately before claiming full issue
closure. Delete recovery (#706), other raw owners (#741/#742), and performance
issues are outside this patch. No merge, deployment or issue closure is authorized
by these local results; the existing Sherlock/Argos and human GO gates remain.
