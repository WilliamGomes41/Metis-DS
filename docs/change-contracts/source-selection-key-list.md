# Bronselectie: lichte sleutellijst (PR-a)

> Historical contract: this key-list API was retired by PR #834 cleanup.
> Production source overviews use compact cards/summaries; no key-list warmup remains.

Change class: B
Promise: GET /source-selection MOET documenten ophalen via een lichte sleutellijst zonder per-document _receipt-deepcopy; HTML, volgorde, zichtbaarheid en verdicts MOGEN NIET wijzigen.
Proof: tests/test_source_selection_key_list_golden.py: golden HTML-gelijkheid (auteur en reviewer, overzicht en gekozen document) tegen het oude list_envelopes-pad; 4 rood op main 7d084fa, groen na; PostgreSQL-variant via workflow_postgres.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Ontwerp: Design B §3.7 (Forge-review), besluit Metis 2026-10-15 (latentiebudget < 45 s live).

## Change

- src/source_selection_ui_v1.py: document_keys(console) en de route gebruiken list_snapshot_ids (PostgreSQL) of de sleutels van de in-memory map (file), in list_envelopes-volgorde.
- src/workflows/workflow_documents_cutover_v1.py: list_snapshot_ids doet dezelfde gezaghebbende read als list_envelopes en vult de read scope, zonder receipts.

Niet geraakt: src/operations_console_v1.py, publicatiepoort, review_configuration, ingest, reservering.

## Limits

OPENVRAAG-B-1 (verdeling van de 17 s in productie) blijft open; deze PR claimt geen productiewinst.
