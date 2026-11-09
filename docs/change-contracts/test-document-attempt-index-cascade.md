# Repair whole-document deletion with a retained attempt index

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes
Promise: the existing publisher test-document command removes its complete confirmed lineage even when PostgreSQL schedules the attempt-input cascade before the attempt cascade.
Proof: a native reproduction raises `document_inputs_attempt_index_immutable` at the document DELETE before the fix; native HTTP, restricted-role, both-input-layout, reordered-FK and upgrade/rollback tests cover the repair.

This is a bug repair within [the approved test-document lifecycle contract](1037-publisher-test-document-deletion.md), not a new removal authority. Its authorization, identity, confirmation, concurrency, serving, receipt, restart and recovery rules remain authoritative.

## Observed failure and cause

Production diagnostics identify the document DELETE and the static guard error, with no committed receipt or deleted-snapshot fence. The native reproduction creates a real relational formation attempt, rebuilds its document FK with the same semantics, then confirms whole-lineage deletion. The index has cascading FKs to both the document and attempt. Its old guard rejects the first cascade when the attempt row remains visible, even though the owning document has already disappeared in this transaction. The original fixture only used inline attempts and did not exercise this boundary.

Migration 040 replaces only `workflow.guard_processing_attempt_input`. DELETE remains forbidden when both the owning document and attempt exist. It remains allowed after attempt removal, and now also after document removal. INSERT/UPDATE validation and TRUNCATE refusal are unchanged. Migration 030 stays byte-for-byte unchanged; the registered ordered migration plan includes 040 last.

## Lifecycle and rewrite mitigation

Lifecycle entity: the confirmed LogicalDocument and its existing processing attempts/index.
Lifecycle transition: present in workflow/serving -> absent, with the same atomic receipt and deleted-snapshot fences.
Initial durable state: the existing contract's non-running published test lineage, including relational attempts and their derived index.
Trigger: the existing publisher's final confirmed test-delete command.
Authorization: existing enabled test mode, current publisher role, exact title/reason/test confirmation and plan fingerprint.
Validation: existing independent native transaction, identity, reservations, running-attempt and sharing checks.
Mutable entities: only the confirmed lineage's existing workflow/canonical rows, receipt and fences under the original command.
Immutable entities: unrelated documents, global review-ledger payloads/hashes, retained source bytes/backups, and the index of an extant attempt in an extant document.
Workflow state before: confirmed published lineage and optional working versions.
Workflow state after: its document, attempts and index absent; unrelated document present.
Release state before: existing publications in the selected lineage.
Release state after: selected publications absent under the original command.
Serving state before: existing registry pointers.
Serving state after: selected knowledge absent, under the original registry authority.
Expected API result: existing deletion receipt, with exact duplicate-command idempotency.
Expected UI result: final HTTP confirmation reaches the existing receipt page instead of a server error.
Failure result: the old-guard reproduction rolls back all serving, receipt and fence writes; forbidden index edits still roll back.
Restart result: the deleted lineage remains absent and the unrelated document remains present.
Recovery result: unchanged recovery-v14 receipt/fence contract; migration application changes no stored inputs.
Legacy-data result: both input layouts and original/rebuilt FK creation order work.
Required black-box scenario: publish old version and a relationally processed successor, preserve another document, log in as publisher, preview/confirm using a restricted DB role, revisit the receipt, restart, and verify the exact absence/preservation.
Explicit non-goals: executing a production deletion, changing feature flags, new grants, source erasure, or changing normal publication immutability.

Rewrite target: correct one existing cascade guard at the shared durable deletion boundary.
Why local patching is insufficient: HTTP handling or application DELETE reordering cannot repair the installed trigger's invalid assumption across supported FK orders and existing writers.
Current authority/writer/reader map: unchanged test-delete command and native workflow transaction; documents/attempts own the derived index, existing status readers consume it, and the registry owns serving.
Supported runtime topologies: existing native workflow/canonical database, both document-input layouts, original/rebuilt FK order, restricted runtime role.
Persisted-state impact: one CREATE OR REPLACE FUNCTION; no row rewrite, table/FK change, grant or destructive migration.
Compatibility/migration plan: reviewed exact-main registered migration plan/digest, with 040 applied last; the currently deployed application can use the corrected guard.
Rollback/recovery plan: application rollback leaves the compatible guard installed; restoring the old function reintroduces the deletion refusal but does not restore deleted data. Existing explicit backup restoration remains the data-recovery owner.
Cutover trigger: explicit operator application of the reviewed migration; feature activation and actual deletion remain separate actions.
Cleanup/decommission criteria: no dual path or temporary runtime state; preserve the historical migration and corrected guard.
Failure blast radius: index DELETE for a removed document or attempt; edits while both parents exist remain refused.
Adversarial proof matrix: original and index-first cascades; legacy/v1 layouts; restricted app role; direct index DELETE, forged UPDATE and TRUNCATE refused; failed old command has no receipt/fence or serving loss; migration is idempotent and preserves exact index rows; duplicate receipt and restart preserve unrelated document.

## Separate adversarial review

The guard has no feature-flag bypass, new role, privileged definer or alternate deletion writer. Existing FKs still require both parents on insert. The new DELETE allowance requires an already absent owner; PostgreSQL's existing whole-document command owns that transition. A direct index DELETE while both parents exist still fails. Migration 040 changes neither request authorization nor the transaction's canonical/delete sequence. The native upgrade test retains exact index records across repeated migration application and demonstrates full rollback of the old failure before retry succeeds.

No production change or successful production deletion is claimed by these local proofs.
