# MET-41: operationele documentopslag en expliciete inputgrenzen

Change class: A
Promise: Operationele documentreads en metadatawrites laden of herschrijven geen verwerkingsarchief; expliciete bron-, vormings-, kwaliteits- en historielezers behouden hun oorspronkelijke domeinregels en exacte inhoud.
Proof: Native twee-compositie groei-/bytes-/query-/lockproeven, bestaande Review→publicatieketen, ontbrekende/corrupte/legacy variant, CAS/concurrency, echte rollback en nieuw proces plus volledige workflowbackup.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Fysieke operationele documentgrens en alle directe artifact-/attemptconsumenten plus triggers 008/020/021/026/027/029.
Why local patching is insufficient: JSON-projectie of timeoutverhoging laat detoasting, globale documentcontrole, historische groei en incomplete proofbinding intact of verplaatst kosten naar writes/redirects.
Current authority/writer/reader map: Bestaande workflow.documents blijft scalar-, identity-, revision- en lockowner; documentstore beheert compacte document_inputs. FormationTaskStore behoudt bestaande archive/source/proofownership en indexed inputdelen; actor/review/publicatie blijven hun bestaande owners. Callermap en bronnen hieronder.
Supported runtime topologies: Beide bestaande FastBadge CompleteWorkflow PostgreSQL-composities met lokale/Azure bronadapter en nieuwe processen/workers; geen nieuwe multi-host-/globale exactly-once-garantie.
Persisted-state impact: Additieve document_inputs en immutable indexed archiefinputs; expliciete layoutpin. Oude envelope blijft bewaard als historische oorspronkelijke representatie; geen wijziging aan gepubliceerde payload, bronbytes, objects of serving.
Compatibility/migration plan: Expliciete prepare buiten locks en cutover met documentrevision/objectgeneration/source/proof-CAS; nooit GET/startupmigratie. Oude layout blijft herkenbaar tot expliciete voorbereiding; compact-corrupt valt nooit op legacy terug. Native, historische semantische en beslisboominputs behouden hun eigen contract.
Rollback/recovery plan: Native rollback van header/ref/object/attempttransitie; vooraf retained artefacten mogen ongebruikt blijven. Bewaar oorspronkelijke payload. Nieuwe layout vereist compatibele binary, oude writers weigeren; exacte operational records/refs en archiefinputs in bestaande versioned workflowbackup.
Cutover trigger: Expliciete gecontroleerde preparation en CAS op dezelfde docrow; productiecutover pas na native acceptatie en gecontroleerde bestaande-dataovergang onder MET-44.
Cleanup/decommission criteria: Geen actieve volledige-envelopefallback, oude hydratatie of dubbele closurepolicy in overgezette route; audits/releasepins blijven leesbaar; vervangen calls/config/diagrammen bijgewerkt.
Failure blast radius: Betrokken revisie/proof kan expliciet onbeschikbaar zijn; geen ongeautoriseerde review, nieuwe release, verloren besluit of wijziging aan actieve voorganger.
Adversarial proof matrix: §11 en §13: missing/corrupt/membership, wrong source/contract, stale claim/revision/binding/policy/actor, alternatieve writers/legacy, rollback/restart, publicatierace en archiefgroei.
Lifecycle entity: Bestaande geregistreerde SourceSnapshot/WorkingRevision en complete immutable vormingsproof bij FormationTaskStore.
Lifecycle transition: Een bestaande revisie krijgt exact equivalente compacte operationele opslag en expliciet gepinde inputrecords, zonder review-/release-/servingbesluit te wijzigen.
Initial durable state: Originele workflowenvelope met volledige input/historie, oorspronkelijke proof/bronpins, actuele objecten/bindings en canonieke releasetoestand.
Trigger: Bestaande geautoriseerde produceractivatie of expliciete operatorvoorbereiding/CAS van bestaande opslagrepresentatie.
Authorization: Bestaande producer/checkpoint/activatieguards; vóór een nieuwe pin ook live poging/claim/deadline, actuele rol/retirement/named-reviewer en exacte input/context/revisie opnieuw toetsen. Historische producerrechten verlenen geen recht op review of publicatie.
Validation: Bestaande joint gate zonder nieuwe materialisatie; exacte contract-/source-viewbinding, owner-calljournal, originele en onbekende bevindingen, resultaatversies, receipt en actuele activatiecapture.
Mutable entities: Bestaande operationele metadata/refs en bijbehorende layoutpin; objects/attempts alleen via hun bestaande domeincommando en bestaande transactieregels.
Immutable entities: Bronbytes, verzegelde bewijsleden, beschermde historische objectinhoud en alle gepubliceerde releases/revisies volgens bestaande contracten.
Workflow state before: Bestaande processing/in_review/blocked/ready_for_publication-toestand; nooit uit bewijsomvang afleiden.
Workflow state after: Dezelfde domeinuitkomst bij representatieovergang; menselijke besluiten en publicatie bepalen hun bestaande volgende toestand, niet de migratie.
Release state before: Bestaande published/superseded/withdrawn release of geen release.
Release state after: Ongewijzigd door voorbereiding/migratie; alleen bestaande publicatie-/intrekkingsopdracht wijzigt release/serving.
Serving state before: Actieve/inactieve set uitsluitend uit publicatieregister.
Serving state after: Ongewijzigd door deze representatieovergang; geen automatische heractivatie na restart.
Expected API result: Bestaand commandresultaat of expliciete weigering; geen succesvolle pin/objectactivatie bij ontbrekend, gewijzigd of ongeautoriseerd bewijs.
Expected UI result: Zelfde inhoud en actuele bron-/reviewbeslissingen, zonder historische payload voor een operationele headerread; bestaande unavailable/conflictregels bij ontbrekend/corrupt input.
Failure result: Geen halve pin, mutatie of verzonnen closure; behouden bestaande work state; canoniek gecommitte release houdt haar bestaande herstelpad.
Restart result: Gecommitte proof/review/bindings blijven herbruikbaar; geen stale activatie, stille herbouw of heropening van gepubliceerd werk.
Recovery result: Bestaande expliciete preparation/retry/reconcile met dezelfde bron-/revisie-/contractregels; geen reset of terugzetten van reviewwerk.
Legacy-data result: Expliciete voorbereiding met exacte pariteit en CAS; onvoorbereid, corrupt en incompatibel apart; gepubliceerd beleid niet herschrijven.
Required black-box scenario: Bestaande incomplete vorming→expliciete opslagcutover→Review en menselijke bronafhandeling→publicatievoorwaarden ongewijzigd→procesherstart/backuprestore; metadata I/O blijft constant bij groeiende onafhankelijke historie; stale cutover wint nooit van review/bron/proofwijziging.
Explicit non-goals: Geen nieuwe closurepolicy/cache, geen tweede kandidaatmaker, geen productiecutover/deployment, geen heropening van gepubliceerd werk. MET-42 bepaalt latere passage- versus documentbeoordelingsscope; deze wijziging levert haar leesbare inputgrens volledig.

## Gronding en voortgang

- [x] Ground: main `16bf47a`, tree `0381230`; #956 gemerged, CI/Docling/topologie/source/Bend success.
- [ ] Sketch: de onderstaande synthese tegen alle concrete aanroepers toetsen.
- [x] Agree: gebruiker vraagt expliciet het resterende MET-41 uit te voeren; geen aanvullende ontwerpstop gevraagd.
- [ ] Implement: rode native grensproef, storage/read/write/triggerintegratie, variant-/herstel-/groeiacceptatie.
- [ ] Scrap: obsolete generieke hydratatie en grote-JSON-triggerpaden uit de omgezette layout verwijderen; bij structurele tegenspraak synthese herzien.

Dit document is een uitvoeringscontract; geen bewijs dat implementatie of productieherstel al gereed is.

## Gebruik vóór implementatie

```python
header = documents.get_envelope(sid)  # compact bij omgezette layout
processing = tasks.current_processing_input(header, command_id=command_id)
formation = tasks.active_formation_input(header)
# De bestaande unresolved_rejections blijft beslissen met actuele objects/bindings/bron.
quality = documents.review_command_quality_input(sid, object_ids)
source = tasks.retained_extraction(header, required_contract=contract)
history = tasks.processing_history(header)  # alleen expliciete diagnose/export
```

Een actuele input is geen historische export. Een inputreferentie is geen afsluitstatus en geen bevoegdheid. Ontbrekend/corrupt/incompatibel input levert een expliciete weigering, nooit een lege closure.

## Twee onderzochte vormen

A: `documents.envelope_payload` verkleinen en huidige readers/writers aanpassen.
B: een compact operationeel record naast de behouden oorspronkelijke envelope.

Afzonderlijke read-only agents met hetzelfde model onderzochten beide kandidaten; geen onafhankelijke cross-model consensus. Beide vereisen dezelfde triggercutover en expliciete consumer-API's. A vereenvoudigt de bestaande writer, maar vereist alsnog een aparte publishedroute om originele gepubliceerde payloads te behouden. B heeft een extra fysieke recordgrens, maar houdt alle scalars/identiteit/revisie/lock bij de bestaande documentowner en beschermt zowel gepubliceerde als ongepubliceerde oorspronkelijke representaties.

Synthese: B, zonder tweede metadata-/workflowauthority. De side row bevat uitsluitend overige actuele metadata, vaste huidige inputrefs en gekozen extractieheader. Geen title/state/revision/objectgenerationduplicatie, geen archieflijst. Grote inhoud blijft bij FormationTaskStore. Alle documentupdates op de omgezette layout gebruiken alleen compacte gegevens; oude triggers mogen niet impliciet de historische envelope lezen of herschrijven.

We accepteren de expliciete extra record-/migratiegrens in ruil voor gepubliceerde-payloadbehoud en een uniforme operationele route. We accepteren geen stille hydratatie onder get_envelope, geen universele lazy mapping en geen nieuwe completionboolean.

## Concrete callermap

| Grens | Huidige uitvoering | Vereiste overgang |
|---|---|---|
| Constructor/list/get/reload | workflow_documents_cutover `_envelope_from_row`, `list_envelopes`, `get_envelope`; full attempt hydration | Compact gekozen layout; geen historie uit native attemptrows |
| Metadata/object/releasewrite | `_write_envelope_locked`, production `PostgresConcurrentWorkflowDocumentStore.write_bundle`, `_write_release_projection_locked` | Bestaande doclock/scalars; compacte metadata/refs; gepubliceerde working input immutable |
| Ingest/reextract/checkpoint | OperationsConsole + TaskCheckpointWriter + FormationTaskStore | Grote retain/validatie vóór outer transactie; refs/claim/revisie/proof opnieuw controleren bij commit |
| Retry/resume/status | processing_retry, source_selection, dispatcher/handover | Current attempt + gerichte command lookup + exacte cap/running/recoverygegevens; geen historische diagnostiek voor gewone status |
| Closure/problems/readiness | processing_status, formation_problems, recoverable_formation | Expliciet intrinsiek vormingsinput; dezelfde actuele regel, complete oorspronkelijke onbekende bevindingen |
| Bron | source_preparation_context, review_source_records, docling_contract | Gekozen complete retained extractie/view onder oorspronkelijke bron-/extractorbinding; geen GET-herbouw |
| Reviewkwaliteit | review_command_quality_input, quality_evidence | Alleen gekozen laatste run en gevraagde kandidaatleden in oorspronkelijke volgorde/fingerprint |
| Diagnose/export/insight | processing_evidence_export, forensic_trace, settings insight/viewcheck | Expliciete historische enumeratie, behoud recorded/not-recorded en originele hashes/links |
| Triggers | 008/020/021/026/027/029 | Layoutbewust, kleine refs/header; generation-only updates raken geen archiefbody |
| Backup | bestaande PostgresWorkflowRecoveryAdapter / formation_recovery | Exacte layout/metadata/refs/inputs erbij; oorspronkelijke archived bytes en generaties behouden |

## Context en validiteit

| Gegeven | Producent → consument | Owner / levensduur | Geldigheidsregel en ontbreken |
|---|---|---|---|
| Identity/scalars/revision/generation | bestaande doccommand → alle lezers | workflow.documents | Actuele docrow en bestaande source/lineage; geen side-table shadow |
| Metadata en vaste current refs | producer/expliciete cutover → gewone headerreader | bestaande documentstore | Layoutpin + complete row; corrupt compact valt niet terug |
| Replay/proof | definitieve producer → expliciete formatie/assessment | FormationTaskStore archive/sealed proof | Bron/contract/hash/membership; ontbrekend is unverified, geen complete |
| Kwaliteitsrun/leden | record_processing → review/metingen/export | bestaande processing archives | Exacte originele inhoud/volgorde; geen closureauthority |
| Extractie/bronviews | bestaande source prep → worker/review | prepared_extraction_versions/source_read | Hash/source/contract + volledige gevraagde membership |
| Poging/command/cap | reservation/checkpoint → status/retry/worker | bestaande processing_attempts | Exacte huidige claim/revisie/deadline + oorspronkelijke retry-capregel |
| Actuele review/bindings/actor | review/identityowner → beschermde commit | bestaande stores | Opnieuw toetsen bij commit; artefact geeft geen rechten |

## Bewijsplan

| Claim | Tegenvoorbeeld | Native proef / bewijsgrens |
|---|---|---|
| Kleine operationele I/O | Historie 1→25→meer records, grote ruwe replay/kwaliteit/extractie | Execute/fetch/bytes/lockduur en fysieke opgeslagen recordgrootte; geen JSON-padselectie als goedkoop bewijs |
| Geen verborgen triggerwerk | Objectgeneration-, metadata-, bindings-, releaseprojectionwrite | Bovenstaande writes terwijl legacy-payloadtoegang instrumenteel geweigerd/geteld wordt |
| Geen false closure | Ontbrekend replay/pin/member/unknown sourcefinding | Zelfde unresolved_rejections met expliciet input, onbeschikbaar blijft open |
| Exact behoud | Archive/run/proposal/member weggelaten of bron verwisseld | Pariteit bij voorbereiding, immutable sealgates en bronbinding; corruptie geen rebuild |
| Native atomiciteit | Echte SQLfout na ref/headerpin, concurrent review/source/proof | Eén rollback; CASweigering bewaart winnaar |
| Herstel | Worker-kill/nieuw proces, volledige backuprestore | Refs/layout/generaties exact; geen extra modelwerk of reactivatie |
| Varianten | Native v1/v2/v3, historische semantiek en tree | Oorspronkelijke gate of expliciet unsupported vóór cutover; geen nieuw beleid uit ontbrekende data |

## Open uitvoering

Implementatie en metingen volgen. Bestaande-data-productiecutover blijft MET-44; deze code mag die niet via GET/startup uitvoeren. MET-41 blijft open zolang de volledige operationele implementatie en haar native acceptatie ontbreken.

## Uitvoeringsnotitie 31 oktober 2026 — WIP, geen cutover

De aparte adversariële review heeft de volgende keuzes aangescherpt:

1. De operationele rij is onderdeel van dezelfde documentaggregate. Een wijziging moet dezelfde docrow vergrendelen, de documentrevision verhogen, alle betrokken projecties vernieuwen en de definitieve proof/sourcebinding controleren. De eerste databaseguards hiervoor zijn aanwezig; de volledige commandintegratie en CAS-proef ontbreken nog.
2. Originele replaylineage blijft de bestaande archive-id/payloadhash. De normalisatie van alleen `formation_progress` heeft een afzonderlijke activatiehash. Native bewijs vereist de oorspronkelijke capture-ref of exact de bestaande activatiebody; bronbinding en verzegelde root blijven verplicht.
3. Een compacte semantische variant zonder verplichte replayref wordt expliciet geweigerd. Tree, oorspronkelijke afwezigheid en legacy zijn geen impliciete semantische succesvariant. Hun volledige adapter/cutover is nog niet geïmplementeerd.
4. Notice is uitsluitend een aan de verzegelde oorspronkelijke replay gebonden negatieve prefilter; geen menselijke afsluitstatus. De SQL-sealcontrole vergelijkt de complete verwachte leden met het werkelijke ownerarchive, ook bij een zelfconsistente vervalste manifest.
5. Exacte getallen moeten behouden blijven. JSONB-gelijkheid alleen is onvoldoende (`1e20`, `1.0`, `1`, `true`). De prototypecontrole gebruikt de oorspronkelijke JSON-getalrepresentatie en controleert object-/arraystructuur recursief; de normale reader vereist canonieke membertekst en hash.
6. Een bestaande compacte layout mag niet terug naar legacy, de oorspronkelijke envelope mag niet door een oude writer worden gewijzigd, en de operationele rij mag niet los worden getrunceerd/verplaatst.

Aanwezig: geïndexeerde immutable replay-/kwaliteitsinputs bij FormationTaskStore, expliciete intrinsieke vormingsinvoer, behoud van oorspronkelijke onbekende bevindingen, gerichte kandidaatselectie met oorspronkelijke volgorde en hash, en native tegenproeven. Dit is **geen** vervanging van de bestaande closure-, autorisatie- of publicatieregel.

Niet gereed: `prepare_operational_inputs` / atomische activatie, compacte generieke documentreader en writer, producer-/checkpointintegratie, actuele retry-/command-/capinvoer zonder historie, alle Review/publicatie/bron/tree/diagnoseconsumenten, volledige backup/restore, oudere-binary/objectwriterfence en groeiproeven. De end-to-endtest in `tests/test_operational_document_inputs_postgres.py` is bewust nog rood wegens ontbrekende cutover-API. Niet verbergen of als acceptatie tellen.

Migratie 030 is een **niet geregistreerd prototype**; productie gebruikt MIGRATION_NAMES en krijgt deze wijziging dus nog niet. De PostgreSQL-testtemplate leest alle SQL-bestanden en toetst het prototype wel. Geen nieuwe runtime-admissionflag, automatische conversie, deployment of productie-/incidentherstel uitgevoerd. Geen PR of Done totdat de volledige belofte en normale verificatie slagen. Compositiediagram volgt binnen #950 vóór de uiteindelijke PR.

Verificatie van deze WIP-tussenstand: native PostgreSQL 16, beide bestaande lokale/Azure composities; `pytest -q tests/test_processing_archive_inputs_postgres.py tests/test_processing_archives_postgres.py tests/test_formation_evidence_postgres.py -x`: **96 passed**, 129,96 s. Architectuurinvarianten: **6 passed**. `compileall src`, architectuurgrenzen en change-contractvalidator slagen. De normale volledige verificatie is nog niet afgerond; de hierboven genoemde end-to-endtest faalt op de ontbrekende `prepare_operational_inputs`-API. Dit bewijs geldt uitsluitend voor de archive/inputprimitive en bestaande geteste proofroutes, niet voor de complete MET-41-belofte of voor productieperformance.
