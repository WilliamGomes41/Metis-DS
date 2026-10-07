# T10 AccountForSource

Change class: A
Promise: One read-only source-domain projection decides source role, closure and human action for the current WorkingRevision; readers consume it without changing T9 content duties.
Proof: Baseline behavioral regressions, source/context adversarial matrix, exact-binding target closure, local/PostgreSQL command/restart tests, unchanged T9 and boom suites, complete GitHub CI and separate audit.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Duplicated source closure and follow-up decisions in source_containers_v1, publication_readiness_v1 and review inventory.
Why local patching is insufficient: Independent closure/task decisions can disagree and governance approval alone currently closes context.
Current authority/writer/reader map: Existing revision bundle owns source_accountability v1/v2, passage_register, source_role_review, confirmed_source_context, governance and object revisions; review bindings/ledger own review evidence. Preparation: semantic_passage_v1 -> semantic_transform_generic_v1 -> admission_gate_v1 -> passage_register_v1 -> OperationsConsole ingest/reextract/resume. Human writers: source_context_review_v1.confirm_source_context/confirm_source_exclusions and existing review/correction commands -> _commit_prepared_store and workflow_transaction. Readers: source_containers_v1.source_usage/partition; publication_readiness_v1.source_passage_closure/review_followup_queues/publication_readiness; OperationsConsole.snapshot_containers/waiting_task_counts; review_workboard_v1.review_work_item; operations_console_app._review_inventory/_render_review_index; processing_evidence_export_v1; diagnostic scripts. PostgreSQL _PostgresBadgeCountsMixin loads current objects/bindings and calls review_work_item, including navigation. context_issues also feeds admission/cockpit/publish integrity checks, which remain integrity validators rather than alternate source closure. knowledge_path/admission/review_duty/retrieval use is_source_record to exclude knowledge authority. quality_metrics/processing_diagnostics/recoverable_formation consume disposition for their separate metrics/preparation contracts.
Supported runtime topologies: Existing file-backed compatibility console; PostgreSQL workflow document/review stores; durable canonical PostgreSQL with Azure immutable sources through existing console composition. No runtime topology change.
Persisted-state impact: None from projection. Existing commands continue appending object revisions, invalidating affected bindings and committing audit atomically. No new fields persisted, migration, schema or backfill.
Compatibility/migration plan: Expand existing source_containers_v1 with the authority and behavioral tests; route existing helpers to it as compatibility wrappers; move consumers together in this unmerged branch. No dual writer or runtime flag. Preserve helper result shapes where feasible. Legacy v1 retains human disposition policy. Target closure now requires T9 exact-current evidence; old governance-only test assumptions must be corrected explicitly.
Rollback/recovery plan: Before deployment this is an isolated branch. Revert reader delegation/projection commits together to restore the old read policy without rewriting any stored evidence. No destructive contract removal or persisted cutover. Restart derives the same result from the existing durable bundle.
Cutover trigger: Future reviewed merge and separately authorized deployment; neither is authorized by this task. Within branch all source readers delegate to one authority.
Cleanup/decommission criteria: Delete duplicate decision branches once compatibility wrappers and reader parity tests pass. Preserve public wrappers; no historical cleanup.
Failure blast radius: Incorrect source task routing or premature/blocked source closure. Publication/serving commands and T9 authority remain independently enforced and unchanged.
Adversarial proof matrix: A-Y from assigned T10 prompt: candidate/structure/metadata/navigation; unresolved; context pending/current approvals/terminal target/stale binding; explicit context/support/exclusion; malformed evidence; legacy; reset/history; idempotency/conflict/atomicity; queues/UI/readiness parity; T9/boom parity; durable restart.
Lifecycle entity: Current WorkingRevision source accountability, derived from existing evidence.
Lifecycle transition: Read-only re-derivation after existing source or target commands; no new persistent lifecycle transition.
Initial durable state: Current revision bundle with valid/invalid source records, optional explicit dispositions, targets and existing exact bindings.
Trigger: Authorized read following existing ingest, source disposition/reset, target review or correction.
Authorization: Existing named-reviewer/read authorization and existing source command role/revision checks; no new privilege.
Validation: Source record binding/text/spans; explicit context_issues; target current provenance and exact review bindings; deterministic metadata rules.
Mutable entities: None during projection; existing source command transaction retains its current mutable object revisions/bindings/audit scope.
Immutable entities: Source bytes, historical object revisions/review ledger, published releases and canonical history.
Workflow state before: Existing processing/in_review/blocked/ready/closed state; projection stores no state.
Workflow state after: Derived source closure/action reflects current evidence; total workflow semantics remain existing readiness composition.
Release state before: Existing none/published/superseded/withdrawn.
Release state after: Unchanged by T10 reads and source commands.
Serving state before: Existing publication registry active/inactive set.
Serving state after: Unchanged; no source record is eligible for knowledge serving.
Expected API result: Containers/readiness/queues share source role/closure/action; no content approval or publication is created.
Expected UI result: Only unresolved valid source opens disposition; invalid evidence opens repair; valid context waiting on target opens no duplicate disposition.
Failure result: Invalid/stale evidence fails closed to repair; rejected/revise/superseded targets cannot retain context closure; stale source commands fail atomically.
Restart result: Identical projection from identical durable evidence; no cache or in-memory status authority.
Recovery result: Existing reset/recovery retains history and causes re-derivation; no new decisions during recovery.
Legacy-data result: v1 source records retain existing human disposition policy; no automatic metadata/context reinterpretation.
Required black-box scenario: GIVEN current source and target evidence, WHEN context is confirmed and target review completes, THEN source closure reflects exact target approvals, correction invalidates closure, stale commands write nothing, and restart preserves evidence and projection with unchanged serving.
Explicit non-goals: T8 materialisation/Admission redesign; T9 review changes; T11 revisions; T12 total publication readiness; boom redesign; migrations/schema/new stores; Azure/deployment/ZIP/merge.


## Baseline proof and staged implementation
Baseline main and T9 merge: 548d9ff46bbc5b1da1e911e620b6874fc7b47299 (GitHub compare identical).
Tests-only commit: e0831726fd3ecd3d1e333db0a87dc69eb722431b.
GitHub run 37665767011, Python 3.13: 5 failed, 3102 passed, 14 skipped. All five behavioral failures are T10 regressions on existing APIs:
- corrupted source binding, spans or text (three cases): repair queue omitted source;
- governance-only approved target: context incorrectly accounted;
- invalid human source role: repair queue omitted source.
Two GREEN GUARD tests: pending valid context produces no duplicate source task; source records never create content ReviewDuty.
The initial release-control metadata marker formatting also failed; corrected to individual marker lines. That process failure is not counted as behavioral RED.

Authority: source_containers_v1.source_accountability, with source_closure summary. source_usage/partition and source_passage_closure/review_followup_queues remain compatibility readers. Workboard and inventory reuse the call-local projection. Detail UI, snapshot containers, readiness and evidence export receive current source/binding inputs.
Schema: no SQL or persisted domain schema changes. Read-only export schema v12 adds source role/closure/human_action columns.

## Legacy clarification
V1 source metadata/navigation is never automatically reinterpreted. Existing explicit exclusions/support dispositions retain their meaning. A human-confirmed label/context link, in either version, follows its current target: pending approval waits; exact approval closes; retired target reopens; corrupt link requires repair. This is the requested current-context invariant, not a historical evidence rewrite.

## Adversarial audit
Independent read-only audit of c748e045 identified export input mismatch, insufficient machine-context validation and an admission-binding mismatch that hid repair work. Follow-up audit of 674cbc38 confirmed these fixes and identified detail UI incomplete inputs and repair precedence in inventory; both are corrected in the follow-up. Malformed source provenance is caught as repair. No source writer, transaction, admission or T9 authority code changed.

## Proof scope
Existing source command tests cover local and native PostgreSQL commit failure, stale second worker, idempotency, conflicting command IDs, published immutability and restart. T10 tests add projection, reader, export and UI parity, exact bindings, malformed context and metadata, legacy role links, reset/history and unchanged ReviewDuties over identical objects.
The existing complete T9/T8/T5-T7, decision-tree, lifecycle and PostgreSQL suites remain required gates. Final CI result and audit closure are recorded in the draft PR after verification.

## T11 and T12
T11 durable KnowledgeUnit revisions/supersession are not implemented. T12 overall publication-readiness design is not implemented. Existing candidate review closure and technical publication gates remain separate from T10 source usage. No deployment or merge is authorized.

T10: NOT DONE (final verification pending)
Merge T10 PR: NO-GO
