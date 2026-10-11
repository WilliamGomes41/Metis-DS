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

## Diagnosis and evidence (2026-10-11)

Continuation contract (PR review): extract-origin `linked_as_support` and
`used_as_context` are automatic source classifications, not human decisions.
Only explicit review-origin non-candidate dispositions may contribute to human
formation closure. Rejected candidates require their current named human
review/hash; approvals keep the existing exact-current T9 checks. All source,
review, transaction, rollback and topology boundaries above remain unchanged.
The added automatic-disposition regression fails twice on 8fda6a2 before edits;
it injects only read inputs and historical errors, never a human decision.

The second PR finding is also reproduced: the fixture provider's actual rejected
selection leaves a coverage_remainder without proposal-only source_blocks_hash.
Real confirm_source_context exclusions still leave formation_incomplete true.
Before its fix, the new source_disposition HTTP story fails at that exact check.
The reader now computes the existing producer's semantic-input fingerprint from
retained fragments and verifies it against replay. Valid T10 source records may
then use their exact literal/source-role evidence without a proposal-only stamp;
proposal-origin objects still require their existing stamp. This is a pure block
projection, not extraction, passage materialisation or model execution. A changed
replay input with a recomputed identity hash still fails closed.

Added controls prove that extract statuses and review markers without human
evidence stay open; real candidate rejection and source exclusion close after
console recreation; missing reviewer/date or stale rejection hash stays open.
Approvals retain exact-current binding/stage enforcement. Non-approval evidence
uses existing current review hashes or the T10-validated source-role record,
plus human reviewer/date and explicit non-candidate register origin.

Continuation focused verification: 71 passed, 4 local PostgreSQL skips in A03
plus recoverable-formation (before the final stale-input assertion). Additional
T9/T10/T12/source-container/source-context regressions: 121 passed, 6 backend
skips. Mandatory preflights, compileall, architecture boundaries and 6 invariants
passed. Native CI/final-tree full-suite results are reported in PR comments.
Local installation of PostgreSQL is unavailable in this environment; skips do
not establish backend acceptance. The new source-disposition story is included
in both file and native-workflow PostgreSQL parametrizations.

Continuation surface/adversarial review: EXTEND the existing read predicate;
REUSE producer fragment partitioning/fingerprinting, T10 source records/role
validation and T9 current approvals. No new writer or abstraction. The source-role
exception is allowed only after source_accountability verifies its current
literal/command/role evidence; stale role, source or input cannot gain closure.
The extra branch complexity is bounded evidence filtering in the same reader,
not another status engine. No changes to lock, transaction, CAS, schema or
canonical/registry ownership. Engineering readiness remains bounded by exact
head native CI; full canonical PostgreSQL, Azure and production are unproven.

The initial tests-only stage (local 913b23f; remote 7991a42e51e70762c285a4e090b9461efc7d594e) ran against unchanged main. Command: `python -m pytest -q tests/test_a03_formation_coverage.py --tb=short`. Result: 12 failed, 14 passed, 2 PostgreSQL skips. Nine failures cover selected-object/call/source-assessment adjacency, reverse order and overlap; the other three are the real-review blocker and both local publication stories. After real reviews the only blocker was source_formation_incomplete. Recovery failed at formation_incomplete before review. Whole-span and gap guards passed.

A union-only intervention made the original command green (26 passed, 2 PostgreSQL skips), supporting single-span containment as the local cause rather than missing independent review or publication authority. Additional context acceptance tests were added subsequently; they are not retrospectively claimed as baseline RED. Synthetic malformed inputs are passed to the read boundary rather than bypassing the append-only revision writer.

Final implementation reuses source_containers_v1._covers. Its input is scoped before interval calculation. Preparation callers supply a jointly validated proposal from pinned source/replay (prepare -> source evidence resolution + semantic validator; bounded execution revalidates the merged proposal; replay exact identity/hash validation). Human closure checks envelope/replay identity, source id/checksum/version, semantic source-block hash, exact literal evidence, T10 source-accountability closure and T9 exact-current approval/review stage. Current object selection belongs to snapshot_objects/current_revisions, never a new revision selector. Source disposition still uses the existing definitive_review_disposition policy; superseded objects do not count. No new SQL, persistent statuses, schema, writer, model call or passage construction.

Status and the standalone technical formation read use stored_extraction rather than its legacy extraction fallback. Missing/corrupt retained source cannot create closure or trigger a rebuild. Readiness continues to supply its existing source/binding inputs.

Executed local focused checks: A03 plus recoverable formation: 61 passed, 3 PostgreSQL skips (before the last notes-only update). Broader A03/recoverable/T9/T10/T12/source-container suite: 174 passed, 5 PostgreSQL skips before the final no-extraction guard; that guard separately passes in A03. Architecture invariants: 6 passed. Repository preflight, release-control preflight, compileall, architecture-boundary checker and change-contract validation: PASS.

A full local intermediate-tree run produced 3238 passed, 303 skipped, 4 failures in 335.87 seconds. All four failures reproduce on unchanged main in an isolated worktree: test_parent_process_death_terminates_transport_worker and three test_security_harden_wave3 proxy/DNS-pin tests. The complete final-tree run is also being recorded; PR comments will state its result and CI evidence. No test or safety gate was weakened to mask these failures.

## Separate surface/adversarial pass

Surface verdict: APPROVE WITH NOTES. Reuse the existing interval algorithm and existing source/review authorities; remove the duplicate rejection-selection coverage decision. Two production files change. No alternate writer/UI gate/context class/configuration flag. Source function complexity signals (bundled AST counter): incomplete 13 -> 32, pending_rejections 25 -> 21. The increased read-filter complexity is explicit source-identity, evidence, and current-review enforcement in one local calculation; extracting a web of one-line predicates would hide that contract. This is an inspectable bounded filter, not a new lifecycle/state engine.

Adversarial inspection traces producer/replay, status, _can_resume_formation, technical/readiness/consider_publish and the file/PostgreSQL publication composition. _can_resume_formation deliberately retains the historical flag and existing reviewed/published guards. Forensic/export consumers remain diagnostics, never publication authority. Stale source/snapshot/version/object/binding, corrupt evidence/location/context, review-required failures, independent immutable-locator gates, unauthorized HTTP actors and missing extraction were challenged. Historical errors are retained. Existing writer CAS/transactions/rollback and canonical registry authority are unchanged. Runtime concurrency/rollback proof must run on PostgreSQL, not be inferred from local readers.

Engineering readiness: NOT ESTABLISHED until required native-backend/CI evidence passes. The PostgreSQL parametrizations use native workflow document/review/identity stores; provider, immutable-source and canonical-publication adapters remain doubles even there. Full PostgreSQL canonical publication, Azure, remote production process restart, live provider quality and production causality are not claimed. The restart proof recreates the console against durable workflow storage; publication/source doubles remain shared, as explicitly stated in the tests. No production acceptance, merge or deployment.
