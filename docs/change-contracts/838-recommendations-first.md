# #838 — aanbevelingen eerst, duurzaam taakplan

William heeft uitvoering expliciet toegewezen: “Start 838”. Basis: main na gemergde #842.

Change class: A
Promise: Een richtlijn krijgt vóór de eerste modelaanroep een duurzaam brongebonden taakplan: mogelijke aanbevelingen met hun bestaande volledige taakcontext eerst, daarna alle overige inhoud; hervatten behoudt plan en geldige resultaten.
Proof: Onafhankelijke Smetten-referentie; aanbeveling op bronpositie 43 als eerste gepland; exacte bronbereikdekking/context; native PostgreSQL-plancommit, rollback, concurrente eerste schrijvers, herstart en hervatten zonder herhaalde geldige taken; diagnostiek/export.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Alleen prioriteitsplanning en het bewaren/teruglezen van één immutable plan per bestaande formation_context; geen nieuwe resultaatidentiteit of workflowautoriteit.
Why local patching is insufficient: Alleen sorteren in geheugen verliest de gekozen volgorde na herstart en maakt meerdere workers afhankelijk van hun lokale plannerversie.
Current authority/writer/reader map: De bestaande PostgreSQL-workflowstore blijft eigenaar. bounded_formation.execute maakt/leest het plan vóór providerwerk via TaskCheckpointWriter; FormationTaskStore bewaart/leest immutable planrecords onder bestaande document-/attempt-/claimlock. Alle v3-console-/dispatcher-/CLI-paden lopen via dezelfde execute. Legacy checkpointcallbacks krijgen een diagnostische planprojectie; nieuwe task-v1-contexten krijgen native duurzaamheid. diagnostic, replay/MCP en evidence-export lezen opgeslagen plan en eigen taakobservaties; GET muteert niets. Bestaande kandidaatmaker en activatie zijn ongewijzigd.
Supported runtime topologies: Native PostgreSQL met meerdere console-/workerprocessen en procesherstarts. Correctheid steunt op transacties, constraints en fencing, niet op gedeeld Python-geheugen. Tijdens uitrol mogen oude writers alleen expliciet als legacy gemarkeerde contexten behandelen; nieuwe contexten vereisen compatibele binaries.
Persisted-state impact: Additieve migration 022, formation_task_plans met context_id als unieke FK, payload/hash en geen bronfragmentkopie. Poging bewaart een kleine planref; resultaatkeys, bron en publicatie onveranderd.
Compatibility/migration plan: Eerst schema 022, daarna compatibele workers. Bestaande context zonder plan krijgt bij de eerstvolgende geautoriseerde verwerking een plan vóór providerwerk; geen GET/startup/backfill. Bestaande exacte resultaten blijven geldig en worden afgetrokken. Bestaand plan wordt nooit opnieuw uit de huidige groepering afgeleid. Legacy diagnostiek zonder plan blijft expliciet leesbaar.
Rollback/recovery plan: Bewaar tabel en plannen, schakel nieuwe admission zo nodig uit en behoud plan-lezende binary. Een binary van vóór #838 bewaart wel resultaten maar garandeert geen gepinde prioriteit en is daarom geen ondersteunde workerrollback voor deze contexten. Geen down-migratie of historische verwijdering.
Cutover trigger: Schema 022 en alle actieve workers plan-compatibel; native restart-/claim-/dekking-/referentieproeven groen; menselijke review en CI vóór merge. Geen productiecutover in deze opdracht.
Cleanup/decommission criteria: Geen dubbele plannerautoriteit; opgeslagen plan is leidend. Legacy diagnostiek blijft leesbaar. Geen oude plan-/resultaatrecords verwijderen.
Failure blast radius: Eén verwerkingscontext; falende/ontbrekende/corrupte gepinde planning stopt vóór modelwerk zonder geldige resultaten of bron te wijzigen.
Adversarial proof matrix: Plan corrupt/missend/verkeerde bron; twee eerste plancommits; rollback vóór commit; claimveroudering; resume na nieuwe groepering; geldige oude resultaten; scope/uitzondering/tabelverwijzing behouden; onbekende aanbeveling blijft in restdekking; mogelijke aanbeveling wordt niet automatisch geselecteerd.
Lifecycle entity: WorkingRevision op één immutable SourceSnapshot, met gepinde verwerkingscontext, attempts/claims en taakresultaten.
Lifecycle transition: processing met geautoriseerde context → processing met duurzaam taakplan → bestaande taakverwerking/hervatting en ongewijzigde gezamenlijke eindpoort → bestaande definitieve in_review-activatie.
Initial durable state: Geautoriseerde richtlijncontext met gepinde bron/revisie/semantisch contract, nul of meer geldige taakresultaten en eventueel een bestaand taakplan.
Trigger: Bestaand toegestaan start-/hervatcommando, claimverwerving en taakcheckpoint binnen de bestaande opdracht.
Authorization: Bestaande actor-/documentrechten en verwerkingsautorisatie worden bij reserveren, claimen, commit en activatie gecontroleerd; claimfencing en deadlines blijven bindend.
Validation: Planversie/hash, context- en exacte inputbinding; volledige oorspronkelijke taakbereiken/context; bestaande lokale en gezamenlijke bronvalidatie blijft bindend.
Mutable entities: Bestaande poging/claim en voortgang; alleen eenmaal toevoegen van een immutable contextplan onder bestaande beschermde transactie.
Immutable entities: Bronbytes, vastgelegde input/extractieversies en gecommitteerde resultaat-/auditbewijzen; alle bestaande PublicationReleases en hun canonieke inhoud.
Workflow state before: processing, of de bestaande expliciete fout-/blokkeerstatus met hervatbaar bewijs.
Workflow state after: processing zolang werk ontbreekt; bij fout de bestaande passende fout-/blokkeerstatus; na geslaagde eindpoort in_review volgens de bestaande lifecycle, nooit automatisch ready_for_publication.
Release state before: De bestaande release(s), of geen release.
Release state after: Ongewijzigd; taakopslag en hervatten besluiten niet tot publicatie, supersession of withdrawal.
Serving state before: De huidige publicatieregistry bepaalt welke release actief is.
Serving state after: Ongewijzigd; geen taakcommit, restart of backfill activeert een release.
Expected API result: Bestaande geldige start-/hervatantwoorden met duurzame taakvoortgang; expliciete bestaande conflict-/autorisatie-/integriteitsfouten waar van toepassing; leesverzoeken blijven beschikbaar en muteren geen workflowstaat.
Expected UI result: Bronselectie toont compacte voortgang uit gecommitteerde resultaten; document en overzicht blijven tijdens checkpoints open; Review verschijnt pas volgens de bestaande voltooide verwerkingsgates.
Failure result: Laatst geldige commits blijven behouden; gefaalde taaktransactie heeft geen gedeeltelijk geldig resultaat of voortgang; activatiefout verandert Review/publicatie niet.
Restart result: Hetzelfde plan/hash en dezelfde geldige taakresultaten worden uit PostgreSQL gelezen; alleen ontbrekende of expliciet afgewezen bronbereiken worden verwerkt.
Recovery result: Alleen expliciet toegestaan resterend of gericht ongeldig werk wordt gepland; geen nieuwe curatorbeslissing, publicatiebeslissing of impliciete budgetverlenging.
Legacy-data result: Geen historische herschrijving. Contexten zonder plan krijgen dat uitsluitend op geautoriseerde verwerking; oude resultaten blijven op hun eigen exacte identiteit herbruikbaar.
Required black-box scenario: Ontvang richtlijn met algemene tekst vóór mogelijke aanbeveling plus scope/uitzondering/tabel. Reserveer en start; eerste providerrequest is aanbevelingstaak met context en plan is al gecommit. Onderbreek na eerste resultaat, herstart console/worker, wijzig lokale groeperingslimiet en hervat. Plan/hash blijven gelijk, geldige taak wordt niet herhaald, overige bron blijft gedekt, bestaande eindpoort bepaalt activatie.
Explicit non-goals: Geen nieuwe aanbevelingstoelating of automatische selectie/review; geen budgetverlenging, workerhandover (#840), brede cache (#839), live modelkosten of integrale klinische eindacceptatie (#837). Geen merge/deployment.

## Ontwerpkeuze en gebruik

Dezelfde agent vergelijkt twee vormen: (A) bij iedere poging opnieuw sorteren en een diagnostische kopie bewaren; (B) één immutable plan per bestaande verwerkingscontext in dezelfde workflowstore. B is gekozen: stabiel bij herstart, één eigenaar, geen groeiende planwrite per checkpoint. A is eenvoudiger maar bewijst geen duurzame volgorde.

Gebruik: `load_task_plan()` geeft het gepinde plan of expliciet geen legacyplan; `retain_task_plan(plan)` commit vóór providerwerk en retourneert bij concurrentie het al geldige plan. Planvelden: versie, exacte source-blocks-hash, mogelijke aanbevelingsspans en compacte taakdescriptors met target_spans, source/evidence block-id's, source_order en priority. Planhash/contextref is audit, geen resultaatkey.

De planner hergebruikt `recommendation_coverage.inventory`; aanvullend kan een normatieve zin buiten een aanbevelingenhoofdstuk een mogelijke aanbeveling signaleren. Een tabelzin blijft slechts mogelijk, nooit een zelfstandig goedgekeurd object. Taakgroepering en referentiesluiting blijven bestaande verantwoordelijkheid. Binnen een taak blijven bronvolgorde, offsets en context behouden. De restplanning wordt per gepinde taak beperkt tot exact resterende bereiken, niet opnieuw gegroepeerd over andere taken.

| Context | Producent → consument | Eigenaar / geldigheid |
|---|---|---|
| bron/validatorinput | bestaande voorbereiding → planner | immutable inputref; exacte public blocks-hash |
| plan | planner → workers/hervatten/diagnostiek | workflow.formation_task_plans; één immutable versie per context |
| resultaat | bestaande provider/lokale validator → hervatten/eindpoort | bestaande taakrecordkey; prioriteit geen onderdeel |
| poging/claim/rechten | bestaande reservering → beschermde planwrite | actuele bestaande TaskCheckpointWriter._locked |
| geselecteerde aanbevelingen | bestaande gevalideerde voorstellen → diagnostiek | afzonderlijk geteld; inventaris is geen selectieautoriteit |

Volgorde: bestaande grenzen hergebruiken; alleen additieve plantabel en resolver toevoegen; planner aansluiten en relevante native regressies uitvoeren. Geen generieke nieuwe scheduler. Implementatie is geautoriseerd; geen extra akkoordmoment. Bij structurele tegenstrijdigheid wordt het ontwerp herzien.
