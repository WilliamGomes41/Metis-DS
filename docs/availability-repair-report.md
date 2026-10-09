# Beschikbaarheidsreparatie A26, A04/A05 en A02

De gevraagde implementatie staat op de lokale branch `fix/availability-a26-a04-a05-a02`. Er is geen merge, deployment, productieverwerking of betaalde modelaanroep uitgevoerd. Het lokale herstel is via geïnstalleerde HTTP-routes en deterministische providerstubs bewezen. Volledig herstel op de productieopslagtopologie en visuele browserwerking zijn nog niet bewezen; dit rapport is daarom geen vrijgaveadvies.

## Revisies en behoud van bestaand werk

- Basis: `0204045d1adc5e7a89e551844e3bf9751715e096` (actuele `origin/main`, gelijk aan de auditbasis).
- Basistree: `27d35705976751b6e89c2b2e45c53186804b1b07`.
- Implementatierevisie: `7f641625eb6e5a886981c55ed9f1416ccc4d422e`.
- Eindbranch: implementatierevisie plus uitsluitend commentaarverduidelijking, dit rapport en bewijsbestanden; de exacte eind-SHA staat in het opleverbericht en is opvraagbaar met `git rev-parse HEAD`.
- Afzonderlijke worktree gebruikt; de bestaande checkout en eerder werk zijn behouden.
- Eerst gelezen: AGENTS.md, Metis Engineer-profiel, execution contract, continuous development, lifecycle VSA, abstraction boundaries, domeinbeschrijving, relevante brongebonden ADR en actuele aanroepketens. Class A / Rewrite risk high vooraf gespecificeerd in `docs/change-contracts/availability-repair.md`. Vaardigheden diagnosing-bugs en domain-first-architecture toegepast.

## Exacte wijzigingen per bevinding

| Bevinding | Wijziging | Bewijs en grens |
|---|---|---|
| A26 | `OperationsConsole.receive_source` registreert uitsluitend geverifieerde onveranderlijke bytes en een lege werkrevisie. `ingest(_receive_only=True)` gebruikt de bestaande autorisatie, metadata-, command- en opslagcontracten, een korte registratiestap en CAS. `_durable_receipt` bevestigt bestand plus lokale registratie met fsync van bestanden en directories; de PostgreSQL-transactie blijft daar de registratieautoriteit. Een identieke command-retry bevestigt ook na een eerdere fsync-fout dezelfde registratie. HTTP `/ingest` retourneert daarna 303 naar het geselecteerde document in Bronselectie. | Ontvangst roept geen extractor/provider aan. Bestand en registratie blijven bestaan na restart en latere providerfout. Opslag-/fsync-fouten geven geen succesvolle ontvangst. Idempotentie geldt voor dezelfde command_id en inhoud; de echte uploadvorm genereert die ID. De bestaande synchrone kernel/CLI-ingest blijft beschikbaar. |
| A26 herstelopdracht | `source_selection_v1.reserve_selection` reserveert een expliciete duurzame poging met actor, bronidentiteit, revisie, command_id, lease en bestaande herstelbudgetten. `/source-selection/start` reserveert in een thread en voert daarna `execute_source_selection` in een thread uit. Een proceslokale task-set houdt alleen wegwerpbare uitvoerhandles; opgeslagen attempts zijn de autoriteit. | Dubbele klik/opdracht geeft één poging en één provideraanroep. Refresh start niets. Na verloren worker en lease-expiry wordt Hervatten mogelijk; een oude worker kan geen resultaat activeren. Gedeeltelijk technisch geslaagde vorming hervat alleen open bronbereiken en behoudt kandidatenidentiteit. |
| A04 | `decision_review_ui_v1` ontvangt de opvolger via `asyncio.to_thread(... receive_only=True)`; provider/extractie begint pas met de aparte Bronselectie-opdracht. Ook synchrone kernelcompatibiliteit verwerkt pas na verlaten van de ouderregistratielock. | Baseline-extractie draaide op de eventloop; herstelobservatie is `(eventloop=False, lockdepth=0, workflow_transaction=False)`. Gezondheids- én echte gebruikersroutes antwoorden tijdens de geblokkeerde provider/extractor. |
| A05 | `decision_successor_v1.execute` verifieert bronbytes buiten de registratielock; korte registratie hercontroleert actor, ouderrevisie, reviewbeleid, hash en bronversie. De opgeslagen `successor_guard` wordt bij reservering én activatie opnieuw gecontroleerd. Dezelfde command is idempotent; een tweede ongepubliceerde opvolger voor dezelfde ouder/policy/klasse wordt geweigerd. Activatie gebruikt de bestaande transacties en revision/lease fences. | Een gelijktijdige ouderbeleidswijziging weigert stale activatie; ouderobjecten en reviewarbeid blijven gelijk. Een onafhankelijke schrijver voltooit terwijl extractie wacht. Lokale lockmeting hieronder; native PostgreSQL-lockbewijs ontbreekt. |
| A02 | `knowledge_materialisation_v1.source_reconstruction_scope(reuse_existing=True)` hergebruikt afgeleide bronblokken per gelijke broninput en heading-view binnen één berekening/GET. De scopes van publication_readiness, review work item/room, console GET-middleware en geïnstalleerde document-statusmiddleware delen de context. Broninput wordt op inhoud gecontroleerd; besluiten en bevoegdheden worden opnieuw berekend. | Zeven echte leesroutes hebben maximaal twee reconstructies per bronrepresentatie; HTML met/zonder hergebruik is gelijk. Volgende aanvragen zien gewijzigde broninput, echte bestandscorruptie en nieuwe reviewbesluiten. Publicatiebevoegdheid wordt opnieuw gecontroleerd. Geen globale bron-/besluitcache. |

A02-leesroutes: `/publish`, `/review`, `/review?task=mine`, `/review?task=disposition`, `/review?task=individual`, kandidaatdetail via `/review?document=…&object=…`, bronpassagedetail via `/review/bronpassage?document=…&object=…`.

## Hoofdindeling en Bronselectie

`operations_console_app`, `console_navigation_simplify_v1` en de vijfkoloms home-CSS maken de hoofdvolgorde exact: **Inleveren → Bronselectie → Review → Publicatie → Documenten**. Bronselectie is een eigen hoofdblok, geen extra tussenstap. Ontvangst redirect direct naar dit blok met het nieuwe document geselecteerd; de geselecteerde kaart staat vooraan.

`source_selection_ui_v1` toont titel, bestandsnaam, bronversie, byteomvang en beschikbare opgeslagen fragmentomvang. Statussen zijn nog niet gestart, bezig, voltooid, onderbroken en mislukt. Acties zijn Starten, Voortgang bekijken, Hervatten en Resultaat bekijken; Naar Review verschijnt bij inhoudelijk beoordeelbare kandidaten. Tijdens verwerking staan fase, verstreken tijd en een onzekere resterende schatting. Na verwerking staan kandidaat-, bronpassage- en blokkadeaantallen. Een technisch geslaagde poging met onvolledige bronvorming wordt als onderbroken gepresenteerd, met volledige bronverwerking afzonderlijk vermeld.

Tijdschatting gebruikt minstens drie geregistreerde volledige ingest-pogingen met vergelijkbare documentklasse, inhoudstype, byteomvang (factor 0,5–2) en verwerkingconfiguratie (modus/model/Docling/deployment). Gedeeltelijke pogingen en resumes tellen niet mee. De grove bandbreedte is gebaseerd op gemeten seconden per byte, met brede marges rond de mediaan. Zonder voldoende vergelijkbare metingen staat er onvoldoende gegevens. Na overschrijden van de gemeten bovenkant wordt geen schijnbare nul-ETA getoond. Bytes voorspellen broncomplexiteit beperkt; dit is geen SLA.

## Rood/groen bewijs

Alle fixtures zijn synthetisch; netwerkproviderstubs gebruiken vaste antwoorden, barriers en gecontroleerde klokken.

| Controle | Basis (rood) | Herstel (groen) |
|---|---|---|
| A26 originele auditprobe | Bestand/document opgeslagen en health 200, maar ontvangst keert niet terug zolang provider wacht. `UPLOAD_RECEIPT_WAITS_FOR_FULL_FORMATION`. | Echte `/ingest` keert terug zonder providerstart; aparte start, restart en latere fout behouden bytes en registratie. |
| A04/A05 originele auditprobe | Opvolgerextractie op eventloop, store lock vast, health wacht. Gewone ingest-controle blijft beschikbaar. | Extractie/provider buiten eventloop, store lock en workflowtransactie; gelijktijdige gebruikersreads en onafhankelijke schrijver slagen. |
| A02 originele auditprobe | `/publish` met 20 bronrecords: 23 reconstructies (3 selection + 20 full). | `/publish` met 80 bronrecords: 2 reconstructies (1 selection + 1 full). Geen afleiding van productie-latentie uit deze verschillende fixtures. |
| Zelfde hersteltests tegen basis en branch | 3 fouten, 6 geslaagd, 2 native skips: ontvangst, opvolger en `/publish` falen. | 9 geslaagd, 2 native skips in dezelfde selectie. |

`locks-green.json`: 44 lock-ingangen, langste lokale hold **0,059033 s**, totale hold inclusief geneste metingen 0,194083 s; extractor buiten lock; gelijktijdige health plus onafhankelijke accountschrijfopdracht voltooid in 0,013313 s. Dit zijn lokale fixturemetingen, geen hard productieplafond en geen PostgreSQL-rowlockmeting. Providers wachten gecontroleerd; beschikbaarheid wordt niet uitsluitend met health aangetoond.

## Testcommando’s en resultaten

Vanuit de repository, Python 3.12 met de bestaande dependencyomgeving:

```bash
.venv/bin/python -m pytest -q tests/test_availability_repair.py
.venv/bin/python -m pytest -q tests/test_availability_repair.py -k "receipt_without or a04_a05 or a02_installed"
.venv/bin/python -m pytest -q tests/test_architecture_invariants.py tests/test_decision_successors.py tests/test_successor_release_cutover_v1.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/validate_change_contract.py --text-file docs/change-contracts/availability-repair.md
.venv/bin/python scripts/check_architecture_boundaries.py
.venv/bin/python scripts/repository_preflight.py
.venv/bin/python scripts/release_control_preflight.py --base origin/main
METIS_PROBE_REPO=/absolute/path/to/base .venv/bin/python evidence/availability/probe_upload_response_lifetime.py
METIS_PROBE_REPO=/absolute/path/to/base .venv/bin/python evidence/availability/probe_successor_availability.py
METIS_PROBE_REPO=/absolute/path/to/base .venv/bin/python evidence/availability/probe_publish_reconstructions.py
.venv/bin/python evidence/availability/measure_locks.py
```

- Hersteltests: **19 geslaagd, 5 overgeslagen** (ontbrekende native PostgreSQL-test-DSN).
- Architectuur/lifecycle/opvolger-suite: **8 geslaagd, 6 overgeslagen**.
- Brede eindrun: **3.072 geslaagd, 207 overgeslagen, 4 fouten** in 232,03 s; alle vier fouten ook op de basis gereproduceerd.
- Contract-, architectuur-, repository- en releasepreflight: PASS; preflightmetadata is geen gedragstest. De path-mapper markeert beschikbaarheid ten onrechte n.v.t.; het expliciete routebewijs hierboven blijft vereist.
- Vier bestaande brede-suitefouten zijn afzonderlijk ook op exact de basis gereproduceerd (`baseline-environment.log`): parent-process transport worker teardown, HTTPS-SNI bij DNS-rebinding, redirect rebind en metadata-redirect. Ze zijn niet onder deze reparatie veranderd. De basiscontrole: 4 fouten, 18 gedeselecteerd. De volledige foutdetails staan in de logs.

De originele ontvangst/opvolgerprobes blijven bewust baselineprobes: ze wachten op de oude impliciete verwerking en zijn niet het groene contract van de nieuwe tweestappenroute. Voor groen gebruik de nieuwe HTTP-regressietests. Het publicatieprobe blijft op beide versies bruikbaar. Bewijsbestanden staan onder `evidence/availability/`; uitsluitend whitespace aan regeleinden is genormaliseerd.

## Adversariële controle en resterende beperkingen

Afzonderlijk gecontroleerd: dubbele command versus andere command met hetzelfde opvolgerdoel; stale ouderpolicy/revisie/hash/version fences; autorisatie vóór opdracht en opnieuw vóór activatie; verloren worker/expired lease; technisch succes met onvolledige vorming; hervatten alleen open ranges; nul kandidaten met wel behouden bronpassages; fsync-fout na registratie met identieke retry; cache omzeilen met dezelfde HTML-uitkomst; nieuwe aanvraag met bron- of reviewwijziging. Het bestaande gedeelde atomic-replace/rollbackmechanisme is behouden; fsync is beperkt tot de nieuwe ontvangstbevestiging zodat reviewrollbackcontracten niet veranderen.

1. Geen native PostgreSQL-testserver/DSN beschikbaar. De vijf nieuwe tests zijn ook voor die backend geparametriseerd, maar overgeslagen. Daardoor zijn rowlockduur, cross-process CAS/concurrentie en database-restart niet bewezen. Een lokale console-restart is bewezen, geen stroomuitval van machine of database.
2. Chromium ontbreekt; downloaden kon niet worden afgerond. `ui-proof.cjs` is aanwezig maar `ui-proof.log` toont de browserstartfout. HTTP/DOM-tests controleren hoofdvolgorde, acties, redirect en automatische documentselectie; drie inline scripts zijn syntactisch gecontroleerd met Node (`inline-script-syntax.json`). Screenshots, responsive overflow en daadwerkelijke browser-JavaScript zijn nog niet visueel bewezen.
3. Workeruitvoering is proceslokaal; na restart start geen ongevraagde modelaanroep. Een verloren poging wordt pas na de bestaande begrensde lease hervatbaar, via expliciete Hervatten-opdracht. Dit is geen automatische queue-redelivery.
4. De cache voorkomt herhaalde bronreconstructie, maar bronvergelijking en alle inhouds-/reviewcontroles blijven per berekening uitgevoerd. Er is geen bewijs dat elke andere productieoorzaak van traagheid/502 hiermee is opgelost.
5. Vier bestaande omgeving-/transportfouten blijven zichtbaar in de brede suite. Geen vrijgave op alleen groene gerichte tests.
6. Automatische goedkeuringscontrole weigerde het pushen van de private branch naar GitHub wegens ontbrekende expliciete toestemming voor overdracht naar die bestemming. Geen omweg geprobeerd; branch en commits zijn lokaal behouden.

Volgens `docs/agents/lifecycle-vsa.md`: “A relevant item with FAIL, UNKNOWN, or NOT TESTED means the slice is NOT DONE.” De implementatie en lokale bewijzen zijn opgeleverd, maar het volledige vrijgavebewijs vereist nog native PostgreSQL en browsercontrole. Geen productieherverwerking of versoepeling van publicatievoorwaarden uitgevoerd.
