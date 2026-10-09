# A26, A04/A05, A02 availability repair

Change class: A
Promise: durable receipt and explicit resumable source selection remain available without long work owning the HTTP event loop or write transaction.
Proof: deterministic provider/extractor barriers on installed HTTP routes, concurrent reads/writes, duplicate commands, stale activation, restart and source reconstruction counters.
Touches lifecycle invariants: yes
Rewrite risk: high

## Domain and transitions

Lifecycle entity: SourceSnapshot / WorkingRevision and its existing processing attempts.
Lifecycle transition: absent -> received empty working revision; received -> explicitly authorized processing attempt -> prepared current candidates or durable failed/interrupted attempt. Successor: existing immutable source -> separate received working revision with the existing lineage and incremented review policy.
Initial durable state: no snapshot for receipt command; otherwise current registered snapshot and exact object revision.
Trigger: Inleveren only receives; Starten/Hervatten separately reserve and execute. Successor form receives a separate working revision.
Authorization: existing researcher receipt rules; researcher or named reviewer for selection; existing review owner/researcher/reviewer rules for successor. Rechecked at activation.
Validation: source digest/type/metadata/reviewer policy, command payload identity, object revision, active attempt lease; successor parent revision/policy captured and rechecked.
Mutable entities: new/unpublished working snapshot, existing processing attempts and quality evidence, unreviewed candidates at the existing guarded commit.
Immutable entities: original source bytes; existing published releases; parent objects, review bindings and history.
Workflow state before: absent/processing or existing parent state.
Workflow state after: processing until candidate activation; then existing readiness authority derives in_review/blocked/ready. No new serving authority.
Release state before: existing releases.
Release state after: unchanged; no publication operation.
Serving state before: existing publication registry.
Serving state after: unchanged, existing publication registry remains sole authority.
Expected API result: receipt redirect only after bytes and empty document registration commit; selection redirect after durable reservation; reads derive current status. Legacy synchronous kernel ingest remains supported.
Expected UI result: Inleveren -> Bronselectie -> Review -> Publicatie -> Documenten; receipt opens source-selection block with selected snapshot. Attempts and formation completeness remain distinct.
Failure result: registration failure produces no successful receipt; later processing failure preserves source and document, evidence, review work and prior releases. Guarded activation rejects stale results.
Restart result: receipt survives; reserved interrupted work survives until the bounded lease expires and becomes explicitly resumable; no automatic new model calls. UI is reconstructable.
Recovery result: existing expiry/retry/recovery budget, immutable-byte resolver and resume-open-ranges mechanism; never reset reviewed work.
Legacy-data result: existing synchronous ingestion and stored attempt/replay formats remain readable; no backfill or destructive migration.
Required black-box scenario: receive with extraction forbidden, restart, explicitly start with provider paused, unrelated HTTP/independent writer completes, duplicate command does not duplicate provider work, activate, refresh and inspect results; interrupted attempt expires then resumes; parent mutation prevents stale successor activation.
Explicit non-goals: unrelated audit repairs, production 502 causal attribution, publication policy changes, merge/deploy/paid calls.

## Rewrite mitigation

Rewrite target: split receipt from source processing and narrow successor lock ownership; read-local source reconstruction reuse.
Why local patching is insufficient: removing await loses the durable command boundary; to_thread alone preserves a long outer transaction; per-record readers recreate the same derived source.
Current authority/writer/reader map: immutable source store/_verified_source_bytes; OperationsConsole.ingest, retry_pre_review, resume_formation, reextract_unpublished, create_review_successor; _commit_prepared_store with local atomic files or workflow_document/review/identity stores and PostgreSQL _reprocessing_transaction; processing_retry reserve/assert_active/finish; source diagnostics checkpoint writer; HTTP ingest/review successor/tree retry/CLI; publication_readiness/consider_publish, review_work_item/render room and source detail readers. Runtime composition: console_asgi + installed document-status/publication/review UI overrides. Document lineage comes from existing workflow store, review authority from durable bindings, serving from publication registry.
Supported runtime topologies: local file single-worker compatibility; PostgreSQL workflow with process-local caches/file locks plus DB row/CAS transaction across runtimes; configured immutable store remains unchanged. No process memory as durable queue/authority.
Persisted-state impact: additive received source metadata and successor parent guard in existing envelope; existing processing attempt format and limits. No schema migration.
Compatibility/migration plan: additive receipt operation delegates existing ingestion validation/storage; synchronous ingest remains available for existing kernel/CLI callers. Explicit source selection reuses existing preparation and activation. Old envelopes remain readable without new metadata.
Rollback/recovery plan: retain additive-data-reading binary and synchronous path; received-but-unprocessed snapshots can use existing guarded retry. Never delete source/review evidence. Running work is fenced by bounded expiry; explicit new command resumes after expiry, old worker cannot activate.
Cutover trigger: only new HTTP receipt and successor form use receipt-only boundary; selection explicitly invoked. No production cutover in this task.
Cleanup/decommission criteria: no temporary second authority or dual-write; legacy synchronous API deliberately retained, no planned deletion in this repair.
Failure blast radius: preparation only affects one unpublished working snapshot; stale output never changes parent or serving release. Successful source receipt is independent of candidate preparation.
Adversarial proof matrix: duplicate receipt/selection/successor; different command same successor context; stale source/parent revision/policy/role; exception after receipt; expired worker and restart; concurrent DB writer and event-loop reads; middleware/installed route scopes; changed source on next request; unknown timing measurements.

Transaction boundary: immutable byte verification precedes atomic empty-document registration; selection reservation is short and durable; long preparation has no outer write lock/DB transaction; activation rechecks lease, authorization, source/revision and successor parent under short transaction. Source file storage may leave unreferenced bytes if registration fails, never a false receipt.
Audit/evidence requirement: existing immutable locator/digest, ingest command payload, attempts actor/source/revision/diagnostics and quality runs. Receipt adds file byte length; timing is derived from recorded attempts/runs and comparable source size, never an authority.
