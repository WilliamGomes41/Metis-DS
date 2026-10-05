# Source accountability recovery — #513

Change class: A
Promise: New semantic processing forms document-wide source-bound knowledge candidates and keeps unformed source accountability outside clinical candidate review, without losing source content or weakening publication closure.
Proof: Metadata versus missed-condition regression; exact source classification validation; broad supplement selection; persisted/restarted source disposition and successor safety; API exclusion and existing lifecycle tests.
Touches lifecycle invariants: yes
Rewrite risk: high

## Authorized scope
William explicitly assigned the attached Metis recovery implementation on 2026-10-04. Baseline main: 6848c75b25b96d4ad0ce7c29b60f208ad0dd21b3. Smetten evidence: 21 selected recommendations (17 allowed/4 blocked), 637 unselected spans, 35 headings. This is not a completeness reference.

## Decisions before implementation
Keep the existing versioned object storage and passage register as authority; source-accountability records are NOT candidate knowledge. Preserve their exact locations and technical storage compatibility. Mark source-only records explicitly, use technical rather than clinical tracking, and enforce routing in the backend. Semantic classification of metadata/structure is a proposal, never automatic human approval or substantive exclusion. Unresolved content blocks closure. A reviewer may explicitly confirm an exact batch of non-knowledge source records with a reason; retain per-record versioned evidence. Existing single-record context/disposition remains usable.
Restore all five existing semantic types in V3. Supplement unselected source ranges across the document, not only recommendation sections. Keep literal field/context admission and no silent fallback.
V2 remains the protocol/default. V3 remains explicitly configured. Correct the stale roadmap rather than changing the protocol to bless V3 as default.
No startup backfill. Existing documents recover through explicit successor work; no transfer of approvals to changed objects.

Rewrite target: Source-accountability/candidate boundary in the existing semantic preparation, passage register and review projection.
Why local patching is insufficient: A screen filter leaves incorrect durable classification and a recommendation-only producer; deleting remainders loses unresolved source content.
Current authority/writer/reader map: Immutable source store -> pre_review_semantic_v1/semantic_passage_v1 -> semantic_transform_generic_v1 -> admission_gate_v1 -> passage_register_v1 -> OperationsConsole ingest/reextract -> _commit_prepared_store/workflow_transaction. Review writers use source_context_review_v1 and existing review/correction commands. Readiness uses source_passage_closure/definitive_review_disposition; review UI is a projection. Retrieval projection and Product API only consume approved published types. console_asgi composes durable/authoritative mixins. decision_successor_v1 preserves prior work using explicit successor ingest. Replay identity includes prompt/schema/contract.
Supported runtime topologies: Local compatibility store (one worker); PostgreSQL workflow/canonical authority with Azure source store (one or supported two workers on one instance). No topology change.
Persisted-state impact: Additive exact source-accountability metadata in existing versioned records; no SQL schema or new authority. Explicit human batch dispositions append revisions and audit, invalidate affected review bindings, never approve knowledge.
Compatibility/migration plan: Legacy records remain readable and open under their existing contract. No historical reinterpretation. New preparation stamps the new contract; use existing successor command for reviewed/published work. Preserve old snapshot, source hash, review history and published release.
Rollback/recovery plan: Keep old records and existing mode configuration. Roll back new formation for future work using a compatible reader. Failed preparation leaves previous work; failed disposition commit restores from authoritative store. No destructive downgrade.
Cutover trigger: New authorized ingest/successor under the updated prompt/schema; production rollout remains blocked on frozen-source human validation.
Cleanup/decommission criteria: No removal of legacy readers in this change. Only a later separately proven change may remove them.
Failure blast radius: One new working revision or explicitly selected source-disposition batch; never active releases or API entitlement.
Adversarial proof matrix: Invalid/overlapping/out-of-bounds classifications; omitted meaningful text; stale evidence after correction; forged source flags; replay contract mismatch; duplicate/concurrent source commands; failed commit/restart; published mutation; legacy and tree route; unpublished/non-entitled API reads.

Lifecycle entity: WorkingRevision and its exact source-accountability records.
Lifecycle transition: Authorized source preparation creates open candidates/source work; explicit reviewer disposition closes only selected non-knowledge source work.
Initial durable state: Existing source snapshot with no new result, or an open working revision with unresolved source records; historical published release may coexist.
Trigger: Existing ingest/successor command; explicit source-disposition confirmation.
Authorization: Existing researcher/reviewer ingest/successor rules; named reviewer for source disposition; never model authority.
Validation: Exact source spans and source hash, existing admission, current revision precondition, immutable published guard, explicit reason and selected records.
Mutable entities: New working revision and versioned non-published source records, associated invalidated bindings, audit.
Immutable entities: Frozen source bytes/hash; prior reviewed revisions/history; all published releases and active registry.
Workflow state before: processing or in_review.
Workflow state after: in_review while any substantive disposition or candidate review is open; readiness only through existing complete gates.
Release state before: Absent or existing published/superseded/withdrawn history.
Release state after: Unchanged; no publication command in this scope.
Serving state before: Existing registry active/inactive set.
Serving state after: Identical to before.
Expected API result: No new unpublished records; existing approved published knowledge and entitlement/context checks unchanged.
Expected UI result: Formed candidates in knowledge review; source-only uncertainty and proposed metadata in explicit source accountability, with proportional nonclinical batch handling.
Failure result: No partial activation or partial batch disposition; old work retained and failure explicit.
Restart result: Durable committed source dispositions and unchanged serving set reconstruct identically.
Recovery result: Existing recovery completes technical work only, never invents approval or source exclusion.
Legacy-data result: No auto-backfill, deletion, reopened published review or migrated approval.
Required black-box scenario: Ingest exact source with metadata, a definition and an unselected condition; verify candidate/source separation and blocked closure; explicitly dispose metadata, retain condition blocking; restart; create successor while old reviewed/published work remains unchanged; fail a commit and prove rollback.
Explicit non-goals: Gateway timeout/background jobs, new knowledge types, deployment/publication, free-prose API generation, broad console rewrite.

## Acceptance limitation
The immutable original PDF and a human-validated frozen reference set are not yet present in the supplied attachments. Processing exports reconstruct evidence but do not prove original-byte extraction fidelity or clinical recall. Deliver code and executed proofs reviewably; do not claim complete extraction, production readiness, or task acceptance without that gate.


## Operator procedure

1. Keep the current source snapshot and active release unchanged. Do not delete the 637 historical remainder records or reclassify them in place.
2. For reviewed or published work, use the existing explicit decision-successor command with its required review-policy revision and authorization. Re-extraction is only permissible where the existing unpublished/no-review guard allows it.
3. Inspect formed candidates and source accountability separately. Metadata/structure roles are model proposals; a named reviewer must inspect source evidence and explicitly confirm selected exclusions with a reason. Unformed substantive text stays open and blocks source closure.
4. Apply existing candidate admission, context resolution, named review, publication and entitlement gates. No command in this change publishes a release.
5. Before production rollout, obtain original source bytes, verify their hash, and freeze a human-validated reference covering all five existing types, conditions, exceptions, context and genuine non-knowledge. The committed Smetten reference draft is evidence to review, not an acceptance oracle.

## Verification boundaries

The new model-double regression proves deterministic routing, source preservation, explicit batch decisions, revision conflicts, rollback, restart and API exclusion. It does not measure live-model recall or clinical completeness. A PostgreSQL-native test covers deferred commit failure and stale workers in the existing CI service. Existing lifecycle/successor tests remain authoritative for release preservation.

The gateway timeout remains a separate, unresolved incident. No request-lifetime or background-job change is included. Do not describe this recovery as a timeout fix.

## Frozen Smetten source check (2026-10-05)

The supplied 46-page original PDF hashes to `62dfd76e0683a372d54b6d7aea8b09b47b2b71022e60ff034d76223919bec47c`, exactly the investigated source hash. `scripts/verify_smetten_frozen_source.py` reproduces 1,014 fragment IDs and hashes against the processing export and locates all 30 anchors in `docs/acceptance/smetten_reference_draft_pdf_v1.json` on their declared PDF pages. Four literal CSV text columns have a prefixed spreadsheet-escape apostrophe; the underlying fragment hashes still match. The PDF itself is not committed.

An initial controlled V2 probe over the full PDF found a previously missed failure: duplicate exact source text could carry a source-only record whose binding span no longer matched the chosen authoritative occurrence. `source_occurrence_authority_v1` now keeps the principal source-only span and role together and drops the source-only marker if a selected duplicate supplies candidate semantics. A focused regression proves the duplicate case. Repeating controlled V2 and V3 PDF probes produced one admitted definition, two proposed metadata records and 642 unresolved source records from 1,014 exact source fragments; the table label stayed open. These are model-double routing proofs, **not** live-model Smetten recall or production outcome counts.

The 30-anchor reference is a draft indexed partly from the earlier candidate export. It covers the five supported types and source-only examples, but it is neither independent nor exhaustive; its 19-recommendation count is a hypothesis from visual review of the numbered recommendation sections and Table 1. A named clinical reviewer must validate and extend the complete reference before any clinical completeness or rollout claim. No provider key or model is configured in this workspace, so no live semantic rerun was executed.
