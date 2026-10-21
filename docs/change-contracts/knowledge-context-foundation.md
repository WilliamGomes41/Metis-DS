# Reliable knowledge context foundation

Reference: e9141ae9f3fc0b27dc1bcf3e2319c072fd3cd505.
Change class: A
Promise: Newly processed or explicitly corrected knowledge cannot resolve necessary context on a scan flag alone; review shows the actual revision and its context.
Proof: Missing neighbor exception/condition blocks admission; real inclusion or existing source-context binding resolves it; paths remain separate; rollback/retry retains work.
Touches lifecycle invariants: yes
Rewrite risk: high

## Inspection before implementation

### Established
- `SourceSnapshot` is the envelope snapshot_id/source_id/sha256/version and verified immutable bytes. `WorkingRevision` owns the versioned JSONB object set; local files are supported compatibility storage. `workflow.documents` and `workflow.document_objects` are the PostgreSQL authority.
- A candidate is an unclassified object with proposed type, semantic spans and admission metadata, not a second aggregate. An object revision is object_id + object_version + canonical_object_hash. History is append-only on review/correction; reviews in review_events and publish_authorizations identify exact versions/hashes/types.
- Source context already exists in `source_context_review_v1`: target metadata owns confirmed_source_context, with source version, literal identities, fragments, checksum, actor, command and reason. Classification-only target changes preserve literal context; changing target text/source or source version invalidates it. Keep that established rule.
- `KnowledgeRelation` already supports applies_if, except_if, explains, supported_by, defines and supersedes. Proposed relations are separate from confirmed relations; relation evidence stores exact spans. Structural parent/child is separate.
- `admit_candidate` runs deep scan; `apply_admission_gate` is shared kernel code. `expand_merge.performed` currently deletes source_fidelity_failure. A scan's include/link disposition does not verify realization.
- Runtime ASGI and console-ingest CLI bind the same semantic dispatcher. Offline semantic-generic remains an explicit spec transformer, not workflow ingestion. V2 field evidence is opt-in and avoids legacy enrichment; source spans/mapping are revalidated in transform. Replay retains proposal and provider evidence with schema/prompt/version identity.
- Graph v1 stores shared node IDs, versioned nodes, literal labels/evidence and independent graph reviews. Structural gate checks missing branches, references, reachability, cycles and bundles. PDF geometric edges remain proposals: unresolved graph and missing graph review prevent publication. No ordered per-outcome path projection exists.
- Stateful commands use _commit_prepared_store; PostgreSQL document/review stores share workflow_transaction and snapshot row locks. Source-context commands deduplicate command/payload and CAS the objectset. Retry reserves existing processing_attempts outside model call, then rechecks source/attempt/revision under lock before atomic activation.
- Existing implicit state: governance validation_status and second_review, admission gate_result, context_scan_done, expand_merge.performed, nullable hash/date/reviewer, envelope publication_eligibility, attempt timestamps/state. These are not interchangeable evidence.
- Existing contracts: semantic-passage-v1.0.0/v1.1.0; semantic-generic-v1.0.0/v1.1.0; source-bound-fields-v2; source-context-review-v1; knowledge-relation-evidence-v1; source-decision-graph-v1; source-reprocessing-v1; versioned processing exports.

### Risk
- A proposed merge removes a real fidelity failure without modifying content or provenance (admission_gate_v1).
- First review suppresses long object bodies when they begin with the abbreviated heading and displays an exception merge without labeling it as a proposal. First/second cards diverge.
- Legacy reextract_unpublished can replace reviewed object sets and clear bindings; retry is guarded, but the direct path needs the same preservation boundary.
- Geometric graph edges can be displayed without their proposal uncertainty; no outcome path projection distinguishes alternative paths.

### Inference
- Adjacent condition/exception cues indicate possibly necessary context, not proven applicability. Conservative unresolved is appropriate until a reviewer or source-bound proposal realizes the context. This does not prove all necessary context was recognized.
- Exact literal binding is preferable to a new context lifecycle/store. Existing correction and confirmation commands are sufficient.

### Required change
- Independently check necessary context against actual selected content and validated existing links, retaining integrity failures. Version new admission evidence, without rereading/reclassifying historic records automatically.
- Reuse source-context confirmation for atomic target re-admission and existing hash/version/approval invalidation.
- Reuse one pure review projection for full passage, essential context, proposals and unresolved reasons. Background and diagnostics are collapsible.
- Add bounded ordered paths over validated graph; bundle members inherit container paths. Graph authority remains unchanged.
- New runtime semantic prose uses v2; preserve explicitly selected deterministic rollback and legacy standalone readers. Extend only v2 context proposals with source references and closed uncertainty reasons; revalidate in transformer.

### Do not change yet
- No clinical correctness model, GRADE, automatic contradiction winner, historical backfill, database replacement, new lifecycle/framework, source identity or publication registry changes.
- No automatic geometrical edge confirmation or semantic rewrite of decision trees.

## State ownership and transitions
Kernel owns existing snapshot/object history/context/reviews/attempts; OperationsConsole is the existing kernel application service despite its name. operations_console_app is presentation only. Review and path cards are stateless projections; selection/open panels are disposable UI state.

Lifecycle entity: WorkingRevision and existing versioned knowledge object.
Lifecycle transition: existing source-context confirmation/correction creates a new target revision, re-evaluates context admission and invalidates current approval bindings. Existing ingest/retry activates an entire prepared bundle.
Initial durable state: immutable source, unpublished working revision with candidate, possible unresolved context and review history.
Trigger: existing ingest/retry, source-context command or explicit source-bound repair.
Authorization: existing named reviewer/researcher guards, source-open guard and published immutability guard.
Validation: source identity/hash, selected source references, literal reconstruction, valid context links, expected objectset revision, current attempt and authority.
Mutable entities: new revisions and their metadata; existing bindings invalidated only by explicit correction; new audit/evidence and attempt result.
Immutable entities: source bytes; earlier object versions/review events; published releases/hashes.
Workflow state before: processing or in_review.
Workflow state after: unresolved stays in_review; technically sound candidate can be reviewed; no automatic approval.
Release state before: existing registry remains authoritative.
Release state after: unchanged, no release created.
Serving state before: current active serving set.
Serving state after: unchanged, publication registry remains sole authority.
Expected API result: existing receipt/command result; explicit conflict/error on stale/invalid work.
Expected UI result: full revision and essential context visible; proposal distinct; independent paths to outcome.
Failure result: old work retained; rejected proposal/integrity failure remains blocked; no partial active bundle.
Restart result: durable revisions/context/reviews unchanged, projections rebuild.
Recovery result: existing transaction rollback/replay/attempt expiry, no destructive reset.
Legacy-data result: original records/hashes/reviews untouched; old contracts readable; no startup backfill.
Required black-box scenario: ingest -> unresolved exception -> confirm context -> new revision -> restart -> review; stale/duplicate command -> retained history; published predecessor unchanged. Existing lifecycle suites verify serving closure/cutover/withdrawal.
Explicit non-goals: clinical validation, historical upgrades, new state machines, production deployment.

## Hard invariants and policy
Hard: scan flags never realize context or waive fidelity; selected text reconstructs from source; context belongs to revision; exact review hash/version remains; writes are atomic; stale results do not activate; duplicate commands preserve results/history; alternative paths remain separate/shared nodes retain identity; uncertain PDF proposals never imply confirmed edges.
Policy: lexical neighbor scan is conservative detection, not completeness proof; configured deterministic rollback remains available. Bounds are explicit failure, never truncation.

## Transactions, failure, concurrency and evidence
Model calls are outside writes. Admission/projections are pure. Source-context re-admission runs inside existing source-context snapshot transaction; revised objects, context metadata, bindings and audit commit together. Any later write failure rolls back. Invalid offsets/source/context cannot be repaired by a flag. New target revision invalidates approval; old event/revision remains.
Duplicate context commands use existing command_id/payload_hash; conflict is explicit. New work pins objects_revision; direct destructive re-extraction of reviewed/context-curated work is rejected. Retry uses existing attempt ownership/expiry/revision and atomic activation. Preserve raw proposal, schema/prompt/replay identity and derived realization evidence in existing metadata/evidence export.

## Rewrite mitigation
Rewrite target: versioned context admission and review projection in existing kernel, plus conservative reprocessing guard.
Why local patching is insufficient: removing one flag waiver alone leaves include/link without realization and cards hiding durable context.
Current authority/writer/reader map: source store -> dispatcher/spec -> transform -> admission -> object-bundle commit; review/correction/source-context commands -> same kernel/versioned store; CLI/ASGI -> dispatcher; UI/readiness/exports/MCP -> stored metadata. Graph commands/graph reviews remain their existing authority. PostgreSQL workflow+reviews, local compatibility and canonical publication/registry stay in place.
Supported runtime topologies: existing one instance/one worker local compatibility; supported PostgreSQL one/two workers with shared commit lock. No added topology.
Persisted-state impact: additive versioned admission/context-proposal metadata in existing JSONB; no SQL schema or automatic migration.
Compatibility/migration plan: readers accept legacy and new records before new writers; stored legacy admission is not recomputed by read or startup. New runtime processing uses v2; original standalone v1 readers remain.
Rollback/recovery plan: disable new processing with compatible reader; retain new context evidence and historical reviews; do not downgrade to binary that interprets scan flags as proof. Forward fix failed work; existing source/reviews preserved.
Cutover trigger: regression, transaction/retry/concurrency proofs and browser review checks; no deployment in this task.
Cleanup/decommission criteria: no temporary authority, dual write, backfill or decommission introduced.
Failure blast radius: one new/corrected unpublished candidate; published objects remain untouched.
Adversarial proof matrix: flag-only merge; inline false source; wrong offsets/source version; missing/stale link; direct reextract bypass; duplicate/CAS conflict; objectwrite then audit failure; stale/expired attempt; first/second review body; mobile overflow; alternative paths/shared nodes/bundles; unresolved geometric routes; legacy hashes.

## Slice order
1. Context realization and non-destructive retry guard.
2. Shared full review projection.
3. Ordered alternative paths and uncertainty.
4. V2 source-bound context proposals and explicit bounds.

Verification results are recorded after implementation; this inspection is not a claim of completion or clinical/semantic validity.

## Separate adversarial review pass
The final pass challenged alternate entry points, not only the happy path:
- Direct `reextract_unpublished` bypass: reject reviewed/context-curated work; retain existing retry ownership and revision checks. CLI and ASGI still enter the same dispatcher/kernel.
- Correction inheritance/storage fallback: the PostgreSQL mixin transaction owns native writes; local compatibility uses its existing store lock/rollback boundary, not the PostgreSQL-only retry helper. Recheck source, publication, current role and revision immediately before commit.
- Partial writes: an audit callback can append once and then fail; rollback now includes that first append. A deferred PostgreSQL commit failure must restore object history, review bindings and audit together; retry succeeds and a stale expected revision conflicts.
- Stale authority: forged offsets, changed source/checksum, stale context owner and stale processing attempt cannot be made valid by `performed`/`resolved`. No new authority or UI-owned lifecycle is introduced.
- Partial contract cutover: legacy v2 readers accept absent optional context evidence; new provider writes require an explicit context array. New metadata is additive. Historical records are not recomputed; published predecessor hashes and review decisions remain protected by existing lifecycle tests.
- Recovery: same context command deduplicates; conflicting reuse/stale revision fails explicitly. Explicit corrections create revisions and invalidate only current bindings, retaining previous decisions. An uncertain model context remains unresolved until an explicit correction settles its meaning; mere literal presence does not resolve semantic uncertainty.
- Read projections: first/second review share full durable content and essential context; technical diagnostics are a separate collapsed panel. Path bounds return an explicit issue, never a partial silently truncated path set; bundle members inherit each alternative separately.

No deployment, schema migration, historical re-extraction or automatic backfill is part of this change. A passing technical test does not establish completeness of context detection or semantic/clinical correctness.

## Final verification (2026-10-02)
- Full repository suite: **2576 passed**, zero failures/skips, Python 3.12 with a real PostgreSQL 17.11 instance (UTC) and Chromium headless shell 151. Five existing dependency deprecation/security-advice warnings; no test errors.
- Browser: all six first-review/second-review/two-path scenarios at 1440px and 390px pass. The second review asserts the exact first-reviewed version and full core/condition/exception. After strengthening stylesheet loading checks, the browser test passed again; desktop and mobile screenshots were visually inspected. These are isolated source/provider fixtures, not clinical validation.
- Architecture invariants: 6 passed. Repository preflight, compileall, change-contract validation and release-control mapping over all 39 changed paths: PASS. Product API generation and backward compatibility against e9141ae9: PASS.
- Full suite includes native deferred-commit rollback, duplicate commands, retry/restart, stale worker/attempt, concurrent publication/context updates, publication successor/withdrawal, legacy mapping and unchanged sibling/publication hash regressions. Packaging creates and inspects the real deployable ZIP; no deployment was performed.
- An unrelated unstaged deletion in `tests/test_console_workspace_layout.py` is excluded from this change. Both original tests from e9141ae9 were run separately and passed, including their original assertions.
- Reproduction: install repository development requirements, supply `METIS_TEST_POSTGRES_DSN` for an isolated PostgreSQL database, `METIS_BROWSER_EXECUTABLE` for Chromium headless shell, and `METIS_PLAYWRIGHT_MODULE` for Node Playwright, then run `python -m pytest -q`. Browser fixtures start their own ephemeral server and do not alter product dependencies. The GitHub matrix additionally covers Python 3.13/PostgreSQL 16.

Contract changes: additive `source-context-admission-v2` and `source-bound-context-v1`; processing evidence CSV v5 and projector/MCP v4. No SQL migration, identifier/publication-hash change or historical backfill. Reader compatibility precedes new writes. Existing uncertainty remains explicit; source proof establishes realized identified context, not detection completeness or semantic correctness.
