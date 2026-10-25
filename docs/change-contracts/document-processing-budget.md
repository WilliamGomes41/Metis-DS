# Documentbudget — vervolg op #840 / PR #845

De gebruiker heeft het voorstel expliciet goedgekeurd: één documentopdracht, vaste begrenzing, tijdelijke workers en één finale activatie. Voorlopig venster vier uur; aantallen en per-call input/output begrenzen modelwerk, geen verzonnen eurotarief.

Change class: A
Promise: Eén expliciete Starten-opdracht kan een volledig compatibel document binnen een vooraf vastgelegd documentvenster en modelwerkbudget automatisch verwerken; workerwissels vernieuwen geen autorisatie, tijd of calls en alleen de gezamenlijke eindpoort activeert het resultaat.
Proof: Native PostgreSQL, één start voor 130 synthetische taken met 70 s virtuele forming per taak (>2,5 uur), meerdere workers/nieuwe kernel zonder nieuwe reserve; exacte eerdere resultaten, één activatie; echte document-/worker-/callgrenzen, concurrency, crash, revocatie, configuratie, legacy en readonly HTTP-projecties.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: De betekenis van de nieuwe-format opdrachtdeadline tegenover technische worker- en modelcalllimieten, in de bestaande processing_attempt-autoriteit.
Why local patching is insufficient: Alleen total=900 verhogen helpt niet: expires_at beëindigt de huidige opdracht na 30 minuten. Een nieuw attempt per worker zou opnieuw deadline/budget/herstelregels autoriseren.
Current authority/writer/reader map: workflow.processing_attempts blijft eigenaar van één gebruikersopdracht. source_selection.reserve_selection reserveert het gepinde documentbudget; processing_document_budget_v1 definieert het versiecontract; worker_handover claim/discover/renew beheert alleen tijdelijke eigendom; TaskCheckpointWriter reserveert calls atomair en bewaart taak/plan/resultaten; bounded_formation en pre_review_semantic respecteren de aparte grenzen; reextract_unpublished blijft enige finale activatiegrens met actuele rechten/revisie/claim. Retry/recovery en published-state-eigenaren blijven gelijk. UI, compacte summaries, bestaande checkpoints/diagnostiek/export projecteren budgetgegevens maar verlenen geen bevoegdheid. Directe legacy CLI/ingest, v1/v2-claims, beslisbomen en alternatieve semantische routes worden niet opgewaardeerd.
Supported runtime topologies: Native PostgreSQL met meerdere workers/processen en herstart; legacy/lokale compatibiliteit zonder automatische overdracht. Geen process-memory autoriteit.
Persisted-state impact: Additief document_budget met versie, venster 14.400 s, totaal maximaal tweemaal het aantal gepinde taken aan calls, maximaal 16.384 outputtokens per call, bestaande inputlimiet 2.000.000 bytes, calls_reserved en planbinding; nieuwe dispatch source-dispatch-v3 met worker_expires_at. expires_at is voor dit nieuwe formaat de vaste documenteinddatum. limits.attempt blijft de technische workergrens (standaard 1.800 s), limits.total de bestaande modelcallgrens. Geen nieuwe tabel.
Compatibility/migration plan: Op aparte branch boven PR #845. Nieuwe expliciete Bronselectie-starts vereisen task-v1, source-bound-v3 HTML/PDF en METIS_DOCUMENT_PROCESSING_BUDGET=v1. Onbekende configuratie weigeren. Bestaande opdrachten worden nooit verlengd of gemigreerd; zonder schakelaar blijven v1/v2 en hun bestaande grenzen intact. Oude workers claimen v3 niet. Compatibele readers/writers uitrollen na drain; geen GET/startupbackfill.
Rollback/recovery plan: Sluit nieuwe admission of schakel nieuw documentbudget uit voor nieuwe starts, behoud alle budget-/claim-/plan-/resultaatrecords en gebruik compatibele v3-workers voor bestaande opdrachten. Geen downgrade/reset van lopende autorisatie. Na echte uitputting is een nieuwe expliciete menselijke opdracht of bestaande herstelgrant vereist. Geen destructieve migratie.
Cutover trigger: Alle native grenzen en de volledige collectie groen, review en merge van afhankelijkheid #845, vervolgens expliciet geautoriseerde uitrol met beide featurevlaggen. Deze opdracht deployt niet.
Cleanup/decommission criteria: Geen tweede jobregister, prijsservice of nieuwe kandidaatmaker. Bestaande 900/1.800-s policy blijft voor legacy. Het documentformaat gebruikt voor forming geen worker-lokale resetbare 900-s budgetklok; oude paden behouden die klok.
Failure blast radius: Eén opdracht/document; laatst geldige resultaten blijven behouden, onzekere niet-gecommitte providercall kan na leaseverlies herhaald worden binnen het resterende absolute budget.
Adversarial proof matrix: Documentwindow/workerlimiet/calllimiet onafhankelijk; callreservering over crash en concurrentie; oude claim schrijft/reserveert/activeert niet; 130 taken met één start en >30 min totaallooptijd; geen reset bij nieuwe claim; plan/budgetcorruptie; intrekking/configuratie; oorspronkelijke resultaten en exacte bronbinding; lege/voltooide taakset met nul resterende calls mag finale poort doorlopen; legacy ongewijzigd.
Lifecycle entity: WorkingRevision op één immutable SourceSnapshot, met gepinde verwerkingscontext, attempts/claims en taakresultaten.
Lifecycle transition: processing onder één nieuw expliciet geautoriseerd documentbudget → tijdelijke workers op dezelfde opdracht → volledige geldige taakset → één gezamenlijke eindcontrole → bestaande in_review-activatie; werkelijke grensoverschrijding blijft blocked met menselijke vervolghandeling.
Initial durable state: Een ongepubliceerde WorkingRevision met gepinde bron/revisie en één expliciete nieuwe opdracht, documentbudget vastgelegd vóór werk; nul of meer compatibele taakresultaten, geen nieuw publicatierecht.
Trigger: Eén geautoriseerde Starten-POST/reserve_source_selection onder expliciet ingeschakelde documentpolicy; daarna alleen technische overdracht/ontdekking binnen dezelfde opdracht.
Authorization: De gebruiker heeft één volledige documentopdracht met begrensd totaalvenster goedgekeurd. Rol, revisie, bron, model/configuratie en claim blijven bij claim, protected write en activatie gecontroleerd. Het nieuwe venster is een expliciete nieuwe beleidsautorisatie, geen stilzwijgende verlenging van oude opdrachten.
Validation: Volledig versiecontract en vaste deadline = started_at + 14.400 s; calls-budget = 2 maal immutable geplande taakset, nooit opnieuw tellen of terugbetalen na onzekere I/O; worker_expires_at per claim begrensd door documentdeadline, limits.attempt en maximaal 1.800 s; dezelfde bestaande bron/input/plan/resultaat- en finale poortcontroles.
Mutable entities: Bestaande opdracht/claim/cursor/summary; modelcallreservering in dezelfde bestaande pogingrij. Budgetbeleid, start en documentdeadline worden na reservering niet gewijzigd.
Immutable entities: Bronbytes, extractieversies, inputartefacten, bronviews, geldige resultaatversies en auditbewijs, oorspronkelijke plannen en bestaande canonieke publicaties.
Workflow state before: processing, of de bestaande expliciete fout-/blokkeerstatus met hervatbaar bewijs.
Workflow state after: processing zolang werk ontbreekt; bij fout de bestaande passende fout-/blokkeerstatus; na geslaagde eindpoort in_review volgens de bestaande lifecycle, nooit automatisch ready_for_publication.
Release state before: De bestaande release(s), of geen release.
Release state after: Ongewijzigd; taakopslag en hervatten besluiten niet tot publicatie, supersession of withdrawal.
Serving state before: De huidige publicatieregistry bepaalt welke release actief is.
Serving state after: Ongewijzigd; geen taakcommit, restart of backfill activeert een release.
Expected API result: Bestaande start levert duurzaam één geaccepteerde opdracht, inclusief vaste budgetprojectie. Technische overdracht gebruikt dezelfde command/attempt-ID. Echte quota/deadlines geven expliciete blokkade zonder publicatie of gedeeltelijke activatie.
Expected UI result: Bronselectie vermeldt het documentvenster en een totaalmaximum van tweemaal het aantal geplande taken aan modelcalls; tijdens gewone overdracht geen Hervatten-knop. Toont oorspronkelijke documenteinddatum en gereserveerd/maximum aantal calls. Geen schatting van eurokosten zonder tariefcatalogus.
Failure result: Laatste geldige TaskResults blijven behouden. Een mislukte call kan één gereserveerde call verbruiken; onzekere requests worden niet gratis. Fencing voorkomt oude writes/activatie; geen gedeeltelijk resultaat wordt gepubliceerd.
Restart result: Dezelfde opdrachtdeadline, calls_reserved, plan, fasecursor en resultaten worden uit PostgreSQL gelezen. Een nieuwe claim krijgt uitsluitend een nieuwe technische workergrens; geen tweede Starten of budgetreset.
Recovery result: Technische workerlimiet/leaseverlies kan overname veroorzaken zolang documentautorisatie en budget gelden. Echte document-/calluitputting, rol/configuratie- of inhoudelijke blokkade blijft menselijke herstelstap onder bestaande caps/grants.
Legacy-data result: Geen interpretatiewijziging van bestaande attempts. v2 blijft 900 s forming binnen oorspronkelijke harde deadline; nieuwe v3 vereist expliciete featurevlag en volledig budgetrecord. Ontbrekend/corrupt v3-record faalt expliciet.
Required black-box scenario: GIVEN één native bron met 130 geplande taken WHEN één expliciete start met 70 s virtuele forming per taak en meerdere technische workerwissels/nieuwe kernel THEN alle taken binnen 4 uur, dezelfde attempt en documentdeadline, één providerrequest per succesvolle taak en één finale activatie; oude claims kunnen niet activeren en echte budgetgrenzen blijven blokkeren.
Explicit non-goals: Geen merge/deploy, echte betaalde modelcalls, geldbedragen/prijsgaranties zonder tarieven, klinische Smetten-acceptatie (#837), algemene jobframeworks, schema-backfill of verlenging van oude opdrachten.


## Ontwerpkeuze en uitvoering

Dezelfde agent vergelijkt A: per worker een nieuw attempt met verse budgetten, en B: dezelfde bestaande opdracht met aparte vaste documentpolicy en tijdelijke workerlimieten. B behoudt één autorisatie-/retry-eigenaar, past bij de bestaande checkpointtoegang en vereist geen tweede tabel of reconciler. A is afgewezen: reset tijd/calls en kan meer menselijke starts of impliciete autorisatie veroorzaken. Een geldbedrag als harde financiële cap vereist een afzonderlijk gepinde prijscatalogus; die bestaat hier niet. Deze begrensde uitbreiding garandeert aantallen en outputplafond, niet een europrijs.

Gebruik: de bestaande expliciete Starten reserveert onder de featurevlag het budget; na bronvoorbereiding pint de bestaande planner de taakset en daarmee het callmaximum. De gebruiker autoriseert vooraf deze formule. Iedere modelrequest reserveert atomair één call vóór externe I/O; fouten/crashes geven geen automatische terugbetaling. Een volgende worker leest dezelfde budget- en fasegegevens. Een technische workergrens mag geen geslaagde taakcommit terugdraaien of documentautorisatie vernieuwen.

| Gegeven | Producent / consument | Eigenaar / geldigheid |
|---|---|---|
| documentvenster en productiecontract | expliciete reservering / alle uitvoerders | dezelfde processing_attempt, vast 4 uur inclusief wachten |
| workergrens, token en lease | claim / protected writes en activatie | dezelfde poging, maximaal oorspronkelijke technische limiet per claim |
| maximaal aantal calls | gepind plan / modelrequest | twee per geplande taak, immutable planbinding |
| calls_reserved | beschermde modelrequest / volgende claims | atomair in dezelfde pogingrij, nooit gereset na crash |
| bron, planning en resultaten | bestaande producers / vervolgworkers | bestaande immutable workflowrecords |
| status, budget en audit | authority / UI en diagnostiek | kleine projecties, geen bevoegdheid of nieuwe inhoudsbron |

Volgorde: bestaande mechanismen behouden; noodzakelijke versiecontracten en callbegrenzing toevoegen; consumers/HTTP-projectie aansluiten; native rood/groen-, tijd-/quota-/restart-/concurrentie-/fencingproeven, afzonderlijke surface-pass en volledige repositorychecks. Geen nieuwe infrastructuur of deployment. Het 130-takenbewijs is een beleids-/opslagproef met een virtuele klok, geen claim dat een live provider of de echte Smetten-richtlijn klinisch is geaccepteerd.


## Concrete begrenzing

Het modelcallmaximum is een totaalbudget van 2 × het aantal geplande taken. De oorspronkelijke initial/recovery-passages blijven apart begrensd; onzekere requests na procesdood kunnen opnieuw worden uitgevoerd maar verbruiken steeds een nieuwe call uit ditzelfde totaal. Dit garandeert geen exactly-once provideruitvoering of twee feitelijke externe requests per individueel bronbereik bij herhaalde crashes. Een worker krijgt nooit meer dan dertig minuten, ook als de oude globale configuratie een uur zou toestaan; kortere geconfigureerde workerlimieten blijven gelden. De afzonderlijke output- en inputlimieten begrenzen per-call blootstelling; er wordt geen geldbedrag afgeleid zonder tarieven.

De native proef van 130 taken × 70 s is al groen: één start, dezelfde documenteinddatum, meerdere claims/nieuwe kernel en één activatie. De eerste versie liet de nieuwe muterende budgetteller ten onrechte meetellen in de domeinbaseline; de correctie vergelijkt de vaste policy en neemt actuele counters bij activatie uit de authority over. Alle bestaande token-/revisie-/rolcontroles blijven aanwezig. Werkelijke procesdood bewaart ook de gereserveerde maar onzekere tweede call: de opvolger eindigt op vier reserveringen voor drie succesvolle taken, zonder terugbetaling of nieuwe gebruikersstart.

## Voor brede verificatie

De gerichte native set slaagt met 88 tests; aanvullende grenzen en HTTP-compatibiliteit slagen met drie tests. De 130-takenproef meet 9.100 s virtuele forming, één geautoriseerde start en één definitieve activatie. De echte SIGKILL-/nieuwe-procesproef behoudt de onzekere callreservering en oorspronkelijke resultaatbytes. Budget-/worker-/callgrenzen, een concurrente laatste callslot, intrekking/configuratie, nul callruimte bij reeds complete resultaten, ontbrekende/corrupte budgetdata, uitgeschakelde nieuwe admission en legacy/mode-compatibiliteit zijn gericht getoetst. De volledige collectie en afzonderlijke mutatiecontrole volgen op de vastgezette runtime; deze tussentijdse bevindingen zijn geen claim over productie of klinische acceptatie.
