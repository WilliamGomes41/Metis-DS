Change class: A
Promise: Every new review-relevant knowledge revision has an exact durable predecessor and fresh exact-current review authority, while legacy and published history stays unchanged.
Proof: Tests-first behavioral regressions on main, A–AC adversarial matrix, PostgreSQL/file concurrency and restart, T4–T10/boom parity, full GitHub CI and separate adversarial audit.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Divergent object revision writers and current-object readers.
Why local patching is insufficient: Type, semantics, relations, context and repair can independently bump versions or rewrite canonical fields without predecessor evidence.
Current authority/writer/reader map: revision_workflow.create_revision is the existing constructor. OperationsConsole writers: confirm_object_type, confirm_relations/_prepare_relation_confirmation (including peer parent updates), review_object, correct_object, accept_source_continuation, reextract_unpublished/resume, promote_class. source_context_review_v1 changes target context (source dispositions stay source-domain). ClosedLoopReviewConsole restores/clears review metadata, reopens review and resolves support. DeterministicRepairReviewConsole finalizes provenance and merges/repairs. review_workflow_v3 and second_review_workflow_v3 prepare governance only; raw review APIs cannot authorize. admission_gate/semantic_transform/materialisation prepare initial candidates and source validity; they are not revision authorities. File _save_objects/_commit_prepared_store, PostgreSQL runtime write_bundle and concurrent override own writes; workflow_transaction owns atomic object/bindings/audit commit. Current readers: OperationsConsole snapshot_objects/snapshot_objects_and_revision, PostgreSQL runtime snapshot/current batch, downstream review duties, T10 containers, readiness, MCP and exports. Canonical publication and registry remain unchanged.
Supported runtime topologies: File compatibility console; PostgreSQL workflow object/review stores with shared transactions; existing canonical/Azure composition, with no Azure access.
Persisted-state impact: Additive metadata revision evidence on new knowledge revisions only, using existing JSON payload. Existing provenance predecessor/reason/patch fields remain. No historical rewrite, backfill or new database schema.
Compatibility/migration plan: Owner-approved forward-only cutover. Missing historical predecessor means unverified, never a proven root. New strict revision may reference the exact stored legacy-current predecessor. Persist contract marker plus exact predecessor evidence in existing metadata (additionalProperties=true). Expand kernel, route writers, validate at existing locked storage boundaries. No parallel store.
Rollback/recovery plan: Revert new writer/reader integration before deployment. Existing JSON metadata remains readable; never remove or rewrite strict evidence or historical hashes. Restart derives lineage solely from stored evidence; invalid strict evidence fails closed. Published legacy releases remain unaffected.
Cutover trigger: New strict object revisions explicitly carrying the persisted contract; never commit time or software version. Deployment is outside this task.
Cleanup/decommission criteria: Remove duplicated knowledge revision construction after relevant paths use revision_workflow. Retain source/structure/boom contracts and legacy read compatibility.
Failure blast radius: Incorrect current selection, lost historical evidence or invalid review inheritance; exact bindings, published immutability and atomic rollback remain independent gates.
Adversarial proof matrix: Original assigned T11 A–AC plus legacy-to-strict transition, missing/forged marker or predecessor, unchanged legacy published read, source/WorkingRevision mismatch and immutable predecessor after restart.
Lifecycle entity: Knowledge object revision within one existing WorkingRevision.
Lifecycle transition: Exact current predecessor -> new version/hash with explicit lineage and fresh review state.
Initial durable state: Open WorkingRevision, exact stored current object, historical rows and optional current approvals.
Trigger: Authorized correction, review semantic change, context/relations change, deterministic repair or same-source preparation mutation.
Authorization: Existing actor roles, named-reviewer, original-source and review-route checks.
Validation: Existing T7–T10 gates, predecessor exact identity/hash and source/WorkingRevision scope, canonical meaning, stale command and published guard.
Mutable entities: New object row/current governance, exact-current authorizations and existing atomic audit/envelope revisions.
Immutable entities: Predecessor canonical content/provenance/hash, historical review evidence, source bytes and all published history.
Workflow state before: Open processing/in_review/blocked/ready state as permitted by existing command.
Workflow state after: Changed revision requires fresh review; a review-induced mutation binds that command only to its resulting tuple. No predecessor approval contributes.
Release state before: Existing none/published/superseded/withdrawn.
Release state after: Unchanged; closed published work rejects mutation.
Serving state before: Existing publication registry serving set.
Serving state after: Unchanged.
Expected API result: Explicit current revision and exact approvals, or atomic conflict/fail-closed.
Expected UI result: Existing review cards reflect new review obligations; no invented user-facing framework.
Failure result: No partial successor, approval invalidation or revision audit on failed commit.
Restart result: Same current revision, predecessor evidence and exact review authority.
Recovery result: Existing technical rollback/replay only; no invented predecessor or inherited review.
Legacy-data result: All existing rows/hashes/reviews/releases unchanged. Unproven history remains unverified. New successor proves only its exact edge to the stored legacy predecessor. Legacy uncertainty never reopens immutable publications.
Required black-box scenario: GIVEN approved legacy/current K, WHEN an authorized change commits, THEN predecessor remains exact, successor has a durable verified edge and no inherited approval, stale retry fails, and restart returns identical lineage and review state with unchanged serving.
Explicit non-goals: T7/T8/T9/T10 redesign; T12 total readiness; cross-source identity/fuzzy matching; source/structure/boom revision redesign; schema migrations, historical backfill, Azure, deployment, ZIP or merge.

Assigned by the repository owner to this coding session, including explicit forward-only legacy cutover authorization on 2026-10-07. Work only through GitHub, branch t11-knowledge-revision-lineage, one draft PR, no merge.
Baseline and T10 merge: 97b87a34268a6e0121a5b09285c0bc8c9528fba6.
Migration: provisionally NOT REQUIRED. Stop before a new PostgreSQL column/index/table or historical backfill.
