# Uitvoerbaar wijzigingscontract: menselijke prozavorming

Change class: A
Rewrite risk: high
Promise: De researcher bouwt één claim met brongebonden context en bewijs uit meerdere exacte bereiken; uitsluitend de bestaande deterministische materialiser maakt kandidaten na expliciete documentafronding.
Touches lifecycle invariants: yes
Proof: de native en volledige ketenproeven hieronder zijn oplevervoorwaarden, geen reeds behaalde resultaten.

## Bronnen en feitelijke stand

Opnieuw gecontroleerd op 8 november 2026: main `e0a3b09ac23a0c226d1546d19fb66885006131bd`,
HA-2a `c23933d23442ac0f54ca8b3523b00d9354c23a04`, ontwerpbranch
`docs/human-annotation-architecture-1014` op `1fb0e09797f9fbcda0681a100171ae17e234b794`.
De ontwerpbranch is niet main. Draft [PR #1021](https://github.com/WilliamGomes41/Metis-DS/pull/1021)
is open en niet gemerged. De checks voor HA-2a bewijzen geen seal, kandidaatbouw,
review, publicatie of verwijdering van het oude pad.

Inhoudelijke bronnen: [#986](https://github.com/WilliamGomes41/Metis-DS/issues/986)/MET-49,
#1013–1017/MET-57–61; architectuur en multi-range-contract op bovengenoemde
ontwerpcommit. Uitvoeringsregels: AGENTS, execution-contract, continuous-development,
lifecycle-vsa, abstraction-boundaries; frontendwerk volgt Impeccable en de
bestaande Metis-brand. Expliciete menselijke implementatieopdracht in deze
sessie is de uitvoeringsopdracht; planninglabels zijn geen bewijs van implementatie.

### Besluiten (GO projectlead, 8 november 2026), betekenis en conflicten

- Leidend: “one claim, held together with its context, its supporting evidence
  and its provenance”. De oudere “kleinste stuk richtlijntekst”-definitie vervalt.
  Een extractieblok, alinea of afzonderlijke muisselectie bepaalt geen KO-grens.
- Keuze A in deze sessie: voorwaarden en uitzonderingen blijven exacte
  brongebonden context **binnen dezelfde claim**. Aanwijzen maakt daarvan geen
  zelfstandig KO. Zelfstandige claims vereisen een afzonderlijke expliciete entry;
  de materialiser mag context niet splitsen of nieuwe expertise afleiden.
  Dit besluit moet bij #986/MET-49 zichtbaar blijven; hun overige open vragen
  worden hiermee niet als opgelost beschouwd.
- `semantic-only-formation.md`, `passage_formation_policy_v1` en de huidige
  `SELECTION_ORIGIN_PROPOSAL`-checks verlangen nog modelselectie. Dit botst
  expliciet met de nieuwe prozaopdracht. De nieuwe human-variant vervangt die
  plicht voor overgeschakeld prozawerk; boomcontract en historische modelbewijzen
  blijven geldig. Geen menselijke selectie vermommen als modelvoorstel.
- Bewijs blijft verplicht per bestaand type; alleen expliciet NVT sluit die
  verplichting af. `supported_by` en `explains` behouden hun verschillende functie.
  Een onderbouwingsbereik wordt niet automatisch een apart uitleg-KO.
- De bij ingest vastgelegde reviewpolicy blijft normatief. Annotatie, gereed,
  seal en bouwen zijn geen inhoudelijk oordeel. Geen nieuwe reviewerselectie,
  auto-approval of verplicht tweede oordeel bij een policy die dat niet vereist.
- Het leesbare claim/context/bewijs/herkomst-pakket is een projectie bij lezen,
  geen tweede opgeslagen object of tweede publicatieautoriteit.

## Geobserveerde owners en volledige wijzigingsoppervlakte

Paden hieronder zijn relatief aan `src/`. “Vervangen” is een uitvoeringsplicht,
geen bewering dat deze callers al zijn verwijderd. Geen productieaantallen of
live opslaglayout zijn vastgesteld met deze repository-inspectie.

| Ingang/eigenaar | Feitelijk gedrag | Contract voor omschakeling / bewijs |
|---|---|---|
| `operations_console_v1.receive_source/ingest` | ontvangt bron, ingestpolicy en lineage; ingest kan ook direct vormen | proza alleen ontvangen/voorbereiden; direct-ingest mag geen modelbouw behouden; boomroute apart |
| `source_selection_v1.reserve_selection`, `OperationsConsole.execute_source_selection`, UI `POST /source-selection/start` | reserveert modelpoging, uitvoering en receipt | vervangen door annotatieprepare/seal; oude start na cutover geweigerd, ook rechtstreeks aangeroepen |
| `OperationsConsole._fragments_and_spec`, `pre_review_semantic_v1.configured_fragments_and_spec` | centrale strategie en modelselectie | menselijke besluitinvoer naar dezelfde materialiser; geen providerfallback |
| `OperationsConsole._execute_source_attempt/retry_pre_review/reextract_unpublished/promote_class/promote_class_document` | retry/herextractie/klassewijziging kan nieuwe prozakandidaten maken | human seal hervatten of expliciete nieuwe bron-/werkversie; nooit terug naar modelvorming |
| `OperationsConsole.resume_formation`, `cli.cmd_processing_retry` | ook zonder browser dezelfde modelpoging starten/hervatten | bestaande kernelgrens weigert oude prozabouw; CLI is geen uitzonderingsroute |
| `source_processing_dispatch_v1.SourceProcessingDispatcher` | duurzame pogingen ontdekken/claimen; geheugen alleen wakehint | zelfde dispatcher/lease-owner levert human-build-kind; startup ontdekt exact dezelfde job |
| `worker_handover_v1.claim_native/renew/validate/discover`, `processing_retry_v1.reserve/assert_active/finish` | CAS, deadline, actuele rechten en pogingstatus | dezelfde claim/leasefence; actor/bron/seal/contract i.p.v. modelconfig voor human-kind |
| `formation_checkpoint_v1.TaskCheckpointWriter` en `FormationTaskStore.retain_input/commit_task` | modelcontext, deeltaken en finalisatie | historische lezer behouden; human invoer via versievariant, geen nepcontext/model/replay |
| `knowledge_materialisation_v1.materialise_knowledge_candidates` | enige maker van tekst, ID en mapping; weigert nu human-origin | uitbreiden met gesloten human-besluittype; tekst/ID/mapping uitsluitend hier |
| `bounded_formation_v1`, `pre_review_semantic_v1`, `recoverable_formation_v1` | drie modelcallers van dezelfde materialiser | prozawriters verwijderen na HA-4; gedeeld/historisch lezen eerst afzonderen |
| `decision_tree_construction_v1` | boomcaller van dezelfde materialiser | behouden; gedeelde creator niet verwijderen met prozawriters |
| `OperationsConsole.correct_object/accept_source_continuation` | bestaande selectiecorrectie en materialisatie | human bronobject opent oorspronkelijke annotation-ID; geen tweede correctiecreator |
| `semantic_transform_generic_v1`, `candidate_eligibility_v1`, `admission_gate_v1` | origin-/metadata-/type-/veldchecks; transformatie na creator | human-origin expliciet lezen; geen bewijs op basis van alleen origine/type; v3-verplichtingen niet omzeilen |
| `source_bound_fields_v2/v3`, `source_context_review_v1` | exacte context/veldankers en contextrealisatie | opvolgercontract voor human-relaties behoudt rol, functie, verplichting, bronanker; bestaand v1/v2/v3 read-only leesbaar |
| `semantic_passage_v1.source_coverage_records`, `source_accountability_v1`, `source_containers_v1.source_accountability/source_closure` | bronrestanten zijn bronrecords, geen kandidaten; T10 bepaalt afsluiting | exact ongebruikt bereik zichtbaar houden; gesloten bestaande bronredenen en vereiste oordelen behouden, geen automatische uitsluiting |
| `formation_evidence_v1`, migraties 029 én 030 | modelproof met verplichte context/replay; 030 vervangt activatietrigger voor twee layouts | gesloten human-proofvariant in dezelfde root/member/FK-grens; beide layouts toetsen |
| `workflow_document_concurrency_v1.write_bundle` én override `workflow_documents_cutover_v1.write_bundle` | activatiecheck, objectmerge, revision frontier en commit | beide roepen dezelfde uitgebreide FormationTaskStore-activatiegrens; geen directe alternatieve objectwriter |
| `workflow_documents_postgres_v1.create_document_bundle`, `object_delta_postgres_v1`, review-deltawrites en legacy import/startup | lagere schrijf-/compatibiliteitsgrenzen buiten producer-orchestratie | SQL ownership/proof-fence blijft gelden; import/recovery is geen vormingstoestemming; geen nieuw human bronwerk uit oude cache reconstrueren |
| `workflow_transaction_v1`, `_reprocessing_transaction` | gedeelde SQL-transactie, autorisatie- en documentlocks | korte commit; bron-I/O, reconstrueren en bouwen buiten documentlock; hercontrole bij activatie |
| `human_annotation_v1`, migraties 034/035 | gepinde set, immutable entryversies, heads/receipts, v2-betekenisvelden/bronrolvoorstellen/relatieverplichtingen en fail-closed legacy fences | huidige save behouden; seal/save delen hetzelfde document/setlock en CAS |
| `operational_document_inputs_v1`, migratie 030 | refs in `document_inputs`, attempts in rijgerichte tabellen; legacy envelope blijft ondersteund | echte human variant met eigen proofref; replay blijft afwezig, geen `semantic` zonder replay |
| `formation_recovery_v1`, `workflow_chain_recovery_v1` | offline exports/imports misten annotatietabellen op c23933d2 | herstelgat repareren in bestaande back-uptransactie; zie herstelcontract, archief v10/formation v3 |
| `deterministic_review_repair_v1`, review duty/policy/bindings/frontiers | revisies en exacte relevante oordelen | gerichte annotatiecorrectie via huidige reviewmutation; onveranderde peers behouden, afhankelijke bindings opnieuw verplicht |
| `operations_console_app` `/review/source-context`, `_source_context_panel`; `source_selection_ui_v1` “Broncontext vastleggen” | aparte contextschrijfroute, knoppen en oude pagina | UI/POST-writer verwijderen in HA-4; benodigde bronrealisatie, historische records en groepsafhandeling naar resterende owners |
| `settings/route_comparison_app_v1.execute_arm`, compare-run endpoints | kan nog `semantic_units_before_review` aanroepen, ook al zijn nieuwe vergelijkingen uitgezet | model-proza-uitvoering en interne endpoints verwijderen; historische vergelijkingen read-only |
| `settings/semantic_safety_app_v1`, `audit_semantic_safety_v1`, passagepolicy/configuration/binder | settings/audit/modelconfig kan proza uitvoeren | product-triggers/config voor oude vorming verwijderen; gedeelde technische en boombindingen behouden |
| `attempt_diagnostics_v1`, `processing_evidence_export_v1`, `forensic_trace_v1`, meet-/probe-scripts en `release_settings_preflight.py` | historische selectievalidatie/bewijslezers, model-meetcallers en releaseconfigchecks | read-only historie behouden; geen modeluitvoering uit diagnose/herstel; oude write-probes verwijderen of afbakenen; releasecheck volgt de nieuwe vormingsconfig |
| `publication_readiness_v1`, `DurablePublicationConsole._publish_locked`, canonical store/registry | readiness en geautoriseerde release, actieve serving | dezelfde bron/context/rechten/status/review-checks op exact object; geen seal als publicatietoestemming |
| `AzureAuthoritativePublicationConsole`, `console_asgi` | productcompositie en blobreadback | lokale en Azure bronstore bewijzen; geen blob- of productieclaim uit lokale test |
| `product_api_v1`, `product_source_authority_v1`, retrieval | REAL API leest actieve registry en geverifieerde bron | draft/blocked/withdrawn/superseded mag niet terugkomen via cache/herstart |
| `settings/metis_mcp_v1` en `metis_mcp_queries_v1` | geauthenticeerde interne werk-/bewijslezers, inclusief ongepubliceerd werk | werkinspectie niet verwarren met publieke kennis; een publieke projectie mag uitsluitend registry-serving lezen |

Controleer de callermap na iedere substantiële wijziging opnieuw met `rg` op
`materialise_knowledge_candidates(`, `_fragments_and_spec(`, `semantic_units_before_review(`,
`assert_activation(` en de verwijderde route-/configsymbolen. Alleen een
grep-resultaat is geen bypassbewijs: direct-call/native tests blijven vereist.

## Bronidentiteit, rollen en rechten

Anker = snapshot + working revision + source SHA/version + immutable extraction
record hash + stabiele reconstructed block-ID + halfopen `[start,end)`
codepointinterval. Bestaande `semantic_source_blocks/normalize_visible_prose`
is de representatie, `metis-visible-prose-codepoints-v1`. Geen nieuwe NFC/NFKC.
Een nieuw extractiebeeld krijgt een andere pin, nooit hergebruik van oude offsets.
DOM UTF-16 wordt naar codepoints vertaald; server controleert graphemegrenzen.
Quotegetuige wordt exact vergeleken; alleen SHA-256 aanvullend opgeslagen.
Identieke tekst op twee locaties blijft via verschillende ankers selecteerbaar.
Verschuiving leidt tot conflict en expliciete herankering in opvolgwerk, niet zoeken.

Per entry: immutable revisies; ordered kernankers; afzonderlijke rolrelaties met
eigen `required_for_meaning`, auteur en bronpin. Dezelfde passage mag in meerdere
entries verschillende rollen hebben. Geen impliciete relaties uit nabijheid.
Kern in bronleesvolgorde; klikvolgorde/relatievolgorde blijft auditbaar. Overlap
tussen afzonderlijke kernankers wordt geweigerd; overlap tussen verschillende
rollen bewijst geen zelfstandige nieuwe claim.

Voor projectie wordt `population` uitsluitend doelgroep; algemeen `context`
blijft algemeen en wordt niet stil als actor, timing of klinische scope getypeerd.
Voorwaarde/uitzondering blijven contextrollen van keuze A. Onderbouwing behoudt
zijn gekozen `supported_by`/`explains`-functie. Een essentieel verband mag niet
stil verdwijnen uit de kandidaat-/review-/leesprojectie. Een nog oningevulde
verplichte relatie blokkeert seal. Ontbrekende bestaande typevelden blijven
Admission blokkeren: vraag dan alleen het ontbrekende exacte subbereik/functie,
geen vrije herschrijving en geen heuristisch verzonnen veldbewijs. Human
veld-/contextrecord krijgt een expliciete variant; historische v3 niet herinterpreteren.

Toegang is geen licentie. Actuele researcher-/reviewerrechten volgen bestaande
source-selection-autorisatie; duplicate commands autoriseren opnieuw. Interne
bronweergave/download blijft onder die grens; geen nieuwe openbare quote-export.
In de onderzochte code staat geen zelfstandig quote-licentiecontract;
`source_declaration` is geen bewezen licentie voor willekeurige citaten. Voor
nieuwe externe verspreiding zijn twee houdbare routes: (1) publicatie alleen
met expliciet vastgelegde toepasselijke bronrechten, of (2) interne annotatie
houden totdat die rechten voor de bron zijn bevestigd. Advies: 1 voor de
uiteindelijke release, 2 zolang het bronrechtenbewijs ontbreekt. Dit blijft een
inhoudelijke publicatievoorwaarde; geen toestemming uit een technische test afleiden.

### Scopeverantwoording zonder tweede goedkeuring

Voor de eerste ketenproef is de hele bron de opdracht. Het overzicht toont ook
de exacte complementbereiken van kern/context/bewijs. Niet aangewezen betekent
onafgehandeld, nooit automatisch uitgesloten. De bestaande gesloten
`source_accountability_v1.ROLES`/redenen en `source_containers_v1` zijn de
eigenaar van brongebruik; geen nieuwe lijst “dit hoofdstuk is nooit kennis”.

Menselijke bronrolvoorstellen worden als een expliciete opvolger-payloadvariant
van de bestaande annotatie-entryversies opgeslagen: exact anker, bestaande
rol/reden, auteur, status en revisie. Dus dezelfde autosave/CAS-/historiegrens,
geen los afvinklijstje of tweede conceptstore. Seal bindt deze bronrol-entryversies
naast de claimentries. Een onbekend bereik zonder expliciete afhandeling of een
open concept blokkeert afronden. Een voorstel voor metadata/uitsluiting is geen
reviewbesluit. Na bouwen gaan bronrestanten via de bestaande bronrecordprojectie
en T10-/reviewclosure; verplichte bevestigingen worden niet overgeslagen doordat
de researcher het overzicht afsloot. De oude pagina verdwijnt pas nadat die
noodzakelijke handeling in de nieuwe werkplek beschikbaar en native bewezen is.

De [HA-2b-inputprerequisite](1015-human-annotation-meaning.md) voegt deze
bronrolvariant en betekenisvelden/relatieverplichtingen toe als expliciete v2
binnen dezelfde tabellen, met native revisie-/headfences in migratie 035.
Seal/job/activatie blijven open; het huidige overzicht bewijst dus nog geen
volledige documentafhandeling. Een context-/bewijsrange kan brongebruik
realiseren, maar alleen bij een actuele geldige relatie naar de betreffende
claim; een ongekoppeld bereik telt daarvoor niet.

Een essentiële relatie is een expliciete verplichting binnen de entry, niet
alleen een vlag die verdwijnt wanneer het bereik wordt verwijderd. De
opvolger-payload bewaart een stabiele relatie-ID, functie en verplichting met
het aangewezen anker of een open reden. Anker verwijderen maakt die relatie
onopgelost; opheffen van de verplichting is een afzonderlijk expliciet,
gereviseerd besluit. Een eerdere essentiële voorwaarde kan dus niet door een
lege rangearray stil uit het overzicht en de sealvalidatie verdwijnen. De
nieuwe payloadvariant moet dit bewijzen; HA-2a levert die relatiehistorie nog niet.

## Afsluiten en bouwen: exacte overgang en data

Lifecycle entity: ongepubliceerde WorkingRevision plus de daarin gepinde annotatieset.
Lifecycle transition: opgeslagen selecties -> exact overzicht -> sealed invoer + één duurzame bouwpoging -> geactiveerde kandidaatversies onder bestaande reviewpolicy.
Initial durable state: geldige bron-/extractiepin, actuele entryheads/generatie, geen actieve incompatibele bouw, alle scopebesluiten expliciet.
Trigger: overzicht is een read; afzonderlijk “Afronden en opbouwen” is een command.
Authorization: actuele bestaande source-selection-rechten bij command, claim en activatie; annotator krijgt geen reviewerrol.
Validation: complete overzichtshash, setgeneratie, iedere entryrevisie/hash, bron/extractie/working identity, object-CAS, verplichte relaties/velden en open scope; lease en actuele policy bij activatie.
Mutable entities: setpointer naar huidig seal, bestaande durable processing attempt/claim, bestaande objectfrontiers en actuele reviewprojecties in workflow PostgreSQL.
Immutable entities: bronbytes, extractie, entryversies, seals, producerproof, historische objectversies/oordelen en releases.
Workflow state before: processing.
Workflow state after: processing bij fout/open werk; na geldige activatie afgeleid in_review, blocked of ready_for_publication volgens de bestaande gates; nooit automatisch closed.
Release state before: voorganger indien aanwezig blijft gepubliceerd.
Release state after: ongewijzigd door bouwen/review.
Serving state before: registrybepaald.
Serving state after: ongewijzigd tot expliciete bevoegde publicatie.
Expected API result: seal-ID/attempt-ID en versie; duplicate zelfde resultaat; stale 409 zonder nieuwe job.
Expected UI result: overzicht, expliciet afsluiten, duurzame bouwstatus en toepasselijke review; fouten openen oorspronkelijke entry.
Failure result: eerdere opgeslagen keuzes blijven beschikbaar; geen gedeeltelijke kandidaatset/approval.
Restart result: dezelfde seal/job/proof/versiekoppeling; geen nieuwe inhoudelijke beslissing of dubbele bouw.
Recovery result: retry hervat exact dezelfde seal via bestaande claimowner; oude worker kan na correctie niet activeren.
Legacy-data result: oude immutable modelbewijzen en releases blijven leesbaar; geen stil takeover van niet-afgesloten bestaand werk.
Required black-box scenario: upload -> ingestkeuze -> menselijke multi-range selectie -> pauze/herstart -> overzicht -> seal/job -> materialiser -> toepasselijke review -> publiceren -> registry/API en geautoriseerde MCP-projectie; daarna correctie/stale builder en restart bewijzen.
Explicit non-goals: geen nieuwe approval-engine, zelfstandige condition-KO's uit rollen, automatische herankering, modelhulp, bulkconversie, zelfmerge of deployment.

GIVEN alle betrokken concepten ready/withdrawn en expliciet afgehandelde scope,
WHEN de researcher de exacte actuele overzichtshash afsluit,
THEN worden immutable seal en één bestaande processing attempt atomair bewaard,
wordt na commit gebouwd, en blijven serving/reviewbesluiten ongewijzigd.

De implementatieshape is een uitbreiding van de bestaande workflowowner:

Voor de caller blijft het documentoverzicht `overview(...)`. De beoogde nieuwe
domeincommand `finalize(console, actor_id, snapshot_id, command_id,
expected_generation, overview_hash, expected_revision)` levert na commit
`seal_id`, `attempt_id` en een bestaand dispatchreceipt. De UI mag pas daarna
notificeren; startupscan werkt ook zonder die wakehint. Dit is het doelinterface,
nog geen beschikbare functie. Een dubbel command autoriseert opnieuw en geeft
dezelfde uitkomst; gewijzigd commandmateriaal of verouderd overzicht geeft 409.

1. Immutable `annotation_seals`: contenthash-ID, snapshot/working/extraction/policy-
   pin, generatie/overzichtshash, expliciet scopebewijs, geordende
   `(annotation_id, revision, payload_hash)`-manifest, actor/command/tijd.
   Actuele sealpointer op de bestaande set; geen tweede mutable entrykopie.
2. Eén `processing_attempts`-kind voor human build met sealref en bestaand
   dispatch-/leasecontract. Uniek command en geen tweede jobqueue. Modelconfig
   en replay zijn afwezig, niet gevuld met dummywaarden. Native attemptinputs
   projecteren dezelfde identity. Legacy opslag wordt expliciet via de bestaande
   operational-input-owner geschikt gemaakt; niet via verborgen envelopevelden.
3. `formation_evidence_roots` krijgt een gesloten variantkeuze: modelvariant
   vereist bestaande context-FK; humanvariant vereist seal-FK en geen context.
   CHECK garandeert precies één geldige variant. Members krijgen human-
   manifest/input/resultrollen; de bronrol blijft huidige geverifieerde bronbasis.
   Oude roots blijven onveranderd. Manifest sealing blijft immutable/deferred.
   Humanheader/reference gebruikt layout 2 en variant `human-annotation-v1`;
   layout 1 blijft historische modelvariant. Alle readers, inclusief de nu
   hardcoded layout-1-read in recovery, dispatchen expliciet op deze versie.
   Niet-ondersteunde layout wordt geweigerd. De bestaande prepare/publish/read-
   operaties blijven de grens; prepare kiest precies context-ID óf seal-ID.
4. Humanheader bindt source identity, extraction, seal, contract/materialiser-
   versie, poging/claim/actor, activatiefrontier, actuele ingestpolicy en exacte
   `(annotation_id, revision) -> (object_id, object_version, canonical_hash)`.
   Lidmaatschap wordt uit ownerrecords afgeleid, niet uit requesttellingen.
5. De bestaande materialiser accepteert een expliciete human-selection decision.
   Hij reconstrueert kerntekst en bronmapping; selector levert geen clean_text
   of object-ID. Context/evidence zijn exacte bindings, geen eigen creator.
   Transformatie/Admission mogen uitsluitend valideren/projecteren/blokkeren.
6. Beide `write_bundle`-implementaties krijgen dezelfde proofcheck vóór writes;
   SQL-fence uit 034 wordt vervangen door exact humanproof/member-validatie op
   gewijzigde objecten. Geen `is_human`, GUC of callerflag die activatie vrijstelt.
   Gewone curation retains producerbewijs maar moet haar eigen mutationcontract
   blijven bewijzen; producerproof is geen algemene updatevergunning.

Opslag wordt rijgericht per entry gebruikt voor autosave; seal leest één
consistente verzameling. Grote bron-/reconstructie-/materialiser-I/O blijft
buiten het lock. Commit lockvolgorde: huidige authorizations -> document -> set
-> poging/frontier, overeenkomstig de bestaande owners. Save versus seal
serialiseert op dezelfde locks. Voor activatie opnieuw bron, sealpointer,
generatie, objectfrontier, actuele bevoegdheid en lease vergelijken. Een wijziging
maakt een oudere seal onbruikbaar; zo wordt het PStack-tegenvoorbeeld een echte
native PostgreSQL-regressieproef. Geen algemene documentstatus naast afgeleide workflowstate.

## Review, herstel en publicatie

Correctie vóór publicatie opent de oorspronkelijke annotation-ID met de exacte
entry-/objectbinding. Opslaan voegt een entryversie toe en bouwt via dezelfde
materialiser nieuwe objectversie(s); oude proof/versies blijven traceerbaar.
Veranderde kern, betekenisdragende context, bewijsfunctie, type of relaties
vernieuwen de betreffende reviewbasis. Afhankelijke peers die naar de gewijzigde
versie/context wijzen worden gericht herbeoordeeld; ongewijzigde onafhankelijke
objecten houden hun geldige oordelen. Geen documentbrede reset of overerven van
goedkeuring uitsluitend op gelijke tekst. Bestaande review_duty en bindinghashes
bepalen de verplichting, niet een nieuwe annotatiestatus.

De objectbinding bevat de eigen annotation-ID/revisie/payloadhash, niet een
documentbrede sealhash die alle onafhankelijke objecthashes zou veranderen.
Na correctie mag het oude object van die gewijzigde entry niet gepubliceerd
worden terwijl herbouw nog loopt: readiness controleert zijn actuele entryhead.
Ongewijzigde peers worden met dezelfde versie/hash in de nieuwe exacte
activatiemanifest hergebruikt; hun reviewbasis verandert niet uitsluitend omdat
een andere entry is gewijzigd. De bestaande bronclosure blijft daarnaast gelden.

Publicatie blijft de bestaande bevoegde object-/releaseoperatie met volledige
bronbinding, context, rechten, status en ingestreview. Gepubliceerd werk wijzigt
nooit in-place: opvolgende WorkingRevision bij nieuwe policycontext, of nieuwe
SourceSnapshot/WorkingRevision bij nieuwe bronversie. `logical_document_id`
blijft gelijk. Vervanging via bestaande atomische registrytransitie; intrekking
met reden blijft historisch zichtbaar en inactief na restart. API/retrieval
lezen de actieve registry. Het huidige MCP is een interne werkinspectie en
mag ongepubliceerde data aan bevoegde deelnemers tonen; die response mag niet
als openbare, beoordeelde kennis worden gepresenteerd.

## Migratie, terugval en verwijdering

Rewrite target: AI-verplichte prozavorming naar human-owner input met dezelfde kandidaat-/review-/publicatiegrenzen.
Why local patching is insufficient: origin-, bewijs-, activatie-, opslag- en herstelcontracten zijn op modelreplay gebaseerd; alleen een nieuwe editor zou bypasses openlaten.
Current authority/writer/reader map: bovenstaande tabel, beide write_bundle-paden, migratie-030-override en back-up/import inbegrepen.
Supported runtime topologies: beide document-input-layouts, task-v1 pogingen, huidige complete PostgreSQL-consoles; lokale en Azure immutable source stores. Geen annotatie-file-storefallback.
Persisted-state impact: additieve immutable seal/proofvariant en bestaande jobrefs; geen tweede workflow-/servingstore en geen herschrijving van oude contenthashes.
Compatibility/migration plan: expand met oude readcompatibiliteit en databasefences; migreren alleen expliciet lege ongepubliceerde bronnen of expliciet geautoriseerde opvolgers; werk met reviews niet stil overnemen. Versiechecks voor human-proof en operational refs moeten vóór activering beschikbaar zijn.
Rollback/recovery plan: bij fout blijft eerdere serving intact. Oude runtime weigert human-owned werk; geen AI-fallback om werk weer leesbaar te maken. Workflowback-up bevat complete annotatie/seal/job/proofhistorie. Alleen expand rollback; destructieve productiecontractie vereist aparte repositoryprocedure en geteste back-up.
Cutover trigger: native opslag-/activatie-/bypassmatrix én volledige upload-tot-servingketen geslaagd op exact hoofdcommit; actuele productietelling van bronroutes/layouts/open pogingen/reviews vastgelegd; merge/releasevoorwaarden voldaan. Lokale fixtures geven geen productie-GO.
Cleanup/decommission criteria: alle prozastarts/retry/reextract/class-change/settings/internal callers naar human-owner of expliciete weigering; model-prozawriters, contextpagina/POST/knoppen/config/helpers en uitsluitend bijbehorende tests weg. Gedeelde boom-/bron-/hash-/historische proofcode eerst onder juiste owner brengen. Eén creator en geen permanent tweede vormingspad aantonen.
Failure blast radius: betrokken ongepubliceerde WorkingRevision; eventuele live voorganger onveranderd. Een proof-/pin-/rechtenfout blokkeert activatie/publicatie.
Adversarial proof matrix: hieronder; aparte reviewpass probeert alternate writers/readers en stale runtime ook bij groene CI.

Vergeleken alternatieven (één agent, geen onafhankelijke beoordeling): aparte
human queue/proofstore zou eigen herstel en activatieauthority introduceren;
afgewezen. Gesloten humanvariant bij bestaande FormationTaskStore, dispatcher en
roots/member-grens behoudt bestaande transacties/claims en legacy-readcompatibiliteit;
gekozen. Scope-/rights-/contentbesluiten worden daarmee niet technisch verzonnen.

## Verificatie en oplevergrenzen

| Risico | Verplicht waarneembaar bewijs |
|---|---|
| Verloren concept of herstelownership | servercommit -> verse sessie/proces -> exact overzicht; ketenback-up naar lege tweede PG-database -> save en legacy fence |
| Duplicate/concurrent/stale | gelijke command identiek resultaat; gewijzigde payload conflict; twee onafhankelijke verbindingen; save versus seal, claim versus correctie |
| Verkeerde bron/Unicode | identieke tekst op twee locaties; emoji/decomposed accent; graphemegrenzen; stale document/extraction en verschoven bron weigeren |
| Context verdwijnt | multi-alinea kern + essentiële voorwaarde elders + uitzondering + beide bewijsfuncties; ontbrekende relatie blokkeert, geen automatisch condition-KO |
| Onbevoegde quoteverspreiding | ingetrokken account, interne bron/origineel en externe literal-projectie onder toepasselijke rechten; geen licentieclaim uit source-declaration |
| Oude worker/proof kan activeren | PStack-pad save -> seal -> build -> correctie -> oude activatie faalt; native SQL oude writer en beide bundleimplementaties |
| Review wordt overgeslagen | één/twee/optionele deelnemers volgens echte ingestpolicy; annotator is geen reviewer; exacte definitieve reviewbasis en gerichte invalidatie |
| Publicatie/serving onterecht | open werk/blocked/missing context/rechten/review weigeren; API en MCP-toegang; vervanging/intrekking/restart behouden registry |
| Fallback blijft bereikbaar | direct ingest/retry/reextract/class-change/settings/internal calls zonder modelkandidaten; gedeelde boomroute blijft werken |

Echte PostgreSQL 16 via `scripts/test_postgres.sh`/pytest-autostart; skip is geen
PASS. Browserproef op productiecompositie en echte opslag. Full-suite-checks,
preflight, releasecontrol en architecture checker volgen de repository. Elke
PR noemt exacte head, contract, code, migratie, verwijderde callers,
testcommando's/resultaten en resterende risico's. HA-2a, HA-2b, HA-3 en HA-4
blijven afzonderlijk bewijsbaar; geen parent-Done vóór de toepasselijke ketenproef.

PStack-toestanden selecteren -> overzicht -> seal/bouw -> ingestreview ->
publicatie zijn de toets voor overgangen. De 80 modeltoestanden bewijzen geen
PostgreSQL-commit, quotejuistheid, autorisatie, autosave of crash recovery; de
restartstap is een aanname. Geen nieuwe TLC-run geclaimd.

Praktijktoets: `docs/plans/human-annotation-practice-acceptance.md`. Echte bron,
inhoudelijke opdracht/eigenaar en onafhankelijke referentie blijven nodig.
Synthetic fixtures, technische regressies en dit contract zijn geen bewijs
van bruikbaarheid, foutdekking of tijdwinst bij researchers.
