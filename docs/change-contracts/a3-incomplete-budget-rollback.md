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
- Pre-rollback check (read-only): count attempts with state 'incomplete_budget' in workflow.documents envelope_payload (PostgreSQL) or the runtime store (file). Zero: rollback past #628 is safe. Non-zero: roll back only to a #628+ commit.
- Forward fix is preferred over rollback.

## Cutover
No migration; new value only on new attempts. Legacy attempts keep their state.

OPENVRAAG-A3-RB-1: if a rollback past #628 is ever required with non-zero records, the mapping (to 'interrupted'?) MOET be decided by Metis before; there is no automatic mapping.
