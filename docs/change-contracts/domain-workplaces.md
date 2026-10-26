# Vaste domeinwerkplekken voor Vorming en Review

Change class: C
Promise: Een uitvoerder heeft één getoetste mapping van gebruikershandeling naar werkplek, bestaande command/read-owner en te verwijderen ingang.
Proof: Onderstaande route-, owner-, caller- en cutoverinventaris, expliciete tellergrondslagen en falsificatieproeven per deelslice; geen productwijziging.
Touches lifecycle invariants: no
Rewrite risk: none

Dit is PR 1 voor [#858](https://github.com/WilliamGomes41/Metis-DS/issues/858),
volgens het [ontwerp en de acht PR's van #857](https://github.com/WilliamGomes41/Metis-DS/issues/857).
Gecontroleerde codebasis: **`efed882c8f2bef850ea2aff47d744214b83131c8`**,
op 26 oktober 2026 via GitHub als actuele `main` bevestigd, gelijk aan de checkout.
De aanvankelijk lokale `origin/main` wees nog naar `d6fe3cbc3335d96256969d63e878de41468496d4`;
die referentie is na remote verificatie lokaal bijgewerkt. Productie-SHA onbekend.
Paden en symbolen hieronder verwijzen naar de gecontroleerde codebasis, niet naar
een veronderstelde toekomstige implementatie. Dit bestand wijzigt geen protocol,
lifecycle, governance, configuratie of productgedrag.

## Ground — verantwoordelijkheid, toestand en werkelijke compositie

De gewenste taakverdeling komt uit #857; bestaande code bewijst alleen het huidige
gedrag. Vorming verwerkt/verantwoordt/structureert/herstelt, Review beoordeelt
exacte kennisvoorstellen, Inzicht verklaart en toont bewijs. Mijn werk vindt taken
en opent de eigenaarwerkplek. Inleveren, Publicatie, Documenten en Instellingen
behouden hun bestaande beloften. Koppen controleren hoort bij Vorming, met behoud
van de bestaande bevestigingsvereisten. Informatie mag elders zichtbaar blijven;
een tweede editor voor dezelfde handeling mag dat niet.

### Module- en entrypointmap

| Bestaand onderdeel | Werkelijke keten en gezag |
| --- | --- |
| `src/console_asgi.py::build_app/build_console_app` | Bouwt de productiecompositie, bindt de vier workflowstores en `bind_pre_review_semantic_processing`. Kiest `FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole` in Azure en `FastBadgePostgresCompleteWorkflowDurablePublicationConsole` daarbuiten. Beide gebruiken PostgreSQL; geen nieuwe filetopologie afleiden uit de basisklasse. |
| `src/operations_console_app.py::create_console_app` | Registreert basis-POSTs, bronopeners, Inzicht, beslisboom- en deelnemersroutes; installeert Bronselectie via de bestaande bronselectie-installatie. `build_console_app` installeert vervolgens werkbord, batch, structured repair, reviewsignalen, legacy-herstelzicht en navigatievereenvoudiging. |
| `src/review_workboard_v1.py::install_review_workboard` | Is eigenaar van GET `/review`. Vervangt de eerdere POST-handler voor `/review/headings/batch-confirm`: bewaart de oorspronkelijke handler en verandert uitsluitend de vervolg-navigatie. Die vervanging hoort bij de cutover; geen tweede registratie toevoegen. |
| `src/review_passage_read_v1.py::read_review_passage/resolve_review_revision` | Een geselecteerd object leest gerichte histories, noodzakelijke buren, koppen, begrensde contextkeuzes en bindings in één bestaande readtransactie. Tijdelijk `review-generation-v1`-formulierbewijs bindt snapshot en documentrevision/object_generation; vertaling naar het bestaande objectsettoken laat de command-CAS intact. Historie/documenttaken gebruiken nog de documentbrede renderer. Dit bestaande onderscheid behouden, geen nieuwe reader maken. |
| `src/workflows/workflow_badge_counts_postgres_v1.py::_PostgresBadgeCountsMixin` | Runtime-override voor badges, compacte document-/werkbordsummaries en publicatiestatus. `review_workboard_summaries` verrijkt via de bestaande `review_work_item`-projectie; niet een nieuwe UI-teller naast SQL en domeinprojectie invoeren. |
| `workflow_remaining_cutover_v1` → `workflow_review_cutover_v1` → `workflow_documents_cutover_v1` | De samengestelde mixins verbinden envelope/objecten, bindings/events en resterende workflowgegevens met PostgreSQL. `_reprocessing_transaction`, `_commit_prepared_store`, `snapshot_objects_and_revision`, `write_bundle` en `workflow_transaction` blijven de bestaande schrijf-/concurrencygrenzen. `PostgresConcurrentWorkflowDocumentStore` bewaakt concurrent schrijven. |
| `ReviewClosureConsole` → `DeterministicRepairReviewConsole` → `ClosedLoopReviewConsole` → `ProportionateReviewConsole` → `OperationsConsole` | Werkelijke review-/repair-overrides. `ReviewClosureConsole.review_object/correct_object` bewaken mutable werkrevisies; structured revise kan `StructuredRepairRequired` opwerpen; closed loop bewaart audit en atomaire besluituitkomsten; batch loopt per object door `review_object`. Alleen de basismethode lezen mist deze grenzen. |
| `src/source_processing_dispatch_v1.py` | Bestaande dispatcher neemt na reservering de poging over via `execute_source_selection`; wake is slechts een hint, pending werk wordt via bestaande startup/poll/claim hervonden. GET naar een andere kamer annuleert geen werk. |
| `src/pre_review_semantic_v1.py`, `src/knowledge_materialisation_v1.py` | Runtimebinding voor semantische vorming; `materialise_knowledge_candidates` blijft de enige deterministische kandidaatmaker vóór menselijke review. Taakresultaten/diagnostiek zijn voorstellen en bewijs, geen alternatieve kandidaten. |
| `src/formation_problems_v1.py::collect` | Leest bestaande replay, pending rejections, taakresultaten, bronverantwoording, Admission en processing status. Afgeleide probleem-ID/bereik/projectie; geen probleemstore of zelfstandige sluitingsstatus. |
| `src/source_containers_v1.py::source_accountability/source_closure` | Bestaande rol-, sluitings- en menselijke-actielogica. `publication_readiness_v1.review_followup_queues` projecteert uitsluitend `source_disposition` en `technical_repair`. |
| `src/review_duty_v1.py` | `review_duty_for`, `reviewer_route_for` en `review_work_projection` bepalen open plicht, stage, lane en actorroute. Exacte actuele bindings blijven autoriteit; een pagina of teller kent geen reviewgeldigheid toe. |
| `src/insight_v1.py` | Diagnose en bestaande pagina-/herstelautorisatieformulieren. `console_navigation_simplify_v1` transformeert uiteindelijk HTML; controleer dus ook de gerenderde samengestelde app, niet alleen templates. |

De opslaggrens is voor alle onderstaande handelingen de **bestaande**
PostgreSQL-workflowautoriteit (documenten/objecthistorie, bindings/events en,
waar geactiveerd, `formation_*`-taakinput/resultaten/checkpoints), met bestaande
Azure immutable bronopslag in productie. Canonieke publicatie en actieve serving
blijven bij de bestaande publicatiestore/`publication_registry`. Een envelope,
UI-projectie, diagnostisch exportbestand of lokaal herstelbestand vervangt geen
autoriteit. De ondersteunde één/twee-workergrens op één instance blijft gelden.
Lokale single-worker/testbasisklassen zijn geen toestemming nieuwe productopslag
of een fallback toe te voegen.

Dominante accesses: compacte persoonlijke documentlijst → gerichte actuele
detaillezing → bestaande expliciete POST/command → bestaande commit → verse
projectie. Bij gedeeltelijke vorming kan de bestaande volledigheidscontrole
documentbreed nodig blijven. Geen extra volledige corpus-/ledgerlezing of deep
check per kaart; vóór/na dezelfde fixture en dezelfde bestaande reads tellen.
Er is hier geen productievolume of latency gemeten.

### Bestaande invoer, fouten en toestand

Gebruik onveranderd `snapshot_id`, bronhash/-versie, `object_id/object_version`,
canonieke hash, `expected_revision`/`snapshot_revision`, waar aanwezig `command_id`,
reviewpolicy, bindings en bronrol/closure/human_action. Queryparameters voor taak,
context of terugkeer zijn verliesbare navigatie, geen duurzame hervatcursor.
Een herstelretour draagt dezelfde identiteit mee maar leest de revisie opnieuw;
een eerdere goedkeuring gaat niet automatisch mee naar gewijzigde inhoud.

Gebruikersroute: reviewer opent persoonlijk documentwerk; een oordeel gebruikt
het bestaande reviewcommand. Ontbreekt context, dan opent hij gericht Vorming
voor dezelfde snapshot/kandidaat; alleen bestaand toegestaan herstel kan daar
worden uitgevoerd. Daarna opent hij de actuele Review-weergave. Een vormer kan
starten/hervatten, bronbestemming vastleggen of herstel uitvoeren zonder daarvoor
een diagnosepagina te moeten doorzoeken. Inzicht is optionele verdieping.

Commands hercontroleren actuele rechten, identiteit, bronbewijs en revisie;
stale invoer behoudt de bestaande conflictuitkomst en herlaadmogelijkheid.
Ontbrekende rechten blijven een weigering; opslagfouten worden geen leeg/groen
werkbord. Duplicate/retrygedrag verschilt per bestaande operatie: een command-ID
is geen algemeen idempotentiecontract voor ieder reviewformulier. Twee reviewers
of een herstelworker blijven door de bestaande transactionele guards/CAS
gescheiden, zonder browserlock of nieuw coördinatieprotocol.

Deze documentatie muteert **geen** domeintoestand. Latere verplaatsingen mogen
uitsluitend de reeds toegestane envelope-/object-/binding-/auditmutaties van hun
command uitvoeren. Bronbytes, snapshotidentiteit, deterministisch gevormde
kandidaatidentiteit/-mapping, gepubliceerd werk, reviewbescherming en serving
zijn geen bewerkbare UI-toestand. I01–I12 uit #857 gelden onverkort; dit bestand
voegt geen nieuwe domein- of ontwikkelregels toe.

## Handelingenmatrix — bestaande routes en doelwerkplek

`S` = snapshot, `O` = object; dit zijn leesnotaties, geen nieuwe API-parameters.
Alle genoemde POST-paden blijven de bestaande eigenaarroute, ook bij historische
woorden `/review`, `/tree` of `/inzicht` in de URL. Het verplaatsen van een
formulier omvat ook foutweergave, structured-repairhandler, vervolgredirect en
alle actieve aanroepers van die handeling. Een read-only bronopener is geen editor.

| ID / handeling, huidige → gewenste werkplek | Bestaande leesroute en read-owner | Bestaande POST/command en gezaghebbende eigenaar | Rechten, revisie, mutatie/opslaggrens |
| --- | --- | --- | --- |
| F1 Starten/hervatten: Bronselectie én Vormingsproblemen → Vorming | GET `/source-selection?document=S`: `source_selection_v1.projection/summary_projection`, `source_selection_documents`, `processing_status`; GET `/formation-problems?document=S`: `formation_problems_v1.collect` | POST `/source-selection/start` → `OperationsConsole.reserve_source_selection` → `source_selection_v1.reserve_selection` → bestaande dispatcher → `execute_source_selection` → bestaande uitvoering/materialisatie/activatie | `source_selection_v1.authorize`: actuele researcher of toegewezen reviewer, geen retired account. Snapshot/source/poging/command-ID/revisie, resumeconfiguratie, retries/deadlines/claim en reviewed-workguards blijven gelden. Bestaande PG-pogingen/checkpoints/objectactivatie; geen nieuwe queue. |
| F2 Problemen begrijpen/behandelen: Vormingsproblemen met links naar Review/Inzicht → Vorming | `collect`, `_formation_groups`, `_formation_problems_html`; probleemdetails uit opgeslagen extractie, replay en bestaande task-store | Geen generiek probleemcommand. Alleen F1, F3–F9 wanneer de huidige bevinding dat toestaat | Bestaande autorisatie van bronselectie. Meldingen zijn geen taken; overlappende of onbekende spans niet samenvoegen alsof identiteit bewezen is. Sluiting uitsluitend bestaande actuele dekking of exact bevoegd bronbesluit. |
| F3 Bronbestemming, context/label/uitsluiten: Review inventory/disposition en broncontextpaneel → Vorming | GET `/review?document=S&object=O&task=disposition`, context_mode/source/context_target; `_source_context_panel`, `_review_inventory`, `source_accountability`; geselecteerd detail via `read_review_passage` | POST `/review/source-context` → `OperationsConsole.confirm_source_context` → `source_context_review_v1.confirm_source_context`; POST `/review/source-exclusions` → `confirm_source_exclusions` in dezelfde module | Toegewezen reviewer, actuele broncontrole/open-original, reden, command-ID, exacte bronreferenties en revisie. Compact detailtoken wordt bij source-context via `resolve_review_revision` vertaald; exclusions gebruikt zijn bestaande objectsettoken. Bestaande transactionele objectversies/rolmetadata, doelcontext, bindinginvalidatie en audit. Uitsluitbatch alleen bestaande metadata/structuurgeschiktheid; geen algemene klinische batchuitsluiting. |
| F4 Koppen/plaats/relaties: Review structure/classification/relatiebediening → Vorming | GET `/review?...&task=structure` en objectdetail; `review_stacks`, `_heading_chooser`, `review_work_item`, bron- en relatieprojecties | POST `/review/headings/batch-confirm` → workboard-vervanger → oorspronkelijke handler → `batch_confirm_headings` → bestaande per-object `review_object`; POST `/review/relations` → `confirm_relations` | Toegewezen reviewer en bestaande structurele geschiktheid; headingcommand hercontroleert actuele rol, revisie en atomiciteit. Geen opheffing van bevestigingsplicht. Relaties wijzigen bestaande objecthistorie/bindings via `_commit_prepared_store`; geen nieuwe relatietabel. Type/plaatswijziging in het gecombineerde reviewformulier valt ook onder conflict C1 hieronder. |
| F5 Bronvoortzetting accepteren: Review objectkaart → Vorming | Objectdetail + `_broncontext_html`, bronfragmenten en `source_continuation` uit bestaande kandidaatcontext | POST `/review/context/accept` → `accept_source_continuation`; runtime-override in `DeterministicRepairReviewConsole` → bestaande kernel | Toegewezen reviewer, exacte bron en bestaande immutable-/reviewgrenzen, vertaald detailtoken/CAS. Bestaande brongebonden objectrevisie en invalidatie; geen vrije tekst toevoegen of goedkeuring overdragen. |
| F6 Kandidaat herstellen: Review repair/gestructureerde correctie → Vorming | GET `/review?...&task=repair`/objectdetail; `StructuredRepairRequired`-handler leest bestaande `source_units`, `source_fragment_catalog`, merge-/supportkeuzes | POST `/review/resolve` → `submit_review_resolution` → bestaande source_units/merge/support/classification-repair; `ReviewClosureConsole`-overrides en revision workflow blijven eigenaar | Toegewezen menselijke reviewer, commentaar, verplichte objectsetrevisie, exact geverifieerde bronselecties; bestaande gepubliceerde/legacy-/reviewgrenzen. Eén bestaande atomaire revise+repair+needs_review-operatie; nieuwe versies/invalidatie/audit via bestaande PG-commit. Geen tweede kandidaatmaker of vrije correctiewriter. **C1: geen losknippen van die transactie in een scherm-PR.** |
| F7 Tekst/type/sterkte/plaats bewerken: huidige gecombineerde Review-kaart → Vorming | `_render_review_card`, `_heading_chooser`, `_recommendation_semantics_block`; bestaande objectdetail-/bronlezing | Bestaande POST `/review` → `review_object` accepteert naast besluit ook type/sterkte/positie/relatievelden; structured revise kan naar F6 gaan | Rechten, source-bound semantiek en exact-reviewbinding blijven bij dezelfde runtimeketen. **C1: deze velden zijn niet allemaal zelfstandige editorcommands.** Geen nieuwe POST/helper om ze kunstmatig los te maken; inhoudelijke bevestiging onderscheiden van kandidaatwijziging vóór cutover. |
| F8 Pagina zonder kennisinhoud verantwoorden: Inzicht document → Vorming | GET `/inzicht/document?document=S`, `_source_pages_html`, bestaande attemptdiagnostiek/page_findings | POST `/inzicht/document/pagina-verantwoorden` → `OperationsConsole.account_source_page` | Bronselectie-autorisatie; categorie en notitie 10–500 tekens; alleen ongevormde bron, laatste mislukte pages_unresolved-poging, exacte pagina/reasons/sourcehash. Geen door browser geposte objectrevisie: command controleert actuele toestand onder `_reprocessing_transaction`. Append-only envelope-accounting; geen bestaande kandidaat of review wegschrijven. |
| F9 Eén extra herstelpoging autoriseren: Inzicht document → Vorming | GET `/inzicht/document`, `processing_status`, huidige retrylimiet/grant | POST `/tree/processing-recovery` → `authorize_processing_recovery` | Actuele publisher én uploader/toegewezen reviewer, reden; unpublished, beperkte pre-review/resumegrens, geen structurele limiet, niet actief en cap bereikt. Command legt huidige bronhash/-versie/revisie vast onder transactie; geen client-CASveld verzinnen. Eén grant, verbruik uitsluitend bij bestaande reservering. Geen Start bij GET of autorisatie. |
| R1 Inhoudelijk goedkeuren/afwijzen/revisie vragen/discrepantie: Review → Review | GET `/review`, werkbord of gericht objectdetail, `review_duty_for/reviewer_route_for` | POST `/review` → werkelijke `ReviewClosureConsole.review_object`-keten; discrepancies blijven evidence bij hetzelfde besluit | Toegewezen reviewer, actuele policy/primary, geldige bron, exact ID/versie/hash/type, revisie, bestaande commentaar-/discrepantieregels. Bindings/audit blijven PG-authority. Afwijzing is geen generieke bronprobleemsluiting. C1 geldt voor gekoppeld herstel en wijzigvelden. |
| R2 Geschikte passages samen bevestigen: Review batch → dezelfde inhoudelijke Review-taak | `normal_risk_batch_queue/counts`, `render_normal_risk_batch_panel`, actuele duties | POST `/review/normal-risk/batch-confirm` → `batch_review_normal_risk` (closed-loop atomaire override) → per-object `review_object` | Maximaal 20, eerste beoordeling, toegestaan type/sectie/bron/risk; geen beslisboom, mixed section/type of verruimde broncontrole. Exacte individuele uitkomst/binding per object. Bestaand revisie- en failure/atomiciteitsgedrag behouden; geen algemeen batchcommand. |
| R3 Onafhankelijke tweede beoordeling: Review second_review/graphpassage → Review | `reviewer_route_for`, actuele exacte approvers; GET `/review?...&task=second_review` en bestaande graafdetaillezing | POST `/review/second-review` → `approve_second_review` of bestaand revise; POST `/review/decision-passage` → dezelfde `approve_second_review` | Onafhankelijke actuele bevoegde reviewer, bestaande policy/required participants, exact tuple en revisie. Geen tweede approval door dezelfde actor; alleen reviewstate/bindings bij approval, geen canonieke tekst-/versiewijziging. De tweede UI-passage-ingang bij graaf meenemen in PR 6; één commandowner houden. |
| G1 Graafstructuur wijzigen versus graafinhoud bevestigen: één huidig Review-graafscherm → Vorming respectievelijk Review | GET `/review/decision-graph?document=S`, `decision_review_ui_v1.graph_get`, bestaande graaf/evidence/objects | POST `/review/decision-graph`, action=graph → `update_decision_graph`; action=confirm → `confirm_decision_graph` | Toegewezen reviewer, command-ID/reden/revisie, brongebonden nodes/edges/evidence, mutable revision en policy/graphreviewguards. Zelfde bestaande endpoint, onderscheiden bestaande commands. Editor verhuist, inhoudelijke bevestiging blijft Review; brongebonden afgeleide graaf wijzigt alleen volgens bestaande domeinregels. |
| I1 Diagnose/historie/export: Inzicht en bron-/Reviewlinks → Inzicht (read-only) | `/inzicht/document`, `/diagnostiek`, `/detaildiagnostiek`, `/poging`, `/verwerkingsbewijs`, `/verwerkingsspoor`, `/publicatiebewijs`, `/blokkade`, `/passages` onder `/inzicht/document`; `/inzicht/reviewsignalen`; `task=history` blijft leesbare Review-historie | Geen domeincommand toevoegen. `collect_blockage(current_checks=checks)` gebruikt bestaande optionele controles; geen herstelopdracht ervan maken | Bestaande per-read autorisatie behouden, inclusief publisher-only release-evidencegrens en researcher reviewsignalen. Geen herhaald deep-checkwerk per kaart. F8/F9-editors verdwijnen uit Inzicht in PR 4; oude diagnose en exports blijven bewijs, geen repair-authority. |

### Domeinbotsingen die een volgende slice niet mag wegpoetsen

**C1 — beoordeling en bewerking zijn deels één operatie.**

Uitwerking voor afronding van B op main `559ab4f05ef6a70689051dd4cf79444233bba1f3`:
de volledige bestaande `submit_review_resolution` kan als één opdracht op Vorming
worden aangeboden. Een vooraf opgeslagen Review-besluit is geen preconditie.
De interne revise/correctie/heropening blijft atomair; er komt geen losse
revisieovergang of extra writer. Inhoudelijke bevestiging van bestaande
voorstellen blijft Review. Het concrete onderscheid, de ongewijzigde guards,
callers en bewijsvoering staan in
[859-b-final-workplaces.md](859-b-final-workplaces.md). De hieronder vastgelegde
waarschuwing blijft gelden voor iedere poging de transactie alsnog los te knippen.

`review_post` stuurt type, aanbevelingssemantiek, documentpositie, relaties,
geschiktheid en besluit naar dezelfde `review_object`. De runtime kan bij revise
met suitability `StructuredRepairRequired` opwerpen; de exceptionhandler rendert
een correctiespecificatie. `submit_review_resolution` commit vervolgens revise,
bron-/merge-/support-/classificatieherstel en heropening in één opdracht.
Een willekeurig los revisiebesluit in Review opslaan en later repareren in Vorming
zou die huidige overgang veranderen. Ook `correct_object` is geen vrij inzetbare
UI-writer: closed-loop neutraliseert de legacy auto-apply en ReviewClosure bewaakt
immutable werk. F6/F7 zijn daarom een **concrete scopegrens voor #859-B**, geen
toestemming een tweede endpoint, tijdelijke probleemstatus of post-reviewrecht
toe te voegen. Verplaats alleen wat met de bestaande operatie kan; als de
Review-belofte een nieuwe domeinovergang vereist, stop die deelslice en herscope
volgens continuous-development/execution-contract. PR 2 (#859-A) is hiervan
onafhankelijk uitvoerbaar. Bij het opstellen van dit basiscontract was de volledige B-belofte nog niet
als haalbaar bewezen; de latere uitwerking hierboven verplaatst de gehele bestaande opdracht.

**C2 — graaf en structuur zijn inhoudelijk verschillend.** Koppenbevestiging
blijft haar bestaande per-object bevestiging uitvoeren in Vorming. Een
beslisboomgraaf wijzigen gebruikt `update_decision_graph`; interpretatie bevestigen
gebruikt `confirm_decision_graph`. Verplaats alleen de editor naar Vorming en
laat de echte graafbeoordeling in Review. Als aanpassen na graafreview een
andere invalidatie-/opvolgerregel vraagt, is dat een apart scopeconflict.

**C3 — protocoltaal en navigatie.** Protocol §11.1 noemt de huidige volgorde
Inleveren → Bronselectie → Review → Publicatie → Documenten. #857 vraagt Vorming
als werkpleknaam. Deze PR verandert dat protocol niet. Een latere slice moet
naamgeving/links consistent maken zonder van het naamverschil een nieuwe
verwerkings- of lifecycle-route te maken; een noodzakelijke normwijziging valt
buiten deze Class C-documentatie.

## Caller- en cleanupinventaris

| Callers/ingangen op de basis | Behouden, verplaatsen, verwijderen en moment |
| --- | --- |
| `source_selection_ui_v1.selection_get` en `_formation_problems_html`: beide POST `/source-selection/start`; `formation_problems_get` toont eigen herstelbediening | PR 2: één Vorming-werkplek met document-/probleemdetail. Verplaats bestaande bediening en verwijder de dubbele actieve start/hervatvorm in dezelfde PR. Verschillende detailweergaven mogen blijven als onderdeel van dezelfde werkplek; een tweede startkamer niet. GET-bookmarks blijven gericht leesbaar/navigeren; geen nieuwe cosmetische POST. |
| `formation_problems_v1.collect` actionlinks; `operations_console_app._formation_incomplete_banner`, bronselectie-vervolglinks, Mijn werk/nav en `review_workboard`-acties | PR 2: links voor starten/problemen wijzen naar Vorming. PR 3: bron-/repair-/structurelinks wijzen naar de verplaatste editor met S/O/context; Review-link alleen voor oordelen. Vervang de caller zodra zijn handeling verhuist, niet pas in PR 7. |
| `_review_inventory` uitsluitbatch; `_source_context_panel` beide source-contextformuliergroepen; `_render_review_index` koppenbatch; `_render_review_card` continuation, classificatie, positie, semantiek en reviewformulier | PR 3: F3–F7 daadwerkelijk verplaatsen, hun oude editors en conflict/foutrerendering verwijderen; R1-besluitformulier blijft. C1 eerst oplossen binnen de bestaande operationele grens of apart herscopen. Geen read-only CSS over een nog actief formulier. |
| `deterministic_review_repair_v1.structured_repair_handler`, `source_units_form/merge_form/support_form`, POST `/review/resolve`; read-only `/review/repair` uit `review_closure_v1` | PR 3: ook de exceptionhandler moet in de Vorming-context landen; geen achtergebleven correctiepagina onder Review. Bestaand resolvecommand behouden. Legacy-herstelzicht is alleen lezen en krijgt gerichte link naar de eigenaar; migratie bij startup blijft ongewijzigd. |
| `decision_review_ui_v1.graph_get` node-/edge-editor, confirmformulier en tweede-reviewpassageformulier | PR 3: graafeditor verplaatsen en oude editor weg. PR 6: oordeel/graafbevestiging behouden als één inhoudelijke reviewtaak; tweede passagebeoordelingsingang consolideren met R3 zonder commandduplicatie. |
| `insight_v1.document_diagnosis` herstelgrant en `_source_pages_html` accounting; bestaande POSTs in `operations_console_app` | PR 4: bestaande formulieren naar Vorming, alle oude mutatiecontrols weg, redirects en foutpresentatie naar de eigenaar. Diagnose behoudt toestand en gerichte links. Behoud bestaande POST en command; geen `/formation/recovery`-wrapper. |
| `/tree/reprocess` en `/tree/resume-formation` | Zijn nu navigerende compatibility-POSTs: published-guard/statusread → 303 Bronselectie, geen verwerking. Geen actieve UI-caller gevonden in huidige templates. Niet als writer tellen. In PR 2/7 caller-/compatibiliteitsbewijs controleren en dubbele doorstuurhandler alleen verwijderen bij bewezen ontbreken van noodzakelijke ondersteunde callers; geen vervangende doorstuurlaag maken. |
| `console_navigation_simplify_v1`, bestaande legacy Inzicht-/Audit-GETs, bronopeners `/review/bronpassage` en `/review/brondocument`, historie | PR 7 controleert resterende verwijzingen en historische bookmarks; read-only bron/evidence en bewijscompatibiliteit behouden met bestaande toegang. Pas HTML-transformatie aan wanneer de caller verhuist, zodat zij benodigde Vorming-acties niet verwijdert of oude editorlinks terugbrengt. |
| `console_asgi.build_app`, `bind_pre_review_semantic_processing`, dispatcher, `ReviewClosureConsole`-MRO, PG-mixins, read-contextwrappers | Behouden in iedere slice. GET-wrappers in `console_read_operations_v1` installeren na routes; nieuwe schermindeling moet dezelfde bestaande request-readcontext gebruiken. Geen command via GET en geen tweede route-installatie. |
| `src/cli.py` `processing-status` / `processing-retry` | Ondersteunde niet-UI-ingangen: halen `console_asgi.app.state.operations_kernel` op; retry gebruikt bestaand `retry_pre_review`, **niet** de UI-reserveringsroute. Behouden met hun huidige strengere guards; een verplaatst formulier schakelt deze route niet uit. Geen nieuwe CLI of fallback introduceren. |
| `src/decision_successor_v1.py` reserve/execute; `decision_review_ui_v1` successor/policy; `review_participation_ui_v1` deelnemers | Opvolger gebruikt bestaande `create_review_successor` en dezelfde verwerking; UI-successor `receive_only=True` stuurt naar bronselectie. Behoud identiteit/policy/revisie en opvolgersemantiek. Deelnemersbeheer heeft bestaande GET/POST `/review/participants` → `manage_review_participation`; traject `/review/trajectory` is read-only. Geen inventaris-editor als tweede vormer. Dit project wijst geen nieuwe beheerwerkplek toe: behoud de bestaande beheerroute als expliciete beperkte uitzondering buiten inhoudsreview; volgende navigatieslice benoemt die nog bestaande beheerhandeling. |
| `scripts/measure_source_task_reuse.py`, `scripts/measure_formation_validation.py`, `tests/formation_process_probe.py` | Reserve/execute rechtstreeks voor meting/herstartbewijs. Behouden, geen alternatieve productroute. Meetfixtures gebruiken bestaande productcommands; geen nieuwe opslagadapter invoeren. |
| `scripts/probes/probe_source_repair_mapping.py`, bestaande herstel-/reviewtests en fixturebouwers | Bestaande `/review/resolve`/kernelcallers behouden en actualiseren voor verplaatste UI, niet hun command omleiden. `src/cli.py review-queue` is bestandsanalyse, geen consolewriter; bestaande offline semantische/audittools zijn geen nieuwe productwerkplek. Geen van die offline tools als herstelautoriteit promoten. |
| `tests/test_source_selection_*`, `test_formation_problems_clarity`, `test_review_formation_problems`, `test_source_context_review_ui_v1`, `test_deterministic_review_repair_v1`, `test_review_workboard_heading_advance_postgres_v1`, `test_insight_v1`, characterization-goldens | Per verplaatste handeling oude schermasserties vervangen door eigenaar + oude ingang afwezig + behouden command/guards. Bestaande `browser_source_selection_*`, `browser_source_context_*`, `browser_formation_problems.cjs` en Raad-menu-/documentchecks meenemen; een gewijzigde golden alleen bewijst geen veilige mutatie. |

Dit is een statisch getraceerde inventaris van repositorycallers en ondersteunde
ingangen, geen runtimeobservatie van externe scripts of oude browserclients.
Niet vastgestelde externe callers zijn een compatibiliteitsvraag bij verwijderen,
geen rechtvaardiging om nieuwe parallelle routes te maken. Geen dode code is in
deze documentatie-PR verwijderd; productcleanup hoort in de betreffende cutover.

## Review-tellers — definities, contradictie en ontbrekend bewijs

| Getal/projectie | Huidige grondslag | Betekenis en beperking voor de nieuwe presentatie |
| --- | --- | --- |
| Persoonlijk open inhoudswerk | `review_work_projection`/`reviewer_route_counts`: actionable contextual + batch + second_review, met actor, policy, huidige bindings en bron | Uitvoerbaar eigen werk per snapshot/revisie. `knowledge_open_count` telt contextual + batch; tweede review heeft een eigen teller en mag niet ongemerkt ontbreken in een algemeen label. Geen bron-, structuur- of hersteltaken erbij optellen als inhoudsreview. |
| Documentbreed open plichten | `review_duty_counts`: één actuele eerste óf tweede duty per exact object, uitgesplitst naar lane | Niet gelijk aan persoonlijk open: een al goedgekeurde actor kan op een onafhankelijke tweede reviewer wachten. Bij een policy kan een andere primary eerst aan zet zijn. |
| Afgerond/voortgang | `_review_progress_summary`: alle niet-documentrecords, `definitive_review_disposition`; `knowledge_progress`: `content_reviewable` met superseded apart; `_lane_total`: open rows + approved/rejected in dezelfde lane | Verschillende noemers, geen persoonlijke voltooiingswaarheid. `_lane_total` sluit source records, label/context/excluded en superseded uit; historische fixes #672/#700 zijn al aanwezig. Een ratio kan bronafhandeling, afwijzing of vervangen werk bevatten; ‘afgehandeld’ bewijst geen inhoudelijke goedkeuring of publiceerbaarheid. |
| Koppen | `review_stacks`, open headings en bestaande bevestiging | Structuurwerk in Vorming; geen inhoudelijke kennisreviewplicht. Verplaats bediening én tellerlabel; schaf bevestiging niet af. |
| Batch | `normal_risk_batch_counts`: geschikte passages; daarnaast aantal groepen per type/sectie, in stukken van maximaal 20 | 40 geschikte passages zijn niet 40 afzonderlijke handmatige taken of één batch van 40; groepsaantal hangt van verdeling af. Individueel/batch zijn presentaties van dezelfde inhoudstaak. |
| Tweede beoordeling / wachten | `reviewer_route_for` met exact-current approvers en actionable/waiting; policy/required onafhankelijkheid | Eigen eerste goedkeuring kan geldig zijn terwijl documentreview niet klaar is. Wachten is geen uitvoerbare tweede review door dezelfde actor. Huidige `waiting_for_other_reviewer` dekt specifiek second_review; geen algemene wachtteller voor alle policysituaties veronderstellen. |
| Bronafhandeling | `source_accountability`: role/closure/human_action/reason/target_ids; `source_closure` vereiste records; `review_followup_queues` menselijke vervolgacties | `closure=open, human_action=source_disposition`: concreet bronbesluit; `repair_required, technical_repair`: herstel; `waiting_on_target, none`: wacht op doelreview; `accounted, none`: geen open menselijk bronwerk. Onbeoordeelde bron mag niet blind als inhoudstaak tellen. |
| Vormingsproblemen / technische taken | `collect` combineert actuele bevindingen; `_formation_groups` groepeert alleen exact bekende spans. Processing progress telt bestaande verwerkingstaken/resultaten | Een bronstuk kan meerdere meldingen hebben, een melding kan geen exact bereik hebben. Taakresultaten/pending rejections zijn geen bewijs dat een mens voor ieder record een formulier moet invullen. Technisch succes sluit niet automatisch inhoudelijk werk. |

**Bekende contradictie uit de opdracht:** 77 open, 37/77 afgehandeld,
37 te beoordelen en 40 batch. Rekenkundig kan 37 + 40 = 77 twee open
presentatielanes beschrijven; 37/77 afgehandeld kan een andere noemer of
documentbrede disposition gebruiken. Dit zijn **hypothesen**, geen reproductie of
vastgestelde oorzaak. Een persoonlijke teller kan bovendien afwijken van een
documentbrede. De huidige werkbordcode combineert actorroute-overrides met
documentbrede progress-/lane-totalen; dat is een concreet te falsificeren
verschil in grondslag, geen bewijs van de screenshottoestand. Ook beide
`_workboard_page`-paden (native summary en objectprojectie) moeten gelijk worden
vergeleken; bestaande compatibility-fallbacks zijn geen ontwerp voor nieuwe UI.

**514 en 183:** geen geautoriseerde export/fixture aangetroffen die deze twee
populaties aan dezelfde actor, snapshot, bronhash, revisie en peiltijd koppelt.
De synthetische schermreferenties en de draft in
`tests/fixtures/smetten_source_accountability_reference_draft.json` zijn geen
bewezen productie-uittreksel. De oorspronkelijke screenshotbestanden en hun
runtime-SHA zijn in deze run niet beschikbaar. Er is dus niet vastgesteld welke
records onder 514/183 vallen, hoeveel daarvan source_disposition,
technical_repair, waiting_on_target of already-accounted zijn, of de categorieën
overlappen. Niets hiervan als handmatige werkvoorraad of percentage rapporteren.

### Kleinste reproduceerbare tellerproef voor PR 5

Gebruik de bestaande native PostgreSQL-consolefixture en bestaande
review-/broncommands, met twee reviewers en één vastgezette bron/snapshot.
Geen nieuwe productopslag of provider/prodwrite nodig. Bouw deze kleine gemengde
populatie; leg de object-ID's per categorie als testbewijs vast:

1. Eén eerste contextual duty voor de primaire reviewer en één daarvoor
   geschikte batch duty. Tel per actor de bestaande routes; geen eigen router.
2. Eén exact goedgekeurd object waarvoor nog een vereiste onafhankelijke tweede
   beoordeling openstaat. De eerste actor wacht, de tweede kan beoordelen.
3. Eén volledig afgerond object, één afgewezen object en één superseded revisie.
   Vergelijk persoonlijke voortgang met documentbrede dispositions zonder ze
   gelijk te stellen; invalidatie van een binding moet de relevante teller wijzigen.
4. Eén open bronbesluit, één technical_repair, één linked_context die uitsluitend
   op doelreview wacht en één accounted bronrecord. Vergelijk de queues met
   `human_action`, niet met ‘alle niet-accounted records’.
5. Eén onafhankelijke geldige kandidaat naast open vorming, één kop en één
   document zonder persoonlijk werk. Maak gedeeltelijke reviewbaarheid,
   structuur en geen-werk afzonderlijk zichtbaar.

Lees op dezelfde captured toestand `review_work_item`, de bestaande native
`review_workboard_summaries`, GET `/review` en geselecteerd detail. Vergelijk
exacte ID-sets per actor/stage/lane, vervolgens labels/noemers en HTML; herhaal
na één bestaand oordeel en refresh. Een tweede goedkeuring door dezelfde actor,
stale token of verwijderde rol mag geen voortgang maken. De noemer mag niet
onzichtbaar wisselen tussen landen op een kaart en die kaart openen.
Dit voorstel is in deze run **niet uitgevoerd** wegens de testomgevingsgrens.
Het vervangt geen gereproduceerde screenshotpopulatie.

Voor 514/183 afzonderlijk een al geautoriseerde read-only export op de bedoelde
bronversie gebruiken: actor/policy, productie-SHA, snapshot/sourcehash, actuele
objectversies/hashes, bindings, spans, role/closure/human_action/reason/targets,
processing storage/attempt/contract en capturemoment bewaren in bestaand
test-/bewijsformaat. Bestaande `source_accountability` en queues hierop draaien,
ID-overlap/deduplicatie tonen en ontbrekend bewijs markeren. Als de beschikbare
exports geen exacte binding/source-invoer leveren, blijft die claim onbekend;
geen nieuwe exportendpoint, store, reconstructieheuristiek of productie-write
invoeren om de aantallen passend te maken.

## Sketch / Agree — het bestaande ontwerp uitvoeren

De twee vormen uit #857 worden hier aan de huidige compositie getoetst, niet
opnieuw als onafhankelijke studie gepresenteerd. De vergelijking is van één auteur.

| Criterium | A: pagina-eigen taakaggregatie/adapters/editors | B: bestaande owners, callers naar domeinwerkplek |
| --- | --- | --- |
| Eén autoriteit en I01–I05 | Meerdere taakwaarheden/ingangen of extra doorstuurlaag nodig | Geen nieuwe state/route; bestaande commands blijven beslissen |
| Dominante leespatronen / I11 | Risico op dubbele summaries en volledige reads | Bestaande compacte lijst en gericht detail blijven beschikbaar |
| Concurrency / revisie | Extra adapter moet guards/tokens correct spiegelen | Bestaande CAS/PG-transacties en passagepin hergebruiken |
| Review-/repaircompatibiliteit | Verbergt C1 gemakkelijk achter een wrapper | C1 expliciet; geen nieuwe overgang als UI-oplossing |
| Lokale cutover en bewijs | Makkelijk twee editors laten staan | Per handeling eigenaar actief en oude editor weg in dezelfde PR |

**Keuze B**, zoals #857. Geen workspace-manager, task-engine, provider,
repositorylaag, statusregister of projectiecache. Er zijn geen nieuwe datatypes
of command-signatures nodig voor PR 2; de bestaande formulieren leveren de
bestaande inputs en fouten. De operationele interface blijft letterlijk:

```text
POST /source-selection/start
  document=S, command_id=K, expected_revision=R
  -> reserve_source_selection(actor_id=current_account, snapshot_id=S, ...)
  -> bestaande dispatcher/execute -> 303 bestaande eigenaarweergave

POST /review/source-context
  snapshot_id=S, source_object_id=O, role, target_object_ids,
  reason, command_id=K, snapshot_revision=R, source_checked=1
  -> confirm_source_context -> bestaande commit/invalidatie -> actuele weergave

POST /review
  snapshot_id=S, object_id=O, snapshot_revision=R, bestaande besluitvelden
  -> huidige review_object-keten, inclusief StructuredRepairRequired
```

Dit zijn bestaande callsites, geen nieuwe API. De tweede en derde interactie
tonen waarom identiteit/revisie én C1 in de overdracht nodig zijn. Geen lege
stubmodules of scaffolding leveren; deze PR implementeert alleen dit document.
Agree betekent toetsing aan de expliciete opdracht/het bestaande ontwerp en
doorgaan binnen #858, geen claim van onafhankelijke review of inhoudelijk akkoord
op nog onbekende lifecyclekeuzes.

## Implement — acht opeenvolgende PR's en kleinste veilige overdracht

| PR / issue | Existing mechanism → verplaatste caller → oude ingang weg | Kleinste falsificatiebewijs en rollbackgrens |
| --- | --- | --- |
| **1 [#858](https://github.com/WilliamGomes41/Metis-DS/issues/858)** | Deze concrete inventaris, geen productwijziging | Routes/symbolen/callers tegen de vermelde SHA controleren; verplichte repochecks rapporteren. Terugdraaien verwijdert alleen documentatie. |
| **2 [#859-A](https://github.com/WilliamGomes41/Metis-DS/issues/859)** | F1/F2: bestaande reserve/dispatcher/status/projectie → één Vorming-bediening → dubbele start/hervatvorm weg | Browser→bestaande POST→echte PG→refresh; start eenmaal, duplicate, stale en onbevoegd; tijdens gepauzeerde verwerking naar Review/Inzicht navigeren zonder annuleren/mutatie; partial kandidaat bereikbaar, open probleem/publicatieblok behouden. Eén POST-owner en geen extra reads/writes. Rollback code/UI samen, bestaande v2-activatiereader/writer van #848 behouden, geen datareset. |
| **3 [#859-B](https://github.com/WilliamGomes41/Metis-DS/issues/859)** | F3–F7/G1-editor: bestaande commands → Vorming → oude Review-editors inclusief exception/foutforms weg | Bronbesluit/context/heading/repair elk bevoegd plus stale/ongeoorloofd, exacte bron/revisie/invalidatie en heen/terug. Ook graafedit versus graphconfirm. C1 vóór productcode begrenzen of herscopen; geen nieuwe transactie om editor en oordeel te scheiden. Rollback herstelt één oude UI bij dezelfde commands; gewijzigde objecten/bindings niet terugschrijven of oude approval herstellen. |
| **4 [#859-C](https://github.com/WilliamGomes41/Metis-DS/issues/859)** | F8/F9: bestaande accounting/grant → Vorming → Inzicht-formulieren weg | Native PG + browser: juiste rol, sourcehash/findings, kandidaat-aanwezig-guard, cap/structurele limiet en duplicate grant/accounting; autoriseren start niets, alleen expliciete bestaande reservering verbruikt grant; herstart behoudt feiten. Inzicht read-only. Rollback alleen presentatie, reeds gegeven grants/accountings behouden. |
| **5 [#860](https://github.com/WilliamGomes41/Metis-DS/issues/860)** | Werkbordsummaries/reviewerroute → directe Beginnen/Verder per document → verborgen primaire actie en dubbele tellerafleiding weg | Gemengde fixture hierboven, native/objectpariteit, eerste/tweede/wachten/klaar/geen werk; één actor/snapshot/revisie/noemer per teller. Geen opgeslagen cursor, extra corpusread of taskwriter. Rollback naar één oude landing, geen statewijziging. |
| **6 [#861](https://github.com/WilliamGomes41/Metis-DS/issues/861)** | R1–R3/G1-confirm: bestaande review/batch/router → één inhoudstaak → concurrerende individuele/batch/graafpassage-ingangen weg | Exacte per-object binding; max20/type/sectie/bron/independence; stale/duplicate/rolwijziging en batchfailure houden bestaande uitkomst. Herstelretour naar F3–F7 zonder oude approvals over te nemen. Rollback alleen UI, geen besluiten terugdraaien. |
| **7 [#862](https://github.com/WilliamGomes41/Metis-DS/issues/862)** | I1 + resterende nav/export/bookmarks/niet-UI → juiste eigenaar → restanten weg | Alle actieve formulieren/action/exceptionhandlers en samengestelde routes doorlopen; Inzicht verklaart, bronopeners read-only, GET-domeinwrites nul, CLI/dispatcher behouden. Dit is geen uitstel van cleanup uit PR 2–4. Rollback presentatie/links gezamenlijk. |
| **8 [#863](https://github.com/WilliamGomes41/Metis-DS/issues/863)** | Gecombineerde route/storage/callinventaris → volledige gebruikersroute → laatste bewezen dode ingangen/imports/config weg | Native PG + echte browser desktop/mobiel/keyboard, herstart, concurrent/stale/unauthorized, gepubliceerde immutable staat en ongewijzigde readiness/serving. Vergelijk reads/writes op dezelfde fixture. Echte reviewer vindt/begint/beoordeelt/herkent eigen klaar; rapporteer menselijke observatie apart van Playwright. Rollback naar vorige geïntegreerde productstand met bestaande opslag-/herstelcontracten, geen historische datareset. |

Volgende uitvoerder: start uitsluitend de expliciet toegewezen #859-A na de
geaccepteerde/geïntegreerde voorganger en controleer actuele `main`/labels opnieuw.
Vul de bestaande stateful Class B-overlay in voor de ongewijzigde
reserve/execute-transactie. Class B / risk none geldt alleen zolang owners en
domeinsemantiek gelijk blijven. PR 3 is niet automatisch vrijgegeven doordat A
haalbaar is. Tussen-PR's gebruiken **Part of #859**, niet Closes; #859 pas na alle
A/B/C-beloften. #857 sluit nooit door één deel-PR. Geen automatische doorstart,
merge, deploy of productiemutatie vanuit deze overdracht.

In tussenstanden kunnen nog niet verplaatste **verschillende** handelingen hun
oude plek houden: na A blijven F3–F7 in Review en F8/F9 in Inzicht; na B blijven
F8/F9 daar tot C. Dezelfde handeling heeft nergens twee editors. De uitzondering
voor bestaand deelnemers-/opvolgerbeheer wordt expliciet gerapporteerd, niet
stil als inhoudsreview voorgesteld. Er is geen impliciete uitrolautorisatie.

### Overlap en bestaand bewijs hergebruiken

- [#848](https://github.com/WilliamGomes41/Metis-DS/issues/848) / PR #850 en
  `848-review-formation-problems.md`: partial activatie, probleemsluiting,
  workerhervatten en v2-activatiebewijs. Code op main; issue blijft open voor
  productie-/Smettenacceptatie. Geen herbouw of claim dat verplaatsen die acceptatie oplost.
- [#851](https://github.com/WilliamGomes41/Metis-DS/issues/851) / PR #852 en
  `851-formation-problems-clarity.md`: letterlijke citaten, exacte groepering,
  bereikbaarheid en browser/typografiebewijs. Huidige code hergebruiken, geen
  tweede probleemprojectie of nieuw redesignprogramma.
- PR #853 / `review-read-performance.md`: passagegerichte reads, generatiepin,
  workboardprojectie en native concurrency. Niet terugvallen op volledige
  objectlezing om een Vorming-kaart te vullen. Bestaande expliciete documenttaken
  kunnen duur blijven; geen algemene performanceclaim.
- [#672](https://github.com/WilliamGomes41/Metis-DS/issues/672),
  [#700](https://github.com/WilliamGomes41/Metis-DS/issues/700) / PR #683:
  lane-totalfouten al gerepareerd; `test_lane_total_672_v1.py` behouden.
  Screenshotaantallen bewijzen geen herhaling van die oude fout.
- Broncontext-/T9–T12-contracten en `docs/agents/abstraction-boundaries.md`
  blijven de bestaande eigenaren en bewijzen aanwijzen. Geen nieuwe backlog,
  lifecycle-engine of publicatiepoort aan dit project toevoegen.

## Scrap en daadwerkelijke verificatie van PR 1

Ground en Sketch zijn uitgevoerd op de genoemde basis; Agree volgt de expliciete
#858-opdracht; Implement levert dit bestand met één gerichte referentiecontrole
in `tests/test_domain_workplaces_contract.py`. Er zijn geen vervangen productbranches/imports/forms in deze
PR; voor iedere latere verplaatsing staat het verwijdermoment hierboven. Herontwerp
alleen als een tweede authority/route of gewijzigde review-/herstelovergang nodig
blijkt; C1 is daarvan de nu aangetroffen concrete waarschuwing.

De architect-skill is gelezen en toegepast. De aanvullende skillresources
`candidate-brief.md`, `design-red-flags.md` en `rationale-template.md` konden via
de skillprovider niet worden gelezen; geen claim dat die templates zijn toegepast.
De bestaande ontwerpvergelijking en rationale uit #857 zijn hier hergebruikt.

Werkelijk uitgevoerd op de codebasis (vóór de documentwijziging): repository-
preflight PASS, release-control-preflight PASS (nog geen changed paths),
`python -m compileall -q src` geslaagd en architecture-boundaries PASS.
Deze artefactchecks moeten op de uiteindelijke documentcommit opnieuw worden
uitgevoerd en met de exacte head-SHA in de PR worden gerapporteerd.
De eerste release-controlcheck met de documentdiff blokkeerde terecht op ontbrekend
gewijzigd testbewijs voor scope/belofte, slop en releasebewijs. De gerichte
artefactcontrole toetst de bestaande bronpaden/symbolen en letterlijke POST-routes
zonder productimports of mutaties; de bijbehorende markers verwijzen naar die
concrete controle. Dit voegt geen product- of governanceregel toe.

**Geblokkeerd lokaal:** `bash scripts/test_postgres.sh` faalde op ontbrekende
`psycopg`; PostgreSQL 16-binaries zijn ook niet aanwezig. Daarna faalde
`python -m pytest -q tests/test_architecture_invariants.py` op ontbrekend pytest;
`pytest -q` kon niet starten (command not found). Een poging de bestaande
`requirements-dev.lock` in `work/test-deps` te installeren vond de vereiste
`jsonschema==4.26.0` niet in de beschikbare index. De shell kon de ingestelde
proxy niet bereiken bij `git fetch`; de GitHub-plugin bevestigde wel de remote
codebasis. Geen checks afgezwakt, geen PG-skip als groen bewijs gebruikt.

Er zijn geen producttests, native tellerreproductie, providerproeven, browserproeven
of menselijke gebruikersacceptatie geslaagd geclaimd. Deze documentatie verandert
geen scherm; nieuwe browserbewijzen horen bij de productcutovers. Ontbrekende
productie-export beperkt uitsluitend productieaantallen/oorzaakclaims, niet het
vastleggen van deze concrete mapping. De PR wordt als concept aangeboden met
deze controlebeperkingen; volledige checkgereedheid wordt niet geclaimd.
