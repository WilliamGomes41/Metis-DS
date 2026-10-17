# Metis — Roadmap v4

**Status:** actief  
**Peildatum:** 2026-10-17

**Gecontroleerde main:** [`4991cc6067d90bd3e839c9943c2d7cfac043e776`](https://github.com/WilliamGomes41/Metis-DS/commit/4991cc6067d90bd3e839c9943c2d7cfac043e776) (merge van #732).

**Functie:** actieve veranderopgaven en bewijspoorten. Uitgevoerde geschiedenis hoort in changelog of `docs/history/`.

Deze roadmap beschrijft het resterende werk op die main-stand. [Protocol v4](PROTOCOL.md) is de norm; GitHub-issues bevatten de actuele voortgang. Gemergde code en geslaagde CI bewijzen geen activatie in Azure of inhoudelijke productieacceptatie.

## Actuele stand (momentopname 2026-10-17)

GitHub-issues blijven de voortgangsbron; dit is alleen een overdrachtsoverzicht en geen tweede statusadministratie.

**Gemergd op 17-10 (geen deploy):**
- #667 R2-fix (remirror onder de storelock) → `59208f02`.
- #683 `_lane_total` (sluit #672 en #700) → `3f9389df`.
- #731 tier D fail-closed (sluit #665, Class A) → `e228aa90`. Opvolging: zie [#733](https://github.com/WilliamGomes41/Metis-DS/issues/733) en [#734](https://github.com/WilliamGomes41/Metis-DS/issues/734) (tests voor hoofdlettervarianten van de detailwaarde).
- #732 deploy-SHA-check (sluit #684, Class B), inclusief de fix voor de afsluitende `/` in `AZURE_*_APP_URL` → `4991cc60`. Nog niet bewezen in een echte deploy.

**Open:**
- [#695](https://github.com/WilliamGomes41/Metis-DS/issues/695) deployvoorwaarden (`critical-path`): Azure-info van William, backup met bewezen herstel, read-only schadecheck tier D, #684-check, GRANTs migratie 018. Er MAG NIETS live voordat #695 is afgevinkt. Geen deploydatum.
- Kernissues: #730 (PG als enige bron van waarheid), #689 (dode code; PR #735 in uitvoering), #737 (flaky peiltijd-test in `test_availability_repair`), #738 (omgevingsafhankelijke tests: SSRF met proxyvariabelen, sandbox als root), #690–#699, #701–#729 (inventaris). Smetten-branch `diag/smetten-coverage-remainder` is gepauzeerd (#515).

**Besluiten William 2026-10-17:**
- Tier D wordt fail-closed geweigerd.
- De drie structurele problemen (twee bronnen van waarheid, te veel topologieën, nesting/N+1) MOETEN in V1 gefixt en getest zijn vóór V2 start.
- B1: PostgreSQL is de enige bron van waarheid. Spiegels worden alleen na een geslaagde commit uit PG herbouwd, door één writer. Geen herstel uit kopieën, geen write vóór commit.
- Al het werk staat in GitHub-issues; het kritieke pad krijgt het label `critical-path`.
- Eén PR tegelijk.
- Per Class A-PR doet Lex alleen de aanvalsronde en Sherlock de begrensde review. Alleen bewezen blockers houden een merge tegen; de rest wordt een opvolgissue.
- Geen merge-GO-verzoek zonder gate-rapport van Argos. Merge of deploy alleen op Williams eigen GO in de chat van de uitvoerende agent.
- Scout is gepauzeerd, de war room is buiten gebruik (agents direct benaderen), Cartograph draait wekelijks of op verzoek.

## R4.1 Huidige en historische code scheiden

**Status:** gedeeltelijk uitgevoerd; verdere pakketorganisatie staat open onder [#335](https://github.com/WilliamGomes41/Metis-DS/issues/335). De Step 10-fixtureroute is gearchiveerd. Verdere verwijdering vereist aanroepbewijs.

- Inventariseer voor elke kandidaat voor verwijdering de imports, CLI-oproepen, scripts, tests, deployment en herstelprocedure.
- Behoud `src/legacy_canonical_recovery_v1.py` zolang `scripts/publication_chain_recovery.py recover-legacy-release` hem gebruikt. Behoud `src/azure_step9_cutover_v1.py` zolang het operatorcommando `scripts/azure_step9_cutover.py` bestaat.
- `config/pipeline.v2.yaml`, historische `output/v2/`-bewijzen en V2-goedkeuringsbestanden zijn geen actuele runtimeconfiguratie. Maak geen nieuwe runtimeafhankelijkheid van die bestanden.
- Oude V2-delta's blijven op hun oorspronkelijke paden wegens hash-, pad- en regressiebindingen. Hun archiefstatus staat in `docs/history/protocol-v2/README.md`; V3 is bevroren onder `docs/history/protocol-v3/`.
- De oude Step 10-fixturebouwer en het bijbehorende handmatige smoke-script zijn buiten de actieve codeboom bewaard onder `docs/history/step10-code/`; ze hadden geen aanroepen vanuit huidige runtime, tests, packaging of deployment.
- Verwijder alleen aantoonbaar onbereikbare code met een gerichte gedragsproef. Geen brede bestandsverplaatsing of refactor onder het mom van archivering.

**Klaar wanneer:** iedere nog aanwezige legacy-entrypoint een benoemde eigenaar/gebruik of een bewezen verwijderpad heeft; actuele runtime en herstel zijn getest.

## R4.2 Lifecycle en distributie bewijzen

**Status:** implementatie en geïntegreerde PostgreSQL-/herstelproeven aanwezig; audit van bestaande data en bewijs op de gekozen runtime blijven afzonderlijke acceptatie.

T9–T12 centraliseren review, bronafhandeling, revisieopvolging en publicatiegereedheid. De [lifecycle-/withdrawalproef](tests/test_lifecycle_withdrawal_recovery_v1.py) en [successor-cutoverproeven](tests/test_successor_release_cutover_v1.py) gebruiken native PostgreSQL; de [historische audit](scripts/historical_lifecycle_audit.py) is alleen-lezen. [CI is geslaagd](https://github.com/WilliamGomes41/Metis-DS/actions/runs/38084894082); de werkelijke gegevens en runtime moeten nog afzonderlijk worden getoetst.

1. Historical Lifecycle Audit — read-only: controleer bestaande data op ontbrekende `logical_document_id`, dubbele actieve releases, conflicterende lineage en actieve registry-rows na intrekking.
2. Legacy lineage repair alleen bij eenduidige herleiding; ambiguïteit blokkeert.
3. REAL Product API lifecycle proof — proof-only: R1 actief → R2 actief/R1 weg → withdrawal niets actief → gecorrigeerde R3 actief, vanuit dezelfde PostgreSQL-authority.
4. End-to-end lifecycle closure — proof-only: ingest → review → publish → successor → withdraw → correct successor, inclusief restart en stale replay/recovery.
5. Performance pas daarna, gemeten op een concrete bottleneck.

Een proof-slice wordt pas een nieuwe repair bij een reproduceerbare invariantbreuk.

## R4.3 Audit, passagevorming en compiled knowledge

**Status:** documentbrede kennisvorming, scheiding van kennis en bronverantwoording en hervatbare V3-vorming staan op main. Inhoudelijke acceptatie blijft open.

- Verifieer dat Experiment en read-only Documentkwaliteit de gedeelde auditstore niet aan een specifieke auditvorm koppelen.
- Beoordeel brongebonden passagevorming op een bevroren set met blinde A/B-review, correcties, foutcategorieën, reviewtijd en bruikbare yield. Onverifieerbare toevoegingen die zouden kunnen doorstromen: nul tolerantie.
- [#513](https://github.com/WilliamGomes41/Metis-DS/issues/513) is in code afgerond via [PR #514](https://github.com/WilliamGomes41/Metis-DS/pull/514). Beoordeel echte bronselectie, aanbevelingscontext en Admission onder [#530](https://github.com/WilliamGomes41/Metis-DS/issues/530), met bevroren bronnen, vooraf vastgelegde menselijke referenties en echte provideruitvoer.
- De Smetten-tabelgrens blijft een afzonderlijke implementatietaak: [#515](https://github.com/WilliamGomes41/Metis-DS/issues/515). Bewaar tabelinhoud als context en bewijs dat echte aanbevelingen behouden blijven; geen historische herverwerking of automatische uitsluiting.
- Verifieer de gekozen verwerkingsroute en rolverdeling conform protocol §5. `semantic-source-bound-v2` blijft de standaard; V1, V3 en deterministische verwerking vereisen expliciete configuratie. Geen stille terugval.
- Audit-bewijs eindigt bij `READY FOR IMPLEMENTATION`. Een menselijke ontwikkelroute buiten Metis beslist over code en releases. Compiled knowledge blijft uitsluitend afgeleid uit actieve gepubliceerde kennis; een module is nog geen bewezen productie-executor.

## R4.4 Aanmelding en uitrol

**Status:** Entra-code, handmatige deployworkflows en GitHub → Azure Repos-synchronisatie aanwezig; daadwerkelijke configuratie en uitrol hiermee niet vastgesteld.

- Controleer tenant, appregistratie, app-rollen, callback, secret en bestaande accountbindingen volgens [de Entra-instructies](docs/ENTRA_SIGN_IN.md). Test toegelaten en geweigerde aanmelding, rolwijziging, blokkering, sessieverloop en terugkeer naar de gevraagde pagina op test.
- De aanwezige [testworkflow](.github/workflows/deploy-test.yml) en [productieworkflow](.github/workflows/deploy-production.yml) gebruiken OIDC en een console-ZIP en starten handmatig. De testworkflow is begrensd door `METIS_TEST_APP_READY`; main-merges deployen niet automatisch. Verifieer doelomgeving, identiteit en artifact en bewijs de exacte commit op test vóór productie.
- [Dockerfile.docling](Dockerfile.docling) en de [Docling-acceptatieworkflow](.github/workflows/docling-acceptance.yml) leveren afzonderlijk image-/containerbewijs. Een console-ZIP levert niet de volledige Docling-runtime. [#531](https://github.com/WilliamGomes41/Metis-DS/issues/531) is op 12-10 gesloten; of er een Docling-restant open blijft (interpreter, modellen, dependencies, hostcapaciteit, herstelketen, deploy- en rollbackroute) is een OPENVRAAG onder [#696](https://github.com/WilliamGomes41/Metis-DS/issues/696). Een Kudu-ZIP is geen vervanging voor dit bewijs.
- [azure-pipelines.yml](azure-pipelines.yml) spiegelt GitHub-branches en tags naar Azure Repos. Verifieer een echte pipeline-uitvoering en rechten; dit is geen DevOps → productie-deployroute.
- De volgende productiedeploy is geblokkeerd door [#695](https://github.com/WilliamGomes41/Metis-DS/issues/695). De deploy-SHA-check uit [#684](https://github.com/WilliamGomes41/Metis-DS/issues/684) staat op main (PR #732), maar is nog niet in een echte deploy bewezen. De live draaiende commit is niet vastgesteld; gemergd op main is niet gedeployed.
- Bewijs dat deployment runtime-data intact laat en niet impliciet G2-publicatie of Product API-toegang activeert.
- Verifieer de echte pilotbron, bronhash en immutable G2-bronopslag vóór publicatie van die snapshot. Bronbewijs voor één snapshot ontgrendelt publicatie niet algemeen.

## R4.5 Resterende auditbevindingen en productieacceptatie

**Status:** voor A01, A02, A04, A05, A09, A15 en A26 zijn reparaties gemergd. De overige twintig staan nog open: A03, A06, A07, A08 en A10 als losse issues (#553, #556, #557, #558, #560), A11–A27 (zonder A15/A26) gebundeld in [#688](https://github.com/WilliamGomes41/Metis-DS/issues/688). Registratie alleen start geen implementatie.

- Volg de bestaande ID-koppelingen in [het auditoverzicht](docs/audit/README.md). GitHub is de voortgangsbron; de HTML is een gedateerde momentopname.
- Verifieer de gemergde beschikbaarheids-, bronhergebruik- en contextnavigatiereparaties via de oorspronkelijke gebruikershandeling op de werkelijk draaiende commit. Gesloten codeissues zijn geen productieacceptatie.
- Leg resterende afwijkingen en niet-gevoelig voortgangsbewijs vast in de bestaande issues. Volledige diagnostiek blijft intern; geen tweede statusadministratie of algemene herbouw.

## Stopregels

- Geen huidige gedragsspecificatie uit historische V2-documenten afleiden.
- Geen herstel-, migratie- of CLI-pad verwijderen op basis van een bestandsnaam of alleen een testverwijzing.
- Geen nieuwe lifecycle-authority, serving-tabel of lineage-heuristiek zonder gereproduceerde gap.
- Geen modeloutput met directe canonieke schrijf-, review- of publicatierechten; geen automatische code- of GitHub-executor vanuit Audit.
- Geen brede console-rewrite, microservicesplitsing of generieke auditengine zonder aantoonbare behoefte.
- Geen algemene G2-`PASS`, Product API-activatie of productierijpheidsclaim op basis van CI alleen.
