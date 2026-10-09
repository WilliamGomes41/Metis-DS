# Azure-owned source processing and explicit strategy

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


## Follow-up contract — explicitly assigned GitHub-only implementation

Statefulness: stateful receipt/selection/reservation/claim/activation/recovery; stateless source/readiness projections. OperationsConsole is the Azure backend kernel despite its name; HTTP modules are the edge.
State owner: immutable Azure source store, PostgreSQL workflow document/review/identity/remaining stores, canonical store and publication registry. Azure startup requires all existing workflow authorities; ephemeral filesystem mirrors never become fallback truth.
Domain entity/aggregate: existing SourceSnapshot/WorkingRevision and processing_attempts. No second queue/status store.
Invariant(s): receipt does not form; each explicit attempt executes at most once before its bounded expiry; no model in source catalog readers; no stale activation; no loss of source/review/checkpoints; serving authority unchanged.
Durable state before: registered received source or compatible unfinished formation.
Durable state after: explicit attempt with durable pending dispatch -> atomically claimed attempt -> existing succeeded/failed/interrupted activation result. Receipt alone has no dispatch marker.
Transaction boundary: source storage precedes document registration; register attempt and pending dispatch in one existing document transaction; claim in a short PostgreSQL row transaction; prepare outside locks; existing guarded activation transaction.
Failure/recovery result: pending dispatch survives failure before wake and is discovered on kernel startup/poll. Claimed work is never blindly replayed; expired claims become interrupted, and a separately authorized new resume command uses existing limits/checkpoints. This avoids duplicate calls after ambiguous provider completion.
Duplicate execution / idempotency result: command payload/source/revision/actor equality required; same command returns the same attempt; only one worker can claim it. Existing successor semantic duplicate fence remains.
Concurrency result: two process-independent PostgreSQL kernels compete for one claim; only one prepares; stale lease/revision/policy/configuration cannot activate.
Audit/evidence requirement: additive dispatch contract/token/claim timestamp and per-attempt processing configuration, alongside existing source/revision/actor/diagnostic/checkpoint history. No secrets stored.
Rewrite target: remove production reliance on local workflow fallback, UI-owned dispatch and runtime method replacement/suppression for source readers.
Why local patching is insufficient: awaiting a thread does not split receipt; memory dispatch loses work before wake; replacing a method changes read semantics invisibly.
Current authority/writer/reader map: existing availability map above plus console_asgi production composition; source_selection reserve and HTTP trigger; kernel dispatcher claim/reconcile; pre_review_semantic binding; deterministic_review_repair.source_fragment_catalog; workflow documents cutover and SQL row transaction; legacy synchronous ingest/retry/resume/reextract/class-promotion and versioned semantic readers.
Supported runtime topologies: existing bounded one/two workers on one Azure instance backed by full PostgreSQL workflow + Azure immutable source; synthetic GitHub Actions compatibility fixtures. Do not widen multi-instance topology.
Persisted-state impact: additive dispatch and configuration fields inside existing attempt envelope_payload, no new table or production migration. Old attempts without dispatch marker are not silently executed.
Compatibility/migration plan: expand with explicit configured strategy, retain synchronous kernel APIs and historical readers, change production composition to fail closed on missing workflow authorities. Synthetic file-backed fixture compatibility remains non-production.
Rollback/recovery plan: older binary still reads additive attempts; no automatic execution of legacy attempts. Before any deployment check flags/schema and bound pending/claimed work; no production cutover in this task.
Cutover trigger: explicit separately approved deployment after native PostgreSQL, browser and lifecycle evidence. New source-selection commands use dispatch marker; registration remains independent.
Cleanup/decommission criteria: no _fragments_and_spec/source_fragment_catalog monkey replacement or semantic_suppressed reader flag in production binding; raw extraction remains an explicit deterministic kernel read boundary.
Failure blast radius: one unpublished working revision; registration/claim failures do not mutate parent/review/release; configuration mismatch fails rather than changing processing strategy.
Adversarial proof matrix: crash after reservation before wake; competing kernels; stale config/revision/lease; no auto-start on receipt; no LLM on catalog; no production file fallback; native restart and route/browser checks.
Required black-box scenario: synthetic received source -> close client -> kernel restart discovers unclaimed authorized attempt -> concurrent duplicate worker cannot prepare -> candidates -> human review -> publication/restart; published predecessor remains active during successor formation.
Authorization: direct user instruction to execute the full prompt, restricted to GitHub/GitHub Actions. No deployment, merge, paid providers, production data or destructive migration.
Verification state: native/browser/complete HTTP lifecycle PROVEN on cf549a945d03eb74b18d336d413253b167091cb1 in GitHub Actions run 37919109973: 67 targeted checks and one real browser check executed without skips. Source phases, PostgreSQL recovery/claim/fencing and human-review HTTP commands are included. Broad CI/PDF gates are independently recorded in PR #578 and docs/availability-azure-followup.md. Existing local evidence is historical. No merge, deployment or production verification.
