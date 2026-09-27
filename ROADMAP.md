# Metis — Roadmap v4

**Status:** actief  
**Datum:** 2026-09-27  
**Functie:** actieve veranderopgaven en bewijspoorten. Uitgevoerde geschiedenis hoort in changelog of `docs/history/`.

De code op `main` is het implementatiebewijs. Een aanwezige route, test of GitHub-workflow bewijst geen activatie in Azure. Protocol v4 is de norm; deze roadmap maakt nog open werk zichtbaar.

## R4.1 Huidige en historische code scheiden

**Status:** gedeeltelijk uitgevoerd; verdere verwijdering vereist aanroepbewijs.

- Inventariseer voor elke kandidaat voor verwijdering de imports, CLI-oproepen, scripts, tests, deployment en herstelprocedure.
- Behoud `src/legacy_canonical_recovery_v1.py` zolang `scripts/publication_chain_recovery.py recover-legacy-release` hem gebruikt. Behoud `src/azure_step9_cutover_v1.py` zolang het operatorcommando `scripts/azure_step9_cutover.py` bestaat.
- `config/pipeline.v2.yaml`, historische `output/v2/`-bewijzen en V2-goedkeuringsbestanden zijn geen actuele runtimeconfiguratie. Maak geen nieuwe runtimeafhankelijkheid van die bestanden.
- Oude V2-delta's blijven op hun oorspronkelijke paden wegens hash-, pad- en regressiebindingen. Hun archiefstatus staat in `docs/history/protocol-v2/README.md`; V3 is bevroren onder `docs/history/protocol-v3/`.
- Verwijder alleen aantoonbaar onbereikbare code met een gerichte gedragsproef. Geen brede bestandsverplaatsing of refactor onder het mom van archivering.

**Klaar wanneer:** iedere nog aanwezige legacy-entrypoint een benoemde eigenaar/gebruik of een bewezen verwijderpad heeft; actuele runtime en herstel zijn getest.

## R4.2 Lifecycle en distributie bewijzen

**Status:** code en deeltests aanwezig; geïntegreerd bewijs open.

1. Historical Lifecycle Audit — read-only: controleer bestaande data op ontbrekende `logical_document_id`, dubbele actieve releases, conflicterende lineage en actieve registry-rows na intrekking.
2. Legacy lineage repair alleen bij eenduidige herleiding; ambiguïteit blokkeert.
3. REAL Product API lifecycle proof — proof-only: R1 actief → R2 actief/R1 weg → withdrawal niets actief → gecorrigeerde R3 actief, vanuit dezelfde PostgreSQL-authority.
4. End-to-end lifecycle closure — proof-only: ingest → review → publish → successor → withdraw → correct successor, inclusief restart en stale replay/recovery.
5. Performance pas daarna, gemeten op een concrete bottleneck.

Een proof-slice wordt pas een nieuwe repair bij een reproduceerbare invariantbreuk.

## R4.3 Audit, passagevorming en compiled knowledge

**Status:** de auditruimte, experimentcode en brongebonden pre-Review-route bestaan; acceptatie en activatie apart bewijzen.

- Verifieer dat Experiment en read-only Documentkwaliteit de gedeelde auditstore niet aan een specifieke auditvorm koppelen.
- Beoordeel brongebonden passagevorming op een bevroren set met blinde A/B-review, correcties, foutcategorieën, reviewtijd en bruikbare yield. Onverifieerbare toevoegingen die zouden kunnen doorstromen: nul tolerantie.
- De semantische productieroute vereist expliciete `METIS_PASSAGE_FORMATION_MODE=semantic-source-bound-v1` én één deployment-owned `METIS_LLM_API_KEY` en `METIS_LLM_MODEL`. Deterministisch blijft de standaard/rollbackroute; een fout in geactiveerde semantic mode valt niet stil terug.
- Audit-bewijs eindigt bij `READY FOR IMPLEMENTATION`. Een menselijke ontwikkelroute buiten Metis beslist over code en releases. Compiled knowledge blijft uitsluitend afgeleid uit actieve gepubliceerde kennis; een module is nog geen bewezen productie-executor.

## R4.4 Aanmelding en uitrol

**Status:** Entra-code gemerged; Azure-configuratie en gecontroleerde uitrol nog afzonderlijk te bewijzen.

- Configureer tenant, appregistratie, app-rollen, callback, secret en bestaande accountbindingen volgens `docs/ENTRA_SIGN_IN.md`. Test toegelaten en geweigerde aanmelding, rolwijziging, blokkering, sessieverloop en terugkeer naar de gevraagde pagina op test.
- Herstel GitHub Actions → Azure OIDC als reguliere deployroute. Bewijs de exacte commit op test vóór productie. Een handmatig Kudu-ZIP is een tijdelijke noodroute met volledige commit-SHA en reproduceerbaar pakket.
- Bewijs dat deployment runtime-data intact laat en niet impliciet G2-publicatie of Product API-toegang activeert.
- De echte pilotbron en bronhash moeten beschikbaar en gecontroleerd zijn voordat die snapshot G2 kan passeren. De ontbrekende bron is geen algemene ontgrendeling van publicatie.

## Stopregels

- Geen huidige gedragsspecificatie uit historische V2-documenten afleiden.
- Geen herstel-, migratie- of CLI-pad verwijderen op basis van een bestandsnaam of alleen een testverwijzing.
- Geen nieuwe lifecycle-authority, serving-tabel of lineage-heuristiek zonder gereproduceerde gap.
- Geen modeloutput met directe canonieke schrijf-, review- of publicatierechten; geen automatische code- of GitHub-executor vanuit Audit.
- Geen brede console-rewrite, microservicesplitsing of generieke auditengine zonder aantoonbare behoefte.
- Geen algemene G2-`PASS`, Product API-activatie of productierijpheidsclaim op basis van CI alleen.
