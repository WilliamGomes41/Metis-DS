# #839 — hergebruik bronrepresentaties en taakresultaten

William heeft analyse en implementatie expliciet toegewezen. Basis: main na gemergde #843 (`846f13a`).

Change class: A
Promise: Een nieuwe workerclaim hergebruikt geverifieerde duurzame bronviews en exact geldige taakresultaten, zonder ruwe herextractie, volledige bronreconstructie per taak of herberekening van het eerdere totaalvoorstel; alleen noodzakelijk resterend bronwerk krijgt modelcalls.
Proof: Native PostgreSQL en echte nieuwe worker/processen; verbied extractor en reconstructie na voorbereidingscommit, wijzig/verwijder/corrumpeer verwijzingen, bewijs gelijke bron/mapping/resultaathashes en providerrequests uitsluitend voor open werk; behoud expliciete herextractie, fencing en één finale gezamenlijke poort. Meet reconstructie/hash/copy-aanroepen en voor/na-uitvoering.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: Herstelvoorbereiding via build_formation_context, TaskCheckpointWriter en bestaande bronreconstructie/materialisatie-readgrenzen; geen vervanging van kandidaatmaker of taakautoriteit.
Why local patching is insufficient: De huidige ContextVar-cache vervalt bij workerrestart en hasht/kopieert de hele bron bij herhaalde validatie. Alleen extractie overslaan voorkomt die reconstructie- en voorbereidingskosten niet.
Current authority/writer/reader map: PostgreSQL-workflow blijft eigenaar van prepared_extraction_versions, formation_inputs/contexts, taskresults en gepind plan. Een additieve immutable bronview-projectie hangt aan de exacte extractieversie. De bestaande geautoriseerde voorbereiding schrijft haar via TaskCheckpointWriter._locked; dezelfde writer/resolver leest haar bij hervatten. _content/_candidate/_evidence_fragments, semantic_passage._reconstructed_blocks, kennis-materialisatie en transformatie lezen gecontroleerde immutable carriers. Normale niet-carrier-input behoudt bestaande reconstructie en mutatiedetectie. Alle v3-worker/console/CLI-routes gebruiken dezelfde verwerking. Diagnostiek/replay/export blijven exacte invoer en historisch eigen taakbewijs lezen. Geen cache van rollen, review, publicatie of validatiebesluiten.
Supported runtime topologies: Native PostgreSQL met meerdere console-/workerprocessen en procesherstarts. Correctheid steunt op transacties, constraints en fencing, niet op gedeeld Python-geheugen. Tijdens uitrol mogen oude writers alleen expliciet als legacy gemarkeerde contexten behandelen; nieuwe contexten vereisen compatibele binaries.
Persisted-state impact: Additieve migration 023 voor formation_source_views; identiteit op exacte prepared-extractiehash plus reconstructie-/block-/filtercontract. Payload bevat gereconstrueerde blocks/mappings en fragmentindexen; geen ruwe inputkopie per poging. Poging bewaart alleen source_views_ref. Bestaande input-, context-, taak- en plansleutels wijzigen niet.
Compatibility/migration plan: Schema uitbreiden, dan compatibele worker. Bestaande task-v1-context zonder viewref wordt uitsluitend tijdens geautoriseerde verwerking één keer voorbereid uit bewezen opgeslagen extractie; geen nieuwe ruwe extractie en geen GET/startupbackfill. Aanwezige maar ongeldige/missende/gecontractwijzigde viewref wordt geweigerd, nooit stil herbouwd. Legacy en beslisbomen behouden hun expliciete bestaande route. De historische #581-module is niet aanwezig op huidige main; alleen de bewezen immutable-carrierbenadering wordt aangepast aan huidige extractie-/inputautoriteit, geen brede query-rewrite.
Rollback/recovery plan: Bewaar schema, bronviews, extracties en resultaten. Stop zo nodig nieuwe task-v1-admission en gebruik een compatible worker. Oude binaries kunnen bestaande taakresultaten lezen maar garanderen de reconstructievrije route niet; zij zijn geen ondersteund herstelpad voor contexts met source_views_ref. Geen down-migratie of historische opschoning.
Cutover trigger: Schema 023 en compatibele workers; native restart-/corruptie-/fencing-/source-equivalenceproeven en risico-passende regressies groen, vervolgens menselijke review en CI. Geen productiecutover in deze opdracht.
Cleanup/decommission criteria: Nieuwe-formatworkerstartroute bevat geen onnodige extractie/reconstructie of voorgaand totaalvoorstelpass. Gewone reconstructiehelpers blijven voor initiële expliciete productie, legacy en geautoriseerde herextractie. Geen tweede authority of onbeperkte gedeelde cache.
Failure blast radius: Eén bron/verwerkingscontext; ongeldig bewijs stopt vóór providerwerk zonder geldig bron-/taakbewijs of review/publicatie te wijzigen.
Adversarial proof matrix: Nieuwe worker na proceskill; missend/corrupt/verkeerd gebonden input/view/resultaat; extractor-/bron-/revisie-/contractwisseling; stale claim/rol/deadline; gelijke en afwijkende immutable commit; rollback; gedeeltelijke oude contexts zonder views; gemuteerde niet-carrierbron; expliciete herextractie; oorspronkelijke bron/mapping-/taakhashes; geen tweede kandidaatmaker.
Lifecycle entity: WorkingRevision op één immutable SourceSnapshot, met gepinde verwerkingscontext, attempts/claims en taakresultaten.
Lifecycle transition: processing met gepinde bron en eerder gecommitte taken → geautoriseerde nieuwe claim leest geldige bronviews en voortgang → alleen open taken → bestaande gezamenlijke eindpoort en definitieve in_review-activatie.
Initial durable state: Eén WorkingRevision met bestaande bron-/extractie-/inputidentiteit, nul of meer geldige TaskResults, eventueel een bronviewref en gepind taakplan.
Trigger: Bestaand toegestaan start-/hervatcommando, claimverwerving en taakcheckpoint binnen de bestaande opdracht.
Authorization: Bestaande actor-/documentrechten en verwerkingsautorisatie worden bij reserveren, claimen, commit en activatie gecontroleerd; claimfencing en deadlines blijven bindend.
Validation: Bron/snapshot/document/versie, exacte extractiehash en extractorcontract, fragmenthash, reconstructie/block/filterversie en payloadhash; volledige semantic/input/resultaatbinding. Actuele rechten, claim, revisie en deadlines blijven op beschermde writes/activatie opnieuw gecontroleerd.
Mutable entities: Bestaande poging/claim en voortgang; eenmalige additieve bronviewcommit per exacte extractie/contract. Geen wijziging van bestaande resultaat-/planidentiteit.
Immutable entities: Bronbytes, extractieversies, inputartefacten, bronviews, geldige resultaatversies en auditbewijs, oorspronkelijke plannen en bestaande canonieke publicaties.
Workflow state before: processing, of de bestaande expliciete fout-/blokkeerstatus met hervatbaar bewijs.
Workflow state after: processing zolang werk ontbreekt; bij fout de bestaande passende fout-/blokkeerstatus; na geslaagde eindpoort in_review volgens de bestaande lifecycle, nooit automatisch ready_for_publication.
Release state before: De bestaande release(s), of geen release.
Release state after: Ongewijzigd; taakopslag en hervatten besluiten niet tot publicatie, supersession of withdrawal.
Serving state before: De huidige publicatieregistry bepaalt welke release actief is.
Serving state after: Ongewijzigd; geen taakcommit, restart of backfill activeert een release.
Expected API result: Bestaande geldige start-/hervatantwoorden met duurzame taakvoortgang; expliciete bestaande conflict-/autorisatie-/integriteitsfouten waar van toepassing; leesverzoeken blijven beschikbaar en muteren geen workflowstaat.
Expected UI result: Bronselectie toont compacte voortgang uit gecommitteerde resultaten; document en overzicht blijven tijdens checkpoints open; Review verschijnt pas volgens de bestaande voltooide verwerkingsgates.
Failure result: Laatst geldige commits blijven behouden; gefaalde taaktransactie heeft geen gedeeltelijk geldig resultaat of voortgang; activatiefout verandert Review/publicatie niet.
Restart result: Dezelfde geverifieerde bronblocks/mappings, het gepinde plan en geldige taakresultaten worden uit PostgreSQL gelezen. Geen ruwe extractie of volledige bronreconstructie voor een compatibel vastgelegd artefact.
Recovery result: Alleen bestaande toegestane resterende of expliciet afgewezen taken; geen kosten-/deadline-/attemptverlenging, nieuwe curator- of publicatiebeslissing. Incompatibiliteit vereist de bestaande expliciete geautoriseerde herextractie waar toegestaan.
Legacy-data result: Afwezige legacy-viewref onderscheidt zich van een verwijzing die haar bewijs kwijt is. Een geautoriseerde worker kan één keer views toevoegen uit geverifieerde extractie; historisch completed wordt niet gepromoveerd tot bewijs. Gepubliceerd werk blijft onveranderd.
Required black-box scenario: Ontvang richtlijn, verwerk en commit een eerste taak plus bronviews, beëindig workerproces, start nieuw proces met extractor/reconstructor verboden en hervat. Alleen open taak krijgt providerrequest, bron/mappings/resultaathashes blijven identiek en finale activatie loopt via bestaande gates. Herhaal met corrupt/missend artefact en stale claim zonder modelwerk; expliciete geautoriseerde herextractie blijft apart mogelijk.
Explicit non-goals: Geen #840 workeroverdracht/budgetbeleid, geen nieuwe dispatcher, geen klinische eindacceptatie (#837), geen brede UI/query-rewrite, geen nieuwe kandidaatmaker, live modelkosten, merge, deployment of productiebackfill.

## Analyse en ontwerpkeuze

Waargenomen: build_formation_context hergebruikt prepared_source_extraction; TaskCheckpointWriter valideert input en bounded_formation hergebruikt taakdeltas. Toch worden input, content/candidate/evidence-blocks en voorgaand replayvoorstel opnieuw opgebouwd. De reconstructiecache serialiseert en deepcopieert volledige input per aanroep.

Dezelfde agent vergelijkt (A) een ruimere procescache en (B) geverifieerde immutable bronviews in dezelfde workflowstore met disposable immutable carriers. B is gekozen: overleeft restart, volgt gepinde identiteit en vermijdt per-kandidaat full-sourcehash/copy. A is eenvoudiger maar bewijst geen restart-/corruptiecontract en mist de huidige normalisatiewerkzaamheden. De benadering van #581/PR #582 is in de historische broncode nagelezen; geen oude opslag-/queryautoriteit wordt teruggezet.

Gebruik: een geautoriseerde worker laadt één geverifieerde preparation; filters en `_reconstructed_blocks` lezen de passende immutable view. Voor gewone mutable lijsten blijft de bestaande reconstructie/mutatiecontrole geldig. Oorspronkelijke kandidaatteksten en bronspans veranderen niet; resultaten/plan behouden hun exacte keys. Voor nieuwe of expliciet opnieuw geëxtraheerde bron wordt voorbereiding buiten de write-transactie opgebouwd en daarna onder de bestaande claimfencing gecommit.

| Gegeven | Producent → consument | Eigenaar / geldigheid |
|---|---|---|
| ruwe extractie | bestaande extractor → voorbereiding | prepared_source_extraction / immutable versie; bron-, extractor- en fragmenthash |
| bronviews | bestaande reconstructie → bronvalidators/materialisatie | nieuwe immutable workflowprojectie, bindt exacte extractie en viewcontract |
| input/semantiek | bestaande inputartefact → nieuwe claim | oorspronkelijke bron-/revisie-/contractidentiteit; corruptie is fout |
| taakresultaat/plan | bestaande taakcommit/planner → hervatten | bestaande unieke records; volgorde en eerder bewijs behouden |
| rechten/claim/review | bestaande domeinoperaties → protected writes/activatie | nooit gecachet als bevoegdheid |

Uitvoering: bestaande eigenaren behouden; alleen noodzakelijke viewopslag/carrier toevoegen; consumers aansluiten, daarna native restart-, fout- en gelijkheidsproeven en volledige repositorychecks. Implementatie is geautoriseerd; bij structurele tegenspraak wordt teruggekeerd naar dit ontwerp.
