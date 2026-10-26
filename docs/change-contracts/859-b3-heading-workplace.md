# #859-B3 — Koppen bevestigen op Vorming

Change class: B
Promise: Een toegewezen reviewer controleert en bevestigt prozakoppen op Vorming; Review biedt dezelfde bevestiging niet aan.
Proof: Bestaand formulier → bestaande POST → PostgreSQL → refresh/herstart; oude Review-ingang zonder bevestigingsformulier; stale/onbevoegd/gepubliceerd zonder writes; desktop en mobiel.
Touches lifecycle invariants: no
Rewrite risk: none

Part of #859 / PR 3 uit #857. Basis: actuele main
`e6a83c646b2020d33ab0cce3deb9086d15b270a7`, met gemergde #867.
Alle invarianten I01–I12 uit #857 blijven gelden.

## Ground — bestaande operatie en scopegrens

| Handeling / caller | Huidig → gewenst | Bestaande grens en behoud |
| --- | --- | --- |
| Prozakoppen selecteren/bevestigen | Review task=structure (alias headings) → Vorming task=structure | GET gebruikt snapshot_objects_and_revision, _review_bindings, review_source_fragments en _review_route_objects; geen nieuwe reader of geschiktheidsregel. |
| Bevestiging | POST /review/headings/batch-confirm blijft | operations_console_app bouwt bestaand structure interaction evidence; batch_confirm_headings controleert actuele reviewerrol, revisie, gehele selectie en per-object review_object onder _STRUCTURE_CONFIRMATION. |
| Runtime POST-vervanger | install_review_workboard blijft de ene geregistreerde POST bezitten | Bestaande oorspronkelijke handler wordt één keer aangeroepen; Vorming-resultaat blijft staan. De bestaande boom-navigatie blijft behouden. Geen tweede endpoint of doorstuurlaag. |
| Kopdetail | Review toont bron en bestaande correctie-/afwijskeuzes; verwijst voor bevestiging naar Vorming | Losse approve van een structural projection wordt door review_object al geweigerd. De misleidende losse goedkeurkeuze verdwijnt; de verschillende bestaande herstelhandelingen verdwijnen niet stilzwijgend. |
| Python/directe POST/native tests | Blijven ondersteund | Dezelfde batch_confirm_headings en /review/headings/batch-confirm; geen tweede writer. Geen verplicht nieuw veld. |
| Beslisboomstructuur/graaf | Buiten B3 | Bestaande path-bevestiging en graafreview blijven in Review. Dit zijn andere handelingen dan prozakoppenbevestiging. |

**Bijgestelde afbakening:** relatie-/plaatsbewerking is geen los actief editorformulier.
De huidige kaart verstuurt die velden samen met een oordeel naar POST /review;
ClosedReviewLoop/ReviewClosure/DeterministicReviewRepair koppelen de correctie
aan bestaande review- en herstelovergangen. /review/relations heeft ondersteunde
directe callers, maar geen zelfstandig actief formulier om te verplaatsen.
Een nieuw los formulier zou een nieuwe producthandeling introduceren. B3 verplaatst
daarom uitsluitend de bestaande koppenbevestiging; C1 blijft expliciet open.
Het gehele kopdetail read-only maken zou ook bestaande afwijzing en herstel
verwijderen: dat alternatief is verworpen. Geen domeinregel wordt gewijzigd om
de schermindeling passend te maken.

## Context en stateful Class B-overlay

| Gegeven | Producent → consument | Eigenaar / levensduur / geldigheid |
| --- | --- | --- |
| Snapshot, bronhash en documentversie | Bestaande envelope → formulier/command | Bestaande PG/Azure-authority; onveranderd, ook bij navigatie/herstart. |
| object_ids | Bestaande structure-projectie → batchcommand | Alleen expliciete selectie; kernel hercontroleert gehele set. Geen nieuwe kandidaat. |
| snapshot_revision | Bestaande snapshotread → expected_revision | Bestaande objectset-CAS. Stale geeft bestaande 409 en verse Vorming-weergave, geen write. |
| interaction_id | Bestaande tijdelijke formulier-ID → build_review_interaction_evidence | Bestaand auditbewijs, geen opgeslagen UI-cursor of nieuwe commandstore. |
| q / page | Bestaande Review-lijst → Vorming GET → Review-teruglink | Alleen tijdelijke navigatiecontext. Zowel actuele dashboardlinks als historische bookmarks behouden zoekterm/pagina; geen opslag of commandwijziging. |
| Actuele rechten/publicatie | Account/envelope/runtime → command | Op mutatie opnieuw gecontroleerd; GET verleent geen bevoegdheid. |

Domain entity/aggregate: bestaande mutable WorkingRevision/objectset en reviewbindings.
Invariant(s): bestaande geschikte structural projections, toegewezen reviewer,
bron-/kandidaatidentiteit, reviewgeldigheid en publicatievoorwaarden blijven gelijk.
Durable state before: geselecteerde open prozakoppen met huidige revision/bindings.
Durable state after: alleen expliciet gekozen koppen bevestigd via dezelfde
per-object operatie; niet-geselecteerde kandidaten/bron onveranderd.
Transaction boundary: _heading_batch_mutation → workflow_documents_cutover:
storelock, autorisatielock, PG-document FOR UPDATE, workflow_transaction;
workflow_review_cutover buffert bestaande events. Objecten/bindings/audit blijven
in dezelfde commit/rollbackgrens. Geen opslag-/schemawijziging.
Failure/recovery result: bestaande rollback en refresh, geen UI-compensatie/datareset;
herstart leest dezelfde PG-state.
Duplicate execution / idempotency result: replay met oud revisietoken faalt stale;
de bestaande commandsemantiek wordt niet uitgebreid tot een nieuwe idempotentiebelofte.
Concurrency result: bestaande native documentlock/CAS behoudt winnaar; A08-proeven
voor batch/single-overlap, COMMIT-fouten en rollback blijven ongewijzigd.
Audit/evidence requirement: bestaande structure-interactie, actor, bron/objectversie,
reviewevents en bindings; geen nieuw register.

## Sketch — twee vormen, keuze en Agree

Gebruik: reviewer opent Vorming?document=S&task=structure, controleert de bron via
de bestaande kopdetail-/bronlinks, kiest expliciet object_ids, verstuurt dezelfde
POST en blijft op Vorming. Historische Review task=headings/structure-links
openen dezelfde Vorming-context zonder mutatie. Een afzonderlijke kennispassage
blijft inhoudelijk reviewbaar in Review.

A: algemene _render_review_index krijgt een edit_structure-vlag; Vorming schakelt
die aan. Weinig markupverplaatsing, maar een Review-caller kan de editor opnieuw
activeren en de algemene renderer behoudt eigenaarschap van de werkplek.

B: verplaats de prozakoppenformulierrendering fysiek naar source_selection_ui_v1.
Review toont uitsluitend toestand en de gerichte eigenaarlink; de aparte boom-
handeling behoudt haar bestaande presentatie. De nieuwe presentatiefunctie
render_structure(console, account, document, conflict=False) consumeert uitsluitend
bestaande shapes; geen commandwrapper of domeinlogica.

| Criterium | A | B |
| --- | --- | --- |
| Eén eigenaar / cleanup | Vlag kan oude editor heractiveren | Prozaformulier alleen in Vorming |
| State/CAS/concurrency | Bestaand | Bestaand |
| Reads | Bestaande snapshotinputs | Bestaande snapshotinputs |
| Lokale wijziging / boomcompatibiliteit | Klein | Klein; apart boomformulier blijft |
| Bewijsbaarheid | Elke callsite moet juiste vlag hebben | Eén presentatie-eigenaar, oude ingang afwezig |

Gekozen: B. Twee werkelijke read-only kandidaatonderzoeken door de subagents
structure_candidate_a en structure_candidate_b onder dezelfde architectbrief;
geen onafhankelijke product-/veiligheidsacceptatie of cross-model-consensus.
Agree: implementatie is door de gebruiker toegewezen, geen extra akkoordpoort.
Architect-referentiebestanden konden via skills.read niet worden gelezen;
de gelezen hoofdskill en repositorycontracten blijven de gevolgde instructies.

## Implement — volgorde, bewijs en cleanup

Eerst de oude prozabevestigingsbediening verwijderen/verplaatsen; bestaande
helpers/fixtures volstaan, geen nieuwe infrastructuur. Daarna succes/conflict en
historische links naar dezelfde eigenaar. Directe POST/Python-ingangen blijven.

| Claim | Foutscenario | Kleinste controle |
| --- | --- | --- |
| Eén werkplek / GET read-only | Review behoudt checkbox/goedkeurkeuze; GET bevestigt stilzwijgend | HTTP en browser: oude lijst/detail, historische link, Vormingformulier, ongewijzigde objects/events na GET. |
| Exacte selectie / identiteit | Alle koppen of kennis worden bevestigd | Formulier-IDs, subset-POST, verse PG-read/refresh/herstart; bronhash en niet-geselecteerde rows gelijk. |
| Huidige guards | Stale/outsider/published kan muteren | Bestaande endpoint/kernel weigert; state/events gelijk. A08 concurrency/rollback hergebruiken. |
| Geen extra deep reads | Nieuwe werkplek leest corpus opnieuw | Dezelfde fixture/counters vóór/na; één bestaande snapshotread en fragmentread voor documenttaak. |
| Bereikbaarheid | Mobiele titel/keyboard/succes/conflict verdwaalt | Werkelijke browser op 390/1440, bron openen, selectie, POST, refresh, terug naar Review. |

Verwijderd: prozakoppenbatchformulier uit Review, losse ongeldige prozakop-
goedkeurkeuze. Verplaatst: bestaande velden, POST-opvolging, stale-weergave.
Behouden: alle kernelcommands, routes, rechten, opslag, boombevestiging en de
nog gekoppelde verschillende C1-correctie-/afwijs-/relatiehandelingen in Review.

## Scrap en overdracht

Stop/herscope als deze verplaatsing een losse relatie-/hersteltransactie,
post-reviewrecht of lifecyclewijziging vereist. Geen workarounds rond C1.
Rollback is code/presentatie bij dezelfde command; geen datareset of herstel
van oude goedkeuring. B3 sluit #859/#857 niet af. Geen automatische volgende slice,
merge, deployment of productiemutatie. Overige B-handelingen en daarna C blijven open.

Werkelijk uitgevoerde controles, exacte head en resterende onzekerheden worden
in de PR vastgelegd; testcode of dit bewijsplan zijn geen uitgevoerde acceptatie.

## Lokaal uitgevoerd vóór publicatie

- De nieuwe HTTP/PG-proef faalt op ongewijzigde main in een geïsoleerde worktree
  doordat het oude Review-koppenformulier nog aanwezig is; zij slaagt op de
  wijziging, inclusief exacte subset, echte opgeslagen state, stale/duplicate,
  onbevoegd/gepubliceerd zonder writes, procesherstart, GET zonder mutatie,
  leesvergelijking en behouden boomnavigatie. De generieke named-reviewerweigering
  blijft HTTP 400; geen statuscode gewijzigd om de test passend te maken.
- 52 bestaande gerichte proeven slagen; de nieuwe native proef slaagt afzonderlijk.
- Werkelijk Chromium op 1440/390 px: bron openen, keyboard naar Vorming,
  expliciete selectie, bestaande POST, refresh en ongewijzigde bron/niet-geselecteerde
  objecten slagen. Zes synthetische screenshots; mobiel en desktop visueel bekeken.
- 38 karakterisatieproeven en 6 architectuur-invariantproeven slagen.
  Zeven goldenwijzigingen: zes alleen de eigenaarlink; één vervangt de ongeldige
  losse kopgoedkeurkeuze door de eigenaarlink. Geen CSS-/assetwijziging.
- Verplichte statische checks uitgevoerd. Volledige suite wordt met de bestaande
  vierpartities-runner uitgevoerd; definitieve resultaten staan in de PR.

Testomgeving: tijdelijke Python-venv/dependencies en uitgepakte Ubuntu PostgreSQL
16.15-binaries in /tmp op Debian 13. scripts/test_postgres.sh start de wegwerpserver
met PGBIN/LD_LIBRARY_PATH. Geen systeemdienst of productomgeving gewijzigd.
Het voorgeschreven installatiescript stopte eerst doordat sudo ontbreekt;
de uiteindelijke native uitvoering is dus wel lokaal mogelijk en niet als skip
gepresenteerd. Oude ongetrackte debug-testkopieën zijn buiten de repo bewaard
na een collectieconflict. De gewone volledige run is vervolgens voor de bestaande
complete vierpartities-uitvoering afgebroken; de afgebroken run telt niet als PASS.

De brede lokale collectie vond vervolgens verlies van q/page bij verplaatsing
vanuit een gefilterde Review-lijst. De bestaande regressie
test_task_back_link_keeps_selected_document_and_search bleef ongewijzigd:
de GET-overdracht en teruglink bewaren nu de bestaande tijdelijke filters.
De door die fout achterhaalde lokale partities zijn gestopt; zij gelden niet
als complete groene suite. De gerichte regressies worden opnieuw uitgevoerd
en de volledige definitieve head wordt in GitHub geverifieerd.
Na dit navigatieherstel slagen 59 gerichte proeven, inclusief die ongewijzigde
regressie, en 18 bestaande kaart-/bronregressies. De kaarttests onderscheiden nu
werkelijke kennisvoorstellen van structurele koppen: kennis behoudt de expliciete
goedkeurkeuze; koppen niet. Type-/bronweigering en de bestaande backendasserties
blijven behouden. Geen kernelregel aangepast.

De volledige GitHub-suites vonden nog afwijkingen in drie presentatie-/bewijscategorieën:
de bestaande koppenlabeltelling was niet overgenomen, twee navigatieasserties
verwachtte de oude Review-bestemming en de bronhergebruikproef veronderstelde
dat ook een koppenlijst kennisbronblokken reconstrueert. Vorming gebruikt nu
dezelfde fast_title-projectie met hetzelfde open-koppenaantal. De ongewijzigde
bestaande tellertest slaagt. De navigatieproef controleert expliciet de ene
eigenaarlink en de afwezigheid van de oude. De readproef gebruikt een werkelijk
niet-leeg koppenformulier en vereist exact nul reconstructies; voor alle andere
Review-taken blijft exact één reconstructie per request vereist. Opgeslagen
toestand en gelijke HTML blijven gecontroleerd. De gerichte set: 64 PASS;
de afzonderlijke structure-readproef eveneens PASS. Geen kernel-/opslagwijziging.
