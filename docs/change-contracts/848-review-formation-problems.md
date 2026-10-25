Change class: A
Promise: Onafhankelijke, gezamenlijk gevalideerde voorstellen worden reviewbaar terwijl ieder actueel vormingsprobleem zichtbaar en behandelbaar blijft vanuit Vormingsproblemen.
Proof: Native PostgreSQL: start met geldig en onafhankelijk ongeldig bewijs → Review + Vormingsproblemen → herstart → gericht hervatten → behoud geldig object; noodzakelijke context, menselijke afhandeling, publicatieblokkades en navigatie via echte HTTP/Playwright.
Touches lifecycle invariants: yes
Rewrite risk: high

# #848 — verplicht uitvoeringscontract vóór productiecode

De volledige vijfstappenchecklist staat voor de implementatieopdracht in issue #848.
William heeft aanmaak en uitvoering expliciet opgedragen. Geen merge/deployment.

## 1. Ground — feiten en onderzoek

De door William gemelde Smetten-export toont afgewezen bronverwijzingen,
witruimtetaken, gedeeltelijke resultaten en `source_formation_incomplete`.
Die export is in deze workspace niet aangeleverd; geen nieuwe productiecausaliteit
of klinische volledigheid claimen. De bestaande offline Smetten-proef staat in
`docs/acceptance/smetten_recorded_formation_replay.json`.

Codepad: Starten → reserve_selection → bestaande dispatcher/claim →
reextract_unpublished → build_formation_context/TaskCheckpointWriter →
bounded_formation.execute → _materialised_content → transform/admission →
reextract_unpublished → PostgreSQL write_bundle/assert_activation → Review.

Vastgesteld in code: pre_review_semantic weigert vóór _materialised_content ieder
durable resultaat met formation_incomplete. De gewone V3-route isoleert al
afwijzingen via recoverable_formation.prepare. Hervatten leest taakresultaten
uit dezelfde gepinde context. processing_status overschrijft bij task-v1 de
inhoudelijke volledigheid met uitsluitend de laatste pogingstatus. _durable_targets
neemt ook lege witruimte tussen selecties op; de coverageprojectie slaat die al over.

Nog te bewijzen: de concrete rood/groenroute en bron-/revisiebehoud bij herstel.
Gerangschikte hypotheses: (1) de vroege durable poort voorkomt materialisatie;
(2) gezamenlijk bron-/relatiebewijs faalt terecht; (3) Admission blokkeert het
individuele object; (4) hervatten verliest eerdere resultaten. De proef moet
onderscheiden of er geen objecten zijn, een gezamenlijke afwijzing is, individuele
Admission faalt, of hetzelfde geldige resultaat opnieuw wordt opgevraagd.

## 2. Sketch — domeinregels en twee vormen

Een object is zelfstandig reviewbaar na exacte bronbinding, geldige verplichte
velden/context, deterministische materialisatie en toegestane Admission.
prepare propageert ongeldige relaties naar hun endpoints en transitieve
afhankelijkheden; onbekende endpoints kunnen de hele betrokken call blokkeren.
De gezamenlijke validator blijft verplicht, ook bij gedeeltelijke taakvoortgang.
Een individuele Admission-blokkade is herstelwerk, geen normale inhoudsreview.

Voorbeeld A: letterlijk geldig advies A krijgt reviewplicht. Onafhankelijk B
met verzonnen veldbewijs wordt geen kandidaat: zijn bronbereik en afwijzing
blijven zichtbaar; publicatie blijft geblokkeerd.
Voorbeeld B: advies C mist de noodzakelijke voorwaarde. Bestaande context- en
Admissionregels blokkeren C; pas correcte bronkoppeling plus hercontrole kan
inhoudsreview toestaan. Een aangetoonde afhankelijkheid blokkeert mede de
afhankelijke objecten; afstand of hoofdstukindeling bewijst geen onafhankelijkheid.

Broninhoud is verantwoord door de bestaande source_accountability/source_closure:
gevalideerde selectie, begrensde machineherkenning van documentinformatie,
actuele gekoppelde context met juiste doelbeoordeling, of bevoegde definitieve
bronafhandeling. Alleen witruimte is deterministisch geen semantische taak;
de letterlijke bron blijft intact. Niet-geselecteerde klinische tekst is geen witruimte.

Een probleem sluit door relevante gevalideerde dekking of bestaande, exacte
menselijke bronafhandeling. Onbekende locatie, stale bewijs of onvolledige dekking
blijft open. Een successtatus, kamerwissel of historische afwijzing verbergen is
geen sluiting. Onverantwoorde bron, open context/Admission, review- en technische
voorwaarden blijven publicatie blokkeren volgens de bestaande eigenaren.

Vorm 1 (gekozen): ontsluit bestaande replay/pending_rejections, taakbevindingen,
bronverantwoording en Admission met links naar bestaande hersteloperaties.
Vorm 2 (verworpen): nieuw duurzaam probleemregister, met aparte status en writes.
Beide ontwerpen zijn door dezelfde agent vergeleken, geen onafhankelijke review.
Vorm 1 heeft geen synchronisatie-/migratielast en behoudt één waarheid; er is geen
aangetoonde ontbrekende domeintoestand die vorm 2 noodzakelijk maakt.

Gebruik: consolegebruiker opent /formation-problems?document=SNAPSHOT, ziet
reden, bronbereik en bestaande herstelactie. Hervatten blijft een expliciete
POST naar /source-selection/start; GET start/stopt geen werk. Review opent
de bestaande kandidaat of bron-/reparatietaak. Geen generieke sluitknop.

## 3. Autoriteit en herstel

| Gegeven | Producent → consument | Eigenaar, levensduur en geldigheid |
| --- | --- | --- |
| Bronversie/hash en extractie | ingest/extractor → selectie/review | immutable bronstore + workflow-extractieversie; exacte snapshot/hash/contract |
| Validatorinput, plan en taakresultaten | voorbereiding/checkpoint → hervatten/eindpoort | bestaande PostgreSQL formation_*; geverifieerde referenties; geen nieuwe opslag |
| Afwijzing en identiteit | prepare/checkpoints → probleemprojectie | bestaande bevinding + snapshot/bron/semantische identiteit/kind/code/bereik; poging is historie |
| Review en bronafhandeling | bevoegde reviewer → closure/readiness | bestaande WorkingRevision, objectversies en reviewbindings; actuele exacte binding |
| Voortgang en probleemscherm | bovenstaande autoriteiten → HTML | afgeleide gegevens, geen console-eigen lifecycle |

Onderbreking vóór activatie bewaart taakresultaten; herstart leest dezelfde context.
Een duplicate command hergebruikt de bestaande poging. Concurrerende herstelacties
zijn gefencet door bestaande document-/poginglocks, claimtoken en objectrevisie.
De ene activatiegrens commit objecten, replay, poging en bronstatus atomair.
Geen nieuwe achtergrondtaak, Azure-mutatie of langlopende leestran­sactie.

**Behouden herstelgrens:** vóór menselijke wijzigingen kan modelherstel gericht
hervatten en exact gelijk gebleven kandidaten behouden. Na menselijke review/
bronwijzigingen blijft de bestaande guard tegen herextractie gelden. Dan gebruikt
de gebruiker de bestaande object-/bronreparatie en expliciete werkrevisie waar
nodig; geen automatische overdracht of verwijdering van approvals. Het scherm
moet dit zichtbaar uitleggen en naar de bruikbare handeling verwijzen.

Rewrite target: De onvoorwaardelijke volledigheidspoort vóór task-v1-materialisatie en afgeleide probleem-/voortgangsweergave.
Why local patching is insufficient: Alleen een knop toevoegen levert geen reviewtaken; alleen de raise verwijderen zonder gezamenlijke validatie en bewaarde publicatieblokkade zou te ruim zijn.
Current authority/writer/reader map: Bronstore → voorbereiding/provider/prepare → TaskCheckpointWriter/FormationTaskStore → materialisatie/transform/Admission → OperationsConsole.reextract_unpublished → workflow PostgreSQL write_bundle/assert_activation. reserve/retry/resume/dispatcher blijven enige opdracht-/claimwriters. processing_status, source_selection.projectie, Review, export en nieuwe probleemprojectie lezen die eigenaren. Publicatieresultaat blijft uitsluitend readiness → durable/azure publication → canonical store/registry → Product API. Legacy ingest/reextract en beslisboom behouden hun bestaande route. Geen nieuwe writer of fallback.
Supported runtime topologies: Volledige productie-PostgreSQL-compositie, met bestaande lokale/Azure bronadapter. Legacy replay blijft leesbaar. File-only runtime is niet ondersteund.
Persisted-state impact: Geen schema of nieuwe probleemstatus; bestaande replay bevat gedeeltelijke gevalideerde selectie en pending bewijs. final_validation versie 2 bindt naast de gezamenlijke resultaatset de actuele activatierevisie; de oorspronkelijke voorbereidingscontext en zijn invoerrevisie blijven immutable. Versie 1 blijft volgens zijn oorspronkelijke revisiecontrole leesbaar.
Compatibility/migration plan: Alleen nieuwe uitvoering onder task-v1 kan gedeeltelijk activeren; oude opgeslagen taakresultaten worden bij expliciet hervatten opnieuw gezamenlijk gevalideerd. Geen GET/startupbackfill of interpretatie van diagnostiek als kandidaat.
Rollback/recovery plan: Sluit nieuwe opdrachten met de bestaande admission-instelling en drain geaccepteerde workers vóór een binarywissel. Bewaar taakresultaten/replay/bron/reviews. Een rollbackbinary moet de versie-2-eindbewijzen blijven begrijpen; een binary van vóór #848 kan de nieuwe activatierevisie niet veilig als schrijfcontract gebruiken en is geen herstelpad na gedeeltelijke activatie. Behoud de compatibele reader/CAS bij terugdraaien van de vrijgavepolicy; nooit bewijsvelden verwijderen of revisies resetten. Geen destructieve migratie; bestaande reviews vereisen bestaande menselijke herstel-/opvolgeroperaties.
Cutover trigger: Lokale acceptatie en verplichte checks plus menselijke PR-review; uitrol is afzonderlijk werk.
Cleanup/decommission criteria: Vervang uitsluitend de onvoorwaardelijke stop; behoud errors zonder geldig voorstel en de enige materialisatie-/activatiegrens. Geen dubbele probleemopslag/configuratie.
Failure blast radius: Eén ongepubliceerde WorkingRevision; bron-/opslag-/gezamenlijke validatiefout behoudt vorige bundle. Serving en historie blijven gelijk.
Adversarial proof matrix: Verkeerd bronbewijs, noodzakelijke ontbrekende context, afhankelijk relationeel voorstel, onbekende locatie, gedeeltelijke dekking, uitsluitend witruimte, corrupt input, stale/duplicate/concurrent herstel, reviewguard, herstart, readonly GET/navigatie, publicatie/API en alternatieve bestaande task/legacy-ingangen.

Lifecycle entity: WorkingRevision op één immutable SourceSnapshot.
Lifecycle transition: Gevalideerd onafhankelijk deel naar in_review met open bronproblemen; geen automatisch curator- of publicatiebesluit.
Initial durable state: Ontvangen ongepubliceerde bron of hervatbare ongereviewde taakresultaten op gepinde bron/context.
Trigger: Expliciete geautoriseerde Starten/Hervatten via bestaande selectieoperatie.
Authorization: Bestaande actuele onderzoeker/benoemde reviewer, revisie, claim, configuratie en deadlines.
Validation: Exacte bron/velden/context/relaties, gezamenlijke validatie, enige deterministische kandidaatmaker en Admission; resterende problemen blijven gepind.
Mutable entities: Bestaande ongepubliceerde werkobjectset, replay en processing attempt; geen console-eigen status.
Immutable entities: Bronbytes/hash, gecommitte geldige taakresultaten, gepubliceerde versies/releases en menselijke reviewhistorie.
Workflow state before: processing of onvolledig ongepubliceerd werk.
Workflow state after: in_review voor geldige kandidaten met open bron-/technische blokkades; ready uitsluitend via bestaande poorten.
Release state before: Geen release of eerdere historische/actieve release.
Release state after: Ongewijzigd.
Serving state before: Bestaande publicatieregistry.
Serving state after: Ongewijzigd; ongepubliceerde objecten blijven onbeschikbaar.
Expected API result: Bestaande Starten accepteert één duurzame opdracht; Review toont geldige kandidaten; probleem-GET muteert niet.
Expected UI result: Review en Vormingsproblemen beide bereikbaar; reden/bereik/herstelactie voor open werk, inclusief guard wanneer modelherstel niet meer mag.
Failure result: Geen geldige onafhankelijkheid of ongeldige gezamenlijke selectie betekent geen activatie; eerdere taakresultaten en probleemhistorie blijven behouden.
Restart result: Zelfde objecten, pending bewijs, review-/publicatievoorwaarden en probleemidentiteiten.
Recovery result: Alleen open ranges verwerken; geen duplicatie/overschrijven van geldig werk; menselijke wijzigingen blijven beschermd.
Legacy-data result: Geen migratie; legacy V3 blijft de bestaande route en bronclosure gebruiken; oude taakresultaten alleen na expliciete opdracht activeren.
Required black-box scenario: GIVEN ontvangen bron met onafhankelijk geldig A en ongeldig B WHEN één Starten THEN A reviewbaar en B zichtbaar als probleem, publicatie geblokkeerd; herstart bewaart beide; gericht herstel vóór review behoudt A exact en voegt B eenmaal toe; menselijke review sluit alleen exacte inhoud, navigeren stopt de dispatcher niet.
Explicit non-goals: Nieuw kennisobjectenmodel, opslagarchitectuur, workflow-engine, versoepelde brongetrouwheid, automatische menselijke reviewtaken voor technische afwijzingen, nieuwe review-/publicatierechten, merge/deploy, echte betaalde modelcalls of klinische Smetten-volledigheidsclaim.

## 4. Bewijs vooraf

| Acceptatie | Fout die de controle moet ontdekken | Bewijs |
| --- | --- | --- |
| Onafhankelijk geldig deel in Review | Vroege durable stop houdt A tegen | Native start met A/B en echte Review-GET; eerst rood |
| Noodzakelijke context blijft geblokkeerd | Te ruime vrijgave | Bestaande context-/relationele tegenproeven plus probleemlink |
| Ieder actueel probleem zichtbaar/behandelbaar | Alleen eerste fout, historische fout als actueel, dode actie | Projectie met afwijzing/Admission/bronclosure; HTTP en paginering waar nodig |
| Witruimte zonder modelcall | Lege gaps verbruiken modelbudget | Provider weigert whitespace-targets; aantal requests en exacte bron controleren |
| Gericht herstel zonder verlies/duplicatie | A opnieuw aan model of gewijzigde identiteit | Herstart + één herstelrequest; object- en taakresultaatvergelijking; duplicate/stale/concurrent proef |
| Sluiten na relevante controle | Successtatus of verplaatsing sluit probleem | Onvolledige/onjuiste dekking blijft open; exacte gevalideerde dekking sluit |
| Publicatievoorwaarden | Partial succes verleent publicatie | Readiness/publish/API weigert; volledige review blijft vereist |
| Navigatie onderbreekt niet | GET annuleert verwerking of muteert status | Lopende provider pauzeren, andere kamer openen, afmaken; echte Playwright/HTTP |

Lokaal: PostgreSQL 16, deterministische provider, bestaande echte consolecompositie.
Productie: na afzonderlijke uitrol Smetten, bronkwaliteit, actuele configuratie,
Review, Vormingsproblemen, Raad en Azure-opslag controleren. Niet lokaal bewezen.

## 5. Implementatie en schoonmaak — voortgang

- [x] Ground: bestaande code, eigenaren en herstelgrens onderzocht.
- [x] Sketch: twee opslagvormen vergeleken en bovenstaande regels vastgelegd.
- [x] Agree: gebruikersopdracht autoriseert uitvoering zonder nieuwe goedkeuringsronde.
- [ ] Implement: rood/groenproef, kleine domeinwijziging en probleemtoegang.
- [ ] Scrap: vervangen stop/dubbele afleidingen verwijderen en einddiff controleren.
- [ ] Verificatie-uitkomsten en beperkingen in issue/PR bijwerken.

### Ontwerpverfijning uit de regressieproeven

Een gedeeltelijke activatie wijzigt de objectrevisie, terwijl de herbruikbare
taakinput bewust op de oorspronkelijke voorbereidingsrevisie blijft staan.
De eindpoort bindt daarom zijn eigen actuele activatierevisie in versie 2 van
het bestaande validatiebewijs. De bestaande bron-/claim-/rol-/deadline- en
objectset-CAS blijven verplicht; dit maakt de oude inputrevisie geen nieuwe
schrijfbevoegdheid. Een lege revisie bij oorspronkelijke registratie blijft
een geldige string, niet een ontbrekend veld.

Budgetstops behouden `incomplete_budget`, ook wanneer geldig werk reviewbaar
wordt. Alleen een nieuwe gecommitte taak telt als voortgang; een duplicaat of
een poging zonder vooruitgang blijft de bestaande retrycap verbruiken.
Een echte verlopen worker-/opdrachtgrens verleent geen gedeeltelijke activatie.
Structurele input-/outputlimieten blijven de bestaande blokkerende foutroute.

Een generiek afwijzingsbesluit over een V2-bronrecord is onvoldoende om de
broninhoud te verantwoorden. De bestaande expliciete bronafhandeling met
exact bewijs, bevoegde actor en revisie is nodig. De probleemprojectie gebruikt
dezelfde sluitingsbeslissing als publicatiegereedheid. Niet-geactiveerde
taakresultaten gelden niet als bewijs van gezamenlijke sluiting.
