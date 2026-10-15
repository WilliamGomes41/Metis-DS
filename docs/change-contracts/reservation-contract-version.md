# Semantic contract version at reservation

Change class: B
Promise: Every attempt reserved by processing_retry_v1.reserve MOET record `reserved_semantic_contract_version`, derived read-only from the envelope's processing configuration, and keep it whatever the outcome (succeeded, failed, interrupted); reservation, retry, resume, verdicts and replay identities MAG NIET change.
Proof: tests/test_reservation_contract_version.py (8 red on 8db82cb, 9 green after), including identical helper output versus the replay identity built at pre_review_semantic_v1:585 and a real resume reservation; existing suites unchanged.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Forge acked this item with limits (only READ the processing configuration).

## Change

- `src/pre_review_semantic_v1.py`: the contract string at line 585 moves unchanged into
  `semantic_contract_version(field_contract_v2, field_contract_v3)` (identical output, used by
  `build_replay_identity` and by reservation). `semantic_contract_version_for_mode(mode)` maps
  v3 / v2 / v1 semantic modes; every other mode MOET map to `None`.
- `src/processing_retry_v1.py` `reserve()`: reads `envelope["processing_configuration"]["mode"]`
  and stores `reserved_semantic_contract_version` on the new attempt. The configuration
  MAG NIET be written. Legacy attempts are NOT backfilled.
- Not touched: `src/operations_console_v1.py`, `OperationsConsole.ingest`, upload form,
  `review_participation_ui_v1.py`, review_configuration paths, publication gate.

## Limits

Attempts are reserved after the caller set `processing_configuration` on the Bronselectie
start (`source_selection_v1.reserve_selection`) and resume (`resume_formation`) paths, so
their value is exact. The ingest reservation (`operations_console_v1.py` line 1896, inside
`OperationsConsole.ingest`, Forge #626 region) and the re-extract reservation (line 2410)
run without a stored configuration on a first ingest and then record `None`.

OPENVRAAG-RESV-1: MOETEN the ingest (line 1896) and re-extract (line 2410) reservations pass
the active configuration? That change lies in operations_console_v1.py (ingest is Forge #626).
OPENVRAAG-RESV-2: the legacy retry path (`operations_console_v1.py` line 2353) reads whatever
configuration the envelope stores; MOET it be refreshed before reservation?
