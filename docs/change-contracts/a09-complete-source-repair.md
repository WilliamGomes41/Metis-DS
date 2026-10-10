# A09 — complete source repair (#559)

Change class: A
Promise: A source repair activates only a technically consistent complete object revision, with current admission and fresh review obligations.
Proof: Original HTTP fault probe, HTTP stored readback/restart regressions, native PostgreSQL concurrency and rollback, alternative correction entrances, repository checks.
Touches lifecycle invariants: yes
Rewrite risk: high

The owner explicitly assigns investigation, implementation, tests and a reviewable PR in this session. #559 remains a progress/acceptance issue; its needs-triage label does not replace that assignment. No merge, deployment, production corrections or automatic backfill.

## Existing operation and mitigation

Rewrite target: strengthen OperationsConsole.correct_object preparation before its existing commit; source-unit/merge callers stop activating provenance/cleanup successor revisions.
Why local patching is insufficient: passing new spans alone repairs materialisation but leaves stale field/context bindings and separate hashed revisions. No replacement operation or storage authority is needed.
Current authority/writer/reader map: source bytes/accepted fragments belong to verified source storage and OperationsConsole._read_source_fragments. HTTP /review/resolve calls submit_review_resolution, then _source_repair/_merge_repair, explicit OperationsConsole.correct_object. Direct calls, ReviewClosureConsole and ClosedLoopReviewConsole overrides also reach that kernel; legacy free-text writes are disabled by closure. correct_object owns successor construction; revision_workflow owns exact lineage/hashes; materialiser owns source mapping; source_bound_fields v2/v3 owns literal field/context bindings; admission_gate owns admission; passage_register is a projection. File _commit_prepared_store and PostgreSQL document/review stores own object history, envelope and binding/audit writes. Current readers, review/readiness, exports and MCP consume snapshot_objects. Production console_asgi composes FastBadge, Remaining, Review, Documents, Identity and Azure-authoritative publication mixins; none owns a competing correction operation.
Supported runtime topologies: local compatibility file console; native PostgreSQL document/review/identity/remaining stores across independent runtimes with shared workflow transactions; Azure source/canonical publication adapters keep existing contracts. No production access.
Persisted-state impact: new successor JSON metadata only; unchanged schema and historical bytes. No backfill.
Compatibility/migration plan: locally extend existing preparation; materialisation and field/context versions remain v1/v2/v3 as applicable. Retain deterministic compatibility repair-spec patch hash and closure lineage patch hash policies. Unchanged selection may reuse verified evidence; changed selection records uncertainty rather than guessing field meaning. Existing boom construction remains source-authoritative.
Rollback/recovery plan: revert code before deployment; retain every new/history row and evidence. Compatible readers use existing versions. No data rollback or history rewrite. Existing workflow transaction aborts unsuccessful activation; local compatibility rollback retains prior files/ledger.
Cutover trigger: execution of the strengthened existing correction operation on new work; historical/published rows are not re-admitted.
Cleanup/decommission criteria: remove only source/merge calls to post-activation finalization and cleanup; keep compatibility helper for other proven callers until separately reviewed.
Failure blast radius: bounded to an unpublished object's revision and merge targets in one WorkingRevision; release/serving never changes.
Adversarial proof matrix: same/expanded/shortened selection, context uncertainty, repeated text positions, malformed direct materialisation, missing selection, mixin/hash policies, stale and overlapping requests, authorization/source mutation before commit, restart, real commit failure with object/binding/audit rollback.

## Exact lifecycle slice

Lifecycle entity: knowledge object revision in an existing open WorkingRevision.
Lifecycle transition: exact current predecessor -> one completely prepared correction successor requiring review; merged targets supersede under the same existing transaction.
Initial durable state: verified immutable source, current object and optional review bindings/history in open working work.
Trigger: authorized correction command containing object identity, expected revision, selected source-unit IDs and reason (HTTP supplies no canonical text/evidence).
Authorization: existing correction/review role and named-reviewer checks, repeated under commit lock/transaction.
Validation: exact positional source spans and source identity, full materialisation/field/context validation, current admission, canonical schema, exact predecessor and expected revision.
Mutable entities: new object revision, current workflow envelope/review bindings, merge target successors and associated audit.
Immutable entities: source bytes/accepted representation, prior canonical versions and review history, published work.
Workflow state before: open in_review/blocked under the existing working contract.
Workflow state after: open with needs_review correction; content deficiencies have current blocked admission.
Release state before: existing release state or none.
Release state after: unchanged.
Serving state before: publication-registry serving set.
Serving state after: unchanged.
Expected API result: HTTP 303 only after complete commit; conflict/technical rejection otherwise.
Expected UI result: existing corrected needs_review projection with admission reasons.
Failure result: no activated partial successor; old object/bindings/audit retained.
Restart result: identical stored revision, mapping, current admission, lineage and review validity.
Recovery result: existing transaction recovery; no inference or automatic source correction.
Legacy-data result: no rewriting, migration or backfill; native boom and compatibility hash contracts stay supported.
Required black-box scenario: GIVEN valid selected source sentence and current review, WHEN reviewer expands selection via /review/resolve, THEN current readback reconstructs exactly, current field/context evidence is valid or explicitly unresolved, admission is current, old approvals cannot authorize the successor, stale retry conflicts, and restart preserves result; commit failure preserves all prior durable state.
Explicit non-goals: merge/deploy/production acceptance, clinical inference, automatic semantic completion, source re-extraction/correction, new status authority/dispatcher/store/context framework.

## Context contract

| Given | Producer | Consumer | Owner/storage | Lifetime | Validity | Missing/stale |
|---|---|---|---|---|---|---|
| Actor/object/expected revision/reason | HTTP or correction caller | existing kernel | command; durable audit after success | one request | current rights, exact revision, mutable work | reject/conflict before activation |
| Source hash/version/fragment identity | verified source owner | selection/materialiser/commit | immutable source + envelope | source snapshot | exact bytes and accepted fragment representation | reject; separate explicit source correction |
| Source unit IDs and positional spans | backend source_units | repair + materialiser | temporary preparation; stored semantic spans | one source representation | position/occurrence, exact source bounds | reject unknown/ambiguous selection |
| Text/mapping/provenance | materialiser | field binding/admission/hash/store | new object JSON | exact object revision | source reconstruction equals text and ordered refs | technical rejection |
| Field meanings/references | previous semantic preparation | existing binder | object metadata | exact selection/type/context | reuse only after unchanged-selection and literal validation | changed selection: closed uncertain fields; no heuristics |
| Context roles/references | previous semantic preparation/review | context binder/admission | object metadata/history | exact target literal | unchanged selection + reconstructed source | changed selection: unresolved relation; preserve history |
| Admission | admission_gate | review/readiness/store | object metadata | complete prepared revision | run after materialisation/evidence | no successful candidate without current outcome |
| Hashes/lineage | revision_workflow/integrity kernel | commit/current readers/review | object metadata/provenance | immutable successor edge | final content/evidence then final hashes | reject invalid edge/hash/schema |
| Review bindings/audit | existing review/correction operations | commit/review/history | workflow review store | exact object version/hash/history | old decisions retained; validity invalidated | rollback together with objects |

Preparation is deterministic and bounded, with no model/provider I/O. No checkpoint or job is introduced. Correct_object reuses the existing write lock and transaction, rechecks current actor/source/mutability/revision before commit. Duplicate commands reuse no implicit identity: replaying an old expected revision explicitly conflicts. PostgreSQL proof must use the production mixin order, not just a store mock. Local file rollback is exception recovery, not a claim of crash-atomic multiple files.

## Verified cause and implementation

On a29ed784 the original `probe_source_repair_mapping.py` produces HTTP 303 with `materialisation_text_mismatch` and absent admission after expanding the source selection. The inconsistency is present inside `correct_object`, before provenance finalization: clean/raw text changed while the old semantic spans/mapping and field/context bindings survived. Admission silently removed the invalid candidate's outcome. Passing fresh spans alone leaves `source_bound_fields_stale`; therefore that intervention is not the repair.

The kernel now materialises the complete selection, validates raw/clean text and source reconstruction, verifies reusable evidence for unchanged selections, records closed missing/unresolved evidence for changed selections, reruns admission, and refuses missing admission on selected candidates. Final lineage/hashes are calculated after preparation. Source/merge and adjacent-continuation corrections no longer activate a preliminary revise row; the successor references the actual predecessor. Existing T11 lineage hashes override compatibility repair-spec hashes; legacy deterministic repair keeps its established policy. Account rights, source identity, mutable work and concurrency token are checked again at the actual commit boundary. The existing PostgreSQL transaction encompasses correction, merge supersession, bindings/workflow and all audit events.

Tests that previously expected invented text and successful storage with no admission were updated to reject technical inconsistency, or to use source-valid revisions when testing review invalidation. A legacy corrupted predecessor is seeded explicitly as an isolated fixture; it is no longer created by the production correction command.

## Evidence and acceptance boundaries

- Original unmodified HTTP probe on main: RED, `REPAIR_SUCCESS_STORES_STALE_SOURCE_SPANS`. The preserved probe after repair: GREEN; same selection remains allowed, expansion is reconstructable and blocked with concrete missing-evidence reasons, never stale evidence.
- A09 plus source-continuation regressions: 24 passed, 16 native-PostgreSQL cases skipped locally. Includes new-process restart, changed context, shortening, repeated positions, prior approval invalidation, stale/overlapping HTTP requests and an older direct preparation losing to a committed winner, role/source changes during preparation, actual commit-boundary failure after prior approval for source repair and merge, merge order and direct/mixin entrances. Noncontiguous selection is rejected according to the existing selection contract without including its gap.
- Architecture invariants: 6 passed. Repository preflight, architecture boundaries, compileall, change-contract validation and committed release-control path mapping: PASS.
- Native PostgreSQL restart/concurrency/deferred-COMMIT rollback scenarios are included using the production workflow mixins and PostgreSQL stores. Local proof remains open: this sandbox maps only uid 0; initdb refuses root and setuid is unavailable. Existing CI supplies PostgreSQL 16. Test source storage is the existing MemorySourceStore adapter; Azure production behavior and production causal validation remain open.
- Four failures from the initial full suite are independently reproduced on unchanged main: one process-child /proc detection failure and three proxy-sensitive SSRF tests. Stable-HEAD full suite with proxy variables removed: 3139 passed, 261 skipped, one independently confirmed baseline /proc detection failure. Packaging recheck: 1 passed. Final A09/continuation/review-audit regressions: 32 passed, 16 skipped.

## Minimal code surface review

Verdict: architecturally contained and reviewable; release readiness is separate and remains unproven until native backend checks and production acceptance.

The patch strengthens three existing product modules (net +120 lines before unused-import cleanup). One evidence-binding function belongs to the existing binder; no new service, dispatcher, status authority, persistence table or generic context object. The two post-correction mutation calls and preliminary review activation are removed from source/merge; adjacent continuation likewise uses one correction. The finalizer helper remains for existing compatibility callers/tests. Materialisation, admission, lineage, field/context contracts and transaction machinery are reused rather than duplicated. No dependency changes or backfill.

Measured whole-repository physical code: 150003 -> 150580 lines; nonblank code 132824 -> 133354; functions 6890 -> 6919; maximum per-function Python CC remains 293. Overall diff before this evidence section: 11 files, +770/-129; most additions are the HTTP regression matrix and preserved probe. Metrics are scope indicators, not an architecture/readiness proof. Remaining tradeoff: changed semantic selection deliberately requires fresh semantic review; conservative unresolved evidence may block more candidates but never lowers admission requirements.

## CI follow-up: construction validation order

The first native PostgreSQL full run on 945b424 failed six cases (Python 3.13: 3384 passed, 15 skipped). Five decision-tree merge cases exposed an A09 regression: source provenance validation had been moved before `rebuild_for_revision`, so a newly selected literal was compared with the predecessor construction proof. The same five cases were expanded to the local ReviewClosureConsole as well as the native PostgreSQL fixture; all five reproduced the exact `decision_unit_source_fidelity_failure` locally before the fix.

Selected raw references are now provisional preparation input. The existing materialisation/construction kernel rebuilds its proof and reference order first; final provenance validation verifies the complete prepared result before lineage/hashes and the existing atomic commit. It never performs a later revision activation. The sixth failure was an invalid test command: PostgreSQL requires at least one account role. The test now removes correction roles while retaining publisher, and still requires the actual commit to reject `correction_role_required`. No account/admission/source validation requirement was relaxed.

After this correction, focused A09, decision-source repair, closure and deterministic-repair suites: 62 passed, 23 skipped locally. The original A09 HTTP probe is rerun. Native backend restart/concurrency/rollback cases passed in the initial native run apart from the invalid role-revocation fixture; the complete updated CI matrix must still succeed. Repository checks and full-suite results for the updated revision are recorded in the PR. Surface review: one existing validation call moves to the complete-preparation boundary; no second operation or authority is introduced.
