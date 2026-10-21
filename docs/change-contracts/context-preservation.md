# Explicit preparation context and retained extraction

Change class: A
Promise: Authorized source processing retains a verified extraction before model work, and restart/resume and readers reuse that extraction without changing existing candidate, review or serving authority.
Proof: Real HTML extraction counted across installed HTTP selection, interrupted provider, restart and resume; corrupt/stale records and concurrent revision changes fail closed; native PostgreSQL rollback/restart uses the same boundary.
Touches lifecycle invariants: yes
Rewrite risk: high

User assignment: implement the context-preservation proposal in this conversation, 2026-10-09, starting at main 77c028b16618f3441d4955b1edc6a0c1e5026ba3.

Lifecycle entity: existing SourceSnapshot/WorkingRevision and processing_attempts.
Lifecycle transition: existing authorized attempt prepares and checkpoints extraction, then prepares candidates and activates through the existing fence. No new lifecycle state.
Initial durable state: received or resumable unpublished source and existing authorized attempt.
Trigger: existing Starten/Hervatten or synchronous kernel ingest/retry/resume.
Authorization: existing source-selection authority; repeat at extraction checkpoint and final activation.
Validation: exact snapshot/source/document/hash/version, extractor contract, record integrity, expected object revision, active actor-bound attempt, deadline and configuration.
Mutable entities: additive prepared_source_extraction on the existing workflow envelope; existing attempts/diagnostics and guarded candidate bundle.
Immutable entities: source bytes, prior object/review versions and published releases.
Workflow state before: existing processing/in_review/blocked projection.
Workflow state after: existing readiness projection; extraction checkpoint alone never makes review/publication ready.
Release state before: existing registry/release state.
Release state after: unchanged; no release writer.
Serving state before: existing publication registry.
Serving state after: unchanged; no serving writer.
Expected API result: existing receipt, redirect or explicit conflict/integrity error.
Expected UI result: existing processing and resume screens; no new UI state.
Failure result: provider failure retains extraction but cannot overwrite candidates; checkpoint failure yields no retained result; corruption is explicit, never an extraction fallback.
Restart result: retained extraction is loaded from workflow storage, not process memory or disposable files.
Recovery result: compatible resume uses retained extraction and existing open-range checkpoint. Uncertain claimed work keeps existing expiry/explicit recovery rules. Explicit re-extraction remains fresh.
Legacy-data result: no backfill. Existing Docling accepted records remain usable through their existing validator; native legacy sources without the new complete record retain their extraction route. Published payloads/hashes unchanged.
Required black-box scenario: receive -> start -> real extraction -> provider failure -> restart -> explicit retry/resume with extractor forbidden -> existing activation; partial resume preserves completed objects; corrupt record and concurrent revision reject without writes.
Explicit non-goals: cross-snapshot reuse, new job authority, changing retries/deadlines, object/review/publication decisions, automatic historical promotion, deployment or paid providers. Dedicated boom/decision-PDF construction stays on its existing path.

Rewrite target: shared preparation handoff and derived extraction reuse, additive to existing workflow storage.
Why local patching is insufficient: passing retained_fragments only in one resume caller leaves receipt/retry/readers and failed-before-formation restart inconsistent.
Current authority/writer/reader map: immutable store/_verified_source_bytes owns bytes; OperationsConsole.ingest/reextract_unpublished and installed SourceProcessingStrategy produce fragments; new shared preparation boundary checkpoints derived extraction through _reprocessing_transaction/_commit_prepared_store. SourceSelection reserve/claim/assert_active/finish remain sole attempt authority; pre_review_semantic consumes fragments/replay; _read_source_fragments/review_source_fragments feed review/readiness/repair/class conversion; quality_processing_runs remains non-authoritative measurement. PostgreSQL document/review/identity/remaining mixins keep their transaction ownership. HTTP source selection and synchronous APIs enter the same kernel preparation; publication registry/canonical stores unchanged.
Supported runtime topologies: file single worker compatibility; existing PostgreSQL one-instance one/two-process deployment.
Persisted-state impact: additive versioned derived record in existing envelope JSONB; no tables, SQL migration, new command identity or authority. Full extraction is untruncated and independently validated.
Compatibility/migration plan: additive readers/writers; old Docling contract unchanged. Historical records are read-only and never promoted from partial evidence. Same-snapshot identity only.
Rollback/recovery plan: code rollback can ignore additive record and use previous extraction path; source/review/history remain unchanged. No deletion/reset/backfill. A crash before checkpoint commit may repeat extraction; after commit it must reuse compatible extraction.
Cutover trigger: original red-capable restart proof, relevant regressions, native PostgreSQL and boundary/preflight checks pass before merge.
Cleanup/decommission criteria: replace duplicate production formation_context literals with one typed builder; no temporary queue/dual authority. Keep intentionally separate legacy decision-tree and standalone transformer paths.
Failure blast radius: one unpublished processing attempt; extraction metadata cannot approve candidates or alter serving.
Adversarial proof matrix: changed source hash/document identity/extractor contract; forged fragment/record hash; changed revision/role/config/expired attempt while extracting; provider failure after checkpoint; failed commit rollback; pending/claimed restart; duplicate start; independent writer during extraction; historical Docling/native reads; explicit fresh re-extraction; published predecessor preserved by existing lifecycle regressions.

## Handoff rules

The typed SourceIdentity and FormationContext builder pins the producing source, actor, expected revision, attempt and original deadline. Optional replay is required by resume; no missing-source default disables replay on kernel calls. A prepared extraction contains complete fragments and the producing extractor contract; semantic decisions and approval are never cached. Readers validate the retained record against its stored contract and source identity; processing additionally checks current extractor compatibility. Reconstructed block reuse stays calculation-local, with current validation/authorization repeated.

GIVEN one immutable source with an authorized attempt, WHEN preparation records extraction and a later dependency fails, THEN the extraction survives restart, the old object set/review/serving remain unchanged, and explicit compatible recovery can prepare without extracting again.
