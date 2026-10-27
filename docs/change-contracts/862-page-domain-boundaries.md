# Eigenaarverwijzingen buiten de werkplekken — #862

Change class: B
Promise: Inzicht verklaart en toont bewijs; behandeling opent dezelfde bron of passage op de bestaande eigenaarwerkplek.
Proof: Geïnstalleerde PostgreSQL/HTTP- en browserroutes, formulierinventaris, exacte passage-/paginaverwijzingen en ongewijzigde toestand na GET.
Touches lifecycle invariants: no
Rewrite risk: none

Base main: `038b2ee79966b9e97377f2bf4a3d938f56080a75` (merge #874).
Uitsluitend #862 / PR 7 uit #857. #863 blijft de afzonderlijke projectacceptatie.

## Ground en Class B-programmaontwerp

`insight_v1.install_insight_routes.document_diagnosis` leest de bestaande
`processing_status`, envelope en `_read_current_objects`. Alleen toegewezen
reviewers krijgen passagecodes/-exports. Researchers krijgen verwerkingsinzage;
publisher-only houdt uitsluitend publicatiebewijs. De laatste poging en historische
exports blijven bewijs. `view_check.panel` bezit de bestaande expliciete weergavecontrole
en annulering; dat zijn geen bron- of kandidaatherstelopdrachten.

De diagnosefamilies linken nu allemaal naar dezelfde algemene herstellijst.
`processing_diagnostic_rows(objects)` projecteert al passage-ID, tekst en families
zonder I/O. Gebruik die capture voor concrete verwijzingen, niet als nieuwe taakstatus.
Een synthetisch `blocked-N` uit diagnostiek bewijst geen objectidentiteit: alleen
daadwerkelijk aanwezige IDs mogen een editorlink krijgen. Codes zonder familie
blijven zichtbaar als ongeclassificeerd; aantallen punten zijn geen handmatige taken.

`publish_readiness_ui_v1._blocker_view` stuurt bronafhandeling en inconsistente
afhandeling nog naar Review; herstel heeft geen verwijzing. Alleen de links wijzigen.
`PublicationReadinessMixin`/T9/T10 en de productie-override van `consider_publish`
blijven de bestaande leesautoriteit; `publish` en het publicatieregister blijven
schrijf-/servingautoriteit. Geen nieuwe gereedheidsbeslissing.

| Handeling / huidige → gewenste ingang | Bestaand lees-/commandpad en owner | Behouden / wijziging |
| --- | --- | --- |
| Diagnosefamilie → concrete kandidaat in Vorming | Inzicht-capture → `processing_diagnostic_rows`; GET `/source-selection` met document/object/task=repair → `render_repair`; POST `/review/resolve` → bestaande compound `submit_review_resolution` | Familie-uitleg/codes/counts behouden; identieke algemene links vervangen door concrete passages. Vorming leest actuele commandrevisie; link verleent geen approval |
| Onverantwoorde pagina in Inzicht → dezelfde pagina in Vorming | `_source_pages_html(editable=False/True)` over envelope/laatste diagnostic; POST `/inzicht/document/pagina-verantwoorden` → `account_source_page` | Bestaande editor blijft alleen Vorming; pagina-anchor vervangt generiek #paginas. Bronhash/findings/notitie/categorie en transactie blijven command-eigendom |
| Publicatie: bronafhandeling → Vorming | Bestaande `consider_publish`-resultaatcode → `/source-selection?document=S&task=disposition`; bestaande POST `/review/source-context` en `/review/source-exclusions` | Alleen verwijzing; de code geeft geen concrete passage-ID, dus geen ID verzinnen |
| Publicatie: herstel/inconsistente afhandeling → Vorming | Zelfde readiness-resultaat → bestaande task=repair-inventaris; bestaand herstelcommand | Geen statuswriter, geen endpoint of gatewijziging; onbekende technische blokkade blijft diagnose |
| Publicatie: ontbrekende eerste/tweede beoordeling → Review | Zelfde readiness-resultaat → `/review?document=S`; bestaande `/review`, batch-confirm, second-review POSTs | Rechten, onafhankelijkheid, CAS, exact-versiebinding en publicatievoorwaarden behouden |
| Herstelautorisatie | Vorming `source_recovery_controls`; POST `/tree/processing-recovery` → `authorize_processing_recovery` | Was al verplaatst in #871; geen formulier in Inzicht. Directe HTTP/Python-callers behouden; autorisatie start niets |

Runtime: `build_console_app` installeert de huidige werkbord-/Vorming-/Inzicht- en
Publicatierenderers boven `ReviewClosureConsole` en de bestaande PostgreSQL workflow-
mixins/FastBadge-compositie, met Durable/AzureAuthoritativePublicationConsole.
`_PostgresWorkflowReviewMixin` en workflow_transaction blijven de echte buitenste
commitgrens. Geen aanpassing van readers, writers, commandvalidatie of MRO.

Mutable state: uitsluitend verliesbare HTML/hrefs; geen nieuwe duurzame toestand.
Immutable: bronbytes/hash/versie, kandidaat-ID/-revisie, bindings/events, attempts,
accountings/grants, publicatie-/servingtoestand. Navigatie/refresh voert geen command uit.
Directe ondersteunde HTTP- en Pythoncommands en bestaande diagnostische legacy-GETs
blijven intact. Historische POST-namen onder `/review` of `/inzicht` zijn geen tweede
bewerkbare werkplek en worden niet hernoemd.

## Inventaris overige pagina's

Mijn werk (`operations_console_app.home`) biedt werkplektegels en logout, geen
broneditor. De geïnstalleerde persoonlijke Reviewlanding consumeert `next_href`
uitsluitend voor de beslisgraaf; een oude disposition-href in de interne work-item-
projectie is geen aangetoonde actieve Mijn werk-ingang. Geen adjacent routercleanup.
Documenten (`tree`) behoudt onderwerp-/klassebeheer en ongepubliceerd verwijderen:
dit zijn andere domeinhandelingen. Diagnose opent Inzicht, verwerking opent Vorming.
Inleveren (`ingest_post`) ontvangt de bron via `receive_source` en redirect naar Vorming;
geen start bij GET. `console_navigation_simplify_v1` verwijdert dubbele navigatiedeuren,
geen editor. Publicatie behoudt publiceren/intrekken en verklaart blockers zonder
herstel-/reviewformulier. Ondersteunde opvolger-/klassewijziging blijft buiten scope.

## Sketch → Agree

Gebruik: diagnose → open de benoemde passage in Vorming → daar verse bron/revisie
lezen → bestaand command. Bij paginadiagnose opent dezelfde document-ID plus pagina-
anchor de bestaande rij. Publicatie heeft alleen documentniveau-evidence en linkt
naar de juiste bestaande documenttaak, zonder fictieve object- of probleemidentiteit.

Twee echte afzonderlijke read-only analyses: `/root/design862_a` en
`/root/design862_b` (zelfde model, geen claim van verschillende modellen).
A: lokale compositie uit reeds gelezen inputs. B: `formation_problems.collect`
hergebruiken als gedeelde projectie voor Inzicht en Vorming. B zou extra object-,
binding-, extractie- en task-storelezingen en nieuwe rechtencoördinatie vereisen;
afgewezen wegens access-fit, scope en het verbod op een nieuwe taskreader in Inzicht.
A wint op locality, compatibiliteit en verifieerbaarheid; beide laten commands eigenaar.
Geen nieuwe datastructuur buiten tijdelijke lijsten/sets van bestaande dicts/IDs.
Agree: uitvoering door gebruiker opgedragen; geen extra toestemmingspoort.
Architect-hoofdskill gelezen; drie aanvullende reference-resources waren onbereikbaar.

| Context | Producent → consument / eigenaar | Geldigheid / ontbrekend |
| --- | --- | --- |
| Snapshot/object | Bestaande capture → eigenaar-GET / PostgreSQL | Exacte bestaande ID; ontbrekend geen gefabriceerde editorlink |
| Pagina | Laatste opgeslagen finding → Vormingrij / envelope | Zelfde document/paginanummer; owner hercontroleert actuele finding/sourcehash |
| Revisie/rechten | Verse owner-reader → bestaande POST / workflow | GET draagt geen toestemming of oude approval over; bestaande CAS blijft beslissen |
| Familie/aantallen | Diagnostische projectie → uitleg / verliesbaar | Geen onafhankelijke taken, prioriteitsautoriteit of probleemstatus |

## Implement → Scrap en bewijsplan

Eerst vervangen algemene foutieve verwijzingen; bestaande fundamenten volstaan.
Geen framework/router/cache toevoegen. Verwijder alleen vervangen rendercode;
compatibele commands/exports en gedeelde historische lezers blijven behouden.
Rollback: presentatie samen terugzetten, nooit opgeslagen besluiten of grants resetten.

Minimale proeven: twee geblokkeerde passages met verschillende families openen elk
hun eigen object in Vorming; ongeclassificeerd/ontbrekend ID levert geen fictieve taak;
pagina opent exacte rij; publicatiebronwerk opent Vorming terwijl beoordeling Review
blijft; browser desktop/mobiel/keyboard, export en rolgrenzen; GETs laten bron,
objecten/revisie/bindings/events/attempts gelijk. Bestaande commandtests bewaken guards.
Verplichte preflights, compile, boundaries, invariants en volledige pytest met echte PG.
Werkelijke uitslagen en exacte gecontroleerde SHA horen in de PR, niet als voorspelling.

Gerichte uitvoering: 117 HTTP/native/browsercontroles geslaagd (9 overige browser-
varianten in deze gerichte selectie uitgesteld naar de volledige suite); 64 aanvullende
inventaris-/complexiteits-/karakteriseringscontroles geslaagd. Chromium volgde beide
passages via toetsenbord op 1440/390px, dezelfde pagina-anchor en bestaande accounting/
grantcommands; screenshots bekeken. De eerste bestaande presentatieassertie faalde
terecht op de vervangen generieke familie-link en is vervangen door exacte ID-controle.
Geen goldens, rechten, domeinregels of complexiteitsdrempels aangepast.
De aanvullende context-skill proof-scenarios-resource was eveneens onbereikbaar;
de concrete native GET-/herstartvergelijking is wel werkelijk uitgevoerd.
Scrap: geen terugkerende afwijking van het gekozen lokale ontwerp; geen nieuwe
infrastructuur of tweede projectie-eigenaar nodig.

## Reviewherstel: publicatieverwijzingen moeten het werk tonen

Class B / Rewrite risk: none, gebaseerd op PR-head `13964dd` en main-base
`038b2ee`. Dit is stateless presentatie: geen lifecycle-, eligibility-,
publicatie-, autorisatie-, transactie- of opslagregel verandert.

Ground: `source_passage_review_incomplete` komt uit `source_closure` over alle
vereiste passages, inclusief kennisvoorstellen. `task=disposition` opent echter
bewust `render_source_accountability` met `source_only=True`; die lijst is geen
algemene lijst van publicatieblokkades. Een normaal `revise` levert bovendien
een T9 `review_repair_duties`-rij op, maar `_review_inventory(task='repair')`
gebruikte alleen de bronopvolging en reguliere reviewroute. De passage verdween
daardoor uit de lijst terwijl haar directe bestaande editor wel bereikbaar was.

Sketch (alternatieven door hoofdagent en afzonderlijke read-only ontwerpanalyse):

- A: brede bronblokkade naar de bestaande Vorming-documentpagina; bestaande
  herstellijst neemt ook de IDs uit `review_repair_duties` op. Geen extra I/O,
  endpoint, viewmodel of authority. Bestaande source-only-editor blijft intact.
- B: `considered`-objectqueues door het publicatieviewmodel voeren en afzonderlijke
  passage-/werkpleklinks renderen. Preciezer bij gemengd werk, maar meer interface-
  en rendersurface dan nodig voor deze twee aangetoonde fouten.

A gekozen op correctheid, locality, access-fit en behoud van bestaande interfaces.
Gebruik: Publicatie → Vorming-document → concrete bron-/kandidaatlink of Review;
Publicatie → herstellijst → dezelfde actuele passage in de bestaande editor.
Datavorm: één tijdelijke set van T9 object-IDs uit de reeds gelezen objectcapture;
alleen de selectie van de bestaande repair-presentatie gebruikt die set. Gewone
review-, bronuitsluitings- en historielijsten behouden hun classificatie.
Concurrente wijzigingen blijven onder bestaande verse owner-reads en command-CAS;
GET verleent geen bevoegdheid, sluit niets en schrijft niets. Alle duurzame state
blijft eigendom van de bestaande kernel/PG-commands. Geen stateful overlay nodig.
Agree: expliciete implementatieopdracht na review, geen extra akkoord vereist.

Bewijs vóór de fix: echte Publicatie-HTML → link → owner-GET mist geblokkeerde
kandidaten respectievelijk een normaal revisieverzoek. Regressies controleren de
bereikbaarheid van de juiste passage, uitsluiting van gewoon reviewwerk, rechten
en onveranderde objecten/revisie/bindings/events. De onafhankelijke reviewprobes
worden opnieuw uitgevoerd op de fix. Bestaande browserproeven bewaken de eerdere
diagnose- en pagina-anchorwijzigingen. PR-contractvelden worden afzonderlijk en
parseerbaar vastgelegd; eerdere lokale suiteclaims gelden uitsluitend voor hun
vermelde oude SHA. Nieuwe verificatie wordt apart gerapporteerd.

Scrap: geen nieuwe layer/helper/route of fallback. Rollback zet presentatie en
link samen terug; opgeslagen revisieverzoeken en besluiten blijven behouden.
