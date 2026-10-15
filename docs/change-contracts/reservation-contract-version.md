# Semantic contract version at reservation

Change class: B
Promise: Every attempt reserved by processing_retry_v1.reserve MOET record `reserved_semantic_contract_version`, derived from the envelope's processing configuration, and keep it whatever the outcome (succeeded, failed, interrupted). On the retry path (`retry_pre_review`, RESV-2) the configuration in force MOET be written to the envelope before a fresh reservation; when it is unreadable the retry MOET be refused with `processing_configuration_unavailable` and no attempt MAG NIET be reserved. Other reservation paths MAG NIET write the configuration. Resume, verdicts and replay identities MAG NIET change.
Proof: tests/test_reservation_contract_version.py (8 red on 8db82cb, 9 green after; the 2 RESV-2 tests red on a3c5d58, green after; 11 total), including identical helper output versus the replay identity built at pre_review_semantic_v1:585 and a real resume reservation; existing suites unchanged.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Forge acked this item with limits (only READ the processing configuration).

## Change

- `src/pre_review_semantic_v1.py`: the contract string at line 585 moves unchanged into
  `semantic_contract_version(field_contract_v2, field_contract_v3)` (identical output, used by
  `build_replay_identity` and by reservation). `semantic_contract_version_for_mode(mode)` maps
  v3 / v2 / v1 semantic modes; every other mode MOET map to `None`.
- `src/processing_retry_v1.py` `reserve()`: reads `envelope["processing_configuration"]["mode"]`
  and stores `reserved_semantic_contract_version` on the new attempt; `reserve()` itself
  MAG NIET write the configuration (only `retry_pre_review` writes it, RESV-2). Legacy attempts are NOT backfilled.
- `src/operations_console_v1.py` lines 2353-2358 only (RESV-2). Not touched: `OperationsConsole.ingest`, upload form,
  `review_participation_ui_v1.py`, review_configuration paths, publication gate.

## Limits

Attempts are reserved after the caller set `processing_configuration` on the Bronselectie
start (`source_selection_v1.reserve_selection`) and resume (`resume_formation`) paths, so
their value is exact. The ingest reservation (`operations_console_v1.py` line 1896, inside
`OperationsConsole.ingest`, Forge #626 region) and the re-extract reservation (line 2410)
run without a stored configuration on a first ingest and then record `None`.

OPENVRAAG-RESV-1: MOETEN the ingest (line 1896) and re-extract (line 2410) reservations pass
the active configuration? That change lies in operations_console_v1.py (ingest is Forge #626).
DECIDED RESV-2 (Metis, Forge cleared): `retry_pre_review` (`operations_console_v1.py` lines 2353-2358)
MOET refresh `processing_configuration` from `source_selection_v1.configuration` before a fresh
reservation and MOET fail closed with `processing_configuration_unavailable` (no attempt reserved)
when the refresh fails. Duplicate commands are unchanged.

## Correction after Sherlock retro-audit (record only)

- The original Promise said the configuration "MAG NIET be written"; RESV-2 writes it on the retry
  path. The Promise above is the corrected record; the code on main is unchanged by this correction.

## RESV-1 F3: mid-flight deploy (fixed in #639)

Rule: a NEW retry attempt MOET pin a deepcopy of the configuration it was reserved under; when a
deploy changes the configuration before execution, the attempt MOET stop with
`processing_configuration_changed` before any provider call. A returned (duplicate) attempt MAG NIET
get its configuration overwritten. Without a configuration the retry MOET fail closed with
`processing_configuration_unavailable` before commit (no attempt, NOOIT KeyError).

Code: `operations_console_v1.py` `retry_pre_review`, the `if fresh:` block directly after
`reserve()`. This line is OUTSIDE the #630 scope (not among the lines #630 added); Forge cleared it.
Proof: tests/test_reservation_contract_version.py: 4 tests red at 83fc6a8 (mid-flight, duplicate
keeps pin, copy not reference, legacy fail-closed), green at dd3b663. The xfail marker is removed.
