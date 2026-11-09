# Publisher deletes one complete test document (#1037)

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes
Promise: during explicitly enabled testing, a publisher can remove one complete
LogicalDocument, including every source/working version and historical/active
publication, from Metis and the Product API. No other document is removed.
Proof: native PostgreSQL HTTP/API, denied-command, rollback, stale-worker,
concurrency, restart and recovery tests; desktop/mobile browser confirmation.

## Decision and scope

GO projectlead, 2026-11-09: user requested publisher deletion of already-published
test documents during the test/build phase and explicitly selected "Hele
testdocument, alle versies en publicaties". This authorizes implementing the
bounded test-data removal exception, not executing a production deletion or
activating it on Azure. Normal published immutability remains unchanged.

The scope is the stored LogicalDocument identity, not title/family matching.
The console is an edge: preview/form/session state is ephemeral. The existing
Azure kernel and its PostgreSQL authorities own the operation and receipt.
Existing working copies, annotations, preparation/task state, authorizations,
canonical object versions, source bindings, registry pointers and release rows
in that identity are removed. The existing hash-chained review ledger remains
intact, with its document FK detached exactly as for unpublished deletion;
removing ledger entries would corrupt other documents' audit history. A deletion
receipt and deleted-snapshot IDs remain as an audit and stale-writer fence.

This is a document reset, not a storage/privacy erasure service. Content-addressed
source files, independent Audit-workspace reports, provider/platform logs and
infrastructure backups retain their existing storage/retention policy. No Blob
deletion is attempted: ingestion stores bytes before registering the document,
so a post-commit "unreferenced" Blob deletion could race a fresh upload. Reusing
those bytes must not reuse the deleted snapshot or its annotations/publications.
The confirmation page discloses retained control history and source storage.

## Lifecycle vertical slice

Lifecycle entity: LogicalDocument and its SourceSnapshots, WorkingRevisions and PublicationReleases.
Lifecycle transition: complete test document present -> absent from workflow and serving, durable deletion receipt present.
Initial durable state: one identity has published/superseded/withdrawn releases and zero or more working versions; no attempt in that scope is running.
Trigger: publisher submits the exact preview with a fresh command ID, reason, exact title and explicit test-document confirmation.
Authorization: current non-retired publisher, rechecked under an account-row lock; CONSOLE_TEST_DOCUMENT_DELETION=on is required in the kernel.
Validation: supported native workflow/canonical stores use the same database; migration/grants installed; exact preview fingerprint and lineage membership unchanged; no running attempt, cross-lineage successor or mixed/shared canonical release.
Mutable entities: only rows belonging to the confirmed identity, publication pointers/items and canonical rows exclusively owned by its snapshots; normalized review-ledger FK is detached without changing event bodies/hashes.
Immutable entities: all unrelated documents, accounts, sessions, topics, Audit-workspace reports and global review-ledger event payloads/hashes; deletion receipts/tombstones are append-only.
Workflow state before: published closed revisions and optional non-running working revisions.
Workflow state after: no document, objects, annotations, authorizations, extraction/task state or document-specific operational view-check rows in the selected identity.
Release state before: any published/superseded/withdrawn history of that identity.
Release state after: those release rows/items/canonical bindings removed, without adding a fake withdrawn/deleted release status.
Serving state before: zero or one active release of that identity.
Serving state after: no registry entry or Product API result from any deleted release; unrelated serving remains byte-for-byte unchanged.
Expected API result: successful command returns its durable receipt; Product API returns no deleted knowledge; duplicate exact command returns the same receipt.
Expected UI result: publisher sees exact versions/counts and retention note, confirms title/test data/reason, then sees a receipt and can return to Documenten where the document is absent.
Failure result: invalid authorization/mode/confirmation/stale plan/running work causes no mutation; a database fault rolls the entire deletion and receipt back.
Restart result: absence and receipt persist; startup reconciliation does not recreate the document.
Recovery result: current workflow recovery exports/restores deletion receipts and fences; old/relabelled bundles containing deletion records are rejected; restore to a nonempty target remains forbidden. Explicit pre-deletion backup restoration is an operator recovery, never automatic resurrection.
Legacy-data result: canonical releases are found through existing snapshot/source/audit lineage; mixed/unowned cross-document releases fail closed rather than guessing from titles.
Required black-box scenario: publish v1, create/publish v2 in the same lineage, preserve an unrelated published document, preview/confirm whole test document, prove both versions absent from UI and API, restart and restore a post-deletion backup, then prove stale snapshot insertion/publication remains refused and fresh upload can be annotated.
Explicit non-goals: deleting Azure data now, merging/deploying, changing normal published immutability, source-byte garbage collection, audit hash-chain rewriting, cancelling running work or deleting accounts/other documents.

## Rewrite mitigation and authority map

Rewrite target: narrowly remove confirmed test lineage across the existing workflow and canonical/publication authorities; preserve normal operations.
Why local patching is insufficient: removing the published-delete guard alone would leave live registry/canonical data, broken lineage or recoverable stale writers.
Current authority/writer/reader map: workflow documents/concurrency/operational-input stores own receipt/object/task/review state; PostgresCanonicalPublicationStore owns canonical versions/releases/source bindings and registry; AzureBlobSourceStore owns frozen bytes; workflow review store owns the global hash chain. Readers include console Documenten/Review/annotations, Product API, MCP, startup release reconciliation and workflow backup/restore. Ingest, successor, review/build activation and publication/recovery are alternate writers. The new operation coordinates SQL in one existing database; it does not create a second publication authority.
Supported runtime topologies: native PostgreSQL production composition in Azure and local native PostgreSQL tests; legacy-inline and operational input/task layouts. Mismatched stores/databases and missing storage capability are refused. File-only mutation is unsupported.
Persisted-state impact: additive migration 039 creates append-only deletion receipts and deleted-snapshot IDs plus insertion fences on workflow documents and canonical source snapshots. No existing row is changed by installing the migration.
Compatibility/migration plan: expand schema and deploy default-off feature first; optional runtime DELETE grants are verified explicitly for test deletion. Enable only during testing. Tombstone triggers keep stale/older writers from resurrecting already deleted snapshots.
Rollback/recovery plan: disable the feature to stop new deletes; never remove tombstones on code rollback. Versioned recovery carries them. A native pre-deletion workflow-chain backup/restore proof through the existing PG/Blob backup owner demonstrates data recovery; code rollback alone does not restore deleted data.
Cutover trigger: migration/grant preflight, passing native/browser/full CI and human release review; explicit app setting enables the action.
Cleanup/decommission criteria: turn the setting off after the test/build phase; retain receipt/fences and supported recovery readers while deleted snapshot IDs could be replayed.
Failure blast radius: one confirmed stored LogicalDocument; table locks are short SQL-only critical sections; no external source I/O under them.
Adversarial proof matrix: wrong/revoked role, mode off, missing confirmation, changed version/release membership, running legacy/operational attempts, shared release/source ownership, rollback after partial SQL, exact duplicate/conflicting commands, concurrent publication/ingest, stale direct snapshot inserts, restart/reconciliation and current/legacy recovery exports.

Lock order: existing local kernel store lock, publisher account row, workflow
documents table write lock, canonical logical-publication advisory lock 2110023,
then canonical tables in their normal publication write order. The workflow
table lock excludes concurrent lineage inserts; canonical locks serialize
direct/legacy writers too. No heavy extraction or Blob I/O occurs inside this
transaction. Receipt and deleted-snapshot fences commit with all row deletions.
No temporary dual read/write or destructive schema migration is introduced.

## Verification and separate adversarial review

Before release: focused native tests, rollback fault injection, explicit
pre-deletion backup/restore and post-deletion workflow recovery round trip;
Chromium confirmation at desktop/mobile widths; normal unpublished-delete,
publication, lifecycle and recovery regressions; repository/release checks.
Review the finished diff separately against alternate writers, FK cascades,
shared objects, layouts, identity isolation, stale state and recovery omissions.
Record observed outcomes in the PR; green CI alone is not lifecycle proof.

### Separate adversarial review, 2026-11-09

Reviewed the finished operation separately against ingest, successor creation,
publication/withdrawal, current/legacy workers, both input layouts, global review
history, canonical sharing, feature disable/rollback and backup import.

- An initial physical `xmin` preview token changed on a harmless startup
  projection refresh. The final preview binds domain membership/identities,
  counts and publication/registry contents instead. Independent-kernel duplicate
  execution now proves one receipt and one delete event.
- Mixed-release membership is explicitly refused. An older canonical-only
  snapshot is included through exact publication lineage and disclosed in the
  preview; no missing source-version number is invented.
- Native SQL fault injection before document cascade proved complete rollback
  of canonical serving, workflow, receipt and fences.
- Direct old workflow/source snapshot inserts are refused after deletion even
  with the test feature off. A fresh upload can open empty annotation work with
  no inherited approval bindings.
- Native pre-deletion backup restoration recovered the publication; post-delete
  backup restoration preserved absence and fences. Relabelling deletion-bearing
  state as an older recovery version is rejected by the current reader.
- A deliberate test-mode bypass in an isolated disposable checkout caused the
  actual published-document deletion denial test to fail with DID NOT RAISE.
  The faulty copy was removed; no mutation entered the delivered branch.
- Chromium proved required confirmation, wrong-title rejection with retained
  reason input, whole-lineage receipt/reload, API absence and the unrelated
  document remaining available at desktop/mobile sizes and 200% text zoom.

Source files and the global hash chain are intentionally retained, as disclosed
in the confirmation. Full suite/CI outcomes remain required before release.
