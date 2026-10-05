# Semantic source-bound V4

Change class: A
Rewrite risk: none
Promise: New ingest or an explicit successor may form source with METIS_PASSAGE_FORMATION_MODE=semantic-source-bound-v4. Understandable source text is not automatically answer-bearing knowledge. Large guidelines stay bounded and resumable, and formation stays incomplete until the original plan is accounted for. Review and publication stay human.
Proof: tests/test_semantic_source_bound_v4.py, tests/test_bounded_formation_v1.py, passage-register gold, closed review loop, recoverable formation, source accountability, replay and publication-readiness tests. PostgreSQL resume and crash-safe support confirmation must actually run with METIS_TEST_POSTGRES_DSN; a skip is not acceptance proof.
Touches lifecycle invariants: yes

Lifecycle entity: WorkingRevision formation evidence, passage register and confirmed supported_by relations on unpublished knowledge objects.
Lifecycle transition: semantic-source-bound-v3 or earlier processing to an explicit semantic-source-bound-v4 formation attempt, including bounded resume of that same plan.
Initial durable state: verified immutable source and, on resume, the stored formation plan plus validated proposal history in the existing working revision.
Trigger: authorized new ingest or explicit reprocessing with METIS_PASSAGE_FORMATION_MODE=semantic-source-bound-v4, or resume_formation on an unpublished V4 plan.
Authorization: existing researcher ingest and named-reviewer commands. ConfirmSupportTargets requires the reviewer role, a named reviewer, command_id and expected_revision.
Validation: existing admission, source-accountability-v3 role checks, relation_endpoint_compatible, and formation complete only when pending tasks, unknown work, pending source ranges and unaccounted source ranges are all empty.
Mutable entities: unpublished working-revision objects, passage register, confirmed relations, formation-plan evidence and one audit decision.
Immutable entities: immutable source bytes, published revisions, review evidence already committed, and the closed object and relation taxonomies.
Workflow state before: unpublished source, formation not started or a V4 plan with pending ranges.
Workflow state after: formation pending or complete. Support without a confirmed target stays not_yet_assessed. Confirmed targets become linked_as_support only inside the same commit.
Release state before: not published.
Release state after: not published. V4 does not publish.
Serving state before: unchanged. Unpublished objects are not served.
Serving state after: unchanged. No serving effect.
Expected API result: processing may succeed while formation_state stays pending; ConfirmSupportTargets returns one result or rejects with no partial edges.
Expected UI result: the console projects the existing formation mode, including semantic-source-bound-v4, and does not gain a second formation authority.
Failure result: provider failure leaves the affected range pending or unresolved; stale revision and commit failure roll back; no partial supported_by edges.
Restart result: the stored plan, completed and pending ranges, validated proposals and confirmed relations are read back from the working revision.
Recovery result: resume continues the same plan from the persisted source representation, sends only open ranges, and does not re-extract. A missing or mismatched representation fails closed.
Legacy-data result: V3 and earlier documents stay readable. No startup migration rewrites reviewed or published revisions.
Required black-box scenario: synthetic Smetten sentences prove background is not a recommendation, context stays context, support links only after confirmed targets, unresolved text blocks source closure, budget exhaustion keeps one checkpoint, and resume skips completed ranges.
Explicit non-goals: no production activation of semantic-source-bound-v4, no merge, no deploy, no canonical-store migration, no new object type, no new relation type, and no clinical completeness claim.

## Established

- V3 remains `semantic-source-bound-v3` with `source-accountability-v2` and `bounded-formation-v1`.
- WorkingRevision evidence remains the formation authority. The console only projects it.
- Knowledge types stay the closed set. `background` is not added.
- `supported_by` stays the support relation. No new relation type.
- Draft PR #523 already bulk-checkpoints V3 budget exhaustion. That repair is integrated, not rewritten.

## Defects this contract closes

- Section role `support` and an explanation type stamped `linked_as_support` without a confirmed edge.
- Budget exhaustion wrote one durable checkpoint per unstarted task.
- V3 replay identity could not name a V4 contract, so a V4 run needs its own prompt, schema and contract version.

## Contracts

- `semantic-source-bound-v4` / `source-bound-fields-v4`: source function plus the existing V3 literal fields.
- `bounded-formation-v2` / `formation-plan-v4`: deterministic plan, bounded execution, one exhaustion checkpoint, resume of open ranges only.
- `source-accountability-v3`: machine roles `metadata`, `structure`, `background`, `context`, `support`, `answer_bearing`, `unresolved`.

`linked_as_support` is stored only when a confirmed `supported_by` edge exists, or when `ConfirmSupportTargets` records that edge and the disposition in one commit.

## Non-changes

No canonical-store migration. No immutable-source migration. No publication-path change. No second store. Reviewed and published revisions are not rewritten on startup. Rollback is code and configuration only. The default formation mode stays `semantic-source-bound-v2`.

## Acceptance

- Same source and contract produce the same plan hash.
- Background text can be proposed without becoming a recommendation or a new object type.
- Support without a confirmed target stays `not_yet_assessed`.
- One command can confirm three `supported_by` edges atomically.
- Fifty unstarted tasks at budget zero make zero provider calls and one exhaustion checkpoint.
- Resume sends only still-open source ranges.
- Formation complete still requires no pending source range. Technical attempt success does not.
- Publication stays blocked until the existing review and governance gates pass.
