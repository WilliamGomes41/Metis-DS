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
Adversarial proof matrix: Bewijsplan hieronder en tests/test_operational_document_inputs_postgres.py plus tests/test_processing_archive_inputs_postgres.py: missing/corrupt/membership, wrong source/contract, stale claim/revision/binding/policy/actor, alternatieve writers/legacy, rollback/restart, publicatierace en archiefgroei.
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
- [x] Sketch: de onderstaande synthese tegen alle concrete aanroepers toetsen.
- [x] Agree: gebruiker vraagt expliciet het resterende MET-41 uit te voeren; geen aanvullende ontwerpstop gevraagd.
- [x] Implement: rode native grensproef, storage/read/write/triggerintegratie, variant-/herstel-/groeiacceptatie.
- [x] Scrap: obsolete generieke hydratatie en grote-JSON-triggerpaden uit de omgezette layout verwijderen; bij structurele tegenspraak synthese herzien.

Dit document is een uitvoeringscontract; geen bewijs dat implementatie of productieherstel al gereed is.

## Gebruik vóór implementatie

```python
header = documents.get_envelope(sid)  # compact bij omgezette layout
processing = documents.processing_command_input(header, command_id=command_id)
formation = documents.formation_input(header)
# De bestaande unresolved_rejections blijft beslissen met actuele objects/bindings/bron.
quality = documents.review_command_quality_input(sid, object_ids)
source = tasks.retained_extraction(header, required_contract=contract)
history = documents.processing_history_input(sid)  # alleen expliciete diagnose/export
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

## Geïmplementeerde overgang en compatibiliteit

Migratie 030 is geregistreerd. `METIS_DOCUMENT_INPUT_STORAGE=v1` kiest alleen voor nieuwe ontvangst de compacte representatie en vereist native `METIS_FORMATION_TASK_STORAGE=v1`. Lege waarde of `legacy` laat nieuwe ontvangst op de bestaande route; andere waarden weigeren. Uitgeschakelde admission zet reeds compacte documenten niet terug. Geen startup-, GET- of retryconversie van bestaande documenten.

`prepare_operational_inputs` maakt een servergebonden plan buiten de documentlock. Dat plan controleert de werkelijke oorspronkelijke envelope, volledige archiveleden, bronbinding en exacte attemptidentiteit. `activate_operational_inputs` vergelijkt revisie, objectgeneratie, bron/proofpins en attemptrecordversies onder dezelfde documentlock. Een gewijzigd plan of stale capture weigert. Een oude writer kan de oorspronkelijke envelope en nieuwe object/attemptstate niet stilzwijgend overschrijven. Legacy inlinepogingen worden alleen als exacte inactieve kopieën voorbereid; eigenaarconflicten weigeren. Niet-compatibele legacyproofs blijven expliciet onvoorbereid.

De gewone reader geeft actuele scalars en compacte metadata. Retry/status lezen geselecteerde laatste/lopende/gevraagde pogingen en scalar captellingen; de volledige historische diagnostiek wordt daarvoor niet opgehaald. Reviewkwaliteit leest alleen de laatste gepinde run en gevraagde kandidaatleden. Vormingscontrole krijgt de oorspronkelijke intrinsieke bevindingen zonder providerbodies; bestaande `unresolved_rejections` blijft beslissen. Expliciete worker-, bron- en diagnoselezers behouden volledige gekozen input. Diagnose kan de originele technische inlinevorm teruggeven; de actieve opslagmarker is geen historisch domeinbesluit.

Beslisboombewijs heeft een eigen immutable archivevariant: oorspronkelijke inventory, constructie en vormingsherkomst. Graaf, besluiten en deelnamebeleid blijven mutable actuele documentgegevens. Commando's verifiëren de oorspronkelijke inventory vóór de transactielock en vergelijken dezelfde treepin opnieuw onder de bestaande fence. De kleine kaartinventory blijft uitsluitend weergaveinput. Een herhaalde gecommitte opdracht behoudt haar bestaande receiptlookup ook bij tijdelijke bronuitval.

Producenten bereiden grote inputs vooraf voor. De bestaande finale activatie bewaakt actuele claim/deadline, sourcepin en proofbinding; de compacte commit schrijft refs en kleine actuele metadata. De oorspronkelijke archive-id en payloadhash blijven behouden naast de bestaande genormaliseerde activatiehash. Een bronvoorbereiding voor B vervangt niet stilzwijgend actieve proof/bron A.

Workflowbackupversie 9 / formationsectie 2 bevat compacte gegevens en verzegelde inputleden binnen de bestaande atomische workflowrestore. Oude backups krijgen alleen lege nieuwe tabellen, geen verzonnen bewijs. De attemptindex wordt uit de oorspronkelijke ownerrijen opgebouwd. Een oudere binary is geen rollbackreader voor geactiveerde layout; rollback vóór productiecutover vereist de bestaande geteste backup en compatibele binary. Productiecutover van bestaande gegevens blijft MET-44.

## Adversariële review

De onafhankelijke read-only review onderzocht concrete bypasses. De implementatie weigert een semantische variant met ontbrekende replay, vervalste attemptindexscalars, gewijzigde membership en cross-aggregate legacyattemptidentiteit. Reviewkaartprojecties zijn niet als commandoauthority gebruikt. De oorspronkelijke base-route behoudt bronverificatie; idempotente graphretries behouden de gecommitte receipt. Stale bron/tree/proof-/revisiecaptures kunnen de winnaar niet vervangen.

## Verificatie

Native PostgreSQL 16, beide bestaande lokale/Azure broncomposities. Gerichte proeven omvatten incomplete vorming, expliciete omzetting, Reviewbron en objectbesluit zonder false closure, hervatten na nieuw proces, nieuwe ontvangst en admission uitzetten, stale CAS, index/variantvervalsing, volledige workflowbackup/restore met actuele metadata, beslisboombewijs en graafcommando, groei van 1 naar 25 grote kwaliteitsruns en gemeten JSONbytes/fysieke compacte rij. Definitieve commandresultaten worden bij de PR vastgelegd; deze sectie is geen productieperformancemeting.

Compositie: [diagram](../architecture/operational-document-inputs-950.md), bereikbaar via Alles over Metis. Geen productiegegevens, deployment of bestaande-data-cutover uitgevoerd.

### Native grensmetingen en tegenproeven (1 november)

Synthetische historie groeit van 1.344.506 naar 31.229.993 ongecomprimeerde bytes. De compacte metadata/ref-rij blijft 2.120–2.126 bytes. Op beide composities blijven de gemeten metadataread/write/statusoperaties 50 SQL-executes en 46 fetches, grootste gedecodeerde JSON 13.208 bytes en totaal circa 216.5 KB. SQLtijd 0,081–0,125 s; grootste gemeten verbindings-/transactiescope (bovengrens voor de daarin gehouden lock) 0,019–0,033 s. Totale operatie 0,156–0,363 s. Geen productiebenchmark of vergelijking onder identieke belasting.

Gerichte geïntegreerde suite: 56 passed; aanvullende bron-A/B-transitie op beide composities en beide opslagvormen: 4 passed. Dit omvat mislukte B-voorbereiding met actieve A ongewijzigd en latere atomische B-activatie. Voor/na-layoutpinning geïnjecteerde echte SQLfouten rollen de layout terug; dezelfde voorbereiding blijft herbruikbaar. Compacte Treevorming→menselijke passage-/graafreview→publicatie bewaart de exacte oorspronkelijke evidence en bereidt de archiveinput vóór de publicatielock; gecommitte retries houden dezelfde receipt. Bron- en proofpins worden onder de bestaande fence opnieuw gecontroleerd. Een extra legacybronproef bewaart de bestaande Doclingkeuze over latere classificatie-/foutruns, zonder provider-/kandidaatbodies te laden.

De volledige regressiesuite wordt op het gecommitte kandidaat-tree uitgevoerd; de uiteindelijke PR vermeldt resultaat, exacte head/tree en eventuele beperkingen. Een afgebroken eerdere run is geen volledige acceptatie.

### Volledige regressie en correcties

De eerste volledige kandidaat (`19cdb417`, tree `fc3c722b`) voerde 6.719 tests uit: 6.656 passed, 37 failed, 26 optionele skips en nul PostgreSQL-skips. De 37 bevindingen zijn opgelost; de betrokken suites zijn integraal opnieuw uitgevoerd: 114 + 18 passed. De correcties behouden expliciete legacyhistorie binnen een reeds gecapturede readscope, halen de actuele ingestreceipt op bij een concurrente duplicate en behouden de bestaande readiness-aanroep wanneer geen treeinput wordt doorgegeven. Historietests en de volledige referentie-oracle lezen nu expliciet historie; de metadatareader wordt niet opnieuw gehydrateerd. De geïsoleerde SQLpariteitsfixture kent de nieuwe legacyreaderfunctie, en de expand-fixture toetst haar uitgestelde constraints vóór de volgende DDL. Alleen het werkelijk benodigde DELETE-recht voor inactieve voorbereidingsrecords is toegevoegd; immutable guards blijven gelden.

Desktop/mobile, donker thema, toetsenbord en no-JS: native Chromiumbrowsertest passed; renders op 1440 en 390 px geïnspecteerd. Impeccable detector: geen bevindingen. De 26 optionele skips betroffen echte Doclingmodellen (12), Bend (11) en het reeds niet geïmplementeerde B23-scenario (3); dit vervangt hun aparte acceptatiejobs niet. De definitieve PR vermeldt afzonderlijk de eindrun op de gecorrigeerde kandidaat.

### Aanvullende bron-/producergrens

Een aanvullende native proef heeft aangetoond dat een geprojecteerde oude Doclingbronrun anders als nieuwe kwaliteitsrun kon worden teruggeschreven. De compacte producerkopie verwijdert nu die leesprojectie vóór `record_processing`; alleen de nieuwe run wordt toegevoegd, terwijl historische export de reeds gecommitte index behoudt. De proef controleert na echte workeruitvoering exact `after[:-1] == before` en één nieuwe run. De geïntegreerde operationele/producerproofsuite is daarna opnieuw uitgevoerd: 85 passed. Ook een aanwezige maar corrupte lege/null-extractie mag niet door cutover tot afwezigheid worden genormaliseerd; de oorspronkelijke bronowner weigert haar. Een oorspronkelijke lege replay behoudt haar exacte historische vorm zonder vormingsproof te verzinnen.

De controle van retrybudget-accounting gebruikt een gecontroleerde monotone modelklok. De oude fixture koppelde dat aan één seconde echte autorisatie-/databasevoorbereiding en kon daardoor onder runnerbelasting terecht op de eigenaar-deadline worden geweigerd. De fixture houdt de echte owner-deadline ruim genoeg en simuleert dezelfde budgetoverschrijding expliciet; productietimeouts en guards zijn ongewijzigd. De native geïsoleerde proef slaagt.

## Definitieve volledige verificatie

Corecommit `6303b0895a5e77c2a84f8659a0babea1e1d972f5`, tree `4cee99338fbca842db9d96ea427b0ce16c56fd4d`: **6.696 passed, 26 bestaande optionele skips, 0 failures/errors en 0 PostgreSQL-skips**. Alle 6.722 verzamelde tests zijn aantoonbaar precies eenmaal over vier onafhankelijke PostgreSQL 16.15-clusters uitgevoerd; de shardverifier controleert complete selectie/uitvoering, dezelfde commit en collectiondigest. Python 3.12.14, Chromium ingeschakeld; maximale shardduur 1.741,515 s. [Compact bewijsrecord](met41-operational-verification.json). Na deze run volgt uitsluitend documentatiebewijs en de vaste GitHub-bronverwijzing in Metis uitgelegd; de betreffende inhouds-/browserchecks worden afzonderlijk opnieuw uitgevoerd.

Documentatieverwijzing na de core-run: 3 inhouds-/Chromiumtests opnieuw passed. De twee gekoppelde nieuwe GitHub-documenten bestaan op de vastgelegde referentierevisie `e6e2470`.
