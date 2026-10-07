# T9 ReviewKnowledge authority

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes

## Promise and authority
T9 closes content review for richtlijn KnowledgeCandidates. T8 materialisation and Admission remain unchanged. The kernel owns candidate eligibility, current ReviewDuty and actor routing. Console, UI, queues, CLI and SQL projections consume that boundary. Exact-current bindings prove approvals; governance and envelope review_passes do not independently authorize review or publication.

## Lifecycle transition
Initial state: a current WorkingRevision containing source-valid materialised candidates and exact historical bindings.
Trigger: named human submits a review decision with current revision/hash/version.
Validation: candidate integrity, allowed Admission, open current duty, actor policy/stage authorization, expected revision and exact tuple.
Success: object governance, exact binding, reconstructable review ledger and working revision commit together through existing snapshot/store transaction.
Failure: no object/binding/ledger authority commits. Concurrent stale submissions fail closed. A duplicate approval cannot count twice or reclassify a completed candidate.
Mutable owner: existing WorkingRevision kernel/store transaction. Immutable evidence: historical source, decisions and distinct exact tuples. Existing authorization validity is a mutable projection: only a new authorized review may renew a withdrawn identical tuple; the original record remains and each decision has immutable ledger evidence.
Release/serving state: unchanged. No deployment or merge.

## Boundaries and topologies
Structure confirmation remains separate QA. Source disposition remains source evidence. Technical repair is not content review. Beslisboom keeps its own policy/domain route. PostgreSQL and file stores share commands; no migration, new table, side index or lifecycle store.

## Compatibility and mitigation
No T10 source-accountability redesign, T11 durable KnowledgeUnit revision lifecycle or T12 publication-readiness redesign. Changed reviewable content invalidates exact-current authority while preserving history. Existing policy, independent second-review and forbidden agent rules remain enforced. Rollback reverts this follow-up branch; no baseline or data migration.

## Proof matrix
Baseline tests exercise direct apply_reviews on blocked/deterministic/coverage/heading/malformed rows, unstamped text/spans/context/type/relations changes, generator bindings, completed-candidate reclassification, general queue closure, failed commit ledger leakage, stale revision and valid exact approval/reject semantics. Tests-only baseline 45cfc121edaf33f265a787fe2d270840690c15e1 / run 37623790345 demonstrates 14 RED and 2 GREEN GUARD. A separate tests-only renewal regression 9f2c5497afda0d4cfc0995bf9ade4c6893d12a38 / run 37633383488 demonstrates 1 RED and 23 passing checks before the renewal fix. Later tests are additional acceptance coverage, not retrospectively labelled baseline RED. Subsequent proof includes queue parity, direct POST, source/structure/boom separation, four-eyes, duplicate submits, existing T4/T7/T8/T7R and full GitHub CI.

## Baseline
Current main before T9: 0e312a151907afef743f4ca4b65d924f5d56ffb0, merged PR #529, T8 implementation c98c77127ce8d8f68746d7c42a3e03c2f51ba33f. Existing creator/materialisation/Admission/source command boundaries inspected on that exact main. T9 works only on t9-review-knowledge-authority. No merge authorized.

## Machine-readable contract
T9 closes review authority on exact current materialised and admitted richtlijn candidates. Tests preceded production changes. Implementation and compatibility evidence are recorded on PR #532; this contract does not grant merge authority.

Change class: A
Promise: One kernel candidate → ReviewDuty → authorized command → exact binding boundary.
Proof: tests/test_t9_review_knowledge_authority.py against baseline, then regression and full GitHub CI; 14 RED and 2 GREEN GUARD on baseline; renewal regression RED before its fix; final-head acceptance and CI results are recorded on PR #532.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Existing ReviewDuty readers and review command boundary, with no new store or lifecycle.
Why local patching is insufficient: Queue and command rules differ; centralize existing domain helpers rather than independent guards.
Current authority/writer/reader map: Materialiser creates candidates; Admission gates; review_duty_v1 derives stages/routes; OperationsConsole owns current working mutation/bindings/ledger; queues, UI, CLI and SQL consume projections.
Supported runtime topologies: Existing file and PostgreSQL workflow stores; shared kernel, unchanged deployment.
Persisted-state impact: New review transitions only; preserve historical bindings and decisions.
Compatibility/migration plan: No migrations or historical rewrite; structure, source handling and boom stay separate.
Rollback/recovery plan: Revert this unmerged follow-up; existing atomic snapshot rollback/recovery remains owner.
Cutover trigger: Green full CI and separate T9 audit; no merge in this task.
Cleanup/decommission criteria: Remove divergent content-review eligibility rules only after live callers consume the existing kernel.
Failure blast radius: One WorkingRevision; failed/stale review commits no object, binding or approval ledger.
Adversarial proof matrix: A–T in user contract, plus generator bindings, failed store commits and unstamped content mutations.
Lifecycle entity: Current WorkingRevision containing KnowledgeCandidates.
Lifecycle transition: Required first/second human review to exact-current decision/binding.
Initial durable state: Source-valid materialised candidate, allowed Admission, current working revision, historical bindings.
Trigger: Named human submits review decision.
Authorization: Existing roles, named reviewers, policy stage, independent human reviewer, forbidden agents.
Validation: Source integrity, allowed Admission, current ReviewDuty, current revision and exact tuple.
Mutable entities: Existing working objects/governance and binding validity within snapshot store transaction; review ledger is append-only.
Immutable entities: Source bytes, historical revisions and review evidence, published releases.
Workflow state before: Admitted candidate with required content ReviewDuty.
Workflow state after: Exact approve/reject/revise/later evidence, optional independent second duty; non-approval gives no authority.
Release state before: Unchanged existing release.
Release state after: Unchanged existing release.
Serving state before: Unchanged.
Serving state after: Unchanged.
Expected API result: Authorized current review succeeds; stale or unauthorized command fails closed.
Expected UI result: All content review surfaces consume same duty; separate structure/source/boom routes remain.
Failure result: No partial object/binding/audit authority.
Restart result: Durable exact-current binding matches committed candidate only.
Recovery result: Existing technical repair routes; no new repair lifecycle.
Legacy-data result: Historical evidence retained; malformed/noncandidate rows acquire no content review authority.
Required black-box scenario: Open candidate X; another actor changes working revision; old submit conflicts and commits no approval evidence.
Explicit non-goals: T8 redesign, T10 source lifecycle, T11 revisions/supersedes, T12 readiness, migrations, Azure, deployment or merge.

Baseline main: 0e312a151907afef743f4ca4b65d924f5d56ffb0 (merged #529).
Branch: t9-review-knowledge-authority.
Contract: docs/change-contracts/t9-review-knowledge-authority.md.

T9 result: see the exact-head evidence report on PR #532.
Merge nieuwe T9-PR: NO-GO

## Storage and concurrency refinement
The existing PostgreSQL UNIQUE tuple already represents one authorization per exact approval. `record_authorization` preserves distinct historical tuples and the original identical tuple record, updating only validity after an explicitly authorized renewal. Reassigning a reviewer does not renew it. Ledger and participation history retain decisions and withdrawn evidence. No schema/migration is required.

All review relation changes are prepared before the final pinned commit. Stale conflicts skip restorative writes in file/document/review adapters, preserving competing writers. File-backed commands reload durable envelope and bindings while holding the store lock, so a second worker cannot authorize against an old in-memory approval view.

PR: #532. CI and a separate T9 audit are required before release consideration.

The adversarial acceptance matrix also exercises direct console denial for blocked/deterministic/coverage/heading/malformed rows, actual first/independent-second commands, forbidden reviewer-account aliases, and explicit cross-domain binding exclusion. Legacy bindings without a domain retain their exact-current contract; a binding explicitly recorded for another domain cannot authorize richtlijn KnowledgeCandidate review.

## Closing HTTP concurrency audit
On tests-only head 8cfe5b0a6798d816ea9f021e70ce9030a2875eda, GitHub CI run 37651082783 showed three genuine RED cases: omitted, empty and whitespace snapshot_revision on POST /review all returned 303 instead of refusing review (44 existing T9 cases passed). The HTTP first/second review boundaries now require the existing snapshot_revision pin before mutation, matching the existing normal-risk batch boundary. The kernel rechecks that revision under the existing atomic mutation/store transaction. Trusted Python compatibility helpers retain their existing optional argument; public content-review forms cannot discard the reviewed revision. No new authority/store or T10–T12 lifecycle was introduced.


## Pre-merge review closure
Automatic review on 6e23c625 found one blocking metrics regression and an outdated README CLI invocation. Tests-only 75ea9b3 followed by the focused CI step on 749c597 (run 37658526880, job 112919840344) proved 4 genuine RED / 42 passing: admitted recommendation/condition/exception workload was 0.0 instead of 1.0 and high-risk definition workload was 0.0 instead of 0.5.

Extraction gold has no live WorkingRevision/source/binding input. Its offline workload diagnostic now reuses existing slow type, lane and risk facts without calling the live ordinary review queue. This diagnostic neither creates ReviewDuty nor grants approval; regression guards keep the live queue empty without authoritative fragments and prove input objects unchanged. Content duty/command authority remains source-valid and fail-closed. The README now supplies required raw-extract and bindings inputs and explains the read-only export.

This bounded repair changes no Admission, materialisation, review store, schema or lifecycle semantics. The existing GitHub CI matrix runs both metrics suites before T9 and the full suite. Merge remains gated on the new head's complete checks and review.
