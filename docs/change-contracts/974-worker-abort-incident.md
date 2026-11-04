# Incident #974: Review opslaan zonder afronding; Vorming en Review openen traag

Issue: #974
Change class: C
Rewrite risk: none
Promise: De projectlead kan alleen-lezen Azure-bewijs verzamelen voor de exitreden van onafgesloten Review-verzoeken en de kosten van trage reads. Een tweede commando verzamelt mogelijke opgeslagen review-events in een tijdvenster; het bepaalt zonder exacte commandokoppeling geen commit of rollback.
Proof: `tests/test_check_review_save_outcome_postgres.py` (PostgreSQL 16, begrensde alleen-lezen uitvoer zonder ids/details, onbekende uitkomst bij zowel lege als gevulde vensters); `tests/test_collect_worker_abort_evidence.py` (nagebootste az; invoergrenzen en alle zes secties). Historische lokale bron- en schedulingproeven: `evidence/worker-abort-974/diagnosis-summary.json`; dit zijn geen live Azure- of HTTP-reproducties.
Touches lifecycle invariants: no

Deze slice voegt diagnose toe. Productiegedrag, schema, autorisatie en lifecycle veranderen niet. Fixes volgen apart; het Vorming-leespad is Class B.

## Waarneming (aangeleverde telemetrie, 2026-11-04)

| Onderdeel | Vastgesteld |
|---|---|
| Review opslaan | 5 × `POST /review` zonder `request_finished`; telkens 39–43 s later een nieuw workerproces |
| Vorming openen | tot 49 s; één verzoek: 945 aanroepen van de bronbloklezer, 25,8 s fasetijd |
| Review openen | tot 14,9 s; één documentverzoek: 31,4 MB `db_json_bytes` |
| `review_disposition_conflict` | HTTP 400 na 3,87 s; de formulierkeuzes ontbreken in de capture |

## Oorzaakanalyse (codebasis `main` 1f9deea)

### 1. Review opslaan: exitreden nog onbekend

De startup zet geen `--timeout`; Gunicorn gebruikt normaal 30 s, tenzij runtimeconfiguratie zoals `GUNICORN_CMD_ARGS` dit wijzigt. Het werkelijk ingestelde timeout- en workeraantal moet uit de runtime blijken. Een nieuwe worker na 39–43 s past bij een watchdog en opstarttijd, maar bewijst dit niet en sluit OOM of een andere stopreden niet uit.

`review_post` is synchroon en draait in een threadpool. Er bestaat echter ook een direct blokkerend pad: bij 'Goedkeuren na correctie' kan `StructuredRepairRequired` leiden naar de **async** `structured_repair_handler` in `src/review/deterministic_review_repair_v1.py`. Die roept `account_for` en `render_repair` synchroon aan; dit omvat bron- en databasewerk op de eventloop.

Dat schedulingprobleem is lokaal gereproduceerd met de echte handler/renderer en 923 bronfragmenten, maar een fake auth/DB/Blob-readmodel: heartbeatgat 1,3443 s; hetzelfde werk buiten de hoofdloop 0,0220 s; HTML byte voor byte gelijk. Dit bewijst de blokkade van dat codepad, **niet** dat de vijf productie-POSTs die route namen of door Gunicorn werden gestopt.

Ontbrekende `request_running`-heartbeats zijn aanwijzingen, geen bewijs van eventloopblokkade of timeout. Nodig: de daadwerkelijke exitregel, runtime-instellingen en zo mogelijk de stack van de betrokken worker. `WORKER TIMEOUT` bewijst een watchdog-ingreep; `SIGKILL ... Perhaps out of memory?` bewijst een harde stop, niet zelfstandig OOM. Ook logdekking, meetvenster en ingestievertraging controleren.

De reviewmutatie wordt atomair gecommit binnen de bestaande PostgreSQL-transactie. Een processtop vóór commit laat die transactie terugrollen; na commit blijft de beslissing bewaard. Een tijdvenster met of zonder review-events identificeert de betrokken opdracht niet. Controleer exact command/interaction, objectversie, bindings en opgeslagen beslissing voordat een individuele actie als opgeslagen of teruggedraaid wordt aangemerkt.

### 2. Vorming openen: vergelijkingswerk bevestigd met de echte bron

`formation_problems_v1.collect` gebruikt `stored_extraction(envelope)`: een gewone fragmentlijst in plaats van de bestaande voorbereide `SourceFragments`-drager. Daardoor vergelijkt `_read_source_blocks` bij een cache-hit opnieuw de volledige geneste bron. Getallen worden via `_SourceNumber.__eq__` vergeleken.

Het echte document heeft **923 evidence-fragmenten**. De productie-counters zijn: **944 invoervergelijkingen, 943 hergebruikte reconstructies, twee opgebouwde weergaven**. De 945 faseregistraties betekenen geen 945 volledige reconstructies. Een synthetische extrapolatie naar circa 4.000 fragmenten is niet nodig om dit incident te onderbouwen.

Lokale differentiële proef: 10 warme toegangen met dezelfde profiler geven 115.580 numerieke vergelijkingen op de gewone lijst en nul via de voorbereide blokindex; de bronblokken blijven gelijk. Voorbereiding heeft zelf kosten; dit is geen volledige HTTP- of Azure-snelheidsmeting.

### 3. Review openen: breed bron-/documentpad aangetoond

`db_json_bytes` is een requesttotaal en wijst bytes niet aan een query toe. De faseboom is wel al onderzocht: in het documentverzoek van 14,89 s valt **5,26 s binnen `source_views_read_records`** en **4,22 s binnen `processing_status`**. Inclusieve fasetijden niet optellen bij bovenliggende fasen.

`read_review_document` haalt brongegevens zonder objectselectie op; de recordlezer kiest dan alle bronblokken, fragmenten en lidmaatschappen. Bij open vorming wordt bovendien de bestaande vormingsinvoer gecontroleerd. De opslagvoorbereiding leest eveneens brongegevens zonder objectselectie. Een passage-GET gebruikt wel een afhankelijkheidsvenster. Dit verklaart een concreet duur pad; welke query welk deel van de 31,4 MB levert blijft open.

### `review_disposition_conflict`

Dit is de domeinweigering van een ongeldige combinatie volgens `ALLOWED_FINAL_BY_SUITABILITY`. De daadwerkelijke formulierwaarden zijn niet bekend. Het gemeten verzoek eindigt na 3,87 s met HTTP 400; bronrecords lezen/valideren/hydrateren neemt circa 2,94 s daarvan in. Dat verklaart een groot deel van de wachttijd vóór de weigering. De generieke melding ontstaat doordat deze foutcode geen eigen gebruikersmelding heeft. Dit verzoek staat los van de vijf onafgesloten POSTs.

## Gegevensregels en beperkingen

Ruwe uitvoer blijft privé, buiten de repo, in een nieuwe map met modus 700 en bestanden onder umask 077. Alleen beoordeelde technische samenvattingen worden overgedragen; geen bronteksten, ruwe provider-uitvoer, secrets of persoonsgegevens. De databasecontrole toont geen document-/object-ids, actoren of eventdetails. Live KQL-validatie blijft open. Het ontbreken van een logtabel of resultaat is ontbrekend bewijs, geen vastgestelde oorzaak.

## Vervolg

Het toegevoegde oplossingsontwerp met synthetische prototypes staat in [974-solution-plan.md](974-solution-plan.md). Het is geen geactiveerd uitvoeringsprogramma; de hieronder genoemde bewijsgrenzen blijven leidend.

1. Exitreden, betrokken handeling en opslagresultaat van de vijf POSTs vaststellen. Timeout verhogen vervangt dit onderzoek niet.
2. De bestaande voorbereide bronrepresentatie doorgeven aan Vorming, met behoud van alle integriteitscontroles en context (aparte Class B-fix).
3. Brede Review-bron-/documentreads begrenzen vanuit het gemeten pad. Aanvullende byte-attributie per query alleen waar die nog een keuze bepaalt.
