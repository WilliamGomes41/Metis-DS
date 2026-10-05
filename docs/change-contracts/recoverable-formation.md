Change class: A
Promise: Source-bound V3 preparation retains independently validated proposals and exact unresolved source work when a producer proposal fails, with explicit recoverable formation evidence and unchanged publication/serving safeguards.
Proof: Recorded Smetten response replay plus ingest -> partial review -> restart -> targeted recovery -> review/publication gates; commit failure, duplicate and stale command regressions.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit assignment: William authorized implementation of the preceding domain/lifecycle design on 2026-10-05. This is one implementation issue; no merge or production deployment in this assignment.

Rewrite target: V3 proposal acceptance/recovery boundary in existing WorkingRevision.
Why local patching is insufficient: One invalid field currently aborts independent validated work; copying a word or weakening exact matching does not repair failure scope.
Current authority/writer/reader map: Immutable source store -> pre_review_semantic_v1/provider -> source_evidence_resolution_v1 -> semantic_passage_v1 -> transform/admission -> OperationsConsole ingest/reextract/retry -> existing workflow transaction/CAS. Diagnostics, processing exports and review projections read existing records. PublicationReadiness/source closure -> durable publication -> registry -> Product API remain sole owners.
Supported runtime topologies: local compatibility store and PostgreSQL workflow store composed with Azure immutable source/publication adapters; no new store or worker.
Persisted-state impact: additive versioned formation evidence in existing semantic replay/provider records; current source work remains exact remainder records. No SQL migration or backfill.
Compatibility/migration plan: V3 contract identity versioned; legacy v1/v2 unchanged and historical reviews immutable. New contract applies to new authorized work only.
Rollback/recovery plan: compatible reader, explicit configuration rollback for future formation; retain existing records and releases. Recovery of unreviewed work uses existing guarded command; reviewed/published work uses explicit successor.
Cutover trigger: controlled commit after deterministic raw response, transaction/restart and publication/API gates pass; no automatic deployment.
Cleanup/decommission criteria: no duplicate authority/temporary store; retain historic readers.
Failure blast radius: invalid candidate plus dependencies, or unusable response; source corruption/durable commit failure still aborts activation. Active releases unchanged.
Adversarial proof matrix: literal mismatch/unknown block; invalid relationships; dependent context; empty valid result; failed primary/supplement; replay/restart; expired/stale/duplicate attempt; failed commit; reviewed/published guard; API/publication exclusion; protocol compatibility.

Lifecycle entity: WorkingRevision derived from immutable SourceSnapshot.
Lifecycle transition: source preparation/recovery commits validated candidate work plus explicit unresolved formation evidence, never approval/publication.
Initial durable state: captured source and no work, or unreviewed mutable work; active historical release may coexist.
Trigger: authorized ingest/reextract/retry or explicit successor command.
Authorization: existing researcher/reviewer role, attempt lease and revision CAS.
Validation: exact source spans, object field/context and relation integrity; complete unresolved range accounting.
Mutable entities: current unreviewed working object set/envelope/processing evidence; successor where required.
Immutable entities: source bytes/hash, reviewed historical versions, published releases and registry.
Workflow state before: processing or incomplete unreviewed work.
Workflow state after: in_review with explicit incomplete source work; ready only through existing closure and technical gates.
Release state before: absent or existing release history.
Release state after: unchanged.
Serving state before: registry active/inactive set.
Serving state after: unchanged.
Expected API result: no unpublished/invalid/source-only objects; previous active release unchanged.
Expected UI result: valid candidates reviewable, unresolved source work visible, diagnostics identify rejected proposals.
Failure result: local producer failure preserves independently valid work; source/storage/revision failure preserves previous durable bundle.
Restart result: same candidates, failures, open source work and serving truth.
Recovery result: targeted supplementary proposal over unresolved ranges without silently retaining stale approvals; reviewed work requires successor.
Legacy-data result: no migration or reinterpretation.
Required black-box scenario: ingest with valid knowledge plus invalid literal -> preserve valid and open source -> restart -> recover missing source -> existing human review/readiness/publication/API checks; injected commit failure preserves prior bundle.
Explicit non-goals: relaxed literal matching, automatic exclusions/approval, clinical completeness claims, Forge table fix, gateway/background infrastructure, merge/deploy.

## Protocol decision
William authorized the preceding domain/lifecycle design and its implementation.
Protocol section 5 is reopened only for versioned V3 producer-error isolation.
Fail-closed admission/publication remains absolute. No literal normalization,
inferred repairs, automatic exclusions or approvals are introduced.
Existing reviewed work requires successor work; direct recovery refuses reviews.
Unknown dependencies quarantine a call. Failed source/store/CAS rejects activation.

## Verification record (2026-10-05)

The unchanged recorded Smetten producer responses were replayed offline through
source resolution, formation, transformation and the existing admission gates.
Aggregate results and source/evidence hashes are in
`docs/acceptance/smetten_recorded_formation_replay.json`; reproduction uses
`scripts/replay_recorded_formation.py` with the original diagnostic evidence.
17 proposals survive (16 recommendations, one definition); admission allows 13
and blocks four on existing reference/context/abbreviation gates. All 639 source
accountability records remain. Twelve conflicting supplemental reselections
remain unresolved and block publication. No wording was repaired. These counts
do not establish that all clinically relevant knowledge was extracted.

Black-box tests cover partial ingest, durable restart, bounded targeted recovery,
unchanged candidate hashes, duplicate/stale/concurrent commands, actor guards,
producer failure and injected commit failure. Review then publication is tested
through the REAL-mode Product API: unpublished knowledge returns 404; after
explicit review/publication it returns 200 with identical knowledge after restart.
This scenario uses memory doubles for canonical publication and source bytes;
native PostgreSQL recovery is separately defined for existing CI.

The offline suite (excluding the unchanged deploy-packaging file) produced
2694 passed, 188 skipped, one failure. The failure is the existing parent-death
transport process test and reproduces on the unchanged baseline. Native PostgreSQL
and other unavailable runtime integrations are skipped locally. Automatic
approval review rejected the full-suite run when unchanged packaging tests
attempted public PyPI downloads; the offline run avoids that network operation.
CI PostgreSQL, packaging and complete-suite checks remain required before merge.
No live model call, Azure activation or clinical reference assessment is claimed.
