# A08 / #558 — commit result and review lock order

Change class: B
Promise: A committed heading batch stays successful when disposable mirror refresh fails, and concurrent ordinary reviews preserve the winner.
Proof: Native PostgreSQL HTTP/direct fault injection after successful COMMIT, real advisory-lock waits, fresh readers/restart, unchanged commit/write rollback tests and required repository checks.
Touches lifecycle invariants: no
Rewrite risk: high

## Assigned scope

The owner explicitly assigned the remaining A08 repair in this conversation.
#558 is the one implementation/acceptance issue, now ready-for-agent. Base:
`76da2d7e29e3b8af8e1fb411f27f22d99930e1c3` (merged #607). Scope is the two
review comments 4250659601 and 4250659587. No merge, production deployment,
production mutation, issue closure, A10 work or unrelated cleanup.

## Existing mechanism and domain contract

HTTP original endpoint and workboard wrapper call `batch_confirm_headings`.
The existing document mixin owns `workflow_transaction`; the review mixin
buffers audit events inside it. `review_object` continues to own all existing
review/authorization rules. Document and review mixins currently run fresh
database reads unconditionally in `finally`, after COMMIT. Ordinary review
writes authorizations before its document row write, whereas the batch first
locks the document row. Shared-runtime flock serializes console commands;
independent disposable mirrors in the existing native test topology require
checking the actual SQL lock order as well.

Domain entity/aggregate: selected structure-review batch in a mutable WorkingRevision.
Invariant(s): selected writes and audit commit together or not; no compensating writes after commit; a disposable mirror cannot decide durable success; existing authorization, stale-write and immutable-publication rules remain.
Durable state before: existing unconfirmed headings, object history, bindings, envelope/revision and audit.
Durable state after: all selected headings confirmed under existing rules, or unchanged authority after a true transaction failure.
Transaction boundary: existing native workflow_transaction plus member writes and buffered audit flush; mirror refresh is post-transaction recovery.
Failure/recovery result: write/COMMIT failure propagates and rolls back; post-transaction recovery must neither turn committed success into failure nor replace the original transaction error. Authoritative readers and startup remirroring recover disposable state.
Duplicate execution / idempotency result: existing exact semantic repeats remain no-op; stale supplied revision conflicts; no new command store.
Concurrency result: shared-runtime and native database boundaries preserve the winner; multi-instance App Service support is unchanged.
Audit/evidence requirement: existing per-object audit events commit exactly once; mirror diagnostics are operational logs, not domain audit.

## Rewrite mitigation

Rewrite target: existing A08 transaction/result and disposable refresh boundary.
Why local patching is insufficient: an HTTP-only catch misses direct commands and both storage mixins; the existing context owners must preserve the native outcome.
Current authority/writer/reader map: batch_confirm_headings/review_object -> document/review/identity participants -> workflow_transaction; PostgreSQL documents/document_objects and publish_authorizations/review_events are authority; files/maps and ledger are mirrors in PG mode; ordinary review_object is the relevant alternate writer; HTTP/workboard/direct commands and subsequent source/review readers consume the result.
Supported runtime topologies: local files, document-PG/local-review and full document/review-PG; inherited durable/Azure-publication compositions reuse these mixins. Native independent-root tests exercise adapters on one host/database, not expanded multi-instance hosting permission.
Persisted-state impact: none to schema, identity, migration, historical data or publication state.
Compatibility/migration plan: local extension of current owners; no alternate writer, authority, new persistent field, dual write or backfill.
Rollback/recovery plan: code revert restores prior outcome/lock behavior without data conversion; never undo committed reviews; existing authoritative reads/startup rebuild mirrors.
Cutover trigger: verified correction, mandatory checks and human review/merge; production deployment separately authorized.
Cleanup/decommission criteria: fault instrumentation stays in tests; no shared request-result marker or temporary authority; existing mirrors remain disposable.
Failure blast radius: A08 command outcome, native lock acquisition and rebuildable runtime state; unrelated publication/serving and source processing unchanged.
Adversarial proof matrix: post-commit read failure in both PG MROs and HTTP/direct commands; true deferred COMMIT/write faults; stale/current repeat without extra events; same-runtime batch/single overlap in both orders; native actual advisory wait with independent mirrors; complete winner state after fresh read/restart; existing access/published rejection.

## Verification record

Tests-only diagnostic revisions were published on `fix/a08-review-completion`.
Run 38297476164 on 7ae0d923 demonstrates ten post-commit failures: PostgreSQL
commits both headings and audit, but the HTTP path returns 500 and the direct
command raises. Run 38297928765 on 9bbc95ae reaches a real PostgreSQL advisory
wait and reports workflow_review_write_failed instead of the expected conflict
for the independent-mirror overlap. Initial test iterations had incorrect
history/event expectations and missing shared source setup; those fixture
problems are separated from product defects, not counted as additional bugs.

The correction is deliberately local: both existing finally blocks log a fixed
non-sensitive diagnostic when disposable recovery fails, preserving success
or the original transaction error. Full-PG batches reuse the existing review
authorization advisory lock before taking the document row lock, matching the
ordinary review write order. There is no new state owner or persistent field.

CI on this review branch also replays the final focused tests on the unchanged
merged base. It requires ten exact committed-result failures, one actual native
DeadlockDetected/40P01, two cleanup-masked COMMIT errors, two passing true rollback
controls and zero skips. The candidate's complete A08 suite then must pass with
zero skips; the pre-existing native write, stale, role and process-restart tests
remain enabled. The baseline comparison is branch-scoped diagnostic proof, not
an expanded production topology or a new application gate.

This paragraph records the pre-execution checkpoint; the executed closure is below.
The local environment has Python 3.12 with repository development dependencies.
It cannot switch to an unprivileged PostgreSQL server user, so native evidence
uses the existing disposable PostgreSQL 16 CI service rather than production.

## Executed closure

Executable revision `360c96279a0d794077302a7d0ec63711086b8d98`, isolated run
[38298617496](https://github.com/WilliamGomes41/Metis-DS/actions/runs/38298617496).
Python 3.12 and 3.13 each execute **97 A08 cases: 71 native and 26 local,
zero skipped/failures/errors**. Both unchanged-base comparison steps pass:
15 native cases per version, 13 intended failures and two true rollback controls
passing. The deadlock carries the actual native `DeadlockDetected`, SQLSTATE
`40P01`; this is no longer merely a difference in lock ordering. Both native
zero-skip-enforcement steps and artifact uploads pass. All four JUnit ZIPs were
downloaded, parsed and SHA-256-checked against GitHub's digests; IDs/digests and
coverage are in `a08-review-completion-evidence.json`.

The original deferred COMMIT failure still propagates and leaves complete
pre-batch state, including when a subsequent refresh fails. A successful COMMIT
with document/revision/review-mirror refresh failure returns success on both
HTTP and direct entry points. Fresh readers and new OS processes retain object
history, envelope, bindings, object/storage revisions and audit. Existing
semantic repeat makes no extra event, while a stale supplied revision conflicts.
The same-runtime overlap is exercised in both orders on all three storage
modes; the native independent-mirror overlap observes a real advisory-lock
wait and now returns the expected revision conflict without losing the single
review winner. The latter setup shares verified source storage on one host;
it does not expand the supported App Service instance topology.

Local focused A08 plus architecture: 32 passed, 71 native cases skipped locally;
native CI above supplies their real execution. Repository/change-contract,
committed release-control mapping, compilation, architecture boundaries and
six architecture invariants pass. Complete local suite: **3425 passed, 379 skipped, four failed**, 412.13s.
The same four failures were separately reproduced before product edits; those tests and
product paths remain unchanged. An initial full local iteration also contained
one invalid newly written fixture case, corrected before the final run.

Separate post-implementation adversarial/surface pass: **APPROVE WITH NOTES**.
The production change stays in two existing mixins (17 added / 5 removed product
lines), using existing transaction and lock owners. No new abstraction, authority,
persisted state, domain audit, migration or repair writer is introduced. Reviewed
the installed HTTP/workboard and direct entrances, inherited durable/Azure
compositions, full/mixed PG and unchanged local file mode, both refresh blocks,
original error propagation, thread-local bypass cleanup, stale/current repeats,
ordinary-review writer order, fresh-read/startup remirroring and winner protection.
The fixed warning messages contain no exception payload or credentials.
Independent PostgreSQL transactions prove the SQL behavior; external Azure,
multi-instance hosting, capacity and file-store power-loss atomicity are excluded.

Engineering readiness: A08 acceptance **PASSED within the stated isolated
topologies**. Overall hosted suite was still running at this evidence checkpoint.
Human review/merge is required before A08 can be Code klaar on main; no merge,
deployment, production acceptance or issue closure was performed. Code rollback
does not undo committed reviews.
