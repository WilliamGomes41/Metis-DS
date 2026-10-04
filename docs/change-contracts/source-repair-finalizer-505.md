# Consolidate source-repair provenance finalization (#505)

Change class: B
Promise: Source-unit and merge repairs share one provenance finalizer while retaining both existing patch-hash contracts.
Proof: Repair/hash/restart/duplicate and rollback scenarios for both consoles, existing source-fidelity and PostgreSQL regressions, repository checks.
Touches lifecycle invariants: no
Rewrite risk: none

The user's direct session assignment authorizes selecting and implementing this
bounded consolidation. Main `78ff64e4237a2ab29d731604065a0cbd41bc3448` was
reconstructed locally and every tracked blob verified against its remote hash.

## Existing mechanism and scope

`/review/resolve` -> `submit_review_resolution` -> authorization and expected
revision -> `_atomic_snapshot_mutation` -> `_source_repair` or `_merge_repair`
-> `OperationsConsole.correct_object` -> `_finalize_source_provenance` ->
`_commit_prepared_store` -> existing review evidence and observable new proposal.

Two finalizer bodies in DeterministicRepairReviewConsole and ReviewClosureConsole
repeat current-version selection, verified source references, canonical hash,
schema validation and revision-checked commit. Their intentional difference is
patch-hash ownership: deterministic compatibility hashes repair_spec; closure
preserves the revision engine's patch hash, linked to revision_created evidence.

Consolidate the body in the existing base class. Override only the pure
`_source_repair_provenance_patch` policy. No new module, class, store, lifecycle,
transaction, access route or configuration switch. Existing callers and dynamic
commit/verification dispatch remain unchanged. This is an implementation-only
refactor, not replacement of the shared persistence or authorization boundary.

## Domain-first assessment

- Entity: existing unpublished WorkingRevision object and its provenance.
- Stateful operation: finalization writes the current corrected object. Its
  small provenance-policy calculation is stateless.
- Owner: backend kernel (despite the Console class names), never HTTP/session UI.
- Invariants: verified source binding, canonical hash/schema, existing patch-hash
  semantics; publication immutability, authorization and review requirements stay
  at their existing boundaries. Historical source and review evidence is retained.
- Before/after: corrected current object -> same object with finalized refs and
  the existing policy's patch hash. No new transition or persisted field.
- Atomicity: public repair already encloses review, revision, finalization and
  audit in `_atomic_snapshot_mutation`. The finalizer uses the same revision-checked
  `_commit_prepared_store`; no external side effect is introduced.
- Failure: source/schema errors precede the finalizer commit. A later failure
  rolls back the enclosing repair. Never delete evidence to retry.
- Duplicate/concurrent commands: existing expected revision and local/PostgreSQL
  locking reject stale commands. The finalizer is internal, not an idempotent API.
- Restart: read the same persisted object and evidence; no migration or backfill.
- Audit: retain repair selection, revision_created hash and review_audit_evidence;
  diagnostic logs are not a new authority.

## Runtime map and compatibility

Local compatibility uses DeterministicRepairReviewConsole directly. Closure uses
ReviewClosureConsole; DurablePublicationConsole derives from it. Azure authority
and PostgreSQL document/review/remaining/badge mixins compose above that boundary
in console_asgi.py. Their commit and atomic-mutation overrides remain unchanged.
The two source-unit/merge callers both resolve the inherited finalizer. Repository
search found no other finalizer override or string-based registration. Existing
tests also exercise an explicit base-method call for negative source validation.

The closure duplicate is removed; both public repair policies remain supported.
Do not mark the whole base class legacy-unused. No adapter is added. Rollback is
a code revert: serialized data and hash policies are identical.

Other processes remain on their established owners: source extraction/readback
in OperationsConsole and Docling contracts; review binding in workflow/review
stores; publication in DurablePublicationConsole; serving from the publication
registry; recovery in existing workflow/publication recovery modules. This pass
does not establish those entire processes as consolidated or safe to remove.

## Acceptance

One finalizer body, unchanged public behavior for both hash policies, successful
source-unit/merge repair and restart, stale replay rejection, and rollback after
an injected failure following finalization. Existing PDF construction proof
negatives and native PostgreSQL tests remain mandatory CI evidence. Full local
checks and CI results must be reported separately from production validation.

## Executed verification

- Six new behavioral cases passed before the production refactor, establishing
  the two existing hash policies, restart/stale replay and post-finalization rollback.
- After consolidation: repair/closure/decision-source suites 39 passed, 7 skipped.
- Architecture/import boundary and transaction/concurrency selection: 30 passed,
  14 skipped. PostgreSQL is unavailable locally; skips are not proof.
- Repository preflight, dependency boundary scanner, compileall, release-control
  mapping on the committed five-file diff, and Product API compatibility: PASS.
- Full local suite: 2648 passed, 179 skipped, 5 failed. Four failures reproduce on
  the unmodified verified-main snapshot: parent-death process detection and three
  proxy-sensitive URL-security tests. The three URL tests pass with proxy variables
  removed. The fifth failure was the subprocess losing PYTHONPATH dependencies;
  the same startup test passes in the isolated verification environment with those
  dependencies on its normal import path. No test or production guard was weakened.
- Focused review checked inheritance, both source-unit/merge callers, local and
  PostgreSQL commit dispatch, absent/present patch-hash preservation and negative
  construction-proof callers. No new authority, migration or rollback policy.
- Product code shrinks by 30 lines; two finalizer bodies become one. No claim that
  the broader console stack or all legacy routes have now been consolidated.

Native PostgreSQL and full CI results are tracked in the pull request for #505.
Local skipped tests do not establish those results. Deployment is outside scope.
