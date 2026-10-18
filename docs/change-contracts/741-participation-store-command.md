# #741/#742 — migrate the participation transaction owner

Change class: B
Promise: A native reviewer participation command has one Storeopdracht owner, one authoritative reload, atomic workflow writes and no mirror write before the outer commit.
Proof: red-first native participation tests for mirror writes, reload/SQL counts and original-error preservation; existing participation authorization, evidence, restart, publication-race and concurrency scenarios.
Touches lifecycle invariants: no
Rewrite risk: high

## Five-step simplification and domain decision

Question: adding, archiving or replacing a reviewer must preserve exact existing
evidence, required independent duties, authorization, stale-revision checks,
command replay and published immutability. These requirements belong to the
existing participation policy, not to its separate raw transaction wrapper.
Delete: remove only participation's raw transaction, duplicate recovery and
extra authoritative reloads. Simplify: reuse the existing Storeopdracht owner;
keep `_execute` as the existing domain transition and keep local file behavior.
Accelerate: measure one command's SQL and reloads before/after, without claiming
to fix the remaining 1+D reviewer reads (#686). Automate: native regression and
CI evidence only after the preserved domain behavior is proven.

Existing call path: POST /review/participants ->
OperationsConsole.manage_review_participation -> review_participation.execute
-> `_execute` -> `_commit_prepared_store` -> PostgreSQL workflow stores.
The current raw owner makes the inner commit enter the compatibility branch.
A native probe on main `93f9023` observes three document-store reloads and eight
mirror writes while the outer transaction is open, covering all four mirrors.

Domain entity/aggregate: existing unpublished WorkingRevision and its participation policy/history.
Invariant(s): no source or clinical identity change; no manufactured/transferred approval; archived required duties remain outstanding; changed membership/object governance/history/audit commit together; mirrors are non-authoritative.
Durable state before: current committed envelope, object versions, exact approval bindings, graph reviews and event history.
Durable state after: the existing participation transition's updated policy/history, document CAS version and affected evidence, or unchanged state after rejection/rollback.
Transaction boundary: existing Storeopdracht holds the store lock, locks the same workflow.documents row, reloads once and commits all workflow writes; mirrors follow outside the transaction under the same lock.
Failure/recovery result: existing Storeopdracht rolls back and rebuilds from PG; a failing recovery cannot replace the command's original error; mirror failure after commit cannot report an uncommitted command.
Duplicate execution / idempotency result: existing command_id and payload hash return the committed result; conflicting replay and stale revision remain refused.
Concurrency result: keep the independent-command rejection, same row lock, store lock and expected revision. A stale second runtime cannot overwrite the winning roster; publication race semantics remain unchanged.
Audit/evidence requirement: existing review_participation_changed event and retired evidence history remain in PG in the same transaction; no new audit authority or event type.

## Rewrite-risk mitigation before production changes

Rewrite target: participation's raw transaction wrapper and duplicate recovery only.
Why local patching is insufficient: deferring just one mirror leaves the other mirrors, repeated reloads and recovery owners; the existing Storeopdracht already owns this invariant across all four mirrors.
Current authority/writer/reader map: workflow.documents envelope owns membership/history, workflow.document_objects carries checked governance/document CAS, workflow.publish_authorizations and review_events own evidence/audit. `_execute` computes the unchanged transition; bound stores persist through `_commit_prepared_store`. UI, policy/readiness and command replay read these existing authorities. Existing mirror writers and `_remirror_from_pg`/rollback recovery remain owned by the review mixin. Canonical releases and serving registry are read for immutability, not written by participation.
Supported runtime topologies: local file harness unchanged; complete local and Azure R+ use the existing shared-store transaction binding. Unsupported partial PG configuration and active raw/owned transaction entry remain rejected by participation's existing independent-command guard.
Persisted-state impact: no schema, domain state format, policy semantics, migration or backfill changes.
Compatibility/migration plan: migrate one caller (participation) onto the established owner; all other raw owners and the general compatibility branch remain for #741 follow-ups. No dual writer or new mode flag.
Rollback/recovery plan: revert this caller migration; no data conversion is required. Keep original faults, native rollback and authoritative mirror recovery observable in tests.
Cutover trigger: code merge only after required CI/reviews and human GO; no production operation in this task.
Cleanup/decommission criteria: this slice removes participation's raw owner and recovery block; general compatibility removal waits for all remaining owners. No obsolete participation fallback remains.
Failure blast radius: native membership commands could be refused or have stale mirrors if ownership is wrong; policy and public command semantics remain pinned by existing tests. No source bytes, canonical releases or serving state may change.
Adversarial proof matrix: raw/owned/foreign nesting rejection; unauthorized/stale/conflicting commands; pre-commit and actual COMMIT faults; failing recovery; all-four-mirror spies; exact evidence preservation and restart; two-runtime stale/concurrent membership and publication races; local-file and complete-PG topologies.

A separate closure pass challenges the final ownership and failure paths. This
is a transaction-mechanism migration of existing semantics, not a change to the
Class A participation domain contract in REVIEW_PARTICIPATION_IMPLEMENTATION.md.
If that contract must change, stop and reclassify instead of changing policy.

Scope exclusions: other #741/#742 owners, #705 heading-copy recovery, #708 guard,
ledger reread policy, publication kernel changes, #686 and other N+1 work. This
slice does not close the parent issues, merge a PR or deploy anything.

## Verification and separate closure review

- Baseline native loop on main `93f9023`: three document-store reloads, 48
  domain SQL calls and eight mirror writes inside the open transaction.
- Red test commit `cded2d8`: 10 failed / 4 passed, covering both complete local
  and Azure R+ classes. The existing participation suite passed 17 tests before
  production changes.
- Migrated owner: 14 passed, zero skips; one reload and 46 domain SQL calls on
  the same optional-add fixture. The new CI JUnit no-skip check passed locally.
  This is a statement-count observation, not a latency benchmark. Store and
  participant savepoints remain intentional.
- Existing participation, explicit-policy, graph, native concurrency, #678 and
  R2 suites: 68 passed, zero skips with native PG enabled. These retain the
  file-backed cases as well as native cases and cover evidence/history,
  restart, stale writers and publication races.
- Separate closure pass: `_reviewer` and `_execute` are byte-identical to the
  base; local/independent-entry guard ASTs are unchanged. The only supported
  command entry is manage_review_participation (including its HTTP route).
  Foreign-owner/partial-store entry reaches the same existing rejection
  predicate; those unchanged guards were also inspected. Failure tests cover
  pre-commit faults, real deferred-FK COMMIT failure, failed recovery and a
  failed post-commit mirror write. No additional blocking finding in this slice.
- Broad local suite without a PG DSN: 4,979 passed, 4 failed, 558 skipped,
  6 xfailed. The four failures also reproduce on unchanged main `93f9023`:
  missing local psql and the three proxy-sensitive HTTPS SNI / redirect
  rebinding / metadata tests in security_harden_wave3. No security guard was
  changed; this is not a wholly green local-suite claim.
- Repository/release preflights, compilation, architecture boundary check and
  six architecture invariant tests passed. Exact-head CI and required external
  Sherlock/Argos/adversarial review and human GO remain pending.
