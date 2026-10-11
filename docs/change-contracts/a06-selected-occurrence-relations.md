Change class: A
Promise: Independently selected occurrences with distinct spans retain their materialised IDs and exact incoming/outgoing relation endpoints through V3 ingest, commit and restart.
Proof: Red-before-green V3 ingest regression, reversed proposal order/section ranks, evidence isolation, replay/retry/resume compatibility, invalid endpoints, failed preparation/commit; file and native PostgreSQL workflow evidence and repository checks.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit assignment: User assigned A06 repair on 2026-10-11 to the Metis Engineer profile. This is the sole implementation ticket; #556 is progress/production acceptance only. Scope: implementation and reviewable PR; no merge/deployment.

Rewrite target: source_occurrence_authority_v1 shared post-materialisation selector.
Why local patching is insufficient: Merely linking relations earlier leaves later deletion possible. Extend the existing selector locally; explicitly reopen T7's one-candidate rule for independent selected spans, retain binding isolation.
Current authority/writer/reader map: knowledge_materialisation_v1 alone creates semantic IDs/spans/mapping; semantic_passage_v1 validates selections and attaches exact relations. pre_review_semantic_v1 and context_aware_split_v1 call the selector. semantic_transform_generic_v1 and admission consume intact rows. OperationsConsole ingest/reextract/retry/resume and source_selection own authorized preparation/activation; source_preparation_context pins source/attempt/revision. Existing workflow_transaction/_commit_prepared_store/PostgresConcurrentWorkflowDocumentStore commit bundle. Review bindings/readiness/publication readers consume existing stored objects; publication registry remains serving authority. Runtime bindings in ASGI/CLI share the kernel. Replay identity/exact_replay_lookup controls reuse.
Supported runtime topologies: File workflow and native PostgreSQL workflow documents/reviews/identity, existing immutable source and canonical/publication adapters. Synthetic provider; no live-provider or Azure-production acceptance claimed.
Persisted-state impact: Future open WorkingRevision bundles can contain several selected identical texts. No ID formula/schema/backfill/release rewrite.
Compatibility/migration plan: Tests-only red stage then local selector extension; version the occurrence rule in semantic replay identity. Old checkpoints cannot silently replay/resume under the new rule. Existing stored objects remain readable and unchanged; new authorized work uses the current contract. No dual authority.
Rollback/recovery plan: Revert code before deployment if proof fails. After cutover retain complete stored bundles/reviews; do not run an older producer on new work without compatibility proof. Suspend new formation and use current reader or forward repair. Existing authorized open-revision/successor route only.
Cutover trigger: Separately reviewed merge and authorized deployment, neither part of this run.
Cleanup/decommission criteria: One selector, one materialiser and one workflow authority remain; remove temporary probes. Source-only/deterministic folding remains.
Failure blast radius: Newly prepared working candidate set; existing source/review/publication controls remain.
Adversarial proof matrix: outgoing/incoming endpoints; different blocks/spans and same text; section ranks/order; isolated field/context evidence; same-span conflict/ambiguity; invalid blocks/bounds/type/unselected endpoints; legacy replay/resume; retry; stale source/revision/actor/attempt; rollback/commit failure; file/PostgreSQL and restart.

Lifecycle entity: WorkingRevision derived from immutable SourceSnapshot.
Lifecycle transition: Existing authorized ingest/reprocessing prepares then atomically commits the complete working object bundle with proposed relations.
Initial durable state: Immutable received source plus reserved attempt; new or open unreviewed working revision, optionally an existing immutable release.
Trigger: Existing ingest or authorized reprocessing command.
Authorization: Existing researcher/source-selection authorization; named review and publisher commands unchanged.
Validation: Source/hash/version/revision/attempt ownership, V3 span/field/context checks, exact relation resolution and admission. Same-span ambiguity/conflicts remain rejected.
Mutable entities: Prepared working candidates/proposed relations and existing attempt/envelope, through existing workflow transaction.
Immutable entities: Source bytes, prior review evidence, published objects/releases.
Workflow state before: Processing or open WorkingRevision.
Workflow state after: Existing review obligations/readiness derived from all selected occurrences; no new state.
Release state before: Existing release or none.
Release state after: Unchanged.
Serving state before: Existing registry-selected release or none.
Serving state after: Unchanged; formation cannot publish.
Expected API result: Both selected occurrences and correct exact relations in the snapshot object bundle.
Expected UI result: Each independent selected occurrence is its own review target; no transferred approval.
Failure result: Invalid preparation/failed commit leaves prior durable work intact.
Restart result: Same IDs, spans, mapping, context/field proof, relations and bindings reload from durable workflow.
Recovery result: Idempotent duplicate command or explicit conflict; old incompatible checkpoint cannot silently resume.
Legacy-data result: Read existing objects unchanged; no automatic backfill, approval inheritance or published mutation.
Required black-box scenario: GIVEN HTML with three selected occurrences, two identical at distinct source positions, WHEN actual V3 ingest with incoming/outgoing relations commits, THEN three independent IDs and exact endpoints survive transformation/admission/storage/restart; same authorized command adds no objects/relations. Failed replacement preserves earlier durable bundle.
Explicit non-goals: Production causality, live model content quality, automatic backfill, old approval adoption, new alias/materialiser/workflow authority, adjacent audits, merge/deploy.

Context contract:
| Datum | Producer | Consumer | Owner/storage | Lifetime | Validity | Missing/stale |
|---|---|---|---|---|---|---|
| snapshot/document/source hash/version | ingest/source store | producer/replay/activation | existing envelope/source preparation context | frozen source | exact source match | reject |
| attempt/actor/expected revision | reserve | checkpoint/activate | existing processing_attempts/workflow | one authorized attempt | current authority and CAS | reject stale activation |
| candidate ID/ordered spans | materialiser | selector/transform/review | existing semantic metadata/object bundle | working object | intact same occurrence | validation rejection |
| fragment refs/source mapping | source reconstruction/materialiser | transform/source readers | same candidate provenance | source-bound | exact own source span | reject, no transfer |
| field/context evidence | V3 validator | admission/review | same candidate metadata | source-bound/review tuple | exact own evidence | reject/retain unresolved per current contract |
| relation proof | validated proposal/exact resolver | transform/review/storage | proposed relations + relation evidence in same bundle | working review tuple | both exact selected endpoints | reject |
| replay identity | producer | retry/resume | existing semantic_replay | contract version | exact source/config/occurrence rule | reject incompatible resume; authorized fresh inference only |

#556 stays open pending separately evidenced deployment and production acceptance.
