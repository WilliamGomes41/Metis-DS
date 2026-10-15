# A3 attempt correctness (reproduction only)

Change class: B
Promise: A budget-exhausted attempt MOET NOOIT as 'succeeded' be stored, and 'Hervatten' MAG NIET be offered or accepted after a semantic contract-version change. This draft contains ONLY the fail-first reproduction; the fix is STOPPED because it requires src/operations_console_v1.py (Forge MOET be informed first).
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
Workflow state after: NOT changed by this draft (reproduction only)
Release state before: unchanged
Release state after: unchanged
Serving state before: unchanged
Serving state after: unchanged
Expected API result: NOT changed by this draft
Expected UI result: NOT changed by this draft
Failure result: NOT changed by this draft
Restart result: NOT changed by this draft
Recovery result: NOT changed by this draft
Legacy-data result: NOT changed by this draft
Required black-box scenario: tests/test_a3_attempt_correctness.py (file and HTTP Bronselectie route)
Explicit non-goals: no fix in this draft; no change to operations_console_v1.py, publication gate, ingest or review_configuration

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

OPENVRAAG-A3-1: which stored state MOET a budget-exhausted attempt get? A new
state (for example `budget_exhausted`) keeps bounded continuation outside the
retry cap; reusing `interrupted` or `failed` would make every bounded continuation
consume the cap (guard test `test_budget_exhausted_resume_with_progress_does_not_consume_retry_budget`).
OPENVRAAG-A3-2: MOET a contract change compare the full version string, or only
the components that alter formation output?
