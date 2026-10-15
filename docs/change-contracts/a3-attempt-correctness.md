# A3 attempt correctness

Change class: B
Promise: A budget-exhausted attempt MOET NOOIT as 'succeeded' be stored on the cleared execution path (new state 'incomplete_budget', never counted against the retry cap), and 'Hervatten' MAG NIET be offered or accepted after any change of the full semantic contract identifier. The ingest path (line 2012) follows after #626.
Proof: tests/test_a3_attempt_correctness.py: 6 tests fail on 8db82cb with the named defect markers (BUDGET_EXHAUSTED_STORED_AS_SUCCEEDED, RESUME_OFFERED_AFTER_CONTRACT_CHANGE, HERVATTEN_OFFERED_AFTER_CONTRACT_CHANGE, semantic_replay_policy_mismatch after work started); 1 guard test passes. CI on this draft MOET be red on exactly these 6 tests.
Touches lifecycle invariants: yes
Rewrite risk: none
Lifecycle entity: processing attempt
Lifecycle transition: running -> terminal (finish) and terminal -> resume offer
Initial durable state: attempt 'running' in processing_attempts
Trigger: finish() after bounded formation; Bronselectie / processing_status read; resume command
Authorization: unchanged (researcher or named reviewer)
Validation: stop evidence from current replay; stored versus current semantic contract version
Mutable entities: processing attempt record
Immutable entities: source, extraction, objects, verdicts, hashes, publications
Workflow state before: budget-exhausted attempt stored 'succeeded'; resume offered after contract change
Workflow state after: re-extract execution stores 'incomplete_budget'; resume_allowed False and resume rejected with processing_resume_configuration_incompatible when the contract identifier differs
Release state before: unchanged
Release state after: unchanged
Serving state before: unchanged
Serving state after: unchanged
Expected API result: resume command returns processing_resume_configuration_incompatible before any work
Expected UI result: Bronselectie shows no Hervatten after a contract change; a budget stop shows 'onderbroken' with done/open task counts
Failure result: unchanged for failed/interrupted attempts
Restart result: stored state survives restart (durable attempt record)
Recovery result: continuation allowed only with an unchanged contract identifier
Legacy-data result: existing 'succeeded' attempts are NOT rewritten; no backfill
Required black-box scenario: tests/test_a3_attempt_correctness.py (file and HTTP Bronselectie route)
Explicit non-goals: no change to line 2012 (ingest finish), 1896 (ingest reservation), 2212 (resume receipt) until #626 merges; no change to 2410 (waits for RESV-1); no publication-gate change

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG.

## Reproduced defects (base 8db82cb)

1. `finish(state="succeeded")` stores `succeeded` when the current replay has
   `formation_incomplete: true` with `source_task_budget_exhausted`
   (ingest, retry and resume).
2. After a semantic contract-version change (`pre_review_semantic_v1.py:585`):
   `processing_status()["resume_allowed"]` stays `True`; Bronselectie renders
   the `Hervatten` button; `resume_formation` reserves an attempt and starts work,
   then fails late with `semantic_replay_policy_mismatch` (consuming retry budget)
   instead of rejecting up front with `processing_resume_configuration_incompatible`.

## Regions the fix MOET change (Forge MOET be informed first)

- `src/operations_console_v1.py` `processing_status` lines 2155-2159 (`resume_allowed`)
  and `_can_resume_formation` lines 2171-2185: compare stored with current contract.
- `src/operations_console_v1.py` `finish(..., state="succeeded")` call sites at
  line 2012 (inside `ingest`, Forge #626 region) and line 2521
  (`_execute_source_attempt`), plus duplicate-command receipts at lines 2212
  (`resume_formation`) and 2356 (retry), which return a receipt only for `succeeded`.
- Outside the gated file: `src/processing_retry_v1.py` (`finish`, `_retry_budget_attempts`,
  `status`), `src/source_selection_v1.py` (`assert_resume_configuration`, `projection`),
  `src/pre_review_semantic_v1.py:585` (extract the contract string into one helper
  with identical output).

## Open questions

DECIDED A3-1 (Metis): 'incomplete_budget'. Former question: which stored state MOET a budget-exhausted attempt get? A new
state (for example `budget_exhausted`) keeps bounded continuation outside the
retry cap; reusing `interrupted` or `failed` would make every bounded continuation
consume the cap (guard test `test_budget_exhausted_resume_with_progress_does_not_consume_retry_budget`).
DECIDED A3-2 (Metis): full identifier. Former question: MOET a contract change compare the full version string, or only
the components that alter formation output?

## Implemented (Forge cleared 2156-2159, 2171-2185, 2356, 2410, 2521)

- `operations_console_v1.py` line 2156 (import) and 2158 (`resume_allowed` requires `resume_contract_current`);
  line 2357 (retry duplicate receipt accepts `incomplete_budget`); line 2522 (`finish(..., budget_aware=True)` in `reextract_unpublished`).
- `processing_retry_v1.py`: `formation_budget_exhausted`, `finish(budget_aware=...)` -> `incomplete_budget`; `_retry_budget_attempts` MAG NIET count it.
- `source_selection_v1.py`: `resume_contract_current` (full identifier equality) used by `assert_resume_configuration` and processing status; projection shows a budget stop as 'onderbroken' with `budget_stopped`.
- `source_selection_ui_v1.py`: done/open task counts; `processing_trace_v1.py`, `blockage_diagnostics_v1.py`: closed state sets include `incomplete_budget`.
- `pre_review_semantic_v1.py`: contract string extracted into `semantic_contract_version()` (identical hunk to #630).

Still open: ingest finish (2012) is a strict xfail test until #626 merges; the resume duplicate receipt (2212) does not yet accept `incomplete_budget`.

OPENVRAAG-A3-3 (from A3-2 'a fresh attempt starts instead'): after a contract change the existing unreviewed candidates block a fresh start (`pre_review_retry_existing_work`). MOET a fresh attempt retire those candidates? That changes `reserve_selection` and existing-work rules.
