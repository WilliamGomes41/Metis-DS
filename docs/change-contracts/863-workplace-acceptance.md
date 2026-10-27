# Integrale acceptatie van domeinwerkplekken — #863

Change class: B
Promise: De bestaande werkplekken en historische ingangen ontsluiten dezelfde actuele bron, passage en opdracht zonder tweede editor of duurzame UI-toestand.
Proof: Gecombineerde native HTTP/PG- en browsermatrix, route/storage-inventaris, gelijke-fixture-lees/schrijfvergelijking en expliciete menselijke acceptatiegrens.
Touches lifecycle invariants: no
Rewrite risk: none

Part of #857. Geïntegreerde onderzoeksbasis: main
`7adbac56f17ae9fd0e278248240f04093beab00c`, na #875/#862.
Projectbaseline vóór productwijzigingen: `efed882c8f2bef850ea2aff47d744214b83131c8`;
`728b6a9d582819392ee0c2b3d6253ce0857428e3` voegt alleen het #858-contract toe.
Deze opdracht is expliciet gegeven; #862 is gesloten en #863 is na scopecontrole
als ready-for-agent gemarkeerd. Geen merge, deployment of productiemutatie.

## Ground → Sketch → Agree

De bestaande owners uit #857 en de contracten #859–#862 blijven leidend.
Vorming bezit de editors; Review de oordelen; Inzicht diagnose/export;
Publicatie verklaart gereedheid en gebruikt de bestaande publicatieopdracht.
PG-workflowcommands/CAS en het publicatieregister blijven duurzame autoriteit.
Deze acceptatie introduceert geen domeinovergang. Fixtures gebruiken bestaande
commands en geïsoleerde testdatabases; geen nieuwe productwriter of kandidaatmaker.

Twee vormen zijn beoordeeld door de hoofdagent en een aparte read-only
ontwerpanalyse (zelfde model, geen multi-modelclaim):

| Vorm | Afweging |
| --- | --- |
| Bestaande native/browserproeven hergebruiken, gerichte regressies en één integrale inventaris toevoegen | Gekozen: bestaande echte commands/fixtures, traceerbaar bewijs, geen nieuwe runner of autoriteit |
| Nieuwe monolithische acceptatierunner met eigen toestands-/taakmodel | Verworpen: duplicatie van bestaande fixtures/projecties; grotere kans op een proef die andere regels dan het product gebruikt |

Gebruik voor historische links: opgeslagen Review-URL met snapshot/object en
review_revision → bestaande redirect → dezelfde Vorming-editor → Review-retour
met dezelfde oorspronkelijke revisie. De actuele editorreader blijft de bron
van command-CAS en bevoegdheid. Een oude revisie wordt nooit approval of writer.

De inventaris vond een concreet restant: de historische context-/repairredirects
lieten review_revision vallen; repair verloor ook de expliciete repair_kind.
De twee native regressies volgen de echte redirects en controleren identiteit,
editorsoort, retour en onveranderde objects/envelopes/bindings/events.
Alleen expliciet ondersteunde verliesbare queryvelden worden doorgegeven;
geen algemene queryforwarder, extra endpoint, reader of opslag.

Mutable state: uitsluitend bestaande verliesbare href-/formcontext.
Immutable: bron, object-ID/-versie, bindings/events, attempts, grants/accountings,
publicatie/serving en alle opgeslagen domeinregels. GET blijft zonder domeinwrite.
Directe Python/HTTP-commands en historische bewijslezers blijven ondersteund.
De stateful Class B-overlay is niet van toepassing: deze patch verandert geen
durable command of toestandsovergang. Agree volgt de expliciete uitvoeropdracht.

## Acceptatiematrix en bewijsgrenzen

Alle rijen worden op dezelfde geïntegreerde codebasis getoetst. Een bestaande
testnaam is een uitvoerbare controle, geen geslaagde uitslag; uitvoering en SHA
staan in de PR en het bewijsartefact.

| Claim / I-invariant | Bestaande native proef |
| --- | --- |
| Eén start/hervatwerkplek; partial review en GET start niets (I03/04/09) | tests/test_formation_workplace.py; tests/test_review_formation_problems.py |
| Broncontext, uitsluiting, structuur, kandidaat-/graafherstel alleen Vorming (I04/06/12) | tests/test_source_context_review_ui_v1.py; tests/test_source_accountability_v1.py; tests/test_heading_workplace_v1.py; tests/test_formation_repair_workplace.py; tests/test_decision_graph_chain.py |
| Pagina-afhandeling/grants met bestaande rechten en grenzen (I07/08) | tests/test_source_recovery_workplace.py |
| Persoonlijk eerste/tweede/wachten/klaar/geen werk, exacte actorpopulaties (I10) | tests/test_personal_review_workboard.py; tests/test_content_review_workplace.py |
| Batch exact per object, stale/duplicate/unauthorized en atomic failure (I06/07) | tests/test_content_review_workplace.py; tests/test_review_batch_atomic_postgres.py |
| Herstelretour en historische bookmarks behouden context zonder approvaloverdracht (I06/09) | tests/test_content_review_workplace.py; tests/test_workplace_acceptance_863.py |
| Diagnose/exportrechten en Publicatie-vervolgwerk blijven bereikbaar (I04/07) | tests/test_document_diagnosis_redesign_v1.py; tests/test_page_domain_boundaries_v1.py |
| Interrupt/resume/herstart en immutable published work (I02/06/07) | tests/test_source_resume_acceptance.py; tests/test_published_working_revision_immutable_2b_postgres.py; tests/test_review_batch_atomic_postgres.py |
| Begrensde reads en gelijke-fixture-vergelijking (I11) | tests/test_personal_review_workboard.py; tests/test_review_document_read_performance.py; evidence/863/read_write_comparison.py |

De bestaande Chromiumproeven gebruiken desktop/mobiel/toetsenbord en echte
HTTP/PG-commands. Zij bewijzen mechanische bereikbaarheid en statebehoud.
Zij bewijzen geen spontane taakherkenning door een mens of minder afhakers.
De bekeken desktop-Review- en mobiele Vorming-uitvoer staat in
evidence/863/desktop-review.png en evidence/863/mobile-formation.png.

## Inventaris en Scrap

Statische vergelijking van letterlijke GET/POST/add_api_route-declaraties en
gewijzigde productopslag/schema/config wordt bewaard in evidence/863/inventory.json.
De native geïnstalleerde route-inventaris toetst daarnaast unieke commandowners;
AST-declaraties alleen bewijzen dat niet.

Reeds verwijderd: operations_console_app._review_count/_review_layers_html/
_review_task_card/_review_task_dashboard; review_workboard._projected_document_dashboard/
_review_activity_status/_work_queue_link/_work_summary; deterministic_review_repair._review_url.
Pagina-afhandeling is verplaatst naar source_selection_ui_v1._source_pages_html.
Geen aanvullend bewezen dode helper aangetroffen. _coverage_panel en
_processing_diagnostics_html blijven historische bewijslezers met bestaande tests;
zij worden niet als tweede actieve werkplek ingezet of blind verwijderd.
De historische redirects blijven als navigatie bestaan; hun contextverlies wordt
hersteld. Er komt geen tweede actieve editor, store, writer of commandrouter.

De vergelijking van de historische Python-landing met de huidige landing draait
boven dezelfde huidige native backend en dezelfde vijf documenten/actor.
Dit is geen vergelijking van twee historische deployments. De instrumentatie
telt bestaande readeraanroepen, drie bestaande writegrenzen en SQL/JSON via
de bestaande performance_scope; envelopes/objecthistorie/bindings/events van
dezelfde vijf documenten worden ook vergeleken.
Het ruwe checkoutinterval bevat eveneens parallel performance-/diagnosewerk;
de verschillen worden niet volledig aan #857 toegeschreven.

Lokale uitvoering (Python 3.13.5 / PostgreSQL 17.11): baseline/current respectievelijk
13/12 SQL-aanroepen, 13/12 verbindingen, 219835/219823 JSON-bytes. De accountlijst
daalt van één naar nul; summaries/enrichment/batchobjecten/bindings/events blijven
ieder één aanroep, source_fragments vijf. Deep snapshot_objects en de drie
getelde writegrenzen blijven nul; de durable snapshot blijft gelijk. Zie
evidence/863/read-write.json. Dit is geen snelheids- of productievolumeclaim.

Rollback van deze slice zet alleen de querycontextreparatie en bewijsbestanden
terug. Alle al opgeslagen besluiten/revisies/bronnen blijven behouden.

## Menselijke acceptatie: open

Nog vereist: een representatieve reviewer vindt zonder uitleg de eigen opdracht,
begint, legt een oordeel vast en herkent eigen afronding. Leg versie/omgeving,
datum, de vier waarnemingen en concrete problemen vast; geen verzonnen observaties.
Een verzoek om bestaand bewijs is aan de opdrachtgever gesteld. Zonder dat bewijs
blijven #863 en parent #857 open, ook als alle technische controles slagen.
De opdrachtgever heeft bevestigd dat zulke observaties nog niet beschikbaar zijn.
