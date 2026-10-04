# Metis-codeaudit — 4 oktober 2026

## Oordeel en afbakening

De audit vindt twee reproduceerbare onderhoudsfouten, een proxy-afhankelijke afwijking in URL-beveiligingstests en een hier niet betrouwbaar uitvoerbare procestest. Dit is geen verklaring dat Metis foutvrij of productiegevalideerd is.

Basis: `WilliamGomes41/Metis-DS`, main-commit `dc5409b940fcdaeba79db459eee6025f06db4e49`. Alle 823 opgehaalde repositorybestanden zijn vóór wijzigingen tegen hun Git-blobhash gecontroleerd. De uitvoerbare bestandsrechten zijn teruggezet naar de remote modes. Er is geen Azure-toegang, productie-telemetrie, echte Docling/modelrun of productiedatabase-audit uitgevoerd.

Deze wijziging is Class C, Rewrite risk: none. Het gedrag verandert niet: de effectieve foutmelding blijft behouden en de ontbrekende import maakt bestaande type-informatie uitleesbaar. Zie `docs/change-contracts/repository-audit-2026-10-04.md`.

## Bevindingen

| ID | Bewijs | Betekenis | Resultaat |
|---|---|---|---|
| A01 | `ERROR_COPY` in `src/operations_console_app.py` bevat tweemaal `pre_review_llm_response_not_completed`. Python overschrijft de eerste waarde. | De eerste tekst heeft geen effect; onderhoud aan die tekst zou ongemerkt niets veranderen. | Eerste definitie verwijderd en als `LEGACY-REMOVED` geregistreerd. De effectieve laatste tekst blijft gelijk. AST-regressieproef toegevoegd. |
| A02 | `typing.get_type_hints(_PostgresIdentityMixin._startup_local_mirror_is_authority)` geeft `NameError: Path is not defined`. | De uitgestelde annotatie veroorzaakt geen aangetoonde normale loginfout, maar type-introspectie faalt. | `pathlib.Path` geïmporteerd en reproductietest toegevoegd. |
| A03 | Drie tests in `tests/test_security_harden_wave3.py` falen met de aanwezige proxyomgeving en slagen zonder HTTP(S)/ALL_PROXY. `fetch_url_limited` maakt een urllib-opener zonder expliciete proxykeuze. | De combinatie van proxyverwerking en directe IP-pinning is niet bewezen. Redirect- en SNI-aannames van de test worden in die omgeving doorbroken. | OPEN. Apart onderzoeken met een gecontroleerde proxy en de ondersteunde deploymentconfiguratie; geen bewezen Azure-SSRF of metadata-exfiltratie claimen. |
| A04 | `test_parent_process_death_terminates_transport_worker` faalt hier bij `/proc`-kindprocesdetectie of de daarop volgende procescontrole. Een losse proef ontving de request en zag de verbinding binnen twee seconden sluiten na beëindiging van de ouder. | De testuitvoering in deze sandbox is geen betrouwbaar bewijs van een verweesd productieproces. Sluiten van de verbinding is ook geen volledig bewijs van procesreaping. | OPEN test-/omgevingvalidatie op gewone Linux CI; niet de guard verzwakken of de test overslaan als productfix. |
| A05 | `audit_experiment_v1` en `compiled_knowledge_v1` hebben tests, maar geen huidige applicatieaanroeper. De auditpagina zegt dat datasetvastlegging een volgende stap is; ROADMAP R4.3 maakt executorbewijs expliciet open. | Aanwezige modulecode bewijst geen aangesloten productfunctie. Deze code is voorbereid, niet verouderd. | `PLANNED-NOT-INTEGRATED`; behouden. |
| A06 | `provider_vector_retrieval_v1` en `embedding_provider_v1` worden door capabilitytests gebruikt; `SafeRetrievalIndex` gebruikt de huidige `HybridIndex`-route. | Een beschikbare alternatiefimplementatie is geen geselecteerde productieroute. | `OPTIONAL-NOT-INTEGRATED`; behouden. |
| A07 | `src/storage_prepare.py` heeft geen huidige runtime-, script- of testaanroeper. Het oude CLI filtert uitsluitend op goedkeuringsvelden; dit is niet de huidige publicatiepoort. | Historische pilotcode kan bij handmatige aanroep ten onrechte als actuele publicatiecontrole worden gelezen. | `LEGACY-UNUSED` voor huidige repositoryproductroutes, in broncommentaar en inventaris. Directe handmatige CLI-aanroep blijft mogelijk; extern gebruik is niet waargenomen. |
| A08 | Agentdocumenten verwijzen naar `CONTEXT.md`/`CONTEXT-MAP.md`, die ontbreken. Het engineerprofiel noemt `scripts/verify_architecture_invariants.py`, dat ontbreekt; CI gebruikt het bestaande `tests/test_architecture_invariants.py`. De repositoryconventies noemen nog `VENVN-DS` als remote. | De beschreven ontwikkelprocedure bevat verouderde verwijzingen. | Gedocumenteerd; geen impliciete wijziging van governance. Actueel protocol en roadmap zijn gelezen; de architectuurtest zelf is uitgevoerd. |

De overige Pyflakesmeldingen betreffen ongebruikte bindings/imports en conditionele herdefinities. Ze zijn onderzoekskandidaten, geen bewijs dat de hele functie of module ongebruikt is. Voorbeelden: `_require_role` blijft een noodzakelijke autorisatiecontrole ook als zijn resultaat niet wordt gebruikt; de conditionele v2/v3-veldimports blijven actief. Publieke herexports, decorators, overrides en side-effects moeten afzonderlijk worden bewezen voordat ze worden verwijderd.

## Legacy-inventaris

`config/code_lifecycle_inventory.v1.json` bevat 476 beoordeelde codeartefacten: 164 src-modules, 31 scripts, 278 tests/hulpmiddelen, één voorbeeld en twee historische bronkopieën. Per bestand staan status, reden, directe CLI en repositoryverwijzingen. Dit is auditbewijs bij de genoemde commit, geen runtimeconfiguratie of automatische verwijderlijst.

| Status | Aantal | Interpretatie |
|---|---:|---|
| ACTIVE-RUNTIME | 134 | Bereikbaar vanaf console, Product API, inspectieservice of geïnstalleerde CLI; inclusief conditionele routes. Dit bewijst geen Azure-activatie. |
| ACTIVE-OPERATOR | 49 | Huidige tooling of rechtstreeks aanroepbare behouden CLI; handmatige uitvoering niet geobserveerd. |
| ACTIVE-TEST | 278 | Testcode en verificatiehulpmiddelen. |
| ACTIVE-PACKAGE | 4 | Python-packagebestanden. |
| ACTIVE-TEST-SUPPORT | 1 | `extract_metrics_v1`: onafhankelijke acceptatiemeting, geen legacy. |
| ACTIVE-EXAMPLE | 1 | Consumentvoorbeeld. |
| LEGACY-UNUSED | 1 | `storage_prepare`: geen huidige productaanroeper. |
| LEGACY-SUPPORTED | 2 | `canonical_store` (SQLite-pilot) en `second_review_workflow_v3` (historische JSONL-review). CLI/tests blijven bestaan. |
| LEGACY-ARCHIVED | 2 | Bestaande inerte Step 10-codekopieën. |
| PLANNED-NOT-INTEGRATED | 2 | Experimentdataset en compiled-knowledge-input. |
| OPTIONAL-NOT-INTEGRATED | 2 | Alternatieve embedding/provider-vectorroute. |

Het bestaande `config/legacy_processing_routes.json` blijft gelden voor acht `LEGACY-FROZEN` deelroutes. `cutover_enabled=false`: bevroren betekent daar niet ongebruikt. Er wordt geen cutover geactiveerd. `legacy_canonical_recovery_v1`, `azure_step9_cutover_v1`, Docling-subprocesscode, lokale ontwikkeltopologieën, migraties en herstelcommando's blijven behouden omdat bestaande entrypoints ze kunnen aanroepen.

Onderzoeksmethode: AST-importinventaris inclusief relatieve imports, moduleverwijzingen/subprocessopdrachten, entrypoints en gericht lezen van CLI, scripts, packaging, tests, protocol, roadmap en herstelroutes. De classificatie is conservatief. Geen statische audit kan onbekende externe imports, handmatige operatoraanroepen of iedere reflectieve functieaanroep uitsluiten. Individuele ongebruikte regels in actieve modules zijn dus niet stilzwijgend tot een ongebruikte hele module verheven.

## Verificatie

- Baseline: 2.608 passed, 178 skipped, 5 failed in 160 seconden. De packaging-fout was veroorzaakt door de lokale snapshotrechten en verdwijnt na herstel van de remote executable modes; dit is geen repositoryfix.
- Gerichte regressieproeven inclusief architectuur en workflowidentity: 17 passed.
- Drie betreffende SSRF-tests zonder proxyvariabelen: passed.
- Losse procestermination-proef: request ontvangen, verbinding binnen twee seconden na ouderbeëindiging gesloten; volledige reaping blijft onbewezen.
- CLI `audit-current`: integriteit PASS, 21 objecten. Publicatiepoort terecht BLOCKED met 21 blokkades; dit betreft de bestaande fixture, niet productie.
- Volledige eindrun: 2.611 passed, 178 skipped, 4 failed in 132 seconden. De vier resterende fouten zijn de drie proxy-afhankelijke URL-tests en de procestest uit A03/A04. Geen nieuwe regressie is gevonden; de suite is nadrukkelijk niet volledig groen.
- Repositorypreflight, releasecontrole tegen de vastgelegde wijzigingscommit, compileall en architectuurtest: PASS; architectuurtest 6 passed. De twee gerichte auditregressies slagen ook na de laatste documentatie-/metadatawijziging.

Overgeslagen proeven omvatten PostgreSQL-, browser- en echte model/Docling-routes met ontbrekende externe voorwaarden. Een PostgreSQL-server kon hier niet worden geïnstalleerd door procesrechten van de uitvoeringsomgeving. Skips tellen niet als aangetoonde werking.

## Opvolging

1. Bewijs proxybeleid en DNS/SNI/redirectgedrag voor URL-ingest op ondersteunde Linux/deploymenttopologie. Maak een eventuele reparatie een aparte gedragswijziging met gericht beveiligingsbewijs.
2. Herhaal de ouder-/workerprocestest op gewone Linux CI en verifieer zowel socketafsluiting als procesbeëindiging/reaping.
3. Herstel verouderde ontwikkeldocumentverwijzingen in een afzonderlijke governance-/documentatieopgave.
4. Houd legacy-supported code tot de CLI-, test- en herstelafhankelijkheden expliciet zijn uitgefaseerd. Markering is geen verwijdertoestemming.
