# HA-4 — startinventaris voor overgang en praktijktoets

Change class: C — deze deelslice documenteert bestaande routes en open bewijs; geen runtimewijziging.
Rewrite risk: none — voor deze inventaris. De latere cutover/verwijdering is Class A / Rewrite risk: high en vereist een eigen volledig uitvoeringscontract.
Promise: HA-4 begint met een versiegebonden verwijderkaart, overgangsvolgorde en concrete ontbrekende praktijkinvoer.
Proof: Statische caller-/importinspectie op onderstaande SHA en controle van de documentverwijzingen; geen runtime-, deployment- of praktijkacceptatieclaim.
Touches lifecycle invariants: no — deze deelslice verandert geen gedrag.

## Opdracht en vastgestelde basis

William gaf op 9 november 2026 opdracht: “Start HA 4”. Dit start #1017 / MET-61.
Deze opdracht is geen merge-, deployment-, productieconversie- of betaalde provideropdracht.
De eerdere planningtekst beschrijft de administratieve sessie van 8 november;
de huidige opdracht autoriseert de voorbereiding van HA-4.

Geïnspecteerde main: `c985eaf376f4c686851f198f526510ca32e98b9e`.
GitHub PR #1032 is gemerged op 9 november 2026 om 03:03:27 UTC; HA-3 is dus
aanwezig in deze codebasis. De eerdere Linear-tekst “gereed voor review” is
achterhaald. Merge bewijst geen deployment of formele praktijkacceptatie.
De formele werkpakketten MET-59 en MET-60 blijven afzonderlijk open;
hun release-/acceptatiebewijs wordt niet door deze inventaris vervangen.

Normatief: [GitHub #1017](https://github.com/WilliamGomes41/Metis-DS/issues/1017),
[HA-2-bouwcontract](1015-human-annotation-build.md),
[HA-3-contract](1016-human-annotation-review.md) en
[bestaande praktijktoets](../plans/human-annotation-practice-acceptance.md).
Het architectuurdocument waar #1017 naar verwijst staat op de ontwerpbranch;
het ontbreekt op deze main. Gebruik de in #1017 gepinde versie, geen verzonnen
lokale kopie als nieuw besluit.

## Huidige codekaart en benodigde subtractie

Alle onderstaande items zijn **open**. Dit is een startkaart uit statische
inspectie, geen verklaring dat alle dynamische callers al zijn afgedekt.

| Oppervlak op geïnspecteerde main | Waargenomen koppeling | Actie en te leveren bewijs vóór sluiten |
| --- | --- | --- |
| `src/console_asgi.py` | Importeert en installeert `bind_pre_review_semantic_processing` bij startup | Vervang de prozarouter na bewezen overgang; startup zonder prozamodelconfiguratie testen, met behoud van expliciete boomconfiguratie |
| `src/vorming/pre_review_semantic_v1.py` | `bind_pre_review_semantic_processing` routeert bomen naar `decision_tree_route_v1.prepare`; overige bronnen gaan via `semantic_spec_from_fragments` naar provider/proposalexecutie | Schrap vervangen prozaprompts, schemas, providerexecutie en modelmodi; test ook directe aanroep, niet alleen HTTP/menu |
| `src/operations_console_v1.py` | Controleert `_pre_review_semantic_bound`; bevat de bestaande verwerking/strategiegrens | Traceer concrete MRO/overrides en interne verwerkingscallers vóór wijziging; geen alternatieve kandidaatmaker toevoegen |
| `src/vorming/human_annotation_materialisation_v1.py` | Importeert `document_spec` uit de oude module | Verplaats de structuurhelper naar een gedeelde bestaande/passende owner vóór subtractie; bewijs identieke canonieke inhoud/hash voor menselijke én behouden boomuitvoer |
| `src/vorming/decision_tree_route_v1.py` | Importeert `_bounded_provider_json` en `_extract_output_text` uit de oude module | Verplaats benodigde transport-/antwoordhelpers of hergebruik bestaande providerowner; behoud boomcontract en test boom-ingest/review/publicatie/herstel |
| `src/vorming/source_selection_v1.py` | `reserve_selection` weigert human-owned bronnen; andere proza kan nog `ingest`, `retry` of `resume` reserveren | Eén producer per werkrevisie handhaven; nieuwe reservering en bestaande pending pogingen afzonderlijk toetsen; geen automatische AI→human takeover |
| `src/vorming/processing_retry_v1.py`, `source_processing_dispatch_v1.py`, `worker_handover_v1.py` | Bestaande reservering/dispatcher/worker; dispatcher roept `execute_source_selection` aan, human-build heeft eigen gepind attempt-kind | Native pending/claimed/expired/restart-proeven: oude prozapoging mag geen providerexecutie hervatten; human-build en boom blijven via dezelfde bestaande dispatchowner werken |
| `src/vorming/source_selection_ui_v1.py` | GET `/source-selection`, POST `/source-selection/start`; `render_context` toont “Broncontext vastleggen” | Verwijder vervangen start-/contextpagina en migreer alle links; behoud noodzakelijke bronverantwoording, herstel, boom en historische inzage; test oude URL en POST rechtstreeks |
| `src/operations_console_app.py`, `src/review/review_workboard_v1.py`, `ko_review_page_v1.py` | Contextlinks/redirects en `/review/source-context`-formulier | Bepaal per bronowner de geldige correctieroute. Human-correctie gaat terug naar oorspronkelijke annotatie. Niet de gedeelde context-/reviewautoriteit blind schrappen |
| `src/settings/audit_semantic_safety_v1.py`, `route_comparison_app_v1.py` | Importeren `semantic_units_before_review` en kunnen oude proza uitvoeren | Sluit instellingen-/experimentexecutie mee af; een verborgen productknop sluit deze ingangen niet |
| `src/vorming/prepared_source_views_v1.py`, `recoverable_formation_v1.py` | Importeren fragment-/bewijshelpers | Scheid deterministische bronprojectie en herstel van provider-/replayexecutie; retained bronmapping/hash moet gelijk blijven |
| `src/workflows/formation_task_store_v1.py`, `formation_evidence_v1.py`, `src/forensic_trace_v1.py` | Importeren fragmenthelpers en/of `semantic_contract_version` voor opslag/bewijs/trace | Behoud historische bewijsvalidatie en read-only inspectie; bewijslezers mogen geen providerexecutie activeren |
| `src/vorming/attempt_diagnostics_v1.py` | Gebruikt oude proposalvalidatie | Bepaal wat historische diagnostiek nodig heeft; behoud lezers, verwijder uitvoerbaarheid van vervangen proza |
| `scripts/replay_recorded_formation.py`, `verify_eenzaamheid_semantic.py`, `measure_formation_validation.py`, `measure_source_task_reuse.py`, `probes/probe_source_repair_mapping.py`, `verify_source_container_diagnostic.py`, `measure_recorded_source_views.py` | Oude uitvoer- of helperimports buiten de app | Classificeer scripts als uitvoering of historische lezer; verwijder vervangen executie zonder een onderhouden tweede prozapad als benchmark te bewaren |
| Configuratie en tests | `METIS_PASSAGE_FORMATION_MODE`, provider/modelinstellingen en veel oude tests zijn verweven met boom/historische contracten | Maak een caller-/configregister vóór verwijderen. Alleen exclusieve prozaconfiguratie/tests schrappen; benodigde tests naar behouden owner verplaatsen, daarna caller/importscan én runtime-bypassbewijs op dezelfde head |

Inspectie is reproduceerbaar met:

```sh
rg -n 'pre_review_semantic|document_spec\(' src scripts --glob '*.py'
rg -n 'resume_formation|human_annotation_build|execute_source_selection' src/vorming
rg -n 'render_context|context_mode|/review/source-context|Broncontext vastleggen' src --glob '*.py'
rg -l 'pre_review_semantic|METIS_PASSAGE_FORMATION_MODE' tests config scripts src
```

## Overgangsvolgorde en rollbackgrens

1. **Voorbereiden:** bevries bron, selectietaak, onafhankelijke referentie,
   ingestpolicy, deelnemers en inhoudelijke acceptatiegrenzen. Hergebruik #530
   voor referentieacceptatie en #863 voor vindbaarheid/afronden.
2. **Inventariseer de doelomgeving read-only:** noteer exacte code/image,
   migraties, opslaglayout, open WorkingRevisions, producer per revisie,
   pending/claimed pogingen, human-seals/proofs en actieve publicatieregistry.
   Deze sessie heeft geen doelomgeving geïnspecteerd; aantallen zijn onbekend.
3. **Leg vóór cutover het uitvoeringscontract vast:** Class A/high met volledige
   lifecyclevelden, alle native/file/Azure/MRO-topologieën die daadwerkelijk
   ondersteund zijn, writer-/readerkaart, transactiegrenzen, expliciete omgang
   met onderbroken AI-werk, getest herstel en benoemd rollback-image/digest.
   Een git-SHA alleen is geen operationeel rollbackpunt.
4. **Beproef de nieuwe route:** bestaande HA-2/HA-3-tests hergebruiken op de
   gekozen releasehead en ontbrekend live/researcherbewijs uitvoeren. Gelijke
   ingestbeoordeling voor alle vergelijkingsvarianten; geen impliciete
   goedkeuring door annoteren, seal of bouwen. Bestaande AI-baseline bevroren
   en buiten productexecutie bewaren; geen nieuwe betaalde modelrun starten.
5. **Gecontroleerde cutover:** uitsluitend na toepasselijke acceptatie en
   expliciet operationeel besluit. Geen historische bulkconversie. Lopende
   AI-revisie behoudt één benoemde owner; menselijke takeover vraagt een
   afzonderlijk expliciet besluit en een gedefinieerde atomische overgang.
6. **Definitieve subtractie:** pas na bewezen cutover vervangbare proza-ingangen,
   prompts, uitvoering, exclusieve instellingen en oude contextpagina
   verwijderen. Behouden helpers/lezers eerst migreren. Sluit elk registeritem
   met bewijs op dezelfde producthead.

Bij mislukte proef/cutover blijft gecommitteerd bron-/annotatiewerk behouden en
blijft de publicatieregistry servingautoriteit. Een rollback naar code die
nieuwe human-proofs/seals niet begrijpt is geen herstelplan: blokkeer zulke
writes en kies forward fix of bewezen restore met een geschikte reader.
Oude prozaproviderexecutie mag geen automatische recoveryfallback worden.
De werkelijke rollback-/restoreproef is nog niet uitgevoerd.

## Minimale bewijsmatrix voor de implementatieslice

| Claim | Weerleggend scenario | Vereist observeerbaar bewijs |
| --- | --- | --- |
| Geen vervangen proza-executie | Oude POST, interne strategie, settings, pending job, retry/resume of herextractie roept provider alsnog aan | Providertripwire plus native opgeslagen toestand; afwijzing zonder halve commits of verlies van bronwerk |
| Bestaande human-route blijft werken | Verplaatste helper wijzigt kandidaattekst/ID/bronmapping of dubbele job bouwt opnieuw | Hash-equivalentie plus native upload → concept → restart → seal → bouw → correctie → vereiste review → publicatie → API/MCP |
| Historie blijft leesbaar | Historische proofreader vereist uitvoerder of publicatie verdwijnt na restart | Oude modelproof/publicatie en lege-doelrestore lezen zonder provider; registry-uitkomst identiek |
| Boom en overige ondersteunde bronklassen blijven correct | Prozasubtractie breekt gedeeld transport, bronprojectie of boomconfig | Tests per daadwerkelijk ondersteunde bronklasse/topologie; geen onbewezen topologie als PASS |
| Minder fouten/arbeid | Minder correcties verhult gemiste claims of extra annotatietijd | Onafhankelijke adjudicatie, aantallen/noemers, annotatie-/review-/correctie-/totale persoonstijd en taakafronding per variant |

## Concrete ontbrekende praktijkinvoer

Het bestaande praktijkplan meldt nog geen beschikbare referentie of toegewezen
deelnemers. #530 noemt Eenzaamheid met bron-SHA
`2185b6502a76b76e942db2352d746a5f1193645091844fd84241dfb94ac51064`
als bestaande kandidaat, maar bewijst geen toegang tot de bytes, actuele
gebruiksrechten of onafhankelijke HA-referentie. Niet als beschikbare testdata
of door de eigenaar gekozen bron presenteren.

Vóór meting nodig: gekozen richtlijn/selectietaak en inhoudelijke eigenaar;
onafhankelijke referentiemaker/beoordelaar en adjudicator; vastgestelde
acceptatiegrenzen; bevroren vergelijkingsuitvoer of afzonderlijk goedgekeurde
baselineprocedure; gelijke ingestpolicy en verantwoorde taakvolgorde. De bestaande
praktijktoets blijft de registratieplek. Geen kwaliteitsscore, tijdwinst of
praktijkacceptatie is in deze sessie gemeten.

## Eerstvolgende actie

Projectlead wijst bron/selectietaak en inhoudelijke eigenaar aan. Daarna kan de
onafhankelijke referentie worden bevroren en de technische overgangsslice met
exacte acceptatie-/rollbackvoorwaarden uitvoerbaar worden gemaakt. HA-4 blijft
In Progress; definitieve subtractie en praktijkacceptatie zijn open.

## Uitgevoerde verificatie van deze documentatieslice

Op 9 november 2026: repositorypreflight PASS (2310 bestanden),
architectuurgrenzen PASS, `git diff --check` PASS en gerichte controle van
21 lokale document-/codeverwijzingen PASS. Productcode is ongewijzigd;
geen console-, PostgreSQL-, browser- of volledige regressiesuite gedraaid.

De eerste release-controlpreflight met alleen de twee documentpaden was
BLOCKED: gewijzigde testmarkers/evidencepaden ontbraken voor scope/belofte,
slop en releasebewijs. PR #1033 reproduceerde deze fout in CI.
`tests/test_human_annotation_transition_docs.py` controleert nu de lokale
documentlinks en de bron-/scriptpaden uit de inventaris en registreert dat
gerichte documentbewijs bij de bestaande releasecheck. Deze controles bewijzen
geen productgedrag, cutover of praktijkacceptatie. CI-regels zijn ongewijzigd.

Hercontrole na herstel: twee gerichte documenttests via `unittest` PASS,
release-control met beide documenten en het nieuwe testpad PASS,
repositorypreflight PASS (2311 bestanden), architectuurgrenzen, compileall en
diffcheck PASS. De aanvullende lokale pytest-run kon niet starten omdat pytest
in deze omgeving niet geïnstalleerd is; dat is geen test-PASS. De GitHub-CI-run
op de nieuwe PR-head blijft het bewijs voor de volledige suite.

## Vervolgimplementatie: gedeelde helpers en expliciete stop

De opdracht van 9 november vervolgt deze inventaris via
[het stopcontract](1017-prose-transition.md) en
[het actuele compositiediagram](../architecture/prose-transition-1017.md).
Bronfilters wonen voortaan in `prepared_source_views_v1`, read-only semantische
contracten in `semantic_proposal_contract_v1` en boomtransport in
`bounded_model_call_v1`. Bron-, bewijs- en diagnoselezers importeren de oude
prozauitvoerder niet meer. Tijdelijke re-exports houden de nog actieve oude
uitvoering compatibel tot definitieve subtractie.

Een bevoegde actor kan een exacte ongepubliceerde prozawerkrevisie expliciet
stoppen. De bestaande attempt-/documentauthority bewaart bronwerk en een
append-only receipt, blokkeert oude workers/retries en behoudt die blokkade
bij herstart en herstel. Installatie stopt niets; praktijkvergelijking,
productiecutover en definitieve verwijdering blijven afzonderlijk open.
