# HA-3 — broncorrectie met exacte revisies en ingestreview

Change class: A
Rewrite risk: high
Promise: Een bevoegde actor corrigeert de oorspronkelijke annotatie; dezelfde deterministische bouwer en bestaande revisieowner leveren een nieuwe exacte objectversie, terwijl alleen geraakte reviewautoriteit vervalt.
Proof: Native PostgreSQL, echte console/UI-keten, races, restart, rollback en herstel; resultaten worden pas na uitvoering toegevoegd.
Touches lifecycle invariants: yes

## Opdracht en betekenis

GO projectlead, 8 november 2026: William gaf expliciet opdracht “Start HA 3”.
Dit is uitvoering van #1016 / MET-60, vanaf main
`dfc077af362e0d8156aa5ea96e05b9d83c45127a` (#1031 gemerged).
De eerdere planninglabels zijn geen nieuwe inhoudelijke blokkade voor deze
expliciete opdracht. Er is geen merge-, deployment- of productiemigratieopdracht.

#986 / MET-49 blijft leidend: één claim met context, onderbouwing en herkomst.
De oude definitie “kleinste stuk richtlijntekst” is achterhaald. Keuze A houdt
voorwaarden/uitzonderingen bij dezelfde claim; optie 1 weigert dubbele actieve
geordende kernbereiken. Een onderbouwingspassage wordt niet vanzelf een KO.
`pre_review_semantic` is de oude AI-prozavorming, geen extra menselijke review.
HA-4 verwijdert die uitvoering; dit contract schrapt geen ingestbeoordeling.

Bronnen: ontwerpbranch `docs/human-annotation-architecture-1014`,
`human-annotation-architecture.md` §§3/6–8 en
`1014-multi-range-annotation.md`; het bestaande HA-2-bouwcontract en T11-revisiecontract.
De PStack-statechart toetst de overgang review → selectiecorrectie → overzicht
→ actuele bouw → ingestreview. Zijn 80 modeltoestanden bewijzen geen SQL-commit,
autosaverace, meerdere objectversies of gedeeltelijke publicatie.

## Lifecycle vóór productcode

Lifecycle entity: ongepubliceerde WorkingRevision met menselijke annotatie-invoer, objecthistorie en exacte reviewbindings.
Lifecycle transition: broncorrectie opslaan → geraakte reviewautoriteit vervalt → exact overzicht verzegelen → bestaande poging bouwt → nieuwe objectversie met exacte voorganger → ingestreview op de eindversie.
Initial durable state: immutable bron/extractie; HA-2 activeerde een humanproof; huidige objecten kunnen bevestigd/beoordeeld zijn, maar deze WorkingRevision heeft geen publicatiebijdrage.
Trigger: bewaren van een gewijzigde oorspronkelijke annotation-ID, daarna afzonderlijk “Afronden en opbouwen”. Openen/overzicht lezen muteert niets.
Authorization: bestaande source_selection.authorize_account (researcher of genoemde reviewer) bij save/seal/claim/activatie; bestaande reviewcommands controleren afzonderlijk reviewerrol, ingestdeelnemers en onafhankelijkheid.
Validation: bron/working/extractie/normalisatie, entry/set-CAS, expliciete huidige objectfrontier, exact oorspronkelijk annotation→objectverband, overzichtshash, actuele producerpin, claim/lease/deadline, reviewer-owned velden en bestaande Admission/relatiecontroles.
Mutable entities: nieuwe annotation-versie/head/generatie, bestaande huidige reviewbindings, setfrontier/sealpointer, bestaande attempts/dispatch, nieuwe objectversies/frontiers, huidige producerpin en audit binnen één workflowdatabase.
Immutable entities: bronbytes/extractie, historische annotaties/seals/proofs, oudere objectversies na een opvolger, historische reviewbesluiten, canonieke releases en servingregistry.
Workflow state before: in_review/blocked/ready_for_publication volgens de bestaande afleiding.
Workflow state after: geraakt werk vereist correctie/actuele bouw en daarna nieuwe toepasselijke ingestreview; ongeraakt werk behoudt zijn exacte toestand. Geen tweede documentstatus.
Release state before: geen release uit deze WorkingRevision; eventuele eerdere release published/active.
Release state after: ongewijzigd door correctie/bouw; gepubliceerd werk wordt niet in-place heropend.
Serving state before: bestaande registry-uitkomst.
Serving state after: identiek tot afzonderlijke geautoriseerde publicatie/opvolging/intrekking.
Expected API result: duurzame save-/buildreceipt; identieke command hergebruikt het resultaat; andere payload, stale frontier/bron/actor geeft conflict zonder half succes.
Expected UI result: broncorrectielink opent dezelfde annotation-ID en gepinde bron, toont huidige objectversie, bewaarde correctie en overzicht; na bouw beoordeelt de bestaande kaart de echte eindversie eenmaal.
Failure result: gecommitteerde aanwijzingen blijven bewaard; geraakt oud werk kan niet opnieuw worden goedgekeurd/gepubliceerd terwijl een correctie openstaat; geen gedeeltelijke nieuwe objectset of providerfallback.
Restart result: dezelfde annotaties, ongeldige reviewautoriteit, seal, poging, proof en objecthistorie; geen nieuw inhoudelijk besluit of tweede opvolger.
Recovery result: bestaande offline lege-doelrestore behoudt exacte input, voorgangers, proofs en receipts en controleert dezelfde native grenzen; corruptie faalt expliciet.
Legacy-data result: layout-1-modelbewijs en oude publicaties blijven ongewijzigd leesbaar. HA-3 neemt geen oude AI-objectset automatisch als menselijke annotaties over.
Required black-box scenario: echte receive/ingest → selectie/save → restart → overzicht/seal/dispatch/bouw → review volgens ingest → oorspronkelijke annotatie corrigeren → pauze/restart → alleen geraakt oordeel ongeldig → herbouw/nieuwe versie → toepasselijke review → bevoegde publicatie → registry/API/MCP; historische release blijft immutable.
Explicit non-goals: nieuwe reviewerpolicy, automatisch oordeel, fuzzy identiteit, impliciete split/merge/terugname van bestaand kenniswerk, historische AI-takeover, nieuwe queue, bulkconversie, praktijkacceptatie en HA-4-decommission.

GIVEN een actuele human-objectversie met een expliciet annotatieverband,
WHEN een bevoegde actor die annotatie bewaart en de gecontroleerde versie laat bouwen,
THEN vervalt geraakte reviewautoriteit onmiddellijk, ontstaat uitsluitend via de
bestaande revisieowner een opvolgversie met dezelfde expliciete identiteit,
blijven ongeraakte exacte oordelen behouden en blijven serving en historie na
restart gelijk aan de gecommitteerde toestand.

## Bestaande eigenaren, aanroepers en opslaggrenzen

| Gegeven / grens | Producent, consument en eigenaar | Geldigheid / ontbrekend |
| --- | --- | --- |
| Bron, Unicode-ankers | immutable source store → retained extraction/source views → annotation save/materialiser/review | HA-2 codepoint-/grapheme-/quotehashcontract blijft; geen herankering of quote-export |
| Keuzes | editor/API → human_annotation_v1.save → annotation_versions/heads/commands | huidige rechten, generatie, entry en objectfrontier; atomair receipt + invalidatie |
| Overzicht/seal | human_annotation_build_v1._capture/overview/finalize → annotation_seals/build_commands | exacte context, input en huidige objectbasis; stale weigeren |
| Job | processing_retry.reserve → source_processing_dispatch → worker_handover → build.execute | bestaande pending/claim/token/lease/deadline/retrybudget; geen tweede statusregister |
| Kandidaattekst/bron/initial ID | human_annotation_materialisation → knowledge_materialisation.materialise_knowledge_candidates → transform/Admission/register | uitsluitend deze creator; ruwe uitkomst blijft bewijs, geen identiteit uit browser |
| Correctie-identiteit/versie | persisted annotation-ID → huidige exacte voorganger → review.revision_workflow.revise_object | geen tekst-/overlapmatch; nieuwe initial-ID-collision weigeren; geen bevestigingen uit oude voorstellen terugzetten |
| Producerbewijs | FormationTaskStore/FormationEvidence prepare/publish/read/assert_human_activation/retain_active_evidence | immutable raw input/output + expliciete revisietoepassing; zelfstandig hercontroleerbaar; historische binding blijft behouden |
| Objectcommit | _commit_prepared_store → workflow_transaction → PostgresConcurrentWorkflowDocumentStore.write_bundle en cutover-override | autorisatie→document lock, objects-CAS, huidige proof en append-order revision-windowvalidatie |
| Oordelen | review_command executor → concrete console-MRO → ko_transitions/reviewpolicy → workflow reviewbindings + ledger | huidige exact-hash/version/type, ingestpersonen/independence; pending broncorrectie verleent geen goedkeuringsrecht |
| Afhankelijkheden | huidige relaties/confirmed_source_context en native review-neighbor readers | onderscheid validatievoetafdruk en werkelijk geraakte betekenis; identieke onveranderde passage elders alleen is geen wijziging |
| Publicatie/lezen | publication_readiness/consider_publish → DurablePublicationConsole/AzureAuthoritativePublicationConsole → canonical store/registry → publieke API/MCP | geen andere servingauthority; gepubliceerd werk immutable, successor via bestaande expliciete operatie |
| Herstel/startup | formation_recovery/workflow backup + operational_document_inputs beide layouts + startup/reconciliation | input/proof/history exact behouden; geen silent rebuild of herextractie |
| Oude routes | source-selection/reextract/class-change/retry/settings/internal repair → bestaande human-owned fences | HA-2 blokkades behouden; geen tweede menselijke editor; volledige oude prozaverwijdering HA-4 |

De file-store is geen annotatietopologie. Ondersteund zijn native PostgreSQL,
beide operationele documentlayouts (legacy/v1), dezelfde worker/dispatcher in
één of meer processen en bestaande lokale/Azure immutable bronstores. Een
lokale bronstoretest vervangt geen PostgreSQL-bewijs of Azure-deploymentproef.

## Ontwerpvergelijking en keuze

Twee aparte read-only runners onderzochten dezelfde basis en rapporteerden
zonder codewijzigingen. A verdiept bestaande seal/build-activatie met de
bestaande revisieowner; B laat de bounded correct_object-command een sealed
correctie consumeren. Criteria: één creator/revisieowner, historische proof-
binding, ongeraakte oordelen, bestaande queue/transactie en herstelcomplexiteit.

Gekozen: A. B vereist dezelfde volledige producerbewijsaanpassing, terwijl de
oude correct_object-voorbereiding bevestigd type wist en legacy v2-evidence
herbindt. A houdt browser en dispatcher bij hun bestaande smalle calls:

```python
saved = annotations.save(..., annotation_id=original_annotation_id,
                         expected_objects_revision=current_frontier)
view = build.overview(...)
receipt = build.finalize(..., overview_hash=view['overview_hash'],
                         expected_revision=view['objects_revision'])
# Bestaande dispatcher levert dezelfde human build; de revisieowner past
# uitsluitend bewezen materialiseroutput op de expliciete voorganger toe.
console.review_object(..., expected_revision=current_frontier)
```

De gegevensvorm houdt annotatie-ID en canonieke identiteit apart. Nieuwe
annotaties krijgen alleen de materialiser-ID; een correctie verwijst expliciet
naar de bestaande canonieke voorganger. Ruwe materialiseruitvoer en toegepaste
revisie mogen niet tot één oncontroleerbaar callerrecord worden vervlakt.
Dominante reads zijn huidige set/objectbasis bij seal, immutable proof bij
historische controle en één entry bij save. Volumes zijn niet gemeten; geen
nieuwe cache/index/performanceclaim. Eerste annotatiesaves schrijven alleen
rijgerichte input. Correcties na activatie gebruiken de bestaande objectfrontier
en historyvalidatie met native delta-DML; hun lees-/serialisatiekosten bij grote
documenten zijn nog niet gemeten en worden niet als begrensde latency beloofd.
Voorbereiding blijft buiten de schrijftransactie; activatie
controleert de echte actuele basis opnieuw.

## Herschrijfrisico en overgang

Concrete additieve representatie vóór implementatie: een correctieseal krijgt
`revision_basis` met de voorafgaande producerproof-ID, exact huidige objectrijen
en de sealactor. De bestaande setpin blijft het HA-2-voorbereidingsfrontier;
de correctieseal bindt zijn eigen actuele objects-CAS. Er komt geen tweede
mutable identitymap of jobtabel. FormationEvidence bewaart de ruwe uitkomst als
`candidate`-leden en de door de bestaande revisieowner toegepaste huidige
versies als `result`-leden. Beide worden onafhankelijk gereconstrueerd en de
basis wordt tegen werkelijke voorgangers gecontroleerd. Historische objecten
blijven aan hun oorspronkelijke sealed proof verifieerbaar; de actieve pin
moet juist de huidige set dekken. Alleen vervangen afgeleide bronrestprojecties
mogen uit de werkset verdwijnen, met historisch bronbewijs in de oude proof;
kennisobjecthistorie wordt nooit verwijderd. Nieuwe basisvorm vraagt expliciet
ondersteunde guards en archiveversie; oude records krijgen geen verzonnen basis.

Pending correcties worden afgeleid uit annotation-head versus geactiveerde
annotation-revisie en actuele inkomende afhankelijkheden. Save trekt hun
bindings en governance atomair in via de bestaande workflow/reviewwriter.
Dezelfde afgeleide pending-set weigert nieuwe approvalbindings op de oude
versie; geen duurzame tweede pending-status. Onveranderd opslaan maakt geen
nieuwe inhoudelijke correctie. Split/merge/terugname van al geactiveerde claims
blijven expliciet geweigerd zolang hun aparte vervangingscommand ontbreekt.
Deze correctieslice behoudt het geactiveerde claimlidmaatschap: na eerste bouw
worden alleen oorspronkelijke annotation-ID's met een bewezen canonieke claim
inhoudelijk aangepast. Nieuwe claims, omzetting van bron-dispositions, splitsen,
samenvoegen en terugnemen vragen de afzonderlijke expliciete vervangingscyclus.
Zonder die grens zou een nieuw ongeactiveerd entry geen geraakte huidige claim
hebben en bij de bestaande publicatiesluiting ongemerkt buiten beeld kunnen
blijven. Dit is een expliciete scopegrens; geen claim dat een algemene heropening
van het gehele geselecteerde document hier is geleverd.

Aanvullende concrete aansluiting gevonden in de echte browserketen: de bestaande
KO-evidencegate kende alleen relaties naar een zelfstandig bewijsobject. Een
geldig aangewezen bewijsbereik binnen hetzelfde human-KO werd daardoor niet als
onderbouwing gelezen; een test kon alleen met de expliciete keuze NVT publiceren.
Dat is geen bewijs van correcte aansluiting. #986/MET-49 en de annotatiearchitectuur
vereisen juist bronbewijs zonder dat aanwijzen een tweede KO maakt. De bestaande
KO-owner krijgt daarom een adapter voor exact gevalideerde human-bewijsbereiken
met functie supported_by/explains. Pas het expliciete bevoegde eindoordeel bindt
dit bewijs aan de exacte objecthash als de bestaande waarde `linked`. Een
annotatie of readfact is geen goedkeuring; NVT bij werkelijk gekoppeld bewijs
blijft een conflict. Geen extra KO, nieuwe reviewvraag of nieuwe approvalengine.
Readfacts pinnen deze nieuwe bronafhankelijkheid onder hun bestaande producer-
compatibiliteit; onbegrijpende oude facts vallen terug op de bestaande volledige
bronlezing, zonder historische reviews/publicaties te heropenen.
Ook de bestaande revision-frontier-producerversie verandert: haar afgeleide
`historical_has_knowledge` omvat nu menselijke claimvorming. Een oude cache die
die herkomst als niet-kennis berekende, mag niet onder het nieuwe contract
worden vertrouwd. De bestaande owner valt terug op volledige historische
validatie en verzegelt daarna opnieuw zijn afgeleide frontier; geen canonieke
backfill, nieuwe lineage of curatorbeslissing bij startup.

De volledige upload-HTTP-proef vond nog een bestaande HA-2-aansluitfout:
nieuwe human-bronresten gebruikten de legacy v1-dispositionpolicy, waardoor
zelfs exact gekoppelde en beoordeelde context opnieuw om een bronbesluit vroeg.
Nieuwe seals pinnen daarom `source_accountability_version=source-accountability-v2`
en gebruiken de bestaande T10-owner voor dekking en sluiting. Zonder die pin
blijft de oorspronkelijke v1-uitvoer exact reproduceerbaar; bestaande seals en
proofs worden niet herschreven of opnieuw beoordeeld. Een onbekende policy faalt
expliciet. Deze versiekeuze sluit uitsluitend bewezen brongebruik; ze keurt geen
claim goed en sluit ongekozen of ongedekte inhoud niet stilzwijgend af.

Archief v12 / formation-sectie v5 bewaart ook de bestaande
`publish_authorizations.authorization_payload` volledig. De oude v11-export
liet die kolom weg en kon daardoor wel het tuple maar niet de drie antwoorden,
bewijskeuze en commandbinding exact terugzetten. Oude archieven krijgen alleen
een expliciete null voor deze ontbrekende capability; er wordt geen historisch
oordeel bij verzonnen. Nieuwe exports/herstel moeten volledige bindings exact
behouden, ook tijdens een open correctie. Deferred headvalidatie weigert bij
restore een oud oordeel dat strijdig is met de actuele annotatie-invoer.

Rewrite target: postactivatie-correctie en exacte human producer-/reviewbinding, zonder de bestaande revisie- of servingauthority te vervangen.
Why local patching is insufficient: 036 bevriest set.objects_revision en vergelijkt ook historische objectversies met uitsluitend het actieve producerresultaat; de oude algemene correctie wist bevestigde classificatie. Een open saveknop zou stale publicatie en oncontroleerbare bronwijziging toelaten.
Current authority/writer/reader map: bovenstaande tabel, bestaande HA-2 execution-inventaris, beide write_bundle-implementaties/cutover-MRO, bounded reviewcommands en directe consolecalls; native triggers moeten ook directe SQL/alternatieve bundlewriters afwijzen.
Supported runtime topologies: native PostgreSQL beide documentlayouts/task-v1, bestaande source stores, meerdere consoles/workers; file-only annotatie niet ondersteund.
Persisted-state impact: additieve versie van sealed correctiebasis/revisieapplicatie binnen bestaande FormationEvidence, expliciete historische producerbinding en aangescherpte native gates; geen backfill of herhash van historische data.
Compatibility/migration plan: expand met additieve migratie; bestaande layout-2-eerstebouw en layout-1-historie blijven geldig. Nieuwe correcties vereisen daadwerkelijk aanwezige native guards. Oude writer mag nieuwe revisiebewijzen niet interpreteren als eerste bouw of legacy AI-invoer.
Rollback/recovery plan: vóór schema-adoptie oude HA-2 lees-/bouwroute behouden; na nieuwe correcties writes blokkeren bij onbegrijpende binary, bestaande registry-serving intact. Forward fix of bewezen nieuwe-reader-restore, geen oude AI-fallback. Geen destructieve downmigratie/produktiedatawijziging.
Cutover trigger: native save/review/publicatie- en activation-CAS-races, exacte onafhankelijke proofcontrole, beide layouts, restart/rollback/restore en UI-keten slagen op exacte head; merge/release blijven afzonderlijk.
Cleanup/decommission criteria: één annotatie-editor, creator, revisieowner, queue en commitgrens; vervangen human-correctie-ingangen worden gerouteerd/geweigerd. Geen permanent tweede correctiepad. Globale oude AI-prozacallers/config verwijdert HA-4.
Failure blast radius: betrokken ongepubliceerde WorkingRevision en werkelijk geraakte afhankelijkheden. Geen mutatie van actieve/historische release of servingregistry. Gedeelde proof/schema/reviewgrens vereist overige producerregressies.
Adversarial proof matrix: forged predecessor/annotation/canonical identity, gewijzigde raw output met herhash, ID-collision, ontbrekende native guard, alternatieve MRO/SQL/bundle/repairwriter, duplicate/stale/revoke, save versus review/publicatie, stale builder na save, claimexpiry, echte rollback/restart en lege-doelrestore.

## Bewijsplan en open werk

- Eerst rode native proef: HA-2-object met bevestigd type corrigeren via dezelfde
  annotatie, exact hervatten, nieuwe objectversie, bevestiging behouden en geen
  geldig oud oordeel. Geen overgeslagen databasetest als succes tellen.
- Aanvullen met ongeraakt tweede object, gedeeld onveranderd bronbewijs versus
  werkelijk gewijzigde relationele afhankelijkheid, meerdere kernbereiken,
  Unicode en identieke tekst/andere positie, stale objectfrontier en duplicate.
- Bewijs herhaalde tweede/derde correctie, voor-/na-commitfailure, review- en
  publicatieraces, ingestvarianten, immutable release, beide layouts en recovery.
- Browser toont echte opgeslagen bron/versie/annotatie en nieuwe reviewkaart;
  onafhankelijke UI-finishcontrole en afzonderlijke adversariële surfacepass.
- Volledige repositorychecks vóór draft-PR. Geen Done, praktijkacceptatie,
  deployment of volledige HA-3-closure zonder toepasselijk echt bewijs.

Ground en twee ontwerpen zijn uitgevoerd. Contract/implementatie/proeven worden
bijgesteld op werkelijk gevonden programmagrenzen; deze tekst op zichzelf is
geen bewijs dat de beschreven nieuwe productroute al werkt.
