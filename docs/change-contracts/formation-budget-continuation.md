# Formation budget continuation repair

Change class: A

PR validation: the lifecycle fields in this contract are mirrored in draft PR #520 because CI validates the pull-request event body.

Promise: bounded Passage Formation V3 may stop at an internal processing deadline without losing validated work, but unfinished source tasks remain explicitly pending and can be resumed until the original source-task plan is fully accounted for.

Touches lifecycle invariants: yes.

Implementation basis: commit `8007b11d1f662f0151551b6647280d21d0ae9603`, the deployed bounded-formation line that produced the supplied Smetten processing evidence.

## Checkpoint-storm follow-up (#523)

The original continuation repair preserved pending source work but the deployed bounded executor still checkpointed once per remaining task after the shared task budget had already expired. On the supplied Smetten resume this produced a roughly 450-second request with 266 database queries.

This follow-up keeps the same lifecycle and authorities. When the remaining task budget is exhausted, the executor records all remaining task ranges in memory as `not_started` with `source_task_budget_exhausted`, requests one durable checkpoint, exits the task loop, and returns control. It must not call the provider after exhaustion.

The dedicated regression uses 50 planned tasks with a zero remaining budget and requires zero provider calls, 50 retained pending tasks, exactly one checkpoint, and `formation_state=pending`.

## Established failure

The supplied Smetten run recorded 67 bounded formation tasks. Seventeen completed, eight were partial and 42 were never started because the shared source-task budget expired. The processing attempt nevertheless ended with transport state `succeeded` while provider evidence recorded `formation_incomplete=true`.

Budget exhaustion is an internal bounded-processing condition, not a billing/credit condition.

## Domain ownership

The WorkingRevision in the Azure/kernel boundary remains authoritative for processing attempts, semantic replay evidence, bounded task history, recovery and publication readiness. The console only projects this state and requests an existing `resume_formation` transition.

No second workflow, source store, approval authority or publication authority is introduced.

## Invariants

- A successful processing attempt is not evidence that formation is complete.
- `formation_state=complete` only when current pending formation findings are empty.
- Every source task stopped by budget exhaustion remains represented by explicit target spans.
- Resume preserves previously validated proposals and operates only on unresolved source work.
- Successful resumes are exempt from the failure-retry cap only when durable evidence proves source-range progress.
- Failed, interrupted and successful-but-stalled resumes consume the failure-retry cap.
- Duplicate resume commands remain idempotent through the existing command id and revision guards.
- Review, publication and source provenance semantics are unchanged.
- Admission is not weakened to compensate for unfinished formation.

## Lifecycle

```
bounded attempt succeeds technically
        |
        +-- no pending formation --> formation complete
        |
        +-- pending formation ----> formation pending
                                      |
                                      +-- resume with progress --> pending or complete
                                      +-- resume without progress/failure --> retry budget consumed
```

The processing attempt may retain its transport/execution state `succeeded`; the distinct durable formation projection prevents that state from being interpreted as document completeness.

## Progress projection

`formation_progress` is derived against the original initial task plan. Recovery may regroup source ranges and therefore receive different task ids; completion is calculated by overlap with the current pending source-range findings rather than by counting historical task ids.

Projected fields:

- `planned_task_count`
- `terminal_task_count`
- `pending_task_count`
- `failed_task_count`
- `partial_task_count`
- `not_started_task_count`

The processing evidence export contract is advanced to v10 and adds `formation_progress.csv`. Processing-attempt evidence also records `formation_progress_made` for resume attempts.

## Admission decision

No automatic sentence-continuation relaxation is part of this repair. The supplied ITD example is a model type-selection problem: `Intertriginous dermatitis (ITD)` was proposed as a definition, while the adjacent continuation states prevalence rather than a definition. Automatically merging and admitting that pair would convert a blocked semantic error into an invalid knowledge object.

The existing literal, source-bound human continuation correction remains available; generic admission constraints remain unchanged.

## Recovery and rollback

No SQL migration and no destructive state migration are required. Existing v9 evidence remains readable; v10 is an additive projection of current stored evidence.

Rollback is code-only: restore the prior bounded-formation/retry projection. Stored task evidence and prior validated knowledge remain intact.

## Acceptance

- budget exhaustion leaves formation pending and publication blocked;
- current status distinguishes processing attempt state from formation state;
- progress survives restart and changes only from durable evidence;
- a resumed source range can resolve a previous budget-exhausted task;
- repeated successful progress-making resumes do not exhaust the failure-retry cap;
- stalled or failed resumes do exhaust that cap;
- recovery authorization uses the same retry-budget semantics;
- evidence export and technical UI show current formation progress;
- admission tests remain unchanged except for lifecycle/progress assertions;
- no deployment or merge is performed as part of this repair.
