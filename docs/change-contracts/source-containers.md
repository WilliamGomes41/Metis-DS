Change class: A
Promise: V3 forms reviewable knowledge in bounded source tasks and accounts for every source range separately, without converting unselected source into individual knowledge review duties.
Proof: Smetten recorded evidence and predetermined source examples; container separation, exact context use, targeted recovery, metadata rules, scope correction, restart/rollback and publication/API exclusion.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit assignment: William approved the implementation proposal and assigned implementation on 2026-10-05 at 11:33 Europe/Amsterdam.

Rewrite target: V3 preparation and source-accountability work boundary.
Why local patching is insufficient: Whole-document repeated producer calls leave source_assessments empty; core-only coverage calls already linked context unresolved; every unselected range becomes manual repair. Presentation-only filtering cannot repair these behaviors.
Current authority/writer/reader map: immutable SourceSnapshot/fragments -> pre_review_semantic_v1/source resolver/semantic_passage -> transform/admission/passage_register -> OperationsConsole ingest/reextract/resume, existing _commit_prepared_store and PostgreSQL workflow overrides. review_duty/workboard/UI/exports read typed source/candidate records. publication_readiness/source closure owns readiness; durable publisher and publication registry own serving; Product API reads registry.
Supported runtime topologies: local compatibility file store and PostgreSQL workflow with immutable Azure source/canonical publication adapters.
Persisted-state impact: versioned additive formation/source-use evidence in existing revision bundle, typed container access; no new serving authority. Preserve legacy readers and exact reviewed tuples.
Compatibility/migration plan: version V3 contract, process new explicitly requested work only; no automatic legacy conversion. Keep source records in compatible durable bundle with explicit source/candidate contract and domain access; physical table splitting is not required.
Rollback/recovery plan: existing version reader retained; resume only incomplete unreviewed tasks with matching source/policy identity. Reviewed/published revisions require explicit successor. No deletion or destructive migration.
Cutover trigger: enable new version only with complete contract/behavioral tests; merge/deploy require their own authorized steps.
Cleanup/decommission criteria: remove old V3 producer orchestration from new-contract path after tests; retain historical replay readers, no dual writer.
Failure blast radius: one bounded task remains unresolved; independently validated source work persists. Invalid source/hash, stale revision or failed storage abort activation. Publication blocked for unaccounted source.
Adversarial proof matrix: context-only input cannot become new candidate; repeated selection rejected; partial context cannot close whole block; invalidated target reopens usage; misleading metadata cannot exclude clinical text; scope normalization cannot erase negation/numbers; duplicate/concurrent commands; restart/failed writes; legacy/published immutability; API candidate/source exclusion.

Lifecycle entity: WorkingRevision from immutable SourceSnapshot.
Lifecycle transition: explicit preparation/recovery produces separate knowledge candidate and source-accountability containers with exact usage and bounded task evidence.
Initial durable state: new or unreviewed incomplete work; optional active prior release remains immutable.
Trigger: authorized ingest/reextract/resume command.
Authorization: existing account/document permissions, review/published guards, attempt limits and revision CAS.
Validation: exact source/core/context bounds, clinical qualifiers and relation validation; source task accounting; narrowly evidenced metadata rules.
Mutable entities: unreviewed revision proposal/source records and formation evidence committed as one bundle.
Immutable entities: source bytes/hash, historical reviews and publication releases.
Workflow state before: processing or incomplete in_review.
Workflow state after: in_review or blocked with identified incomplete tasks; ready only through existing closure and review gates.
Release state before: absent or prior active immutable release.
Release state after: unchanged.
Serving state before: publication registry active set.
Serving state after: unchanged.
Expected API result: only explicitly published knowledge/context; source records and unapproved candidates never served.
Expected UI result: knowledge container with proposals and repairs; source container with linked uses, document information and grouped unresolved work, not 639 presumed clinical defects.
Failure result: incomplete task remains explicit; previous durable work intact on source/store/CAS failure.
Restart result: same containers/task progress/source usage and serving truth.
Recovery result: only unfinished task regions are selectable, prior cores context-only; no reassignment of old approvals.
Legacy-data result: historical stored records retain prior semantics; new policy requires explicit new work.
Required black-box scenario: ingest source with metadata, known recommendations and linked table/list -> separate containers -> interrupted task -> restart/resume -> review -> publish -> API; stale/duplicate and injected activation failure preserve state.
Explicit non-goals: clinical completeness claim from counts, automatic approval of knowledge, fuzzy source repair, changed publication registry, new permanent environment, automatic deployment, speculative two-stage field extraction without comparative evidence.

Policy decisions approved with proposal:
- Exact document metadata/structure may be machine-disposed with versioned evidence, reversible decision and no inference of irrelevance from section alone.
- A context region is usage-accounted only for its exact range and valid target; proposed context never approves a candidate.
- V3 may normalize case/terminal punctuation only for duplicate scope matching; literal source storage/validation and clinical qualifiers remain strict.
- Bounded tasks must retain needed document/section context and explicit external references; no source region silently dropped.
