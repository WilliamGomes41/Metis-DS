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
