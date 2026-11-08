# HA-2a: uitgevoerd bewijs en grenzen

Status: werkende bron-/conceptslice, **geen complete annotatie-tot-publicatie-route**.
Basis: main `e0a3b09a`; ontwerpbranch `1fb0e097`.
Contract: [1015-human-annotation-source.md](1015-human-annotation-source.md).

Aanvulling na de hieronder beschreven tussenruns: de complete herhaling op
`c23933d2` eindigde met **8352 passed, 46 skipped, 3 xfailed en 32 geslaagde
subtests; exit 0** (`pytest -q -n 4 -rs --tb=short`, echte PG16 per worker).
De 23 browsergevallen waren afzonderlijk daadwerkelijk uitgevoerd en slagen.
De 12 echte Docling/PDF-acceptatiegevallen en 11 optionele Bend-proeven waren
niet uitgevoerd; geen PDF-/releaseacceptatie afgeleid uit skips. Dit resultaat
staat ook in draft PR #1021. Vervolgwijzigingen hebben hun eigen bewijs nodig.

De vervolginventarisatie vond een herstelgat buiten procesherstart: annotaties
ontbraken in de workflowketenback-up. Reparatie en nieuwe proeven staan in het
[herstelcontract](1015-human-annotation-recovery.md). De resterende uitvoerbare
vormings-/cutovergrenzen staan in het [uitvoeringscontract](1015-human-annotation-execution.md).

## Uitgevoerd

- Lokale echte PostgreSQL **16.4**, via `scripts/test_postgres.sh`; geen PG-skip.
  De managed Debian-omgeving had geen PostgreSQL/sudo. De testserver is lokaal
  uitgepakt uit de Zonky Maven-distributie; `psql` 17.11 uit het officiële
  Debian-pakket is uitsluitend de client voor bestaande SQL-controles.
- `python -m pytest -q tests/test_human_annotation_postgres.py
  tests/test_workflow_postgres_migration_v1.py tests/test_architecture_invariants.py
  tests/characterization/test_review_overview.py`: **28 passed**.
- `METIS_BROWSER_BASE=http://127.0.0.1:8765
  METIS_BROWSER_EXECUTABLE=/usr/bin/chromium
  METIS_BROWSER_OUTPUT=/tmp/metis-annotation-browser
  node tests/browser_human_annotation_check.cjs`: **exit 0**.
  Server: `python -m uvicorn tests.browser_human_annotation_fixture:app
  --host 127.0.0.1 --port 8765`, met dezelfde test-PostgreSQL.
  Muis met emoji, meerdere bereiken, exacte voorwaarde, netwerkfout zonder
  vals opgeslagen/navigeren, pauze tot commit, nieuwe login, overzicht,
  toetsenbordselectie en hervatten van een nog niet gekoppelde aanwijzing.
  Screenshots op 1440/390 pixels bekeken; geen horizontale overflow.
- `python scripts/check_architecture_boundaries.py`: **PASS**.
- `python -m compileall -q src`, `node --check
  src/vorming/human_annotation_editor.js`, `git diff --check`: **exit 0**.
- `python scripts/repository_preflight.py`: **PASS**.

Gebruik een lokale virtualenv met `requirements-dev.lock` en de nieuwe
`requirements-console.txt`; zet `PGBIN` naar de test-PostgreSQL-16-binmap.
De complete suite is opnieuw gestart op de laatste code; die wordt pas als
geslaagd gerapporteerd na een afgeronde run. Een eerdere tussenrun eindigde
na interrupt op **690 passed** en telt niet als complete regressiecontrole.
De eerste brede run vond een routelijst die voor de zes nieuwe HTTP-routes
moest worden bijgewerkt en de ontbrekende `psql`-client; beide zijn gecorrigeerd.

De afgeronde brede run vóór de laatste rechtenreparatie gaf **8348 passed,
3 failed, 45 skipped, 3 xfailed en 32 geslaagde subtests**. Twee fouten betroffen
de nieuwe guard die van oude, beperkte writers ten onrechte SELECT op de nieuwe
annotatietabel verlangde. De drie guards lezen nu uitsluitend het ownershipsignaal
onder vaste eigenaarrechten, met `search_path=pg_catalog`; de oude rol krijgt
geen toegang tot annotatiegegevens. De derde fout was de expliciete allowlist
voor lichte consoleafhankelijkheden: `regex` is toegevoegd voor Unicode-graphemen,
met behoud van de weigering van de retrieval/ML-stack.

Na de rechtenreparatie: **83 gerichte tests PASS**, inclusief de oorspronkelijke
28 en de vormings-/writerproeven. De 22 bestaande opt-in-browsergevallen zijn
afzonderlijk met Chromium daadwerkelijk uitgevoerd en slagen; hun skips in de
brede run worden dus niet als bewijs gebruikt. Overige skips, waaronder optionele
Docling-acceptatie, zijn geen geslaagde proeven en geven geen PDF-/releaseacceptatie.

Daarna zijn de drie regressies expliciet herhaald met de bronroute (**28 passed**).
De opslagmatrix is vervolgens met zowel `legacy` als `v1` voor operationele
documentinputs, waaronder een afzonderlijk Python-proces, opnieuw uitgevoerd
(**28 passed** voor die matrix plus migratie-/consolegrens). De nieuwe browserproef
is in `test_browser_knowledge_context.py` opgenomen, dus in de bestaande verplichte
CI-browserjob; de nieuwe parameter afzonderlijk geeft **1 passed**.

## Afzonderlijke adversariële controle

| Poging | Werkelijk gecontroleerd resultaat |
|---|---|
| Zelfde command-ID met gewijzigde inhoud | Conflict, geen extra versie; verwijdering van deze guard in een geïsoleerde codekopie maakte de test rood met `DID NOT RAISE` |
| Twee consoles tegelijk op generatie 0 | Eén commit, één expliciet conflict; dubbele retry geeft hetzelfde receipt |
| Crash vóór commandreceipt | Versie, head en generatie rollen samen terug |
| Bronversie vervangen of verkeerde extractie sturen | DB-pin weigert bronmutatie; save weigert verkeerde extractie; geen quote-search |
| Identieke tekst op twee posities/blokken | Beide exacte locaties blijven afzonderlijk selecteerbaar |
| UTF-16, emoji en decomposed accent | Browserconversie en servergraphemecontrole; doorgesneden teken geweigerd |
| Researcherrechten intrekken, daarna duplicate sturen | Nieuwe autorisatie weigert ook het oude command |
| Oudere writer rechtstreeks object/poging laten invoegen | Native SQL-trigger weigert; geen geactiveerde kandidaten of pogingen |
| Concept/pending-range als gereed verklaren | Open aanwijzing en ontbrekend kern-/bewijsbesluit geweigerd |
| Bewaren als review of publicatie gebruiken | Objecten en reviewbindings blijven leeg, envelope/ingestpolicy bytegelijk |
| Bestaand geautoriseerd ongepubliceerd document verwijderen | Bestaande delete-operatie ruimt de ondergeschikte annotatiegegevens atomair op |

Dit is een afzonderlijke controlepass, geen claim van onafhankelijke review
door een tweede mens/agent. De mutation-copy is wegwerpwerk en geen productcode.

## Niet bewezen / niet geleverd door deze slice

Geen seal/job, human FormationEvidence, kandidaatbouw, gerichte objectherbouw,
correctie/publicatierace, volledige upload→API/MCP-proef, globale cutover,
verwijdering van oude prozaroutes, native Azure-opslagproef of praktijkacceptatie.
Historische AI-werkrevisies worden niet overgenomen. De oude route blijft alleen
voor nog niet overgeschakelde revisies bestaan; HA-4b moet die uiteindelijk
verwijderen. Deze PR mag het project of #1015 niet sluiten.

De PStack-controle is ontwerpbewijs; zij vervangt geen van bovenstaande proeven.
Het Impeccable-contextcommando kon de engine niet downloaden. De bestaande
brandregels en vendored playbooks zijn rechtstreeks gelezen; geen engine-audit
of detectorpass geclaimd. Browsercontrole is daadwerkelijk met Chromium uitgevoerd.
