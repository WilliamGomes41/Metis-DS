Change class: A
Promise: Een reviewer kan een actuele kennisobjectversie alleen volgens één centrale overgangscontrole goedkeuren of gericht corrigeren; een weigering schrijft niets, een correctie levert een nieuwe open versie en alle bestaande autorisatie-, bindings- en publicatiegrenzen blijven behouden.
Proof: Native PostgreSQL-transitietests, echte kaart → weigering → onderbouwing of expliciet niet-van-toepassing → akkoord → bon → correctie → nieuwe review, vervalste aanvragen, gelijktijdigheid, rollback/herstart, onafhankelijke adversariële review en vooraf vastgezette vergelijkende p95-metingen van goedkeuren en corrigeren.
Touches lifecycle invariants: yes
Rewrite risk: high

## Opdracht en gegronde scope
De operator geeft op 6 november 2026 opdracht KO-4 met pstack te bouwen. Expliciet aanvullend GO in deze sessie: dezelfde onderbouwingsregel bij iedere volgende goedkeuring, ook bestaande ongepubliceerde objecten; gepubliceerde historie blijft onveranderd. Onderbouwing is volgens Appendix C verplicht voor ieder type, met expliciet geregistreerd niet-van-toepassing als geldige sluiting.

KO-2 is nog niet op main: #1001 is naar de al afgesloten ontwerptak gemerged. Prerequisite #1004 / PR #1005 integreert exact de eerder goedgekeurde kaart/bon naast KO-3. KO-4 bouwt op die integratietak, oorspronkelijk main9cd19ab7. Geen merge/deployment geautoriseerd.

Dit issue realiseert de onafhankelijke review-/correctieslice van KO-4. Broncontextcommands blijven expliciet afhankelijk van #942 en worden niet via een nieuwe parallelle schrijver omgeleid. Volledige KO-4-programmabelofte blijft open zolang die broncontextslice niet aangesloten en bewezen is. KO-5/6, destructieve migratie, productie-audit en publicatieactie #991 vallen buiten deze uitvoering.

## Gegrond ontwerp
Pstack how is uitgevoerd door twee readonly explorers en een explainer; werkrapport /workspace/ko4-how-brief.md. De huidige ReviewCommand legt beperkte histories, bindings en brongegevens vast, controleert rechten/CAS en voert de bestaande MRO uit binnen de bestaande PostgreSQL-grens. Review kan in dezelfde command type/relaties bevestigen en daarmee een nieuwe canonieke tuple voorbereiden vóór het exacte akkoord. De nieuwe controle moet die uiteindelijke tuple gebruiken, niet alleen het vooraf getoonde statelabel.

Gekozen vorm A: TRANSITIONS en apply_ko_event op reeds vastgelegde commandfeiten binnen de bestaande mutation boundary, met bestaande staged writer als enige schrijver. Geen nieuwe read-rondgang, transactie, statuskolom, event-store, dispatcher of cache. Vorm B, een buitenste dispatcher die de console opnieuw leest en de MRO aanroept, is afgewezen wegens stale prechecks, recursie en dubbele orchestratie.

## Expliciete afspraken vóór implementatie
- Alle nieuwe KO-goedkeuringen, ook directe native ingangen en tweede akkoorden, krijgen de drie expliciete antwoorden via hetzelfde ReviewAssessment-contract. Een ontbrekend/negatief antwoord mag niet door serverdefaults worden goedgekeurd. Structurele en bronrecords blijven hun eigen bestaande beoordeling houden.
- Onderbouwing wordt gecontroleerd op de bevestigde uiteindelijke relaties en actuele doelversies; alleen een voorstel is onvoldoende. Expliciet niet-van-toepassing is een ongevraagde default nooit: de reviewer kiest dit zelf in dezelfde kaart.
- N/A wordt als genormaliseerd feit in de bestaande exacte goedkeuringsbinding en bijbehorende audit vastgelegd: supporting_evidence met een versietag en applicability. De binding draagt snapshot/object/versie/hash/reviewer. Geen extra governance/schemafield en geen hash-selfreferentie in metadata.
- Een nieuwe tweede goedkeuring heeft haar eigen expliciete keuze als onderbouwing ontbreekt. N/A van een eerdere reviewer wordt niet stilzwijgend als nieuwe keuze overgenomen. Een materiële nieuwe versie erft geen geldige keuze van de oude tuple.
- Exacte replay van een eerder bevestigde identieke command behoudt de bestaande no-op; replay is geen nieuw reviewbesluit. Een nieuw besluit op dezelfde tuple moet zijn nieuwe assessment/onderbouwingsfeit correct vastleggen.
- Geen universele tweepersoonsregel. Bestaand risico-/reviewbeleid bepaalt eerste of tweede beoordeling; bestaande exacte bindings blijven autoriteit.
- Correctie is een command die een nieuwe open versie oplevert. Nieuwe opgeslagen validation_status=revise verdwijnt. Bestaande legacy revise blijft herstelbaar via een expliciet compatibiliteitspad; geen startup-migratie of datawijziging uitgevoerd.
- Support/classificatieherstel steunt nu op een tussentijdse revise met audit. Dat protocol wordt vervangen door expliciet gevalideerde in-command reparatiecontext binnen dezelfde transactie; geen publieke bypassparameter en geen tweede reparatieregister.
- De bon blijft uitsluitend na bevestigde commit en vermeldt het werkelijk vastgelegde besluit/onderbouwingsfeit. Er komt geen extra formulier, bevestigingspagina of processtap.

## Rewrite mitigation
Rewrite target: gedeelde review-/correctieovergangen en verspreide disposition-/follow-upregels.
Why local patching is insufficient: losse statusschrijvers en wrappers laten alternatieve native ingangen, steunherstel en directe base-correctieaanroepen langs verschillende regels lopen.
Current authority/writer/reader map: ReviewClosureConsole.review_object → execute_review_command/ReviewCommandState → DeterministicRepairReviewConsole → ClosedLoopReviewConsole → ProportionateReviewConsole → OperationsConsole.review_object; approve_second_review, confirm_object_type, correct_object; private _apply_review_state en revise_object als voorbereiding; _commit_knowledge_change en bestaande support-/mergehelpers; bestaande workflow store bundle/binding/audit owners. UI: KO-2-kaart/bon, bestaande batch-/beslisboom-/legacy commandproducenten. Read: KO-state, review_duty, readiness, receipt evidence. Source-role single/batch/group/reset blijven #942. Canonieke publicatie/registry en hun herstel blijven ongewijzigd.
Supported runtime topologies: alleen ondersteunde PostgreSQL-workflow, één/twee workers, lokale immutable source store en bestaande Azure-adapter met lokaal testtransport. Lokale proeven zijn geen Azure-productieclaim.
Persisted-state impact: geen schema/identiteitsmigratie of extra statusautoriteit; additief exact reviewbewijs in bestaande bindingJSON/audit. Nieuwe correcties slaan needs_review op hun opvolger op; historie wordt niet herschreven.
Compatibility/migration plan: codecutover per bestaande command naar één guard met bestaande writer; noodzakelijke aanpassing van ondersteunde producers/fixtures aan expliciete antwoorden, geen verborgen autofill in productie. Oude records leesbaar; oude echte replay herkenbaar. Broncontextslice pas na #942.
Rollback/recovery plan: vorige image op dezelfde database blijft bestaande bindings lezen; additieve bewijsvelden blijven behouden, geen destructieve cleanup. Native rollback/restartproeven bewijzen dat er geen halfbesluit of extra akkoord ontstaat.
Cutover trigger: alle unit/native/live/perf/CI- en adversariële gates op exacte PR-head groen, zichtbare kaart/bon-video en operatorreview. Geen autonome merge/deployment.
Cleanup/decommission criteria: geen nieuwe opgeslagen revise; verspreide suitability/follow-upguards vervangen door centrale regels; geen alternate approveturn die drie antwoorden/onderbouwing omzeilt. Legacy readers/herstel blijven alleen waar aantoonbaar vereist. #942-broncommands zijn expliciet pending, niet claimen als geconsolideerd.
Failure blast radius: review, typebevestiging, gerichte correctie, steunrelaties en merge van ongepubliceerde KOs; geen servingactivatie of mutatie van gepubliceerde gegevens.
Adversarial proof matrix: directe en HTTP-ingangen, MRO/basecalls, eerste/tweede review, alle drie negatieve/missende antwoorden, ongeldige N/A/relaties, oude versie/hash/snapshot/actor, exact replay vs nieuw besluit, support/classificatie zonder tussentijds revise, merge, twee workers, geforceerde commitfout, worker-crash, restart, oude records en coderollback.

## Lifecycle slice
Lifecycle entity: huidige ongepubliceerde WorkingRevision met exacte KO-tuple en reviewbindingen.
Lifecycle transition: open huidige tuple → expliciet toegestaan akkoord op uiteindelijke tuple → Goedgekeurd of Tweede review volgens bestaand beleid; gerichte correctie → nieuwe open opvolgerversie met oude versie als historie, daarna opnieuw review.
Initial durable state: native PG-snapshot met open/ontbrekende onderbouwing of bestaande eerste review; eventueel actieve oudere release van dezelfde documentlijn.
Trigger: bestaande bevoegde reviewer verstuurt de kaart of een ondersteunde native review/correctiecommand.
Authorization: actuele actieve/named reviewer en bestaand primary/independent-second beleid, opnieuw gecontroleerd binnen bestaande commandgrens.
Validation: exacte bron/snapshot/objectversie/hash/CAS, drie expliciete ja-antwoorden bij KO-akkoord, geldige bevestigde onderbouwing of expliciete N/A; bestaande source/type/disposition/closure/repairvoorwaarden.
Mutable entities: alleen huidige ongepubliceerde objectopvolgers, exacte goedkeuringsbindingen en bestaande ledger/projecties via bestaande writers.
Immutable entities: bronbytes/snapshotidentiteit, gepubliceerde releases/tuples/hashset en historische besluiten.
Workflow state before: in_review of blocked met open review/correctiewerk.
Workflow state after: alleen bij werkelijk afgeronde bestaande curator-/technische gates ready_for_publication; anders open/blocked. Correctie opent nieuwe review; geen publication command.
Release state before: geen huidige release, eventueel gepubliceerde voorganger.
Release state after: ongewijzigd; review is geen publicatie.
Serving state before: bestaande actieve voorganger of geen release.
Serving state after: ongewijzigd; uitsluitend de bestaande registry beslist serving.
Expected API result: bestaande serving blijft identiek; ongepubliceerde/gewijzigde werkversie wordt niet geserveerd.
Expected UI result: duidelijke weigering zonder bon; geldige commit geeft bon van exacte opgeslagen versie; correctie toont nieuwe open versie. Onderbouwing/N/A blijft herkenbaar, geen extra formulier of verplichte tweede reviewer.
Failure result: bestaande transactie rolt object/binding/audit samen terug; geen gedeeltelijke goedkeuring, N/A-feit of nieuw event bij weigering.
Restart result: uitsluitend volledig bevestigde review-/correctiebesluiten blijven bestaan, geen nieuwe reviewbeslissing door startup.
Recovery result: bestaande recovery mag geautoriseerde technische commit afronden maar geen reviewerbesluit of publicatie verzinnen.
Legacy-data result: regel geldt voor ieder volgend akkoord op bestaande ongepubliceerde KOs; oude publicaties onveranderd. Bestaande echte revise wordt niet stilzwijgend als afgerond beschouwd; geen backfill/migratie.
Required black-box scenario: GIVEN open KO zonder onderbouwing WHEN reviewer probeert akkoord THEN weigering zonder writes; WHEN reviewer echte onderbouwing bevestigt of expliciet N/A kiest en drie ja-antwoorden opslaat THEN exact akkoord+binding+bon atomair; WHEN die KO gericht wordt gecorrigeerd THEN nieuwe open versie en oude binding ongeldig; restart bewaart ieder volledig resultaat.
Explicit non-goals: #942-bronrolconsolidatie/broncontextfase, KO-5/6, destructieve migratie, nieuwe opslag of transactieautoriteit, publicatieactie #991, merge/deployment, autonome productie-inventaris.

Part of MET-56.


## Context en geldigheid bij de commandgrens
| Gegeven | Eigenaar / overdracht | Geldigheid en verval |
|---|---|---|
| Snapshot, object-id/versie/hash | Bestaande ReviewCommand-input en exacte binding | Dezelfde huidige tuple; materiële opvolger maakt oude binding ongeldig |
| Verwachte revisie en actor/policy | Bestaande PostgreSQL-command/CAS | Binnen de bestaande transactie opnieuw gecontroleerd; oude invoer weigert |
| Drie antwoorden | Expliciete ReviewAssessment van huidige reviewer | Alle drie ja voor ieder nieuw KO-akkoord; nooit impliciet ingevuld |
| Onderbouwing/N/A | Uiteindelijke bevestigde relaties of eigen expliciete keuze op nieuwe binding | Alleen huidige versie/doelversie; keuze van vorige reviewer geldt niet als nieuwe keuze |
| Reparatiecontext | Private gevalideerde in-command context | Alleen actor/snapshot/object van deze atomaire command; reset bij verlaten scope |

De bestaande expliciete steunreparatie schrijft nog legacy confirmed_relations. Binnen diezelfde reparatie wordt de actuele, brongebonden claim als open opvolger via de bestaande relationbuilder en bestaande _commit_knowledge_change voorzien van versiegebonden relaties. Dat is geen algemene backfill: alleen de expliciet gerepareerde claim verandert, blijft onbeoordeeld en moet daarna de normale relation-ack/assessmentcontrole doorlopen. Er komt geen tweede relatieschrijver of nieuwe transactie.

## Aanvullende gegronde ingangen en relatierichting
De bestaande publieke confirm_relations-command gebruikt dezelfde relationpreparer die binnen review_object voorkomt. Alleen de publieke command krijgt een centrale confirm_relations-overgang en controle van zijn voorbereide opvolger; de private helper blijft voorbereiding binnen dezelfde goedkeuring. Ook de bestaande later-commit wordt centraal gecontroleerd. Dit voegt geen nieuwe actie of schrijver toe.

De actuele D4.2-eigenaar knowledge_relation_proposal_v1 definieert explains als claim naar context met doeltype explanation. Daarom telt de uitgaande bevestigde explains-relatie mee als onderbouwing van de claim. Een inkomende explains-relatie is niet automatisch onderbouwing van het doelobject. De kaart/bonlabels worden op deze bestaande regel aangesloten; de opgeslagen relaties worden niet omgedraaid. Alleen geldige huidige versiegebonden bevestigde relaties voldoen aan het nieuwe akkoordguard; geen promotie van losse legacy- of voorstelregels.

Bij expliciet reviewbeleid met meerdere verplichte mede-beoordelaars kan ook een tweede-reviewbijdrage de afgeleide toestand Tweede review behouden tot alle bestaande vereiste actuele akkoorden aanwezig zijn. De overgangstabel controleert deze werkelijke voorbereide na-toestand met de bestaande deriver; zij schrijft geen vast label of nieuwe reviewerregel.

Expliciet aangeleverde antwoorden worden vóór de replaybeslissing genormaliseerd en gevalideerd. Twee aanwezige antwoorddragers moeten overeenkomen; tegenstrijdige interaction-evidence en command-antwoorden weigeren atomair. Nieuwe commandhashes omvatten de genormaliseerde antwoorden. Alleen een werkelijk oud identiek voltooid command zonder nieuw aangeleverde antwoordfeiten behoudt zijn historische replaypad; een nieuw nee-antwoord is geen replay van een eerder ja-besluit.
