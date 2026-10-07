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
Mutable owner: existing WorkingRevision kernel/store transaction. Immutable evidence: historical source, decisions and exact bindings; no rewriting of old evidence.
Release/serving state: unchanged. No deployment or merge.

## Boundaries and topologies
Structure confirmation remains separate QA. Source disposition remains source evidence. Technical repair is not content review. Beslisboom keeps its own policy/domain route. PostgreSQL and file stores share commands; no migration, new table, side index or lifecycle store.

## Compatibility and mitigation
No T10 source-accountability redesign, T11 durable KnowledgeUnit revision lifecycle or T12 publication-readiness redesign. Changed reviewable content invalidates exact-current authority while preserving history. Existing policy, independent second-review and forbidden agent rules remain enforced. Rollback reverts this follow-up branch; no baseline or data migration.

## Proof matrix
Baseline tests exercise direct apply_reviews on blocked/deterministic/coverage/heading/malformed rows, unstamped text/spans/context/type/relations changes, generator bindings, completed-candidate reclassification, general queue closure, failed commit ledger leakage, stale revision and valid exact approval/reject semantics. RED versus GREEN GUARD classification will be recorded from baseline CI before production changes. Subsequent proof includes queue parity, direct POST, source/structure/boom separation, four-eyes, duplicate submits, existing T4/T7/T8/T7R and full GitHub CI.

## Baseline
Current main before T9: 0e312a151907afef743f4ca4b65d924f5d56ffb0, merged PR #529, T8 implementation c98c77127ce8d8f68746d7c42a3e03c2f51ba33f. Existing creator/materialisation/Admission/source command boundaries inspected on that exact main. T9 works only on t9-review-knowledge-authority. No merge authorized.

## Machine-readable contract
T9 closes review authority on exact current materialised and admitted richtlijn candidates. Tests precede production changes; implementation is pending.

Change class: A
Promise: One kernel candidate → ReviewDuty → authorized command → exact binding boundary.
Proof: tests/test_t9_review_knowledge_authority.py against baseline, then regression and full GitHub CI; baseline results pending.
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
Mutable entities: Existing working objects/governance, review bindings and ledger within snapshot store transaction.
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

T9: NOT DONE
Merge nieuwe T9-PR: NO-GO
