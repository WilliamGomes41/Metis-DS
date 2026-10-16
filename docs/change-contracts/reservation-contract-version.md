# Semantic contract version at reservation

Change class: B
Promise: Every attempt reserved by processing_retry_v1.reserve MOET record `reserved_semantic_contract_version`, derived from the envelope's processing configuration, and keep it whatever the outcome (succeeded, failed, interrupted). On the retry path (`retry_pre_review`, RESV-2) the configuration in force MOET be written to the envelope before a fresh reservation; when it is unreadable the retry MOET be refused with `processing_configuration_unavailable` and no attempt MAG NIET be reserved. `processing_retry_v1.reserve()` itself MAG NIET write the configuration. The surrounding reservation paths keep writing it as before: `source_selection_v1.reserve_selection` (Bronselectie start and resume) and `OperationsConsole.ingest` MOETEN store the configuration before they reserve (correction after Codex P2 on #639). Resume, verdicts and replay identities MAG NIET change.
Proof: tests/test_c2_pinned_configuration_fence.py, tests/test_c3_processing_admission.py and tests/test_reservation_contract_version.py (8 red on 8db82cb, 9 green after; the 2 RESV-2 tests red on a3c5d58, green after; 11 total), including identical helper output versus the replay identity built at pre_review_semantic_v1:585 and a real resume reservation; existing suites unchanged.
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
  MAG NIET write the configuration. Writers around reserve(): `retry_pre_review` (RESV-2),
  `source_selection_v1.reserve_selection` and `OperationsConsole.ingest`. Legacy attempts are NOT backfilled.
- `src/operations_console_v1.py` lines 2353-2358 only (RESV-2). Not touched: `OperationsConsole.ingest`, upload form,
  `review_participation_ui_v1.py`, review_configuration paths, publication gate.

## RESV-2 decision

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

## #628 F3: reserve → execute configuration change on re-extract and ingest

Documented outcome: the command MOET be refused with `processing_configuration_changed`, the attempt MOET end
`failed` with that error_code, and no new objects MAG NIET be written. Re-extract already did this
(passing test). Ingest returned `processing_command_conflict`: `source_preparation_context_v1.retain` now
separates the configuration check from the identity check. Tests: tests/test_resv1_reservation_configuration.py,
red at 3dbff26 (ingest), green at 07c55dc.

## Codex findings on 97c458b and Sherlock 02:55 (fixed in this PR)

- C2 / Codex P1, one fence: `src/source_preparation_context_v1.py` `build_formation_context` MOET compare the attempt's pinned configuration with `active_configuration` as its first step, before every early return (non-HTML/PDF, beslisboom, resume checkpoint) and before extraction. A difference MOET give `processing_configuration_changed`. An attempt without a pinned configuration (absent or empty) MOET be refused with `processing_configuration_unpinned`; there is NOOIT an exemption. The separate check before the reuse return in `retain()` (6cb2953) is removed; the in-transaction check in `retain()` (#628 F3) stays. Proof: `tests/test_c2_pinned_configuration_fence.py`, 7 red at 78f05ed, green at bcd953f; extractor sentinel count MOET be 0 on refusal.
- C3, admission: `METIS_PROCESSING_ADMISSION` with a value other than unset, empty or `open` MOET refuse every new reservation in `processing_retry_v1.reserve()` with `processing_admission_closed` (fail-closed). The ingest reservation goes through `reserve()` and MOET be refused the same way, with no envelope stored. A repeated command_id MOET return its existing attempt. `scripts/processing_rollback_precheck.py` is read-only (PostgreSQL `BEGIN READ ONLY` + rollback, or a file read) and MOET exit 2 while any attempt is `running` or `incomplete_budget`, 1 when the store is unreadable, 0 only when clean. Proof: `tests/test_c3_processing_admission.py`, 12 red at 95c4f36, green at 98bac0c.
- C6 / Codex P2, exact counters: the fence tests MOETEN count each stage on its own call (`console._extract`, `strategy.prepare`, provider HTTP). Proof: with the 97c458b version of `source_preparation_context_v1.py` the reuse test is red with `extract: 1`.
- Codex P2 doc: the promise above is narrowed to `reserve()` itself.
- `operations_console_v1.py` and the publication gate are not touched.
