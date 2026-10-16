# A3 F2: budget stops without progress count toward the retry cap

Change class: B
Promise: An 'incomplete_budget' attempt WITHOUT formation_progress_made == True MOET count toward the retry cap; only budget stops (and successful resumes) with proven formation progress MAG NIET count. A missing progress marker MOET be treated as no progress (fail-closed).
Proof: tests/test_a3_attempt_correctness.py: test_budget_stops_without_progress_reach_the_retry_cap[retry|resume] and test_budget_stop_without_recorded_progress_counts_fail_closed fail on main 1624da7 (NO_PROGRESS_BUDGET_STOP_FREE, 0 == 2) and pass after the fix; the progress guard test stays green.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Source: Sherlock retro-audit #628 F2; Metis A3-1 intent.

## Change

- src/processing_retry_v1.py `_retry_budget_attempts`: an attempt is free only when `formation_progress_made is True` and it is either `incomplete_budget` or a succeeded `resume`. Everything else counts.
- tests/test_a3_attempt_correctness.py: the old test that asserted "incomplete_budget never counts, even without progress" encoded the wrong intent and is replaced by the red tests above.

Not touched: src/operations_console_v1.py, the publication gate, the stored attempt schema, existing records (no backfill).

## Limits

- Progress is computed only for `kind == "resume"` attempts (operations_console_v1 ~2610). A budget stop on a fresh retry/ingest therefore always counts. That is fail-closed and intended here.
- OPENVRAAG-A3-F2-1: MOET a fresh (non-resume) budget stop with progress also be free? Requires computing progress outside operations_console_v1 resume branch; Metis decides.
