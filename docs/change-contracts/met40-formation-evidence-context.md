# Vormingsbewijs en actuele bronafhandeling — contract voor #949

Change class: C
Promise: Eén toetsbaar ontwerp bindt herbruikbaar vormingsbewijs aan de bestaande bron-, review- en publicatieautoriteiten, zonder een tweede voltooiingsstatus.
Proof: Herleidbare reader/writer-/contextinventaris, expliciete bewijs- en transactieregels, compatibiliteitsmatrix en falsificerende acceptatieproeven voor #950–#953.
Touches lifecycle invariants: no
Rewrite risk: none

Deze classificatie geldt uitsluitend voor deze ontwerpdocumentatie. Het ontworpen
vervolg raakt activatie, gedeelde bewijsgrenzen, migratie en publicatie en wordt
als **Class A / rewrite risk high** behandeld. Dit document implementeert niets,
wijzigt geen bestaand protocol en bewijst geen productieherstel.

Onderdeel van [#948](https://github.com/WilliamGomes41/Metis-DS/issues/948),
[MET-40](https://linear.app/metis-phoenix/issue/MET-40/949-leg-het-integrale-vormingsbewijs-en-contextcontract-vast)
en MET-6/#877. Onderzochte basis: `0bbd58f2aa2b1f4a9e6dff288458ec76b4809c56`.
Gebruikersopdracht: MET-40 starten op 31 oktober 2026. De onderstaande keuzes
vormen een ontwerp ter review, geen toestemming voor een runtimecutover.

## 1. Probleem, bestaande norm en bewijsgrens

De operationele envelope bevat zowel actuele documentgegevens als complete
vormings- en kwaliteitsgeschiedenis. De aangeleverde productiemeting noemt
circa 25 MB logisch JSON en 4,2 MB gecomprimeerd: 13 MB replay, 9 MB kwaliteitsruns
en 2,8 MB extractie. Dit zijn aangeleverde meetgegevens, geen opnieuw uitgevoerde
database-inspectie. QueryCanceled/SQLSTATE `57014` en de ingestelde SQL-grens van
vijf seconden zijn vastgesteld. De specifieke falende SQL/fase blijft apart te
bevestigen onder MET-38; een lokale GIN-proef bewijst die oorzaak niet.

Er bestaan twee verschillende full-envelopepaden:

- `read_review_document` haalt bij `_review_check_formation` de volledige
  envelope **binnen** de repeatable-readcapture op.
- `read_review_passage` doet dat niet op dezelfde plaats. Tijdens de latere
  `_review_formation_notice` wordt de compacte request-envelope verwijderd en
  opnieuw via `_envelope/get_envelope` geladen. Bron- en closurewerk volgt daarna.

De oplossing mag dus geen onbewezen gelijkstelling van die twee paden bevatten.
Ook een JSON-padprojectie kan de grote JSONB nog volledig laten detoasten.
Een kleiner responseobject bewijst geen passende fysieke toegang.

De domeinregel blijft die van `unresolved_rejections`: oorspronkelijke
producerbevindingen worden gecombineerd met actuele, exact geldige menselijke
bronafhandeling. Negen gedeeltelijke taken betekenen niet negen actuele blockers.
Onbekende bronlocaties verdwijnen niet doordat alle zichtbare objecten beoordeeld
zijn. Bronbytes, kandidaattekst/-identiteit, mapping en bestaande besluiten blijven
onder hun bestaande owners; deterministische materialisatie blijft de enige
kandidaatmaker. Publicatie-/servingauthority blijft canoniek, conform
`docs/agents/lifecycle-vsa.md` en de bestaande broncontextcontracten.

## 2. Gebruik en operatiescopes

De volgende interfaces beschrijven verantwoordelijkheid; zij zijn **geen reeds
geïmplementeerde API's** en vereisen geen nieuwe servicelaag.

```python
passage = kernel.read_review_passage(actor, working_revision, object_id)
# Actueel passage-/contextbewijs en de bestaande commandpreconditie.
# Documentbeoordeling: NotEvaluated tenzij een complete geldige capture bestaat.

assessment = kernel.assess_working_revision(actor, working_revision)
# Complete bronverplichtingen + actuele review/bindings + exacte dependencyset.

result = kernel.review_object(existing_command, precondition=passage.precondition)
# Bestaande mutatie, autorisatie, exacte broncontrole en variantcontract.

release = kernel.publish(existing_publish_command)
# Complete actuele beoordeling onder de bestaande publicatie-/canonieke grens.
```

| Operatie | Vereiste scope | Uitkomst en grens |
| --- | --- | --- |
| Passage/context openen | Geselecteerd object, vereiste inkomende/uitgaande context, relevante versies/bindings en gecontroleerde bron | Geen volledige documentclosure of retry/resume-berekening als verborgen bijwerking |
| Overzicht/kaarten | Actuele compacte kaartinputs en actor | Bestaande kaartfacts blijven niet-autoritatief; geen publicatiebewijs |
| Document beoordelen / vormingsproblemen | Alle verplichtingen en voor hun afhandeling noodzakelijke huidige objecten/bindings en complete bronbasis | Eén bestaande evaluator; geen passagewindow als complete bron |
| Besluit opslaan | Volledige validatie- én invalidatieclosure van het command, actuele bevoegdheid en bestaande preconditievariant | Snapshot-generation, objectsetmerge en interaction-identity zijn verschillende contracten |
| Publiceren | Complete actuele beoordeling, bronintegriteit, objectversies, vereiste beslissers en lifecycle | Publicatie beslist opnieuw; een eerder getoonde beoordeling verleent geen bevoegdheid |
| Diagnose/export/historie | Expliciet gekozen historie of archiefrecords | Mag groter zijn; behoud autorisatie en gepinde bron-/code-/contractidentiteit |

Documentbeoordeling heeft onderscheiden resultaten: `NotEvaluated`,
`Evaluated(unresolved, dependencies)` en een expliciete onbeschikbaarheidsreden.
Een lege lijst telt alleen na een volledige geldige beoordeling. Deze waarden
zijn vluchtige queryresultaten; geen nieuwe lifecycle of persistente cache.

Het bestaande bronbesluit blijft gelden: het oorspronkelijke bronbestand wordt
bij openen/beoordelen/publiceren gecontroleerd zoals de huidige contracten eisen.
De kosten daarvan worden gemeten, niet stil vervangen door kaartfacts of een
existence-/sizecheck. Noodzakelijke dependencygroei wordt niet afgekapt.

Behoud de bestaande uitzondering voor veilige niet-inhoudelijke disposition bij
ontbrekende oorspronkelijke bron: `test_review_command_source_failure_v1.py`
bewijst dat zo'n exact retained bronrecord kan worden afgewezen terwijl content
approval wordt geweigerd. Dit ontwerp maakt geen algemene bronopenplicht voor
ieder besluit en verruimt evenmin de bestaande approvalvoorwaarden.

## 3. Gegevensmodel en eigenaarschap

| Gegeven | Betekenis / bestaande eigenaar | Opslag- en mutatieregel |
| --- | --- | --- |
| LogicalDocument / SourceSnapshot | Bestaande documentidentiteit en immutable bronversie | Geen nieuwe identiteit uit naam, hash of zichtbare versie afleiden |
| Voorbereide bron | Extractie-/viewcontract bij FormationTaskStore en source store | Exacte bronbinding, gecontroleerde complete root/membership; selectie bewijst alleen haar scope |
| Vormingscontext en resultaten | Bestaande poging/context, task checkpoints, joint validation | Actuele taakresultaatprojectie blijft wijzigbaar volgens bestaande correctieregels; wijziging invalideert de receipt. De actieve proof bindt afzonderlijke immutable resultaatversies; een oude claim activeert niets |
| Geactiveerd vormingsbewijs | Volledig gevalideerde immutable bewijsset, nieuw inputcontract bij dezelfde owner | Geen `complete=true/false`; bevat ook oorspronkelijke afwijzingen en onbekende scope |
| WorkingRevision | Actuele objectversies, review, source roles/context en bindings in workflow PostgreSQL | Bestaande atomiciteit, historie en gepubliceerde immutability behouden |
| Documentbeoordeling | Berekening door bestaande bronaccountability-/recoverable-formationowners | Huidige afhandeling afleiden, niet historisch producerbewijs herschrijven |
| Publicatie | Canonieke publicatiestore/registry | Release en actieve serving-set hebben geen envelope-/UI-authority |
| Kwaliteits-/verwerkingsarchief | Herleidbare historie bij bestaande stores | Afzonderlijk adresseerbaar; geen onbegrensde lijst in de operationele header |

`OperationsConsole` is kernelorchestratie ondanks de naam.
`operations_console_app` is HTTP/presentatie; `console_asgi` is de composition root.
Geen duurzame domeintoestand verhuist naar de console, procesgeheugen of een
nieuwe achtergrondmanager. Geen nieuwe databaseprovider of algemene eventbus.

## 4. Vormingsbewijs: inputcontract en vertrouwensgrens

Een voorgestelde `FormationEvidenceRef` moet naar **één complete gecontroleerde
set** verwijzen. De precieze fysieke tabelvorm wordt in #950 uitgewerkt binnen
de bestaande store; dit contract bepaalt reeds wat die vorm moet bewijzen.

| Verplichte binding | Te behouden inhoud |
| --- | --- |
| Bron/revisie | LogicalDocument, SourceSnapshot, WorkingRevision, source ID, bronhash/-versie en contentkind |
| Producent | Semantische identiteit met de bestaande prompt/schema/model-/policy-/extractor-/reconstructiecontracten |
| Voorstel | Exact volledig geactiveerde/geresolveerde replayvoorstel, bestaande voorstelhash en joint-validationresultaat; ruwe provideruitvoer blijft afzonderlijke historie |
| Resultaatset | Geactiveerde context/poging, alle resultaatidentiteiten/hashes en volledige manifest/memberdekking |
| Bevindingen | Alle oorspronkelijke open afwijzingen, exacte spans, redenen en expliciete onbekende scope; niets wegfilteren |
| Bronbasis | Gecontroleerde extractie-/viewreferentie en source-blocks-/evidence-basis volgens het oorspronkelijke validatorcontract |
| Activatie | Bestaande claim/eigendom, verwachte revisie, activatiebinding en producer-/validatorversie |

De huidige `exact_replay_lookup` controleert en kopieert het volledige voorstel
bij gebruik. De nieuwe reader mag dat alleen vervangen door een verzegelde,
eerder volledig gecontroleerde bewijsset. Een type, `proposal_hash` of bestaande
`final_validation`-receipt is op zichzelf niet voldoende.

Belangrijk: bounded formation berekent al bevindingen vóór de joint gate; de
definitieve replay-/checkpointassemblage van die bevindingen volgt later. De
joint-validationreceipt bindt voorstel/resultaatset, maar **niet** de volledige
bevindingenset en bronbasis. De nieuwe seal moet deze complete invoer na de
bestaande definitieve assemblage en vóór activatie omvatten. Anders wordt alleen
het voorstel bewezen, terwijl publicatie op ontbrekende bevindingen kan worden
gebaseerd. Dit contract verplaatst geen domeinregel naar de provider.

Het replayvoorstel is de exact geresolveerde/gevalideerde activatie-invoer. Het
is niet noodzakelijk de onbewerkte modelrespons: recoverable formation kan een
opnieuw gevalideerd deelvoorstel behouden en bounded formation voegt geldige
taakvoorstellen samen. Bewaar de ruwe provideruitvoer apart met haar provenance;
label die niet als het gezamenlijk gevalideerde voorstel.

De writer controleert complete invoer en joint validation, bewaart complete
records en verzegelt hun leden/identiteit. Na verzegeling mogen normale
applicatiewrites geen leden toevoegen, wijzigen of verwijderen. De activatie
pint slechts zo'n complete set. Readerchecks omvatten contract, bronbinding,
inhoudsintegriteit en volledige gevraagde membership; een per-recordhash bewijst
geen afwezige leden. Het manifest mag geen tweede handmatig bijgehouden lijst zijn.

Immutability geldt zolang de complete bewijsset wordt behouden. Zij trekt niet
stil de bestaande geautoriseerde verwijdering van een volledig ongepubliceerd
aggregate in. Toegestane cascades volgen de bestaande delete-/audit-/retentieregels
en mogen geen overlevende root, revisie of release met een verdwenen lid achterlaten.
Dit ontwerp introduceert geen nieuwe verwijder-/GC-bevoegdheid.

De actieve set verwijst naar onveranderlijke resultaatversies, niet uitsluitend
naar de huidige vervangbare `formation_task_results`-rijen. Een volgende nog
niet geactiveerde poging of resultaatcorrectie mag een oudere geactiveerde set
niet stil wijzigen. Haar nieuwe set doorloopt opnieuw voorbereiding/seal/activatie;
de bestaande review-/resume-/human-workguards blijven van toepassing.

Capabilityvarianten blijven expliciet: task-v1 en legacy semantische verwerking,
de oorspronkelijke v2/v3-contracten, en de structurele beslisboomroute. Die laatste
kan bewust zonder `validator_input_ref` lopen en heeft een eigen activatiecontract.
Zij mag niet door de aanwezigheid van een generieke proofvorm als geverifieerd
worden aangemerkt. Een variantadapter moet hetzelfde bestaande contract bewijzen
of expliciet niet ondersteund zijn vóór cutover; geen impliciete default-/policywissel.

De bestaande source-readrecords bieden een patroon met database-sealing.
Niet alle huidige FormationTaskStore-records zijn al zo beschermd: `_immutable`
controleert gelijkheid via de store-API; dat is geen algemene DB-immutabilityclaim.
#950 moet alle ondersteunde directe SQL-/legacy-/oude-binarywriters inventariseren
en de nieuwe bescherming daadwerkelijk afdwingen of de writer weigeren.

Het vertrouwensmodel blijft dat van de vertrouwde kernelwriters en immutable
PostgreSQL-/bronopslag. Hashes detecteren corruptie; zij zijn geen bescherming
tegen een beheerder die inhoud en hashes samen herschrijft. Volledige
bron-/voorstelcontrole bij bewijsproductie blijft verplicht. Alleen geverifieerde
inputs mogen de bestaande evaluator bereiken; geen willekeurig request-JSON dat
een gevalideerde carrier kan nabootsen.

## 5. Eén regel voor actuele bronafhandeling

`recoverable_formation_v1.unresolved_rejections` blijft de regelowner.
Het herbruikbare immutable bewijs vervangt inputherhaling, niet de regel.

- Een oorspronkelijk modelprobleem blijft reconstrueerbaar.
- Definitieve menselijke afhandeling telt alleen voor de exacte bron, passage,
  context, objectbetekenis en geldige reviewbindings die het bestaande contract eist.
- Correctie, contextwijziging, reset, tweede review of gewijzigde policy kan de
  huidige geldigheid wijzigen zonder het oorspronkelijke producerbewijs te wijzigen.
- Onbekend of niet exact gelokaliseerd bewijs blijft onopgelost volgens de huidige regel.
- Een geslaagde poging, taakpercentage, lege projectie of kaarttelling is geen
  bewijs van complete bronafhandeling.

Herbruikbare intrinsieke feiten en actuele domeinbeslissingen blijven
onderscheiden. `ReviewObjectFacts` mag niet ongemerkt naar KnowledgeObject,
commandinput of publicatiebewijs worden gecast. Geen tweede SQL-reglement,
persistente closureboolean of actor×document-statusdatabase.

## 6. Contextcontract tussen stappen

| Gegeven | Producent → consument / eigenaar | Levensduur en geldigheid | Ontbrekend/verouderd |
| --- | --- | --- | --- |
| Bronidentiteit | Ingest → alle stappen / source/document owner | Immutable snapshot en exacte lineage | Geen andere bron raden; protected actie weigeren |
| Configuratie/route/contract | Bestaande reservation/routeowner → worker/checkpoint/activatie | Gepind per compatibele context; R4.6/MET-29 blijft eigen contract | Expliciete incompatibiliteit, geen stille routewisseling |
| Poging/claim/verwachte revisie | Reservation/dispatcher → checkpoint/activatie | Actuele eigenaar en deadline; niet uit tijdelijk geheugen afleiden | Conflict/verlopen claim, geen activatie |
| Extractie/bronviews | Bestaande voorbereiding → review/worker/closure | Exacte input- en producerbinding; onafhankelijk herbruikbaar waar contract gelijk blijft | Legacy-onvoorbereid apart van corrupte gepinde bron |
| Complete bewijsset | Bestaande validatie/activatieowner → evaluator | Immutable complete seal, exacte bron en oorspronkelijke contractversie | Niet geëvalueerd/onbeschikbaar; geen nul bevindingen |
| Actuele objecten/bindings | Bestaande commandstores → beoordeling/commit | Eén coherente capture; relevante historie en wijzigingscontract | Conflict of nieuwe capture; geen gemengde generaties |
| Policy/deelnemers/bevoegdheid | Bestaande document-/identityowners → protected commit | Actueel aan commitgrens; statische proof verleent geen recht | Weigering of herbeoordeling |
| Kwaliteit/diagnostiek | Processing/audit → expliciete diagnose/export | Historische versiegebonden waarneming | Geen substituut voor actuele domeinwaarheid |
| Tijdelijke berekening | Query → presentatie | Alleen deze capture; veilig te verliezen | Opnieuw lezen, geen herstel uit proceskopie |

Gebruik bestaande gerichte types en overdrachten. Geen universeel contextobject
of nieuwe dispatcher; bestaande duurzame reservation/workermechanismen blijven.

## 7. Transacties, lifecycle en fouten

De stateless query krijgt geen lifecycle. Stateful voorbereiding/activatie en
WorkingRevision-mutaties blijven bij hun bestaande owners.

1. **Registreren:** bestaande geautoriseerde idempotente opdracht/poging met
   bron/configuratie/revisie reserveren; nog geen nieuw bewijs actief.
2. **Voorbereiden:** model-/bron-/hash-/volledige validatiewerk buiten gedeelde
   schrijflock én de werkelijke buitenste DB-transactie.
3. **Checkpoint/seal:** complete gecontroleerde artefacten duurzaam bewaren;
   dezelfde claim, bron, configuratie, rechten en deadline opnieuw toetsen.
4. **Activeren:** onder de bestaande documentbarrière de complete verwijzing
   pinnen met de huidige revisie-/claimvoorwaarden. De deterministische maker
   en bestaande activatie behouden kandidaattekst/-identiteit/-mapping.
5. **Menselijk besluiten:** objectversies, context, bindings en audit als één
   bestaande commandtransactie; huidige mutability en actor opnieuw controleren.
6. **Publiceren:** complete actuele beoordeling en canonieke commit volgens §8;
   WorkingRevision sluiten zoals het bestaande lifecyclecontract vereist.

Een crash vóór pinning kan een ongebruikt geldig artefact achterlaten, nooit
een half geactiveerde set. Na commit moet een nieuw proces dezelfde pin kunnen
hergebruiken. Dezelfde opdracht met dezelfde payload volgt het bestaande
duplicatecontract; afwijkende hergebruikte identiteit geeft conflict. Geen
globale exactly-once-providerclaim. Een oudere voorbereiding overschrijft de
winnende revisie niet. Buiten-gepubliceerde herverwerking blijft de bestaande
geautoriseerde route; een reeds beoordeeld document wordt niet als migratie
opnieuw door model/materialisatie gehaald.

## 8. Coherente capture, bindings en werkelijke publicatiecommit

Capture van mutable input gebeurt kort en coherent. Zware pure berekening volgt
buiten die SQL-transactie. Het resultaat verwijst naar de exacte dependencyset.
Beschermde commands lezen onder hun bestaande locks relevante mutable inputs
opnieuw, toetsen de originele preconditievariant en valideren het bereik opnieuw.

`object_generation` is geen complete geldigheidsvector. Binding-only vervanging,
policy, deelname, bron-/vormingspin, contract en rol-/retirementwijzigingen moeten
door een bestaande coherente capture/lock of een bewezen vernieuwde afhankelijkheid
worden gedekt. Geen nieuwe teller introduceren zonder writerdekking; geen huidige
disjuncte storage-merge omzetten naar een universele generation-CAS.

De huidige topologie heeft **geen gezamenlijke workflow/canonical transactie**:
`console_asgi` bindt de workflowstores; `OperationsConsole.publish` houdt de
workflow-documentbarrière vast; `persist_published_release` gebruikt een eigen
canonieke verbinding/transactie en logical-documentlock. De canonieke commit
kan geslaagd zijn vóór de workflowprojectie is bijgewerkt.

#952 moet bewijzen dat de laatste geldigheidscontrole de onafhankelijke canonieke
commit afdekt via de bestaande workflow-document- en canonieke barrières, inclusief
alle relevante schrijvers. Alleen een proceslock of readtoken bewijst dat niet.
Na canonieke commit is een mislukte workflowprojectie een bestaande herstelbare
projectiefout, geen teruggedraaide release. Serving blijft uitsluitend registrywaarheid.
Slotvolgorde, audit-hashketen en actuele account-/policychecks blijven behouden;
de D1-/D2-opdrachten van MET-36 worden niet stil herontworpen.

Accountrollen worden voor de **huidige actie** gecontroleerd. Dit ontwerp maakt
geen nieuwe regel dat een latere rolwijziging alle historische goedkeuringen
intrekt. Die historische geldigheid blijft volgens de bestaande domeinregels;
een wijziging daarvan vraagt een afzonderlijk inhoudelijk besluit.

Globale `replace_bindings` is een apart operator-/restorepad: de huidige
authorizationlock bewijst geen volledige bescherming door documentbarrières.
Ontwerpkeuze: globale restore heeft een expliciete **exclusieve onderhoudsscope**;
zij is geen gelijktijdig operationeel review-/publicatiecommand. #952 moet de
mechanische uitsluiting op de echte opslag-/runtimegrens bewijzen, met behoud van
alle gecontroleerde operatoringangen. Zolang dat bewijs ontbreekt is de online
cutover niet toegestaan. Geen concurrerende restore toestaan op grond van een
UI-waarschuwing, alleen een proceslock of de aanname dat een operator voorzichtig is.

## 9. Bestaande ingangen en gewenste aansluiting

Dit is een map van concrete bestaande grenzen op de gepinde basis. Zij is geen
claim dat een dynamische reachability- of runtimeproef al is uitgevoerd.

| Pad / bestaande owner | Bestaand bereik | Opdracht voor vervolg |
| --- | --- | --- |
| `console_asgi.build_app` en beide FastBadge CompleteWorkflow-klassen | Productiecompositie met workflow/canonical en lokale of Azure bronadapter | Geen alternatieve authority; dezelfde contracten op beide composities |
| `review_workboard_v1.install_review_workboard/review_get` → `read_review_passage/read_review_document` | Persoonlijk overzicht, object, documenttaken, navigatie na POST | Expliciete scoped query, geen documentstatus als verborgen detailafhankelijkheid |
| `operations_console_app._review_formation_notice` → `processing_status` | Full-envelopeherlezing, volledige bron/objects/bindings en resume-/retry-informatie | Ontkoppel presentatie van volledige statusberekening; complete beoordeling blijft expliciet |
| `source_selection_ui_v1` en `formation_problems_v1.collect` | Vorming, broncontext, problemen en gerichte herstelacties | Zelfde evidence/evaluator; diagnoses behouden hun expliciete complete scope |
| `settings.insight_v1` en `console_read_operations_v1` | Diagnose/detail versus compacte operationele overzichten | Geen onbedoelde detailfallback; onbekende input niet als leeg tonen |
| `workflow_documents_cutover_v1` documentreads/writes | Envelope/card projections, task-v1-hydratatie, list/refresh/startup en bundlewrites | Ook constructors, reloads, triggers en legacywriters in de fysieke kosteninventaris |
| `review_command_v1` → `apply_review_changes` | Gerichte bestaande command met actuele auth, generation-/objectsetvariant, bindings/audit | Beide bewijs- en mutationclosure behouden; geen readwindow als saveclosure |
| Bronbesluiten, context/reset, batch/groep, correctie, type/relaties, tweede review, heropenen en repair | Bestaande objectversies en invalidatie van reviewevidence | Alle betrokken writers op één gedeeld inputcontract; MET-35/#942 en MET-36/#729 blijven eigen opdrachten |
| Deelname/reviewconfiguratie en identiteit | Wijzigen van wie mag/moet beoordelen | Live policy-/actorwaarheid, geen artefact als rechtenbewijs |
| Ingest/reextract/klassepromotie/resume/worker | Bron-/vormingsreferenties en objectsetactivatie | Bestaande claim, mutability, compatibiliteit en deterministic materialisation |
| Publicatie, opvolger, withdrawal/reconcile | Canonieke release/serving en afgeleide workflowprojectie | Gepubliceerde historie immutable; geen status uit envelope of kaart als servingauthority |
| Processing-evidence/export/MCP/retrieval/CLI en directe storecalls | Andere consumers buiten de Review-knop | Expliciete adapter/versiecontracten; ongepubliceerde bronnen niet via Product API uitleveren |

Method resolution is op beide ondersteunde FastBadge-klassen geïnspecteerd:
`processing_status` komt uit OperationsConsole, `publication_readiness` en
`consider_publish` uit PublicationReadinessMixin, `_publish_locked` uit
DurablePublicationConsole, `_envelope/_save_envelopes` uit de PostgreSQL-mixin
en `review_object` uit ReviewClosureConsole. Namen alleen zijn dus geen veilige
scopegrens; subclass-/overridepaden horen bij de bewijsinventaris.

## 10. Overgang en compatibiliteit

| Fase | Authority en toegestaan gedrag | Exitcriterium |
| --- | --- | --- |
| Expand | Bestaande geldige representatie blijft leidend; nieuwe schema/validators en volledige bescherming toevoegen | Writer/readermap en opslagconstraints getest; geen twee onafhankelijke beslissers |
| Prepare | Expliciete idempotente operator-/migratieopdracht uit bestaande retained bron/replay; zwaar werk buiten lock | Complete verificatie én oude/nieuwe domeinpariteit op dezelfde capture |
| Pin | Onder bron-/revisie-/contract-CAS complete referentie installeren | Nieuwere writer wint; stale voorbereiding blijft ongeactiveerd |
| Cutover | Alleen bewezen compatibele readers/writers voor voorbereide revisies | Native correcte gebruikersflow, restart/rollback, alle ingangen en acceptatiebudgets |
| Contract/cleanup | Oude actieve volledige-envelope-/hydratatiepaden verwijderen uit overgezette operaties | Geen permanente GET/startupherbouw of full-archivefallback; historie nog reconstrueerbaar |

Tijdelijke inline compatibiliteitsgegevens mogen alleen door dezelfde bestaande
writer atomair worden onderhouden, met één aangewezen authority en een expliciet
exitcriterium. Zij mogen geen blijvende dubbele truth worden. Nieuwe readers
worden niet gecombineerd met oude writers die hun referenties/geldigheid niet
onderhouden. Een binaryrollback naar een lezer die het nieuwe bewijs niet begrijpt
is geen ondersteund herstel totdat het compatibiliteitsbewijs dat toelaat.

Voor legacy zijn drie verschillende uitkomsten verplicht: nog niet voorbereid,
gepinnd maar corrupt/onvolledig, en incompatibel contract. Geen van deze betekent
compleet of nul problemen. Onvoorbereide documenten houden tot hun expliciete
cutover een duidelijk benoemde compatibele route; geen onverwacht massaal
onleesbare documenten. De nieuwe route valt niet stil terug op het oude archief.

Voorbereiding van Smetten behoudt bestaande menselijke besluiten en sluit
oorspronkelijk gelokaliseerde bevindingen opnieuw af met die actuele besluiten.
Geen producerwerk herhalen, kandidaten reconstrueren, context invullen of
ongekende spans verzinnen. Gepubliceerde releases/revisies blijven onder hun
oorspronkelijke contract; nieuw beleid krijgt de bestaande opvolgerroute.
Retentie van superseded objecten blijft MET-37; niets gepinds of releasevereists
wordt verwijderd om een prestatiedoel te halen.

Gepubliceerde legacy-envelopes worden niet alsnog vervangen door nieuwe
referenties. Hun immutabilityguard geldt ook na een canonieke commit waarvan de
workflowprojectie nog niet is hersteld. Voor deze revisies mag alleen een
additieve afgeleide lookup buiten de verzegelde oorspronkelijke payload worden
voorbereid. Technische inhouds-, hash-, membership- en oorspronkelijke
contractcontrole blijven bij die voorbereiding verplicht. Het is geen nieuwe
inhoudelijke beoordeling onder nieuw beleid en geen vervangende publicatiereceipt.
Als het oorspronkelijke bewijs/validatorcontract niet kan worden vastgesteld,
blijft historische compatibiliteit of een expliciete niet-ondersteunde leesuitkomst
over; een additive lookup op basis van alleen een hash wordt geen vertrouwde proof.
De reeds canoniek vastgelegde release/serving wordt daardoor niet herbeoordeeld.
Een mutatie van gepubliceerde payload valt buiten deze opdracht en vraagt een
afzonderlijk geautoriseerd lifecyclecontract; het is geen technische uitzondering.

## 11. Invarianten en falsificerende proeven

| Invariant / owner | Handhaving in het ontwerp | Tegenproef die moet falen |
| --- | --- | --- |
| Exacte bron en enige kandidaatmaker / bestaande source/materialisationowners | Geen kandidaat(re)constructie of tweede creator bij lezen/migratie; bronviews alleen expliciet voorbereiden met bron-/mappingpariteit | Gewijzigde tekst, locator of tweede creator via fallback |
| Complete oorspronkelijke bewijsset / FormationTaskStore-activatie | Volledige validatie, seal/membership en exacte pin | Eén bevinding/taak/member weglaten met verder geldige hashes |
| Actuele menselijke afhandeling / bestaande evaluator | Exacte object-/bron-/context-/bindingsregels live | Goedkeuring of source role voor oude literal/andere bron hergebruiken |
| Onbekend bewijs blijft open / recoverable formation | Unknown-scope apart behouden | Alle zichtbare objecten klaar maar niet-gelokaliseerde finding verdwijnt |
| Geen stale command / bestaande commandowners | Oorspronkelijke preconditievariant plus actuele mutable dependencies | Alleen relevante binding/policy of huidige actorbevoegdheid aanpassen tussen GET en commit |
| Atomiciteit/audit / workflowstores | Object, binding en event gezamenlijk committen | Fout na objectwrite maar vóór binding/event geeft half besluit |
| Publicatie immutable/registryauthority / canonical owners | Volledige huidige beoordeling tot canonieke commit | Context/publicatie-race of workflowprojectie als releasewaarheid |
| GET read-only / bestaande queryscope | Geen bewijsbouw, materialisatie, nieuwe domeinstatus of backfill | Ontbrekende proof veroorzaakt writes of providerwerk bij lezen |
| Herstart behoudt werk / checkpoint/activationowners | Duurzame referentie, claim/revisie en compatibiliteit | Nieuw proces activeert oude claim of verliest gecommitte besluit |
| Groei past bij operatie / bestaande kernelread-/writerowners | Fysiek passend bereik, noodzakelijke dependencies apart | Onafhankelijke archiefgroei vergroot vaste passage-I/O of iedere savelock |

## 12. Lifecycle-/rewritecontract voor #950–#953

De volgende velden beschrijven het **ontworpen vervolg**, niet een in deze PR
uitgevoerde transitie. Per implementatieslice moeten zij concreet worden bewezen.

Lifecycle entity: Bestaande SourceSnapshot, WorkingRevision en PublicationRelease; complete vormingsartefacten bij de bestaande checkpointowner.
Lifecycle transition: Geautoriseerde complete bewijsset voorbereiden/verzegelen en voor dezelfde toegestane revisie activeren; bestaande menselijke curation en publicatie blijven hun bestaande overgangen.
Initial durable state: Geldige huidige revisie met retained bron/producerbewijs, eventueel partial formation en menselijke besluiten; gepubliceerde voorganger kan actief zijn.
Trigger: Expliciete bestaande verwerkings-/voorbereidings-/migratieopdracht, daarna afzonderlijke bestaande review- en publicatiecommands.
Authorization: Actuele bestaande actor/rol/named-reviewer/policy, claim/poging en mutabilitychecks; geen recht uit een proof of kaart.
Validation: Complete bron-/semantic-/voorstel-/resultaat-/findingbinding, oorspronkelijke contracten, actuele revisie en menselijke bronafhandeling.
Mutable entities: Toegestane actuele WorkingRevision-records en geautoriseerde operationele referentie; review/bindings/audit alleen via hun bestaande commands.
Immutable entities: Bronbytes, verzegelde bewijsleden, beschermde historische objectinhoud en alle gepubliceerde releases/revisies volgens bestaande contracten.
Workflow state before: Bestaande processing/in_review/blocked/ready_for_publication-toestand; nooit uit bewijsomvang afleiden.
Workflow state after: Dezelfde domeinuitkomst bij representatieovergang; menselijke besluiten en publicatie bepalen hun bestaande volgende toestand, niet de migratie.
Release state before: Bestaande published/superseded/withdrawn release of geen release.
Release state after: Ongewijzigd door voorbereiding/migratie; alleen bestaande publicatie-/intrekkingsopdracht wijzigt release/serving.
Serving state before: Actieve/inactieve set uitsluitend uit publicatieregister.
Serving state after: Ongewijzigd door deze representatieovergang; geen automatische heractivatie na restart.
Expected API result: Scopepassend leesresultaat, bestaand commandresultaat of expliciet conflict/forbidden/unavailable; geen succesvolle mutatie bij onvolledig bewijs.
Expected UI result: Beoordeelbare passage met exact bronbewijs; globale beoordeling alleen bij complete geldige capture, anders expliciet niet geëvalueerd/onbeschikbaar.
Failure result: Geen halve pin, mutatie of verzonnen closure; behouden bestaande work state; canoniek gecommitte release houdt haar bestaande herstelpad.
Restart result: Gecommitte proof/review/bindings blijven herbruikbaar; geen stale activatie, stille herbouw of heropening van gepubliceerd werk.
Recovery result: Bestaande expliciete preparation/retry/reconcile met dezelfde bron-/revisie-/contractregels; geen reset of terugzetten van reviewwerk.
Legacy-data result: Expliciete voorbereiding met exacte pariteit en CAS; onvoorbereid, corrupt en incompatibel apart; gepubliceerd beleid niet herschrijven.
Required black-box scenario: Ingest → partial activation → passage openen/beslissen → restart → gelokaliseerde bevinding geldig afhandelen → volledige beoordeling → publicatie → opvolger → intrekking → restart; daarbij oude releases, bron en besluiten behouden.
Explicit non-goals: Nieuwe kandidaatmaker, semantische versoepeling, completioncache, nieuwe servingauthority, langere SQL-grens, destructieve opschoning, modelherverwerking als migratie of deployment door deze ontwerp-PR.

Rewrite target: Gedeelde input-/bewaargrens voor vormingsbewijs en operationele documentreads, met aansluiting op bestaande command-/publicatieowners.
Why local patching is insufficient: JSON-projectie of timeoutverhoging laat detoasting, globale documentcontrole, historische groei en incomplete proofbinding intact of verplaatst kosten naar writes/redirects.
Current authority/writer/reader map: §3, §9 en de concrete inventaris in §16 op deze gepinde basis; alle ondersteunde directe writers en overrides moeten vóór cutover worden afgedekt.
Supported runtime topologies: Beide bestaande FastBadge CompleteWorkflow PostgreSQL-composities met lokale/Azure bronadapter en nieuwe processen/workers; geen nieuwe multi-host-/globale exactly-once-garantie.
Persisted-state impact: Additieve, complete verzegelde bewijsrecords en operationele referenties bij bestaande owners; geen gewijzigde bron/kandidaat-/release-identiteit of nieuwe statusauthority.
Compatibility/migration plan: Expand → expliciete voorbereiding → domeinpariteit → CAS-pin → compatibele reader/writercutover → contract; §10 is verplicht.
Rollback/recovery plan: Oorspronkelijk retained bewijs en besluiten behouden; alleen bewezen compatibele binarycombinaties; herstel vanaf gecommitte authority, geen destructieve terugzetting of los geheugenarchief.
Cutover trigger: Volledige proof-/writer-/reader-/legacydekking, bestaande domeinpariteit, native concurrency/restart/rollback en ongewijzigde gebruikersbudgets; aparte geautoriseerde uitrol.
Cleanup/decommission criteria: Geen actieve volledige-envelopefallback, oude hydratatie of dubbele closurepolicy in overgezette route; audits/releasepins blijven leesbaar; vervangen calls/config/diagrammen bijgewerkt.
Failure blast radius: Betrokken revisie/proof kan expliciet onbeschikbaar zijn; geen ongeautoriseerde review, nieuwe release, verloren besluit of wijziging aan actieve voorganger.
Adversarial proof matrix: §11 en §13: missing/corrupt/membership, wrong source/contract, stale claim/revision/binding/policy/actor, alternatieve writers/legacy, rollback/restart, publicatierace en archiefgroei.

## 13. Bewijsopdracht en overdracht

Dit document is een contract, geen uitgevoerde native acceptatie. Hergebruik
bestaande tests/oracles; voeg in implementaties alleen gedragstests toe die
de betreffende fout werkelijk kunnen vinden.

| Proef | Vereiste observatie | Bestaande bewijsbasis / opvolger |
| --- | --- | --- |
| Echte falende route/fase | Exacte oorspronkelijke capture/renderquery onderscheiden; dezelfde symptoomroute vóór fix rood | MET-38; geen GIN-proef als substituut |
| 25 MB partial-formation, 1096 versies | Openen → besluit → redirect → heropen → volledige beoordeling/publicatie; requests en duurzame resultaten juist | `test_review_formation_problems.py`, `test_review_passage_read_postgres.py`; #950–#953 |
| Gelokaliseerde versus onbekende findings | Geldige actuele menselijke afhandeling sluit alleen exact gedekte gelokaliseerde bevindingen | Recoverable-formation/source-context/dispositiontests; #951 |
| Verzegeling en membership | Verwijderd lid, verkeerde bron/contract, corrupte root of geldige hash met verkeerde binding wordt ontdekt | Source-readrecordtests en nieuwe formation-proofnativeproef; #950 |
| Binding-only/policy/actor | Geen stale toestemming bij onveranderde objectgeneration | Review-command/binding/participationtests; #952 |
| Crash en duplicate | Vóór commit geen activatie; na commit nieuw proces hergebruikt checkpoint; commandvarianten behouden eigen duplicatecontract | Workflow/formation-task/recoverytests; #950/#952/#953 |
| Publicatierace en projectiefout | Exacte beoordeling tot canonieke commit; na canonical-success geen fictieve rollback | Bestaande publication/lifecycletests op echte topologie; #952 |
| Legacy met menselijke besluiten | Voorbereiding herhaald en onderbroken zonder nieuwe kandidaten of verloren menselijke afhandeling | Nieuwe native migratie-/restartproef; #953 |
| Groei en kleine controls | Vaste passage/dependencies onafhankelijk van historische archiefgroei; geen kleine-bronregressie of verschoven write-/redirectkosten | #888-budgets en bestaande controles blijven; #953 |

Meet totale HTTP-latency, SQL execute/fetch, overgedragen JSON/records, bron- en
proofvalidatie, lock wait/hold en transactietijd afzonderlijk. Koude/warme,
succes-/fout-/conflict-/retrygevallen en niet-afgeronde requests blijven zichtbaar.
Geen O(1)-belofte voor groei van werkelijk noodzakelijke context of verplichte
broncontrole. Geen PG-skip als pass, verruimde budgetten of uitgemiddelde missers.

## 14. Ontwerpkeuze, scope en gereedheidsgrens

Vergeleken zijn (A) gerichte projectie uit de bestaande envelope met bestaande
validatie per klik, en (B) complete eerder gecontroleerde bewijsrecords bij de
bestaande owner met live menselijke afhandeling en expliciete operatiescopes.
Gekozen ontwerp B pakt opslag, hergebruik, geldigheid en bereik samen aan.
A blijft onvoldoende als blijvende oplossing: SQL kan de hele envelope
uitpakken en iedere passage kan documentbreed werk blijven oproepen.

Het voorstel hergebruikt FormationTaskStore/source views en bestaande kernelregels.
Het is geen volledig nieuwe gesynchroniseerde Review-database. We accepteren
additieve opslagbescherming en een expliciete migratie in ruil voor herbruikbaar,
controleerbaar bewijs zonder volledige historische verwerking per handeling.

MET-36/#729 behoudt objectmutatie-, D1-/D2- en contractwerk; zijn huidige §11
sluit envelopeopslag uit. MET-35/#942 behoudt de bronrolschrijver. MET-37 behoudt
groei/retentieonderzoek; MET-25/#904 en MET-26/#905 zijn fundamenten, geen te
vervangen projecten. MET-17/#888 houdt oorspronkelijke budgets/open bewijs;
MET-11/12 houden cleanup en eindacceptatie. MET-38 sluit pas op gebruikers- en
productiebewijs, niet op dit ontwerp.

Overdracht: #950 implementeert fysieke bewijsopslag; #951 scope/evaluator;
#952 beschermde commits; #953 legacy, cutover, cleanup en integraal bewijs.
Geen van die implementaties is uitgevoerd of uitvoeringsgereed verklaard door
deze PR. Uitvoeringsissues moeten hun concrete fysieke keuzes, writerdekking en
native tegenproeven aan dit contract koppelen; geen materiële aanname als bewijs.

## 15. Bronnen en inspectie

Alle paden verwijzen naar de hierboven gepinde basis, tenzij de ontwerp-PR ze
expliciet wijzigt. Bestaande implementatie/bewijsgrenzen blijven onderscheiden.

- `docs/agents/lifecycle-vsa.md`, `continuous-development.md`, `abstraction-boundaries.md` en `docs/SOURCE_CONTEXT_REVIEW_CONTRACT.md`.
- `src/review/review_passage_read_v1.py:33,133`; `src/operations_console_app.py:3581`; `src/operations_console_v1.py:1881`.
- `src/vorming/recoverable_formation_v1.py:225`; `semantic_replay_v1.py:119`; `pre_review_semantic_v1.py` en `formation_checkpoint_v1.py:294`.
- `src/workflows/formation_task_store_v1.py:25,248`; `review_source_records_v1.py`; migraties `021_formation_task_records.sql`, `026_review_source_records.sql`, `027_review_card_facts.sql`.
- `src/workflows/workflow_documents_cutover_v1.py:105,328,547,675`; `workflow_document_concurrency_v1.py`; `workflow_review_cutover_v1.py`; `workflow_transaction_v1.py`.
- `src/review/review_command_v1.py`; `src/console_asgi.py`; `src/publication/durable_publication_console_v1.py`; `canonical_publication_postgres_v1.py`.
- Bestaande bronview-/kaartontwerpen `docs/architecture/review-source-904.md`, `review-cards-905.md`; MET-36-contract en bestaande review-readperformancecontracten.

Statische code-/schema-/testinspectie en method-resolutioninspectie zijn uitgevoerd.
Native migratie-, concurrency-, foutinjectie- en productieproeven voor dit
**nieuwe** bewijscontract zijn toekomstige acceptatie, geen al geleverde PASS.

## 16. Concrete inventaris op de onderzochte basis

Deze tabel maakt de afbakening reproduceerbaar. Lijnnummers zijn alleen ankers
op `0bbd58f2`; functies en hun werkelijke methode-eigenaar zijn leidend.
De inventaris is statisch en aangevuld met Python-MRO-inspectie; zij bewijst
geen runtimebereikbaarheid van iedere combinatie. Afzonderlijke read-only
vormings- en command/publicatie-inspecties hebben de grenzen hieronder getoetst.

### Vorming, bron en activatie

| Bestaande grens | Concrete plaats | Relevante eigenschap |
| --- | --- | --- |
| Storeconstructie en compositie | `src/console_asgi.py:103,176,185` | Beide composities gebruiken PostgresConcurrentWorkflowDocumentStore; canonical wordt niet met de workflowstores gebonden |
| Reservatie/uitvoering | `src/vorming/source_selection_v1.py:72`; `src/operations_console_v1.py:1839,1848,2174` | Bestaande opdracht/poging en route/configuratie; geen tweede dispatcher |
| Validatorinput opslaan/herladen | `src/workflows/formation_task_store_v1.py:37,78` | Bron-/input-/semanticbinding; resolve_preparation hydrateert volledige extractie, geen begrensde detailread |
| Checkpointselectie | `src/vorming/formation_checkpoint_v1.py:342`; `src/operations_console_v1.py:2033` | Task-v1 versus legacy diagnostic-writercallback; legacy heeft full-envelopewerk |
| Checkpointlock en taskcommit | `src/vorming/formation_checkpoint_v1.py:49,278`; `src/workflows/formation_task_store_v1.py:213` | Bron, generatie, claim, poging, rechten/config/deadline opnieuw; resultaatcorrectie behoudt history en invalideert final_validation |
| Gezamenlijke gate / materialisatie | `src/vorming/pre_review_semantic_v1.py:459,879`; `src/vorming/knowledge_materialisation_v1.py:235` | Alleen bestaande deterministic materialisation maakt kandidaten |
| Receipt en definitieve findingassemblage | `src/vorming/formation_checkpoint_v1.py:294`; `src/vorming/bounded_formation_v1.py:418`; `src/vorming/pre_review_semantic_v1.py:943` | Bounded formation kent al findings; definitieve replay-/checkpointassemblage volgt na receipt, die de complete findings/bronbasis niet bindt |
| Eindafwijzing | `src/vorming/formation_checkpoint_v1.py:317` | Exact gelokaliseerde taak afwijzen; onbekende globale scope niet zelf lokaliseren |
| Activatiechecks | `src/workflows/formation_task_store_v1.py:248`; `src/workflows/workflow_documents_cutover_v1.py:728`; `src/workflows/workflow_document_concurrency_v1.py:553` | Base én override controleren activatie; beslisboom zonder validator_input_ref heeft expliciet eigen contract |
| Herverwerking/commit | `src/operations_console_v1.py:2243,2395` | Actuele claim/bron/revisie/config/actor onder beschermde commit; human-workguard behouden |
| Resume en bewaarde input | `src/operations_console_v1.py:1966,1993`; `src/vorming/formation_checkpoint_v1.py:173,190` | Compatibiliteits- en human-workguard; retained broninput is geen algemene GET-herbouw |
| Dispatcher/workerwissel | `src/vorming/source_processing_dispatch_v1.py:16,48,81`; `src/vorming/worker_handover_v1.py:64,89,129,145,181,210` | Claim/lease/config/actor en harde budgetten blijven geldig na restart |
| Bronvoorbereiding en expliciete pin | `src/workflows/review_source_records_v1.py:60,168,198,207`; `src/operations_console_v1.py:2719,2753` | Prepare/publish/pin gescheiden; volledige of selectieve scope; sourcepinwrite verhoogt niet vanzelf documentrevision |
| Bronviewcompatibiliteit | `src/operations_console_v1.py:2670,2685,2760`; `src/workflows/formation_task_store_v1.py:124` | Legacy-extractie, None, volledige hydratatie en raw-sourcefallback zijn verschillende paden |
| Opslagbescherming | `db/migrations/021_formation_task_records.sql`; `db/migrations/026_review_source_records.sql` | API-gelijkheidscontrole van inputrecords niet verwarren met DB-sealing van source-readroots/members |

### Review, herstel en publicatie

| Bestaande grens | Concrete plaats | Relevante eigenschap |
| --- | --- | --- |
| Document-/passagecapture | `src/review/review_passage_read_v1.py:33,133`; `src/review/review_workboard_v1.py:685` | Verschillende capturepaden; vijfseconden-SQL-grens komt uit workflow_read_transaction |
| Detailstatus | `src/operations_console_app.py:3581`; `src/operations_console_v1.py:1881` | Full-envelopeherlezing voor notice; status berekent ook retry/resume en volledige bronafhandeling |
| Gewone/tweede review | `src/review/review_closure_v1.py:57`; `src/review/review_command_v1.py:103` | Gerichte command; bronvoorbereiding vóór lock, actuele actor/source/precondition/dependencies bij commit |
| Delta/historycommit | `src/workflows/workflow_document_concurrency_v1.py:183` | apply_review_changes bewaakt exacte histories, appendvolgorde, revisionchain en canonieke immutability |
| Broncontext/reset en groep | `src/review/source_context_review_v1.py:265,428,453` | _source_batch en _confirm_source_context hebben eigen idempotentie, autorisatie-, document- en sourceregels |
| Correctie/batch/koppen | `src/review/review_closure_v1.py:70`; `src/review/closed_review_loop_v1.py:71`; `src/operations_console_v1.py:3044`; `src/workflows/workflow_review_cutover_v1.py:363` | Niet alle commands gaan via de gewone reviewwrapper |
| Structured repair | `src/review/deterministic_review_repair_v1.py:720,777` | Prepare buiten lock; preflight/source/revision opnieuw binnen beschermde mutatie |
| Participation/configuratie/boomcommands | `src/review/review_participation_v1.py:18,40`; `src/review/review_configuration_v1.py`; `src/review/decision_review_commands_v1.py:16,33` | Bestaande afzonderlijke owners; geen nieuwe generieke policywriter |
| Shared command en compatibiliteit | `src/workflows/workflow_review_cutover_v1.py:198,377` | StoreCommand, scoped review, headingbatch en raw-transactionbranches onderscheiden |
| Binding-only wijzigingen | `src/workflows/workflow_review_postgres_v1.py:542,560,638` | Snapshot/delta lockt document zonder bewezen counterbump; globale replace_bindings heeft alleen authorizationlock |
| Rollen | `src/workflows/workflow_identity_postgres_v1.py:193,307` | update_roles wijzigt account; current=True kan FOR SHARE nemen; geen nieuwe historische approval-revocationregel |
| Lifecycle/readiness | `src/publication/publication_readiness_v1.py`; `src/operations_console_v1.py:4219,4295` | Bestaande gates/context-suppliedregels; één recoverable-formationoracle |
| Publicatie en canonieke opslag | `src/operations_console_v1.py:4458`; `src/publication/durable_publication_console_v1.py:219`; `src/publication/canonical_publication_postgres_v1.py:202,235,239` | Workflowdocumentbarrière en afzonderlijke canonieke verbinding/commit met logical-documentlock |
| Withdrawal/reconcile | `src/publication/durable_publication_console_v1.py:75,185,190,272`; `src/publication/canonical_publication_postgres_v1.py:529` | Canonieke commit leidend; projectiesynchronisatie kan pending blijven |
| Gepubliceerde immutability | `src/operations_console_v1.py:831,847`; `src/workflows/workflow_document_concurrency_v1.py:401,433,495` | Ook na canonical-success/projection-failure geen nieuwe mutatie aan de verzegelde revisie |
| CLI/MCP/export | `src/cli.py:122,127`; `src/settings/metis_mcp_queries_v1.py:123`; `src/operations_console_app.py:5514`; `src/vorming/processing_evidence_export_v1.py:180,393` | Expliciete geautoriseerde status-/historieconsumers; geen herstel of nieuwe klinische besluiten bij export |

De volledige generatie-/freshnessdekking van deze ingangen is **niet** bewezen
door deze tabel. Concreet ontbreekt een algemene counterdekking voor
binding-only-, legacy-object-, sourcepin- en accountwijzigingen. #952 moet deze
afhankelijkheden mechanisch beschermen; een ontwerp mag dat gat niet als
voltooide invariant presenteren.

### Bestaande falsificerende bewijsbasis, gelezen

- `tests/test_formation_task_store_postgres.py`: inputcorruptie, idempotente/atomaire checkpoint, claimfencing, old-writer refusal en echte process kill/restart.
- `tests/test_source_task_reuse_v1.py`: herstart zonder extractor/reconstructor, corrupt committed input, expliciete legacyvoorbereiding en claimfenced bronacceptatie.
- `tests/test_review_source_records_v1.py`: complete/selected pariteit, sealing/membership, corruptie, concurrent publiceren en stale bronpin.
- `tests/test_review_formation_problems.py:189` en `tests/test_recoverable_formation_v1.py:527`: menselijke afhandeling naast historisch pendingbewijs; producerapproval en onbekende failures sluiten niet impliciet.
- `tests/test_review_command_storage_v1.py`, `tests/test_review_command_dependencies_v1.py`, `tests/test_review_command_bounded_http_v1.py`: correcte commandclosure, atomiciteit, stale/bron-/binding- en begrensde read/writevoorwaarden.
- `tests/test_source_context_review_v1.py`, `tests/test_b6_source_group_command.py`, `tests/test_review_participation_management.py`: context/reset/groep, publicatierace, deelname en reviewinvalidatie.
- `tests/test_review_command_source_failure_v1.py`: veilige retained bronafwijzing zonder oorspronkelijke bytes, maar geen content approval.
- `tests/test_published_working_revision_immutable_v1.py`, `tests/test_lifecycle_withdrawal_recovery_v1.py`, `tests/test_withdrawal_reconciliation_v1.py`: canonieke crashwindow, gepubliceerde guards en recovery/withdrawal.

Nieuwe sealed formation-proof-, manifest-/findingdekking-, migratie- en
commitbarrièreproeven blijven de opdracht van #950–#953. Bestaande tests opnieuw
groen krijgen zou hun nog ontbrekende nieuwe bewijs niet vervangen.

## 17. Review en werkelijk uitgevoerde verificatie van deze contractslice

Twee afzonderlijke read-only reviews op hetzelfde model hebben respectievelijk
vorming/bewijs/legacy en commands/publicatie onderzocht. Dit is geen cross-model
consensus en geen onafhankelijke runtimeproef. De reviews leidden tot expliciete
correcties: geactiveerd voorstel versus ruwe uitvoer; receipt bindt niet alle
findings; mutable taskprojectie versus immutable activatieversie; technische
integriteit versus nieuw beleidsbesluit voor gepubliceerde legacy; en behoud van
bestaande geautoriseerde aggregate-delete en veilige source-disposition.

Op de ongewijzigde productcode van `0bbd58f2` met dit ontwerpdocument zijn uitgevoerd:

- Change-contractvalidator: PASS.
- Repository-preflight, architectuurgrenzen en `compileall -q src`: PASS.
- Release-control-preflight voor uitsluitend het document en de twee bijbehorende
  contractcontroles: PASS; geen productcategorie geforceerd door een documentatie-PR.
- 67 concrete bronverwijzingen en hun regelbereik gecontroleerd: PASS.
- Twee contractcontroles voor metadata, lifecycle-/rewriteoverdracht en verwijzingen: PASS.
- 19 geselecteerde bestaande architectuur-/validator-/domeintests: PASS. De native
  gevallen gebruiken PostgreSQL 16 na `scripts/test_postgres.sh`: exacte menselijke
  bronafhandeling, onbekende failures, idempotente taskcommit, bronsealing, veilige
  source-disposition en canonieke crashwindow-immutability.

De volledige repositorysuite, browser-/provider-/productieproeven en nieuwe
formation-proof-/migratie-/publicatiebarrièreproeven zijn hier niet uitgevoerd.
De lokale GIN-proef, gebruikersuploads en ruwe telemetrie maken geen deel uit
van deze wijziging. Het Smetten-incident en #950–#953 blijven open.
