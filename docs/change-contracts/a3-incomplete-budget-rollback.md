# #628 rewrite risk HIGH: rollback plan for the durable 'incomplete_budget' state

Rewrite risk: high (reclassified after Sherlock retro-audit / Codex). This document is the rollback plan; it changes no code.

## What is durable
- `processing_attempts[].state = 'incomplete_budget'` (new value), `phase = 'budget_stopped'`, `stop_reason`, `semantic_contract_version`, `reserved_semantic_contract_version`, `processing_configuration` on attempts.
- No backfill: existing 'succeeded' attempts were NOT rewritten.

## Readers that MOETEN understand the state
status/retry cap (processing_retry_v1), source_selection_v1 (Hervatten/onderbroken), source_selection_ui_v1, blockage_diagnostics_v1, processing_trace_v1, duplicate-command receipts (operations_console_v1 `{"succeeded","incomplete_budget"}`).

## Rollback rules
- Rollback MOET be a code revert to a commit that still reads 'incomplete_budget' (any main from #628 on). A deploy of code older than #628 MAG NIET happen while any stored attempt has state 'incomplete_budget': older code treats it as unknown (not running, not succeeded), so the retry cap and status would differ.
- Stored records MAG NIET be rewritten during rollback; NOOIT convert 'incomplete_budget' to 'succeeded' (that is the A3 defect).
- Pre-rollback check, in this order (Codex P1 on #639): a zero count is only a point-in-time observation, so attempt writers MOETEN be stopped first.
  1. Stop admission: set `METIS_PROCESSING_ADMISSION=closed` on every instance and restart them. `processing_retry_v1.reserve()` then refuses every new ingest, Bronselectie, hervat-, re-extract- or retry-attempt with `processing_admission_closed`.
  2. Drain: wait until no attempt has state 'running' (or until `expire_running` has marked it 'interrupted'). The check MAG NIET start while any attempt is 'running'.
  3. Run `python scripts/processing_rollback_precheck.py --postgres` (or `--envelopes-file <runtime>/envelopes.json` for the file backend). It is read-only. Exit 0: no attempt is `running` or `incomplete_budget`, so rollback past #628 is safe. Exit 2: wait (running) or roll back only to a #628+ commit (incomplete_budget). Exit 1: the store is unreadable; rollback past #628 MAG NIET start.
  4. Admission MOET stay closed until the rollback target is deployed and running. A rollback target older than #639 does not read `METIS_PROCESSING_ADMISSION`, so the console MOET stay stopped through the cutover. Reopening admission between the count and the cutover voids the count; the check MOET then start again at step 1.
- Forward fix is preferred over rollback.

## Cutover
No migration; new value only on new attempts. Legacy attempts keep their state.

OPENVRAAG-A3-RB-1: if a rollback past #628 is ever required with non-zero records, the mapping (to 'interrupted'?) MOET be decided by Metis before; there is no automatic mapping.
