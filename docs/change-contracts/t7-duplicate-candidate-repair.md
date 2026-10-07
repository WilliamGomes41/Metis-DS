# T7 duplicate occurrence repair

Change class: A
Promise: Exact duplicate folding selects an existing materialised candidate without transferring another occurrence's identity, spans, provenance or candidate authority.
Proof: Red-before-green tests for summary-only, primary-only and both selections in either order; source-only duplicates; binding isolation; actual ingest/approval/restart; complete repository CI.
Touches lifecycle invariants: yes
Rewrite risk: high

## Boundary and mitigation

Rewrite target: Post-materialisation exact duplicate folding in source_occurrence_authority_v1.
Why local patching is insufficient: Copying semantic evidence onto another source row creates a second creator. Remove that transfer at the shared domain operation.
Current authority/writer/reader map: knowledge_materialisation_v1 alone creates semantic identity/content/source provenance. semantic_units_from_proposal supplies selection decisions. prefer_authoritative_exact_occurrences is called by pre_review_semantic_v1 and context_aware_split_v1; it chooses rows and records alternate occurrences only. semantic_transform_generic_v1 persists the chosen spec row through OperationsConsole ingest/reprocess and existing workflow bundle transactions. apply_admission_gate, review_duty_v1, exact review binding readers, consider_publish and preserve_unchanged consume the resulting candidate. No storage, serving or publication writer changes.
Supported runtime topologies: File and PostgreSQL workflow adapters, immutable source adapters and canonical publication adapters use the same processing kernel.
Persisted-state impact: No backfill, schema change, historical object/hash/binding rewrite or release mutation.
Compatibility/migration plan: Preserve the pre-T7 span ID formula. Future formation chooses a complete already-materialised selected row, prioritising its own section only among selected rows. Unselected higher-ranking occurrences remain alternate evidence. Existing stored work is not rewritten.
Rollback/recovery plan: Revert this repair before merge if checks fail. Existing snapshot revision/source checks and atomic bundle writes remain. Rebuilding the same selected inputs produces the same chosen identity; no approval transfer to another selected span.
Cutover trigger: Human-reviewed repository change after complete CI; no deployment in this task.
Cleanup/decommission criteria: Delete semantic donor copying; retain one exact occurrence selector and its alternate evidence projection.
Failure blast radius: Working candidate folding only. Existing releases, registry and serving remain unchanged.
Adversarial proof matrix: Selected summary plus unselected primary; selected primary plus source summary; two independently selected occurrences with different IDs/maps; reversed input order; none selected; old binding on discarded candidate; actual formation, approval and restart. Also retain deterministic splitter/boom and source-only regression proof.

Lifecycle entity: WorkingRevision derived from SourceSnapshot.
Lifecycle transition: Authorized formation/reprocessing prepares a valid object bundle, then existing kernel commit persists it.
Initial durable state: Immutable source and either a new processing revision or an existing open working revision with exact bindings.
Trigger: Existing ingest/reprocess command.
Authorization: Existing researcher/processing authority and named reviewer for approval.
Validation: Existing selector/materialiser/transform/admission checks; duplicate folding cannot alter a candidate's identity or source binding.
Mutable entities: Prepared object bundle and open WorkingRevision through existing transaction.
Immutable entities: Source bytes, published releases and prior review evidence.
Workflow state before: Processing or open working revision.
Workflow state after: Existing derived review/block/readiness state; no new lifecycle state.
Release state before: Existing release or none.
Release state after: Unchanged; formation does not publish.
Serving state before: Registry-selected release or none.
Serving state after: Unchanged.
Expected API result: One intact selected candidate for repeated prose, with exact source references and alternate occurrences.
Expected UI result: Review targets that selected candidate's source; an unselected occurrence does not gain a content duty.
Failure result: Existing validation/commit failures preserve durable state and bindings.
Restart result: Persisted chosen object and exact binding are unchanged.
Recovery result: Stable ordered selected spans retain their pre-T7 identity; bindings of another occurrence cannot authorize the chosen candidate.
Legacy-data result: No automatic rewrite or inferred approval inheritance.
Required black-box scenario: Duplicate-source ingest with summary-only and both-selected proposals, assert materialiser ID/spans/fragment references, approve selected candidate, restart and compare durable objects/bindings.
Explicit non-goals: T8 admission-integrity work, T9-T12, production migration, deployment, merge, second PR.

## Separate adversarial surface review

The only production change is the shared exact occurrence operation; both callers retain it. Selecting complete rows removes cross-row semantic authority rather than adding a gate or marker. Canonical transformation, workflow revision/transaction checks, source readers and publication registry remain their existing owners. Source-only and deterministic inputs retain section priority. Boom construction is untouched. Alternate evidence cannot supply selection authority. There is no dual writer or new store.

## Red proof

Tests-only head 85abdc47d9a7b234ed21bb043476554b1d827cf0: 5 failed, 5 passed on Python 3.13 (and failing matrix on 3.12). Unit proof shows source-only promotion and cross-candidate span/mapping transfer. Actual ingest proof shows the wrong legacy span ID for summary-only selection and the wrong selected spans when both occurrences are selected. Actions: https://github.com/WilliamGomes41/Metis-DS/actions/runs/37605633099.
