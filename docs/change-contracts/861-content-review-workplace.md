# Eén inhoudelijke reviewtaak — #861

Change class: B
Promise: De reviewer beoordeelt kennisvoorstellen zonder vooraf een individuele of groepsgewijze taak te kiezen.
Proof: Gemengde PostgreSQL/HTTP/browserproef met individuele, batch- en onafhankelijke tweede beoordeling, ongeschikte batch en herstelretour.
Touches lifecycle invariants: no
Rewrite risk: none

Base: `7ca29cfa5661a8dececbf160e81b9a60ffb99f4c`, actuele main na #873.
Scope: uitsluitend PR 6 uit #857; #862/#863 blijven afzonderlijk. Geen merge/deploy.

## Ground

`review_workboard_v1.install_review_workboard.review_get` gebruikt
`read_review_document` voor een taak en `read_review_passage` voor objectdetail.
Deze bestaande readers leveren objecten, actuele revisie, bindings en broncontext.
`operations_console_app._review_route_objects` gebruikt uitsluitend
`review_duty_v1.reviewer_route_for`; `review_duty_lane` blijft de enige eigenaar
van presentatiegeschiktheid. De landing gebruikt bestaande actorcounts en lanevolgorde.

Huidig: drie afzonderlijke inhoudelijke indices/contextual, batch, second_review.
Gewenst: één index Kennisvoorstellen beoordelen met passende bestaande lijsten en
batchformulieren. Historische GETs blijven deze ene presentatie openen. Structuur,
graaf, inventaris, historie en bronafhandeling behouden hun verschillende eigenaren.
Geen nieuwe endpoint/router, reader, writer, fallback, kandidaatmaker of productopslag.

| Handeling | Lees-/POST-route en owner | Behouden / verplaatst / verwijderd |
| --- | --- | --- |
| Individueel oordeel | GET /review object; POST /review → review_object | Bestaande exacte bevestigingen, suitability, bron/context, reden, CAS en guards behouden; lijst onderdeel van één taak |
| Batchbevestiging | GET /review task=batch; POST /review/normal-risk/batch-confirm → ProportionateReviewConsole.batch_review_normal_risk → review_object | Bestaande groepering/max20/selectie/broncontrole/per-object commits behouden; alleen actor-uitvoerbare batchleden renderen met bestaande routefilter |
| Onafhankelijke tweede review | GET /review object; POST /review/second-review → approve_second_review of review_object(revise) | Exacte bindings en onafhankelijkheid behouden; lijst binnen dezelfde taak |
| Herstel en broncontext | GET /source-selection object; bestaande POST /review/resolve, /review/source-context en /review/context/accept | Vorming blijft enige editor; heen/terug bewaart snapshot/object en verliesbare oorspronkelijke reviewrevisie, nooit approval-overdracht |

Runtime: bestaande ReviewClosure/durable workflow/PostgreSQL-compositie en
AzureAuthoritativePublicationConsole blijven owner; native store-/badge-mixins
worden niet gewijzigd. Ondersteunde directe HTTP/Python-callers, legacy POST-drafts,
boom/graaf-override en bounded passage-reader blijven behouden. Geen nieuwe CLI.

## Stateful Class B-overlay

- Domain entity/aggregate: bestaande snapshot/WorkingRevision, exacte kandidaatversie en reviewerbinding.
- Invariants: toegewezen bevoegde reviewer, geldige bron, exact ID/versie/hash/type, onafhankelijke vereiste deelname; immutable bron/gepubliceerd werk; bestaande batchgeschiktheid.
- Durable state before: actuele kandidaat met bestaande reviewplicht en bindings.
- Durable state after: uitsluitend bestaande individuele approve/reject/revise of tweede-reviewuitkomst, exacte binding/events; herstel via bestaande Vorming-command maakt opnieuw te beoordelen werk.
- Transaction boundary: bestaande review_object/approve_second_review workflowcommit, PG-documentlock/CAS. De base batchimplementatie voert per-object review_object aanroepen met revision-pin uit. De productie-override ClosedLoopReviewConsole.batch_review_normal_risk omvat die hele reeks met _atomic_snapshot_mutation; _PostgresWorkflowReviewMixin sluit aan op de bestaande Storeopdracht/workflow_transaction. Objecten, bindings en events committen daardoor als één native batchopdracht. Die buitenste transactie blijft intact.
- Failure/recovery result: bestaande validatie/conflict/native rollback: een fout in een batchlid laat de hele productie-batch ongewijzigd. De bestaande partial-batch-foutrenderer blijft compatibel maar definieert geen alternatieve productiecommit. Refresh/herstart leest PostgreSQL; geen UI-compensatie.
- Duplicate execution / idempotency result: bestaande expected_revision/conflict en bestaande command-ID-regels; interaction_id is bewijs, geen nieuwe deduplicatieautoriteit.
- Concurrency result: actuele bindings/CAS hercontroleert command; oude browserrevisie mag geen nieuwere schrijver overschrijven. Geen browserlock.
- Audit/evidence requirement: bestaande review_events/ledger en exacte binding per object, bestaande repair-evidence; geen extra register.

## Sketch → Agree

Gebruik: Beginnen/Verder → één inhoudelijke index → bestaande passagekaart of
expliciet geselecteerde coherente groep → bestaande POST → verse projectie.
Tweede reviewer opent dezelfde taak met onafhankelijke tweede-reviewpresentatie.
Bij ontbrekende context: dezelfde passage naar Vorming → bestaand herstel →
dezelfde passage opnieuw lezen/beoordelen; veranderde revisie expliciet tonen.

Datastructuren blijven bestaande objectlijsten, actorroute, bindings/fragments en
revision-string. Geen nieuwe domain types/store nodig. Oorspronkelijke reviewrevisie
is alleen verliesbare navigatiecontext; command gebruikt uitsluitend zijn eigen
actueel gelezen formulier-revisie en bestaande resolver/CAS.

Twee daadwerkelijke onafhankelijke read-only runners op dezelfde Ground:
`/root/review861_design_a` en `/root/review861_design_b` (zelfde model, afzonderlijke analyses).
A consolideert bestaande indices, B opent automatisch een concreet eerstvolgend
object/groep. Gekozen A: geen extra queue-read plus detail-read of GET-redirect,
behoudt lijst/backnavigatie en bestaande paginering. B vraagt meer doorstappen of
een tweede lezing; geen gebruikersbelofte vereist dat. Beide houden state owner.
A scoort beter op locality/access-fit; beide behouden concurrency door commands
ongemoeid te laten. Geen nieuwe algemene taakselectie of workflow-engine.

Architect-hoofdskill is gelezen. Aanvullende skill-resource candidate-brief faalde;
de overige referenties zijn daarom niet als gelezen geclaimd. Projectontwerp #857
blijft de basis. Implementatie is geautoriseerd; Agree vereist geen extra toestemming.

## Contextcontract en bewijsplan

| Gegeven | Producent → consument / eigenaar | Geldigheid |
| --- | --- | --- |
| Snapshot/object | Bestaande reader → Vorming/Review-links | Exact dezelfde IDs; geen browseropslag |
| Commandrevisie | Bestaande snapshot/bounded reader → bestaand POST/resolver | Actuele CAS; ontbrekend/stale blijft bestaande afwijzing |
| Oorspronkelijke reviewrevisie | Reviewkaart → verliesbare heen/terugquery | Alleen vergelijk-/waarschuwingstekst, nooit command-CAS of bevoegdheid |
| Review/bron/type | PostgreSQL/Azure → bestaande reader/kernel | Iedere beschermde mutatie hercontroleert; herstel draagt approval niet over |

Minimale falsifieerbare proeven: individuele+minstens twee batchleden bij optional
deelname, daarnaast tweede review op required snapshot; twee verplichte reviewers
maken ook definities individueel. Die actuele domeinregel blijft intact; actorfilter; max20/andere sectie/type/risico/onbekend geweigerd;
exacte opgeslagen beslissingen; native stale/unauthorized/duplicate/restart;
herstel heen/terug, actuele gewijzigde versie en geen approval-overdracht;
GET/refresh schrijft niets. Zelfde fixture/readvergelijking: één documentreader,
geen extra volledige corpus/ledger-read. Desktop/mobiel/keyboard via echte browser.
Verplichte repo-checks inclusief volledige pytest; PG-skips tellen niet als bewijs.

## Implement → Scrap

Verwijder vervangen inhoudelijke indices en ongebruikte dashboard-/categoriehelpers
zodra hun callers weg zijn; behoud gedeelde _lane_total/_review_lane_copy zolang
andere productiecallers bestaan. Oude POST-contracten/guards blijven intact.
Rollback is code terugzetten met behoud van alle opgeslagen versies/bindings/events;
geen datareset of herstelde approvals. Werkelijk bewijs/SHA volgt in de PR.

## Verfijning en tussentijds bewijs

De drie presentaties delen één verliesbare actorrouteprojectie binnen dezelfde
renderaanroep. Iedere objectroute wordt eenmaal berekend; filters lezen diezelfde
projectie. Dit is geen nieuwe router/cache/authority. De bestaande batchrenderer
hercontroleert haar eigen geschiktheid. Native proef telt de aanroepen per object.
Op dezelfde productiecompositie/fixture is voor iedere historische taak-GET op
main en deze wijziging gemeten: één read_review_document en één
review_source_fragments; nul snapshot_objects_and_revision, object_review_bindings,
list_document_cards of _load_objects naast die capture. Geen productielatentieclaim.

De oude exclusieve dashboard-/categorie-CSS en actieve readiness-selector zijn
verwijderd/vervangen. De gezamenlijke werkplek en persoonlijke werkvoorraad zijn
nu de readiness-evidence. Gedeelde stijlen blijven behouden. Assetfingerprints in
33 bestaande HTML-goldens zijn exact bijgewerkt; inhoudelijke HTML-wijzigingen
zijn apart bekeken. Alle niet-HTML-resultaatvelden blijven identiek.

Bij contextkeuze uit een ander bronfragment blijft context_target het terugkeerobject;
de bestaande return_object_id stuurt de POST terug naar datzelfde voorstel.
Oorspronkelijke reviewrevisie blijft bewaard in links, GET-keuzes en bestaande
POSTs; actuele formulierrevisie blijft de enige CAS-invoer.

De afsluitende MRO-controle corrigeert de eerste beschrijving van de batch:
alleen de base per-objectlus bekijken was onvoldoende. De buitenste
`ClosedLoopReviewConsole.batch_review_normal_risk` en
`_PostgresWorkflowReviewMixin._atomic_snapshot_mutation` bepalen de werkelijke
productietransactie. `tests/test_review_batch_atomic_postgres.py` bewijst native
rollback, herstart en stale replay. Geen productcode of transactie is hiervoor
gewijzigd; de bestaande legacy-foutrendering blijft behouden.
