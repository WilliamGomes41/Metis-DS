# #840 — gecontroleerde workeroverdracht

William heeft analyse en implementatie expliciet toegewezen. Basis: main na gemergde #844 (`ff13c33`).

Change class: A
Promise: Een technische workerstop wordt binnen dezelfde geautoriseerde opdracht automatisch overgenomen; resultaten, plan, bron, harde deadline en budget blijven behouden, echte grenzen blokkeren expliciet.
Proof: Native PostgreSQL: overdracht en nieuwe kernel zonder tweede start, uitsluitend open taken, concurrerende claims, stale writes/activatie, intrekking/configuratie/deadline/budget en Bronselectieprojectie; volledige regressies.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Claim-, discovery- en checkpointgrenzen van SourceProcessingDispatcher en task-v1; processing_attempt blijft de duurzame opdracht.
Why local patching is insufficient: Een claim heeft nu geen lease en kan niet terug naar pending; een nieuwe poging zou deadline en budget herstarten.
Current authority/writer/reader map: workflow.processing_attempts blijft enige opdracht- en claimautoriteit. reserve_selection reserveert; source_processing_dispatch claimt/ontdekt; TaskCheckpointWriter checkpoint en overdracht; reextract_unpublished activeert met actuele claimcheck; record_task_failure stopt uitsluitend eigen claim. source_preparation_context en bounded_formation lezen bestaande input/views/plan/resultaten. Bronselectie/status/export zijn projecties; lokale/legacy paden behouden v1 en worden niet automatisch overgenomen.
Supported runtime topologies: Native PostgreSQL met meerdere workers/processen en herstart; legacy/lokale compatibiliteit zonder automatische overdracht. Geen process-memory autoriteit.
Persisted-state impact: Additieve versie source-dispatch-v2 in bestaande poging-JSON: tijdelijke token, lease, workergrens, claimnummer en vaste budgetdeadline. Bestaande attempt/command/revision/input/plan/resultaatidentiteiten blijven gelijk. Geen nieuwe tabel of backfill.
Compatibility/migration plan: Alleen nieuwe task-v1 startopdrachten voor source-bound-v3 HTML/PDF (geen beslisbomen) met compatibele workers krijgen v2; bestaande v1 blijft v1. Drain actieve workers vóór binarycutover. Oude dispatcher claimt geen v2-opdracht. Geen GET/startupmigratie.
Rollback/recovery plan: Stop nieuwe admission, drain v2-workers, behoud alle records en compatibele worker voor bestaande v2-opdrachten. Geen downgrade van tokens of reset van deadline/budget; verlopen opdrachten volgen bestaande menselijke herstelregels.
Cutover trigger: Native overdracht-/restart-/concurrentie-/fencing-/grensproeven en volledige verificatie groen, menselijke review; geen deploy in deze opdracht.
Cleanup/decommission criteria: Geen tweede dispatcher/opdrachtregister. v1 blijft alleen bestaande legacycompatibiliteit; v2 uitsluitend bestaande opdracht met vervangbare claim.
Failure blast radius: Eén opdracht/document; laatst geldige resultaten blijven behouden, onzekere niet-gecommitte providercall kan na leaseverlies herhaald worden binnen het resterende absolute budget.
Adversarial proof matrix: Twee gelijktijdige claims, overdracht na taakcommit, crash en leaseexpiry, oude claim writes/activatie/failure, autorisatie-intrekking, configuratiewijziging, deadline en budget vóór nieuwe claim of volgende taak; geen tweede attempt/activatie, legacy ongewijzigd.
Lifecycle entity: WorkingRevision op één immutable SourceSnapshot, met gepinde verwerkingscontext, attempts/claims en taakresultaten.
Lifecycle transition: processing met bestaande opdracht en claim → technische stop/leaseverlies → dezelfde opdracht pending → nieuwe geautoriseerde claim → open taken → bestaande gezamenlijke eindpoort en één in_review-activatie.
Initial durable state: Eén WorkingRevision met bestaande bron-/extractie-/inputidentiteit, nul of meer geldige TaskResults, eventueel een bronviewref en gepind taakplan.
Trigger: Bestaande gebruikersstart; daarna dispatcher-discovery en technische overdracht tussen gecommitteerde taken, geen nieuwe gebruikersstart.
Authorization: Bestaande actor-/documentrechten en verwerkingsautorisatie worden bij reserveren, claimen, commit en activatie gecontroleerd; claimfencing en deadlines blijven bindend.
Validation: Actuele autorisatie/configuratie, source hash/version, documentgeneration en verwachte revisie, claimtoken en lease, oorspronkelijke expires_at en vaste budgetdeadline; bestaande bron/input/plan/resultaatintegriteit.
Mutable entities: De bestaande opdrachtstatus en tijdelijke workerclaim/lease, vastgepinde budgetdeadline en compacte voortgang. Geen wijziging van bestaande resultaat-/planidentiteit.
Immutable entities: Bronbytes, extractieversies, inputartefacten, bronviews, geldige resultaatversies en auditbewijs, oorspronkelijke plannen en bestaande canonieke publicaties.
Workflow state before: processing, of de bestaande expliciete fout-/blokkeerstatus met hervatbaar bewijs.
Workflow state after: processing zolang werk ontbreekt; bij fout de bestaande passende fout-/blokkeerstatus; na geslaagde eindpoort in_review volgens de bestaande lifecycle, nooit automatisch ready_for_publication.
Release state before: De bestaande release(s), of geen release.
Release state after: Ongewijzigd; taakopslag en hervatten besluiten niet tot publicatie, supersession of withdrawal.
Serving state before: De huidige publicatieregistry bepaalt welke release actief is.
Serving state after: Ongewijzigd; geen taakcommit, restart of backfill activeert een release.
Expected API result: Bestaande geldige start-/hervatantwoorden met duurzame taakvoortgang; expliciete bestaande conflict-/autorisatie-/integriteitsfouten waar van toepassing; leesverzoeken blijven beschikbaar en muteren geen workflowstaat.
Expected UI result: Bezig bij actuele claim, wacht op uitvoering bij overdracht; echte grens geblokkeerd met reden en benodigde menselijke handeling. Hervatten niet tijdens automatische overdracht.
Failure result: Laatst geldige commits blijven behouden; gefaalde taaktransactie heeft geen gedeeltelijk geldig resultaat of voortgang; activatiefout verandert Review/publicatie niet.
Restart result: Discovery vindt pending of verlopen lease uit PostgreSQL. Nieuwe claim behoudt opdracht-ID, deadline, budget en alle gecommitte bron/plan/resultaatverwijzingen.
Recovery result: Geen nieuwe poging of verlenging door workeroverdracht. Harde deadline, ingetrokken autorisatie/configuratie of budget blokkeren via bestaande stop- en herstelregels.
Legacy-data result: Bestaande v1/lokale opdrachten blijven op oorspronkelijke route. Nieuwe native task-v1 starts krijgen v2. Geen automatische promotie van historische completed-events.
Required black-box scenario: Ontvang bron, start eenmaal, commit eerste taak, draag worker gecontroleerd over, herstart kernel en laat dispatcher zonder nieuwe reserve-oproep open taken afmaken. Oude claim kan niet schrijven/activeren, eerste resultaat blijft identiek en slechts één activatie. Herhaal met leaseverlies en echte grenzen.
Explicit non-goals: Geen verlenging harde deadline of totaalbudget, geen nieuwe herstelautorisatie, geen klinische eindacceptatie (#837), provider exactly-once, merge, deployment of productiemigratie.

## Ontwerp en bewijsgrenzen

Twee vormen door dezelfde agent afgewogen: (A) nieuwe jobtabel boven attempts; (B) bestaande attempt als geautoriseerde opdracht, vervangbare v2-workerclaim eronder. B behoudt één eigenaar en voorkomt dubbele deadline-/retryadministratie. A is afgewezen vanwege tweede statusautoriteit en migratiekosten zonder benodigde domeinwinst.

Gebruik: reserve_source_selection eenmaal; dispatcher claimt met lease; TaskCheckpointWriter bewaart elke geldige taak; tussen taken kan hij dezelfde opdracht naar pending teruggeven. Geen activation bij overdracht. Volgende claim leest dezelfde input/views/plan/resultaten.

Budget: de bestaande totale formation-looptijd (limits.total) wordt bij de eerste modeltaak als absolute deadline vastgelegd, begrensd door expires_at. Workerwissel, downtime en onzekere externe calls zetten die klok niet terug. Dit is conservatief: wachttijd telt mee. Er wordt geen nieuw kostenbudget of ongeautoriseerde verlenging ingevoerd.

|Gegeven|Producent / consument|Opslag en geldigheid|
|---|---|---|
|Opdracht/revisie/start/deadline|reservering / alle workers|bestaande processing_attempt, onveranderd bij overdracht|
|Token/lease/workergrens|claim / protected writes en activatie|dezelfde poging, vervangen onder documentrijlock|
|Bron/input/views/plan/resultaten|bestaande voorbereiding / volgende worker|bestaande immutable workflowrecords|
|Budgetdeadline|eerste modeltaak / volgende taken en claims|dezelfde poging, nooit opnieuw gestart|
|Rechten/configuratie|actuele kernel / iedere claim en beschermde mutatie|nooit uit broncache als bevoegdheid gelezen|

Verificatie volgt de echte native opslaggrens, inclusief concurrency, restart, rollback/fencing en gebruikersprojectie. Geen wijzigingen aan publicatie/serving of kandidaatmaker. Implementatie is expliciet geautoriseerd.

Alternatieve semantische modes, beslisbomen en legacy houden v1: zij hebben niet het task-v1 bron-/plan-/resultaatcontract waarop automatische overdracht steunt. Een tijdelijke ContextVar geeft uitsluitend het stop-signaal van de huidige uitvoerder door; opdracht/claim/budget blijven uitsluitend PostgreSQL-autoriteit.

## Concrete grenzen

Een claim krijgt standaard 240 seconden tot de coöperatieve workergrens; de lease verloopt uiterlijk 180 seconden later (voldoende voor de bestaande begrensde modelcall van maximaal 120 seconden plus commitruimte), nooit later dan de harde opdrachtdeadline. De worker draagt alleen tussen taken over en alleen na een geslaagde taakcommit. Een shutdown-signaal gebruikt dezelfde grens. Gecrashte uitvoerders worden pas na leaseverlies overgenomen; een niet-gecommitte call kan worden herhaald. De eerste modeltaak pint de absolute formation-budgetdeadline; lokale monotone budgetcontrole blijft daarnaast gelden. Er is geen nieuwe beleidsbeslissing over langere verwerking.

Classificatie/ontwerp zijn vóór productiecode vastgelegd en issue #840 is op basis van de expliciete toewijzing en het concrete contract getrieerd naar ready-for-agent. De aanvullende skillreferenties voor architectuur en contextbewijs waren via de provider niet beschikbaar; de hoofdskills en repositorycontracten zijn wel gelezen. Geen onafhankelijk-agentreview geclaimd.

De uiteindelijke surface-pass begrenst bovendien de modeltaakallowance door de actuele workerlease, naast de harde opdrachtdeadline. Voor iedere taak wordt ook de resterende lease met 5 seconden commitruimte toegepast. Een bijna verlopen lease kan de reeds vastgelegde voorbereiding zonder modelcall teruggeven. Daarmee krijgt een late taak geen verse modellooptijd voorbij de eigendomsgrens. Een gerichte grensproef controleert de aangeboden harde uitvoeringsdeadline en de leasegebonden taakallowance. Dit begrenst lokale uitvoerders; het garandeert geen annulering bij de externe provider of globale exactly-once uitvoering.

## Lange voorbereiding en leasebehoud

Een PDF-extractie heeft al een toegestane eigen looptijd tot 1.200 seconden. Het vast begrenzen van de hele uitvoering op de eerste workerlease zou deze bestaande route ten onrechte inkorten. Daarom blijft de extractie-/opdrachtdeadline de oorspronkelijke expires_at. De actieve worker bevestigt iedere 30 seconden zijn huidige token via dezelfde korte SQL-grens en houdt zijn lease maximaal 180 seconden vooruit geldig, steeds begrensd door de oorspronkelijke opdracht- en budgetdeadline. De technische workergrens blijft vast: na een taakcommit kan de worker pending teruggeven. Per modeltaak blijft de actuele leaseallowance met commitruimte bindend.

De heartbeat is een wegwerptimer, geen tweede statusautoriteit. Hij kan een verlopen of vervangen token niet herstellen, eindigt bij overdracht/stop en voert zelf geen modelwerk of activatie uit. Procesdood stopt de timer; discovery kan de achtergebleven lease overnemen. De thread ververst geen budget of gebruikersautorisatie en mag bij ingetrokken rechten alleen de geaccepteerde opdracht blokkeren. De proeven voegen lange voorbereiding, threadopruiming en verlopen/vervangen heartbeatfencing toe.
