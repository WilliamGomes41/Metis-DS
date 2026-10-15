# Bronselectie: estimate eenmaal per verzoek (PR-b)

Change class: B
Promise: De vergelijkbare metingen voor estimate MOETEN één keer per verzoek over alle documenten berekend worden, NOOIT per document; de uitkomst van estimate MAG NIET wijzigen (selectieregels identiek).
Proof: tests/test_estimate_linear_golden.py: golden-gelijkheid tegen een letterlijke kopie van de oude estimate over 25 willekeurige corpora x 3 configuraties en de 0.5/2.0-grenzen; routetest (één opbouw per verzoek) rood op main 7d084fa, groen na.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Ontwerp: Design B §3.7 (Forge-review), besluit Metis 2026-10-15 (latentiebudget < 45 s live).

## Change

- src/source_selection_v1.py: comparable_observations(documents) (één doorloop), estimate(envelope, documents, *, observations=None) met ongewijzigde publieke uitkomst, projection(..., observations=None).
- src/source_selection_ui_v1.py: de route berekent observations één keer en geeft ze door.

Niet geraakt: src/operations_console_v1.py, publicatiepoort, review_configuration, ingest, reservering.

## Limits

OPENVRAAG-B-1 (verdeling van de 17 s in productie) blijft open; deze PR claimt geen productiewinst.
