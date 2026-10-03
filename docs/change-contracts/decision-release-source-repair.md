Change class: A
Promise: A reviewed constructed decision graph with literal branch labels publishes and reads back coherently, and source-bound corrections rebuild construction evidence without bypassing fidelity.
Proof: Constructed PDF -> review -> publish -> read -> restart; correction/merge -> source fidelity -> review, with tamper, stale revision and failed commit negatives.
Touches lifecycle invariants: yes
Rewrite risk: high

Explicit user assignment: repair both review findings from PR #488. No separate tracker issue was assigned; the direct session instruction authorizes this bounded implementation and draft PR. The user subsequently authorized merge after final checks/review; no deployment, production retry, deletion or backfill.

## Domain and exact transition

Kernel-owned WorkingRevision and PublicationRelease use the existing authorities. Source bytes remain immutable source-store truth; workflow PostgreSQL owns curation, canonical publication store owns release objects, publication registry alone controls serving. Branch-label context is graph evidence bound to graph review, not approved standalone knowledge. Pure label classification and reconstruction have no lifecycle. Browser session state has no durable authority.

Lifecycle entity: existing WorkingRevision/PublicationRelease.
Lifecycle transition: existing revise -> new needs_review object version; existing ready working graph -> immutable published active release.
Initial durable state: unpublished working revision with source-bound units; for publication, required passage and graph reviews complete.
Trigger: correct_object with explicit reason/source references, or existing publish command.
Authorization: existing researcher/named reviewer correction and publisher checks; rechecked at mutation boundary.
Validation: immutable source checksum, source fragment identity/hash/locator and selected literal; expected revision, published immutability, existing graph structure and exact reviewer targets.
Mutable entities: unpublished object history, invalidated review bindings and existing envelope where correction requires rereview; existing release/registry publication transaction.
Immutable entities: source bytes, prior object versions, historical review evidence and published releases.
Workflow state before: revise for correction; ready for existing publication.
Workflow state after: corrected needs_review (graph may require endpoint refresh); closed published work after publication.
Release state before: no release for this working revision.
Release state after: unchanged by correction; published by existing atomic publication command.
Serving state before: existing active set unchanged.
Serving state after: unchanged by correction; registry activates only approved canonical knowledge objects. Branch labels remain immutable graph evidence.
Expected API result: source-bound new version or explicit validation/conflict; published graph readable without release tuple mismatch.
Expected UI result: existing repair/review route can proceed; no new UI state or approval shortcut.
Failure result: previous object/reviews/source intact; no partial correction or release activation.
Restart result: same corrected version/evidence and registry-backed released graph.
Recovery result: existing transaction rollback/retry rules; no new auto-recovery decisions.
Legacy-data result: markerless objects keep existing correction/serving contracts; no historical writes or relabeling.
Required black-box scenario: constructed decision PDF including Ja/Nee -> source review and graph review -> publish -> read and restart; incomplete unit -> checked source merge -> new fidelity-valid version -> update graph endpoints -> review.
Explicit non-goals: #489 offset resolver, serving activation changes, new graph semantics, source/review backfill, production mutation.

## Rewrite mitigation before implementation

Rewrite target: consistency of graph-evidence versus canonical-object comparison, and source-bound construction proof on correction.
Why local patching is insufficient: exempting labels from mismatch without retaining graph review/source binding would hide corruption; changing only displayed correction text retains stale durable proof.
Current authority/writer/reader map: correct_object/create_revision/accept_source_continuation; decision_review_commands graph/confirm; consider_publish; OperationsConsole.publish and DurablePublicationConsole.publish; release_graph/read_active_graph/Product API; canonical PostgreSQL release metadata and registry; existing workflow store inheritance, _commit_prepared_store, transactions, revision/locking and startup reconciliation. No new writer, store or serving authority.
Supported runtime topologies: existing local compatibility and PostgreSQL workflow/canonical runtime; no expanded multi-instance promise. Memory stores used only test doubles; native tests when database available.
Persisted-state impact: existing v1 construction records rebuilt using existing closed span shape and newline separator. Release payload shape unchanged; canonical set stays approved objects, graph retains source context.
Compatibility/migration plan: additive reader logic recognizes only construction-backed label_usage evidence. Legacy markerless objects are still compared against canonical tuples. No migration/backfill, no new schema version, no deletion of historical release evidence.
Rollback/recovery plan: source and historical objects retained; correction uses existing atomic commit and invalidates reviews. Old reader can reproduce prior label mismatch, so retain compatible reader after affected releases; forward-fix rather than mutate published data. No destructive rollback.
Cutover trigger: regression positives/negatives and normal repository checks; final CI and separate adversarial review before the explicitly authorized merge; deployment remains outside scope.
Cleanup/decommission criteria: no dual write/temporary authority introduced; existing evidence remains required.
Failure blast radius: one correction or read/publication of one snapshot; no source mutation or other release changes.
Adversarial proof matrix: canonical object removed/changed, forged label/mode/review target, stale/invalid source reference, nonliteral or ambiguous repair, legacy markerless correction, stale revision, duplicate/concurrent command, precommit and native transaction rollback/restart. Separate review before draft PR.

## Transactions, evidence and surface

Model/extraction/reconstruction happen before mutation; existing lock/expected revision and PostgreSQL transaction revalidate source working state and actor. New object+metadata+binding invalidation+audit commit together. Publication still uses existing canonical transaction. Same existing publish command returns its immutable release; correction repeats fail through revise-state/revision checks, not duplicate versions. Revision reason, previous version, patch hash and source reconstruction proof remain auditable. No weakening of passage review or graph confirmation requirements; graph evidence integrity is checked even when label tuples are excluded from knowledge-object equality.

Prefer REUSE existing source adapters/record/reconstruct/label_usage and EXTEND existing correction/read paths. No wrappers, parallel pipeline or unrelated refactor.

## Executed evidence and separate review

Both defects reproduced before production edits: constructed branch-label publication succeeded but read_active_graph raised decision_graph_release_mismatch; literal source merge retained decision_unit_source_fidelity_failure. After repair, 93 targeted tests passed on main cd78d1b (including #489) with isolated PostgreSQL 16; no skips in that run. An additional native correction proof injects failure after actual SQL writes and checks rollback before a successful retry/restart. Full suite and final targeted results are recorded in the PR.

Separate adversarial review reproduced a branch-label span-tampering bypass in the first reader change; validate_hashes now verifies every payload object before exact graph review/label exemption. It also identified overlapping substring ambiguity; find/rfind checks reject it. Wrapper routing is limited to boom + construction marker, matching the receiving kernel. No alternate authority or metadata patch path introduced.

Correction scope: one fragment may be narrowed to a unique exact literal; a multi-fragment merge includes each explicitly referenced fragment in full, modulo whitespace converted to the existing literal newline representation. Partial multi-fragment selections, ambiguous literals and nonliteral prose are rejected, not guessed. Rebuilt versions need new source review and current graph endpoints/review; this is not auto-approval. Markerless compatibility is tested. Existing proza continuation behavior remains unchanged.

Automatic PR review identified a later-primary merge ordering defect. Native submit_review_resolution reproduced the failure; rebuilding now orders verified source units by minimum immutable extraction position, retaining their internally verified span/layout order, matching the existing merge planner. Native forward/predecessor and reverse-insertion grouped merges, restart and absorbed-object supersession are tested; reversed-source-order text is rejected without writes.

The independent follow-up review additionally reproduced reversed PDF insertion versus layout grouping, and finalization overwriting kernel order for interleaved repeated-text fragments. Existing selections retain verified original span order even when extended. Both DeterministicRepairReviewConsole and the native ReviewClosureConsole override use the same pure finalized_source_refs kernel validation: constructed units preserve kernel refs only after exact selected ID/hash/locator equivalence and fidelity validation. Each finalizer retains its own existing revision-patch-hash semantics; markerless behavior remains unchanged. Real-PDF native regressions cover these cases without inventing completeness.

Skill bundled metrics/resources could not be read through skills.read and measure_code_surface.py is absent locally; no complexity metrics are claimed. Git diff supplies exact additions/deletions. The prescribed verify_architecture_invariants.py script is absent; existing tests/test_architecture_invariants.py is executed instead. No browser layout changes or live processing/model acceptance are claimed.
