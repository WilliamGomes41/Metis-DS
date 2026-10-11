Change class: A
Promise: Located formation failures cease blocking only when current valid spans of one source/block jointly cover the complete range, separately for validated preparation and definitive human disposition.
Proof: Baseline RED regression, interval/context adversarial matrix, real review commands and authorized HTTP publication/restart; native PostgreSQL workflow proof with explicit adapter limitations.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit assignment: User assigned A03 repair on 2026-10-11; #553 is tracking only. This ticket is the sole implementation assignment to the Metis Engineer profile, scoped to implementation and a reviewable PR, without merge/deploy.
Baseline: main 502085766b47fd16788eb8881c8455477a230dd7.

Rewrite target: Existing recoverable_formation read-side closure predicate, not its durable authority.
Why local patching is insufficient: Replacing single-span comparisons alone does not prove current source/revision/review binding. Extend the existing read operation narrowly with current inputs; no wholesale rewrite.
Current authority/writer/reader map: Source bytes/fragments remain the immutable source store. prepare/pre_review_semantic/bounded_formation produce validated proposals/provider evidence; replay lookup pins source/snapshot/contract and revalidates. OperationsConsole ingest/resume commits existing bundles via workflow transaction/CAS. Existing review/source-disposition commands own current object/binding/history writes. incomplete is consumed by processing_status, _can_resume_formation and consider_publish; PublicationReadiness/ReviewClosure/DurablePublication/PostgresReview console compose existing gates and publish. source_selection/UI/export consume these projections. forensic_trace invokes pending_rejections for diagnostic proposals only. Canonical publication store and registry own releases/serving; startup reloads durable evidence. No new writer.
Supported runtime topologies: File workflow compatibility; native PostgreSQL documents/review/identity workflow; existing canonical/immutable-source adapters and Azure composition. Tests will distinguish real workflow PostgreSQL from test doubles for canonical/source and provider.
Persisted-state impact: No new schema, records, status or migrations. Historical provider errors and review evidence unchanged. Only derived closure changes.
Compatibility/migration plan: Tests-only stage then bounded reader extension in same unmerged branch. Keep legacy no-objects incomplete behavior. Existing evidence remains readable; missing/invalid source or review inputs fail closed. No dual writer.
Rollback/recovery plan: Revert reader changes together before separately approved deployment; retain all existing data. Restart reloads same bundle and re-derives closure; no destructive rollback or reprocessing.
Cutover trigger: Future reviewed merge and separate deployment; neither authorized now.
Cleanup/decommission criteria: Reuse _covers; remove only duplicated single-span checks and temporary diagnostics. No parallel status mechanism.
Failure blast radius: Formation blocker falsely open/closed on current WorkingRevision. All independent admission/review/publication/serving gates remain.
Adversarial proof matrix: adjacency/order/overlap/gap, other block/source/snapshot/version/semantic input, malformed/unknown locations, stale/insufficient review, explicit requires_review/conflict, historical error retention, no model/extraction reads, HTTP actor guard, restart, PostgreSQL rollback/concurrency via existing transaction tests.

Lifecycle entity: Current WorkingRevision derived from immutable SourceSnapshot.
Lifecycle transition: Read-only re-derivation of formation closure after existing validated preparation or human review; publication remains a separate authorized transition.
Initial durable state: Current snapshot, source-bound replay/provider historical failures, current objects and review bindings; optional older active release.
Trigger: Existing validated preparation or definitive review, then status/readiness/publication read.
Authorization: Existing producer attempt/role/CAS controls and named human review controls; publication uses existing publisher command.
Validation: Exact spans, same block and source/hash/version/snapshot/replay input; current source evidence and review finality. Validated selection is not approval; requires_review cannot be cleared by selections.
Mutable entities: None in closure calculation. Existing commands alone commit current working objects, bindings and audit.
Immutable entities: Source bytes/fragments, historical formation failures/reviews and publication releases.
Workflow state before: Formation incomplete, with possible open curation.
Workflow state after: Formation complete only when all located failures have valid complete coverage; other open curation/technical gates still block readiness.
Release state before: Absent or existing immutable releases.
Release state after: Unchanged by closure; existing publication command alone creates/closes a release.
Serving state before: Existing registry active/inactive set.
Serving state after: Unchanged by closure; authorized publication retains existing registry semantics.
Expected API result: Current processing/readiness agree on formation closure; unauthorized publication refused; fully reviewed eligible work can publish through HTTP.
Expected UI result: Existing formation blocker disappears only for covered valid current work; no UI exception.
Failure result: Gaps, unknown locations, invalid/stale evidence, conflicts and incomplete review remain open. Existing failed durable commands rollback.
Restart result: Identical closure/current review/publication result from durable bundle; no model or passage rebuild.
Recovery result: Existing validated resume may resolve located non-review failures; definitive current human disposition may resolve review-required failures. No automatic reviewer decision.
Legacy-data result: Keep historical errors and no-objects behavior; missing identity or evidence does not gain closure. Published history is not modified.
Required black-box scenario: GIVEN ingested source with two adjacent source-bound objects and a synthetically injected historical located failure, WHEN existing real review commands finish both and authorized HTTP publication runs, THEN formation blocker closes, independent gates still apply, publication succeeds and restart retains exact history/serving. Also prove validated new split selections after failed initial selection and reviews before HTTP publication.
Explicit non-goals: Clinical/model correctness, production causality/acceptance, model calls or passage rebuild during closure, MVC redesign, alternate authority, merge/deploy.

## Context contract
| Datum | Producent | Consument | Eigenaar/opslag | Levensduur | Geldigheid | Ontbrekend/verouderd |
|---|---|---|---|---|---|---|
| Source hash/id/version, snapshot/document | ingest/source store | closure/replay | existing envelope + objects | immutable source | exact matching envelope/replay | stays open |
| Block ids/offsets | source reconstruction/validated proposal | interval union | existing semantic metadata/provider evidence | source contract | nonempty exact spans, same block | stays open |
| Proposal/semantic input identity | validated producer/replay | closure | existing replay record | exact preparation | revalidated input, pinned replay | stays open |
| Current object versions/hash and human review | existing review commands | closure/readiness | existing current objects/bindings/ledger | current review tuple | definitive disposition plus existing exact review authority | stays open |
| Historical failures | producer checkpoints | diagnostics/closure | provider evidence | retained history | observation, not mutable status authority | never deleted |

Locks/transactions: closure is a pure read within existing console snapshot/readiness inputs. Ingest/resume/review/publish retain existing outer snapshot and workflow transaction/CAS scopes. No new commit, cache, job, idempotency key or lifetime. Native PostgreSQL tests use a disposable backend only; no production changes.
