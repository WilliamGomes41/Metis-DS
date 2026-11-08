# HA-2b: exact document afsluiten en deterministisch opbouwen

Change class: A
Promise: Een researcher controleert de opgeslagen bronkeuzes, sluit de exacte versie af en hervat één duurzame bouwopdracht die via de bestaande materialiser kandidaten met menselijk producerbewijs activeert.
Proof: native PostgreSQL- en browserketen; actuele resultaten in 1015-human-annotation-build-evidence.md.
Touches lifecycle invariants: yes
Rewrite risk: high

Expliciete opdracht #1015/MET-59, vervolg op keuze A en de
[caller-/uitvoeringsinventaris](1015-human-annotation-execution.md). Dit contract
legt de geïmplementeerde route op de featurebranch vast; merge en release
blijven afzonderlijke stappen. Bestaande ingestreview blijft gelden. Praktijkacceptatie,
bronrechten voor externe verspreiding en de totale cutover blijven afzonderlijke
releasevoorwaarden. Een technische fixture is geen researcherpraktijkbewijs.

## Lifecycle

Lifecycle entity: ongepubliceerde WorkingRevision, gepinde annotatieset en bijbehorende producerpoging.
Lifecycle transition: gecommitteerde ready/withdrawn entries -> gecontroleerd overzicht -> exact seal + bestaande duurzame poging -> deterministische activatie -> afgeleide review/blocked-toestand.
Initial durable state: immutable bron/extractie, actuele heads/generatie, expliciete scope-afhandeling en geen incompatibele lopende poging.
Trigger: afzonderlijke command “Afronden en opbouwen”; het overzicht zelf blijft read-only.
Authorization: huidige source-selection-autorisatie bij seal, claim en activatie, met bestaande immutable-publication- en successorgrenzen.
Validation: bron/working/extraction/normalisatie, exacte overzichtshash en manifest, entrygeneratie, primaire kern/velden/context/bewijs of expliciet NVT, bronrestanten, object-CAS, actuele actor en claim/lease bij activatie.
Mutable entities: bestaande annotatieset-sealpointer, bestaande processing_attempt/dispatch, bestaande objectfrontiers en reviewprojecties in één workflowdatabase.
Immutable entities: bron/extractie, entryversies, seals/documentcommands, producerbewijs, eerdere objectversies/reviewbesluiten/publicaties.
Workflow state before: processing.
Workflow state after: processing bij onvolledig/fout werk; na activatie in_review/blocked/ready_for_publication afgeleid via bestaande regels, zonder auto-approval.
Release state before: eventuele gepubliceerde voorganger.
Release state after: ongewijzigd.
Serving state before: actieve publicatieregistry.
Serving state after: ongewijzigd door bouwen.
Expected API result: immutable seal-ID/attempt-ID; duplicate zelfde receipt, gewijzigde payload/stale 409 zonder extra job.
Expected UI result: exact bron-/rol-/veld-/scopeoverzicht, afzonderlijk afsluiten, duurzame bouwstatus, toepasselijke review en broncorrectielinks.
Failure result: keuzes en exacte mislukte poging blijven behouden; geen gedeeltelijke activatie of AI-fallback.
Restart result: dezelfde job en invoer via bestaande dispatcherscan; een tweede worker kan niet dezelfde claim activeren.
Recovery result: dezelfde sealed invoer herhalen; een oude build na nieuwe selectierevisie wordt geweigerd; workflowback-up bewaart seal/proof/commandhistorie.
Legacy-data result: oude modelproofs blijven layout 1 en read-only leesbaar; niet-geannoteerd werk wordt niet stil overgenomen.
Required black-box scenario: echte productiecompositie -> receive/ingestkeuze -> menselijke selectie/veldkeuze -> save/pauze/verse console -> overzicht -> seal -> dispatcher -> enige materialiser -> immutable humanproof -> objectactivatie -> toepasselijke review, zonder servingwijziging vóór geautoriseerde publicatie.
Explicit non-goals: praktijkmeting, productiedeployment, historische bulkconversie, verwijdering van alle oude callers en volledige correctie/publicatie-integratie zijn met enkel kandidaatactivatie niet gereed.

## Concrete opslag- en aanroepkeuzes vóór migratie 036

GIVEN actuele gecommitteerde selecties en expliciete bronafhandeling,
WHEN de bevoegde researcher de exacte overzichtshash afsluit,
THEN worden seal en bestaande processing attempt atomair gereserveerd en mag
alleen de actuele geclaimde build exact dat resultaat activeren.

- `annotation_seals`: immutable source/working/extraction/policy/generatie en
  geordend entry-/scope-manifest. Contenthash-ID, bewaarde canonieke JSON-getuige,
  auteur/tijd en FK naar de bestaande set. Uniek per snapshot/overzichtshash; de hash bindt ook de materialisatiecontext, niet alleen generatie.
- `annotation_build_commands`: immutable aanroep-ID/actor/verzoekhash/receipt,
  gekoppeld aan seal en bestaande attempt. Geen eigen queue of jobstatus.
- `annotation_sets.current_seal_id`: enige huidige invoerpointer; een gewijzigde
  generatie maakt de oude seal onbruikbaar. Save, seal en activatie delen de
  bestaande autorisatie/document/setlockvolgorde.
- Bestaande `processing_attempts` krijgt kind `human_annotation_build` met
  top-level `annotation_seal_id` en producercontract. Geen modelconfig of
  `reserved_semantic_contract_version`. Bestaande lease/claim/budget/expiry-
  mechanismen blijven owner; de dispatcher krijgt alleen de nieuwe deliverytak.
- `formation_evidence_roots`: context-FK wordt nullable met een gesloten XOR-
  CHECK: layout 1 vereist modelcontext, layout 2 vereist human seal en variant
  `human-annotation-v1`, zonder modelcontext. Bestaande leden voegen de rol
  `annotation` toe. Input/source/job/result en elke entryrevisie zijn manifestleden;
  human memberhashes en de immutable seal bepalen exact de te activeren set.
- De bestaande FormationTaskStore prepare/publish/read- en activatieoperaties
  dispatchen op de layout. De owner bouwt het verwachte resultaat uit de seal
  opnieuw met dezelfde materialiser; callerJSON of zelfconsistente vervangende
  hashes zijn geen producerbewijs. Nieuwe root/pin en objectbundle vallen binnen
  de bestaande activatietransactie. Native fences vervangen 034's tijdelijke
  totale weigering door de exacte human binding, zonder bypassflag.
- Beide operationele documentlayouts ondersteunen een echte `human`-variant
  met seal/proofrefs en extractionpin; replay is afwezig. Geen dummy replay om
  migratie-030-checks tevreden te stellen. Historische model-/boomrefs veranderen niet.
- Workflowarchief gaat naar versie 11 / formation-sectie 4: nieuwe tabellen en
  rootkolom worden meegenomen; oude roots krijgen uitsluitend een lege human-FK,
  nooit verzonnen producerbewijs. Herstel toetst layout 1 én 2 via hun eigen owner.

De op main geleverde bronkeuzes hebben een expliciete v2-inputvariant voor exacte veldankers en
bronrolvoorstellen. Alleen noodzakelijke ontbrekende velden vragen een extra
aanwijzing; geen vrije herschrijving. Het aangewezen kernverband zelf is het
typebewijs en bij een aanbeveling de volledige normatieve kern, ook wanneer
die uit meerdere bronblokken bestaat. Onderwerp/gezegde/handeling/doel worden
niet uit het hele kernblok geraden. Hun bestaande v3-verplichtingen blijven
gelden via een echte human-veldvariant. Oude clients mogen die input niet
stil wegschrijven. Bronrol-entry's zijn nooit kandidaten; hun bestaande
role/reason-contract en T10-closure blijven gelden.

## Herschrijfrisico

Rewrite target: prozabouw uit sealed menselijke invoer binnen dezelfde producer-/workflowautoriteit.
Why local patching is insufficient: de huidige modelcontext/replay/FK-/originchecks kunnen menselijke invoer niet uitdrukken; een los knopje of permissieve origincheck zou oude writes openlaten.
Current authority/writer/reader map: uitvoeringscontract; expliciet beide write_bundle-implementaties, migratie-030-overrides, native worker_handover, operational inputs, FormationTaskStore/FormationEvidence, source containers, recovery, review/readiness/API/MCP en settings/interne callers.
Supported runtime topologies: beide document-input-layouts, task-v1 processing, lokale en Azure bronstores in de bestaande productiecompositie; geen annotatie-file-store.
Persisted-state impact: additieve seal/commandtabellen en human-FK, bestaande job- en proofowner uitbreiden; immutable historische content/hashes blijven intact.
Compatibility/migration plan: expand; bestaande layout-1-bewijzen behouden; oude writers weigeren human-owned werk; voorbereiden en bouwen gebruiken dezelfde bronpin en geen automatische takeover.
Rollback/recovery plan: fouten houden bestaande serving en opgeslagen input intact; oude binary mag nieuw humanwerk niet terugzetten naar modelvorming. Lege-doelrestore behoudt exacte versies/claims/proofs zonder nieuwe besluiten; geen destructieve productiecontractie.
Cutover trigger: native duplicate/concurrent/stale/seal-versus-save/claim/restart/bypass- en black-boxproeven slagen op exacte codeversie. Globale prozacutover pas na vervolgketen en repositoryreleasevoorwaarden.
Cleanup/decommission criteria: geen tweede jobstore of kandidaatcreator; tijdelijke oude prozawriters verdwijnen in HA-4 met caller-/config-/endpointbewijs. Shared boom-/bron-/hashhelpers blijven bij hun bestaande owner of worden gericht verplaatst.
Failure blast radius: betrokken ongepubliceerde WorkingRevision; geen live release of registrymutatie.
Adversarial proof matrix: forged/trimmed proof, ontbrekende member, andere bron/extractie/entryrevisie, dubbele commands/workers, stale builder na save, revoke na seal/claim, beide SQL-/bundle-/storagevarianten, herstel na restart/lege-doelrestore en oude AI-reservering/ingest/reextractie.

Twee afzonderlijke read-only runners hebben de kandidaten op main94e3bf78
onderzocht. Kandidaat A: immutable bronverwijzende seal + bestaande processing
attempt en gesloten humanvariant binnen FormationEvidence. Kandidaat B: echte
human-sumtype-uitbreiding van formation_inputs/context/result. Beide behouden
één creator/job/proofowner. A is gekozen: B zou ook de modelsemantische
formation_contexts/validatorinputs/resultkeys moeten migreren, zonder winst voor
de dominante toegang (sealed entrymanifest lezen). B wijst terecht op dezelfde
vereiste typed-field/context/complementvalidatie; die wordt gedeeld hergebruikt.
De twee runners hebben geen code gewijzigd of implementatieproeven uitgevoerd.

Vergelijkingscriteria: behouden authorities, actualiteit bij gelijktijdige save,
gesloten native variant, reader-/restorecompatibiliteit en expliciete callers.
Een aparte humanqueue of mutable proofstore voldoet aan geen van beide vormen
wegens twee herstel-/activatiegrenzen en is uitgesloten.

Bewijs en afwijkingen worden toegevoegd na daadwerkelijke uitvoering;
geen slice-Done op grond van dit document.


## Actuele basis en concrete grenzen

Basis: main94e3bf7878cfcda0f752403214ea37480cd7106b, na#1021/#1022/#1030.
Dit is uitvoering op de expliciete vervolgopdracht voor MET-59/#1015; geen
nieuwe starttoestemming afgeleid uit oude planninglabels. Voorwaarden en
uitzonderingen zijn context binnen dezelfde claim (keuze A, #986/MET-49).
De oudere definitie “kleinste stuk richtlijntekst” is achterhaald.

Consumergebruik:

```python
view = human_annotation_build_v1.overview(console, actor_id=actor, snapshot_id=sid)
receipt = human_annotation_build_v1.finalize(console, actor_id=actor,
    snapshot_id=sid, command_id=command, overview_hash=view['overview_hash'],
    expected_generation=view['generation'], expected_revision=view['objects_revision'])
# Alleen na commit: laad receipt['attempt_id'] via native_attempt en notify de bestaande dispatcher.
# Restart ontdekt dezelfde bestaande attempt via dispatch scan.
```

De seal bevat canoniek geordende entry-ID/revisie/payloadhash, bron-/extractiepin,
normalisatie, objectfrontier en exact materialisatiecontext (titel/familie/klasse,
datum/URL, reviewpolicy/configuratie en deelnemers, successor_guard en
replaces_snapshot_id). Jobmetadata/heartbeat verandert die
context niet. Policy-/metadataverandering kan zonder annotatiegeneratie gebeuren;
daarom uniek op snapshot/overzichtshash, nooit alleen generatie.

Een save vóór eerste activatie mag de huidige seal invalidateren: nieuwe
entryversie/generatie en current_seal_id=null atomair. De oude onveranderlijke
seal blijft historie; oude claim/proof kan niet meer activeren. Na succes blijven
versies/proof traceerbaar. Volledige correcties na objectactivatie en gerichte
reviewinvalidatie behoren aan de bestaande review-/revisieowner in HA-3; deze
stap versoepelt niet stil de gepinde objects-CAS of gepubliceerde immutabiliteit.

Duplicate finalize autoriseert opnieuw en retourneert dezelfde opgeslagen
receipt, ook na succesvolle bouw. Fout/restartdelivery behoudt dezelfde logical
task (seal-ID); de bestaande leaseowner hervat een geclaimde/pending attempt.
Een expliciete retry na een terminale fout gebruikt de bestaande retryowner en
hetzelfde sealed input, zonder nieuwe inhoudelijke beslissing of tweede queue.
Bestaande source retrycap/cooldown/recovery grants blijven gelden; geen nep-
modelcontract of verzonnen progress om een budget te omzeilen.

Preview controleert bron/velden/context zonder KnowledgeCandidate te maken.
Alleen de materialiser creëert text/ID/mapping na seal. Complementbereiken
blijven zichtbaar; alleen geldige kern/context/bewijs via hun actuele claim of
expliciete metadata/structure-entry verantwoorden brongebruik. Ongeselecteerde
bron is geen automatische uitsluiting. Bronrolvoorstel/annotatie-ready is geen
T10-/reviewbevestiging. Een standalone type met unresolved via_relation blijft
geblokkeerd zolang geen werkelijk expliciet doel bewezen is; geen doel uit
nabijheid of een condition-KO uit een contextrol verzinnen.

Identieke geordende kernranges in aparte actieve claimentries worden expliciet
geweigerd, zonder automatisch samenvoegen. De gebruiker koos optie 1 op
2026-11-08. Bestaande creator-identiteit blijft behouden. Save controleert de
andere actuele heads onder dezelfde document-/setlock; het overzicht toont
beide betrokken annotaties en afsluiten/bouwen herhaalt de controle. Gedeelde
context/onderbouwing en identieke tekst op verschillende bronlocaties blijven
mogelijk. Een withdrawn entry reserveert geen claimidentiteit.

Compatibiliteit: beide document-input-layouts ondersteunen de humanvariant.
Bestaande inline terminale attempthistorie mag alleen exact worden gekopieerd,
nooit heropend; running modelwerk blokkeert takeover. Alleen de bestaande
operational-input CAS mag inline geschiedenis representatiegetrouw verplaatsen.
Recovery leest eerst extraction/annotation/seal-eigenaren, daarna attempts en
proofs, met bestaande deferred FK's en één offline lege-doeltransactie.

Activering vereist werkelijke036-constraints/guards naast035; ontbreken of
uitschakeling weigert nieuwe seal/activatie en nieuwe humanrestore. Geen
callerflag/GUC kan de034-fence vrijstellen. Gewone curation behoudt immutable
producerproof via haar eigen bestaande revision-owner; producerproof is geen
algemene updatevergunning.

## Implementatie 2026-11-08 — featurebranch, nog geen release

Migratie036 is geregistreerd. De productiecompositie gebruikt dezelfde dispatcher
voor bestaande bronselectie en menselijke bouw. De overview-, finalize- en
statusroutes zijn aangesloten; save wist de actuele seal bij nieuwe invoer.
Een exacte save-retry retourneert zijn bestaande receipt ook na activatie,
zonder nieuwe wijzigingen na die activatie toe te staan.

De native objectfence toetst bij eerste online invoeging de actuele seal en het
exacte producerresultaat. De aanvullende deferred aggregatecontrole toetst ook
vervalste humanmarkers op modeldocumenten. Daardoor mag offline archiefherstel
objecten vóór hun annotatie-/proofhistorie laden, maar alleen in dezelfde
transactie met de volledige correcte binding. Geen herstel-GUC of andere bypass.
Historische seals en producerproofs blijven leesbaar nadat gewone metadata
verandert. De huidige context is wel verplicht voor nieuwe seal/claim/activatie.

De operationele humanvariant kan niet via de oude inputwriter worden verwijderd
of naar een ander actief proof worden omgebogen. Oude label-/contexttoevoeging
via Broncontext vastleggen wordt voor humanwerk geweigerd. Gewone review van
het bestaande brongebonden resultaat blijft mogelijk. De bestaande revision-
en publicatieowners blijven verantwoordelijk; dit is geen HA-3-correctieroute.

De builder hergebruikt de bestaande object_diff-owner voor opvolgers, toetst de
actuele parentguard en voegt actuele heartbeatdiagnostiek samen vóór finish.
Dubbele kernranges worden in save onder dezelfde locks geweigerd; preview en
seal toetsen dit opnieuw. Er is geen retrospectieve unieke headconstraint die
historische concepten onleesbaar zou maken. Het overzicht meldt zulke concepten
bij de oorspronkelijke annotaties; alleen gecorrigeerde invoer kan afsluiten.

De afzonderlijke adversarial pass vond en herstelde de grens tussen verse
activatie en historisch herstel, de mogelijkheid een humanmarker op ongebonden
modelobjecten te zetten, en het verwijderen van humanrefs via de oude writer.
Native negatieve proeven dekken deze grenzen. De bewijsnotitie vermeldt de
werkelijk uitgevoerde commando's, resultaten en beperkingen.

Nog buiten deze slice: correctie na eerste activatie met gerichte reviewinvalidatie
(HA-3), volledige verwijdering van oude prozawriters/configuratie (HA-4), formele
referentie-/selectietaak MET-58, researcherpraktijktoets, merge en deployment.
Geen parent-Done of globale omschakeling op grond van deze featurebranch.
