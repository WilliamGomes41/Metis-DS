# Selectiebegeleiding — technische proef

16 november 2026, main-basis `9245b3bfe8d0bd7338a77bd67afce8d51fd5d53d`.
Alle broninhoud in deze proef is synthetisch. Geen externe modelaanroepen:
de bestaande fixture vervangt alleen provider-I/O; HTTP, bronbinding en
PostgreSQL-opslag zijn echt.

- Gerichte run: 46 passed, 20 deselected (34,62 s).
  Bestanden: `test_architecture_invariants.py`,
  `test_human_annotation_materialisation.py`, `test_human_annotation_preview.py`,
  `test_human_annotation_reading_view.py`, `test_annotation_suggestions.py` en
  de `browser_annotation_suggestions_check`-parameter in
  `test_browser_knowledge_context.py`.
- Laatste browserrun na normaliseren van de screenshot-scrollpositie:
  1 passed, 20 deselected (22,15 s).
- Browser: Chromium, Playwright; desktop 1440 × 1100 en mobiel 390 × 844.
  [Desktop](selection-guidance-desktop.png), [mobiel](selection-guidance-mobile.png).
- Aangetoond: openen/sluiten via Enter, behoud van focus bij de helpknop,
  correcte `aria-expanded`/`aria-controls`, geen horizontale overflow op mobiel,
  geen POST-verzoeken door hulpbediening, exact ongewijzigde API-toestand na
  herhaald openen en sluiten. De bestaande proef doorloopt daarna nog opslaan,
  typecorrectie, bronselectie tijdens een modelantwoord en providerfoutherstel.
- Omgeving: Python 3.12, repositorydependencies in een geïsoleerde virtualenv,
  PostgreSQL 16.11 gebouwd onder `/workspace` omdat systeeminstallatie niet
  beschikbaar is. Geen productdependencies gewijzigd.

Reproduceren met een beschikbare test-PostgreSQL en browser:

```sh
bash scripts/test_postgres.sh
python -m pytest -q tests/test_browser_knowledge_context.py \
  -k browser_annotation_suggestions_check
```

Zet `METIS_BROWSER_EXECUTABLE` en `METIS_PLAYWRIGHT_MODULE` zoals in de bestaande
CI-browserjob. Zet ook de PostgreSQL-clienttools op PATH voor de volledige suite.
De eerste brede run is onderbroken nadat 20 tests alleen door ontbrekende `psql`
op PATH faalden; dat omgevingsprobleem is hersteld voor de vervolgrun.

Dit is geen gebruikersproef, volledige screenreadertest of bewijs dat menselijke
KO-selecties inhoudelijk beter worden. De vergelijkende acceptatie met medewerkers
uit PR #1092 blijft open. De Impeccable-engine was niet beschikbaar; de vendored
richtlijnen zijn rechtstreeks toegepast, geen detectorresultaat geclaimd.
