# MET-42: actuele passagecontext en expliciete documentbeoordeling

Change class: A
Rewrite risk: high
Touches lifecycle invariants: yes
Promise: De MET-42 leesgrens levert actuele volledige vereiste passagecontext binnen bestaande budgets; volledige documentbeoordeling/publicatie behoudt dezelfde kernel en complete input. Het overkoepelende doel omvat ook beoordelen, redirect en heropenen zonder vertraging; dat doel blijft open zolang het commandpad faalt.
Proof: Rode native dependency-query op 1100 versies/18.6 MB wordt groen; de gecombineerde HTTP-keten met partial formation en historische versies blijft rood op POST-latency, ook na compacte opslagovergang. Zie evidence/review-scoped-951/README.md. Geen volledige ketenacceptatie.

## Ground → Sketch → Agree → Implement → Scrap

- Ground: productie 1.1.513 / main 5a1ec16d, QueryCanceled57014 in review_neighbor_ids; 5481ms, 425841 ontvangen JSONbytes. Eén aanvraag met dubbele logkopie.
- Ground: lokale exacte storemethode met 1100 rijen/18.6MB, 150 object-/blocktargets: 5.0103s QueryCanceled onder oorspronkelijke 5s-transactie. Seq Scan per probe. Commandlookup heeft eigen latest-positionfilter.
- Sketch: onderstaande alternatieven en eigenaarschap vóór productcode.
- Agree: William heeft MET-42 expliciet aangewezen, uitvoering eerder opgedragen en veilig naar publicatie als doel bevestigd. Geen extra ontwerpcheckpoint gevraagd. Geen merge-, deployment- of productiemigratie-GO.
- Implement: nog open; geen gebruikersacceptatie uit een snelle SQLproef afleiden.
- Scrap: oude per-probe grote-payloadread verwijderen uit beide actieve lookups; geen generiek query-/cacheframework.

## Gebruik vóór interne vorm

```python
passage = read_review_passage(console, reviewer, sid, focal_id)
# Same captured generation; required CURRENT dependency component,
# full histories for lineage of selected identities; picker is display input.
console.review_object(..., expected_revision=passage.revision)
# Existing live actor, source, policy and revision guards; same object owner.
console.publication_readiness(sid)
# Complete coherent document input; original unresolved_rejections authority.
```

## Kandidaten en metingen

A: bestaande payload + GIN, queryvorm aanpassen; geen nieuwe fysieke representatie. Lokale ANY-variant faalt ook op 5.0134s bij 150 targets. Tijdelijk MATERIALIZED afleiden van dependencyvelden geeft 0.1922s met dezelfde dependency-uitkomst, maar blijft elke ronde afhangen van omvang van alle overige actuele payloads. Daarmee geen blijvende isolatie van ongerelateerde objectinhoud.

B: één compacte, door PostgreSQL GENERATED ALWAYS afgeleide dependencywaarde per oorspronkelijke objectversie, onder document_objects. Objectpayload blijft enige authority; geen applicatiedualwrite. Actuele versies selecteren via position, volledige geselecteerde historie daarna aan current_revisions. Lookup raakt niet het grote payload. Geen envelopecutover nodig om deze lookup te gebruiken.

Synthesis: B voor de fysieke grens; expliciete huidige afhankelijkheden en scheiding picker versus noodzakelijke context apart met full-current oracle toetsen. Beide kandidaten zijn door hoofdagent onderzocht, plus een aparte read-only agent met hetzelfde model; geen cross-modelconsensus. Geen truncatie van werkelijk benodigde context. Een MATERIALIZED SQLsnede wordt niet als eindoplossing verpakt.

Geaccepteerde afweging: één additieve gegenereerde kolom/index en gecontroleerde schemaovergang voor stabiele kleine lookup-I/O en onderhoud door alle bestaande writers. Geen eigen dependencytabel, geen herbouwdoorGET, geen completionboolean.

## Gegevens en betekenis

- `document_objects.payload` en objectidentiteit/versie/position blijven gezaghebbend.
- Afgeleid `review_dependency_keys`: JSONB `{objects:[typed target values], blocks:[typed block values]}`. Objects is de unie van de vier bestaande relationfamilies en confirmed_source_context.source_object_id; blocks komt uitsluitend uit source_bound_context.entries[*].span.block_id.
- Positieve containmentsemantiek behouden, inclusief JSONtypes, null versus absent, duplicaten en niet-arraywaarden; geen tekstnormalisatie of afgeleid kandidaatschap.
- Alle historische rows blijven bestaan. Current lookup selecteert alleen hoogste bestaande position per object_id; volledige historie van geselecteerde identiteiten wordt daarna gevalideerd. Historische weergave heeft expliciete historische input, geen bevoegdheid uit een oud relationlid.
- Passage-invoer en documentbeoordeling krijgen afzonderlijke resultaatvarianten. Niet geëvalueerde documentscope is geen complete/incomplete uitkomst. Een passagewindow wordt niet aan de documentkernel aangeboden als complete bron.
- Contextkeuzes zijn expliciete weergave-DTO's zonder objectversie/hash/reviewauthority. Gekozen doelen en bestaande koppelingen blijven volledige noodzakelijke context, ook buiten de pagina. Een bron met bestaande contextrol kan voor een extra doel worden gekozen.
- Complete compacte documentcapture legt pogingen en verwijzingen vast in hetzelfde SQLsnapshot als objecten/bindings. Immutable bewijs wordt daarna met deze pins gelezen; geen tweede actuele-pogingenread tijdens rendering. Iedere nieuwe passage-/documentcapture wist eerdere request-lokale processinginput voor die snapshot.

## High-risk grenzen

Rewrite target: Gedeelde passage-/commanddependencylookup en passage-versus-documentassessmentgrens.
Why local patching is insufficient: Timeout verhogen of LATERAL door ANY vervangen laat omvang-/TOASTafhankelijkheid bestaan; alleen envelopecutover verandert deze falende query niet.
Current authority/writer/reader map: document_objects owner: write_bundle/_save_objects/_commit_prepared_store, native apply_review_changes/delta, produceractivatie, bron/context/relationcommands en expliciete restore/legacywriters. PostgreSQL generated value leidt op iedere payloadINSERT/UPDATE dezelfde keys af. Readers: review_neighbor_ids/command-neighbors, passagecapture/rendering, commandcapture/current_revisions. Formatie: FormationTaskStore input + recoverable_formation_v1.unresolved_rejections. Publicatie: bestaande readiness, durable publication en registry; nooit de dependencyprojectie.
Supported runtime topologies: beide FastBadge CompleteWorkflow PostgreSQL-composities, lokale/Azure bronadapter, huidige toegestane workers op één instance; geen nieuwe multi-hostgarantie.
Persisted-state impact: additieve afgeleide objectkolom/index; bron/objectpayload/hashes/reviews/proof/release/serving ongewijzigd door DDL. Passage-read schrijft geen domeintoestand.
Compatibility/migration plan: DDL expliciet vóór code via bestaande geregistreerde migratierunner/preflight; bestaande rows afleiden onder PostgreSQL-DDLtransactie. Nieuwe code vereist schema; geen stille payloadfallback. Bestaande payloadwriters hoeven geen tweede waarde te schrijven.
Rollback/recovery plan: native rollback van objectpayload en afgeleide keys als één rowwrite. Oude binary negeert afgeleide kolom en kan oorspronkelijke payload blijven lezen/schrijven. Legacybackup/restore bouwt dezelfde waarde uit payload; geen nieuwe authority-backup of reset. Productie uitsluitend volgens deploymentprotocol, afzonderlijk GO.
Cutover trigger: gecontroleerde schema-/privilegeverify PASS en compatibele code, geen GET/startupcutover of verwerking van bron opnieuw.
Cleanup/decommission criteria: per-probe full-payloadlookup uit beide actieve routes weg; bestaande payloadGIN behouden waar andere lezers hem gebruiken. Geen archief-GC of verwijdering historische data.
Failure blast radius: betrokken read/command expliciet unavailable/conflict; geen foutieve bronclosure, verloren besluit, nieuwe release of servingwijziging.
Adversarial proof matrix: beide MROs, alle write-ingangen inclusief oude directe SQL, type/null/duplicate/arraygevallen, historische/new current edges, stale generatie/actor, gewijzigde bron, fout na write, restart/backuprestore; grote payload/historie/probes en exacte dependency-/domeinpariteit.

## Lifecycle slice

Lifecycle entity: bestaande SourceSnapshot/WorkingRevision, bestaande bron- en reviewbindings.
Lifecycle transition: geldige passagebeoordeling via bestaande review_object; de reader levert actuele coherente input zonder documentclosure te verzinnen. DDL voegt alleen een derived access path toe.
Initial durable state: oorspronkelijke objecthistorie/bron/proof/menselijke besluiten en eventuele immutable vorige release.
Trigger: bestaande geautoriseerde passage-GET of review-POST.
Authorization: named reviewer en actuele rol/retirement/policy; POST hercontrole onder bestaande doclock.
Validation: current_revisions, bronintegriteit, bestaande reviewkernel en generation/revision-CAS; documentclosure alleen met complete input aan oorspronkelijke owner.
Mutable entities: uitsluitend bestaande geautoriseerde review-/object-/bindingwijzigingen bij POST; derived keys atomair mee.
Immutable entities: bronbytes, oorspronkelijke historie en alle gepubliceerde release-inhoud.
Workflow state before: bestaande processing/in_review/blocked/ready.
Workflow state after: GET onveranderd; POST uitsluitend bestaande kerneluitkomst, geen nieuwe betekenis van ready.
Release state before: bestaande none/published/superseded/withdrawn.
Release state after: onveranderd door read/review; bestaande expliciete publicatie blijft enige releasewriter.
Serving state before: registry bepaalt actief/inactief.
Serving state after: onveranderd door deze read/write-grens.
Expected API result: bestaande objectcontext of expliciete fout; POST exact bestaand besluit/conflictresultaat.
Expected UI result: passage met noodzakelijke broncontext en opgeslagen besluit; documentassessment afzonderlijk en niet geëvalueerd als hij niet is berekend.
Failure result: geen half object/projectie/binding, geen impliciete closure; oude review blijft intact.
Restart result: dezelfde objecten, derived keys, besluiten en actieve registrytoestand.
Recovery result: originele payload hersteld via bestaande owner, keys deterministisch gegenereerd; geen modelwerk of nieuw curatorbesluit.
Legacy-data result: bestaande objecten afleiden zonder herinvoer, identities/hashes/historie behouden; legacyformation apart correct niet-voorbereid/incompatibel behandelen.
Required black-box scenario: 25MB partial formation + 1100 versies → passage GET → geldig besluit → redirect → opnieuw openen → complete documentassessment met echte/onbekende bronbevindingen → juiste publicatie-uitkomst, met oorspronkelijke budgets en twee broncomposities.
Explicit non-goals: Geen gewijzigde closure-/publicatievoorwaarden, tweede kandidaatcreator, herinvoer, timeoutverhoging, bewijsverwijdering, nieuwe cacheauthority of impliciete productiecutover. De rode gecombineerde POST-proef blijft een expliciete ketenblokkade.

## Pad naar publicatie

| Stap | Afhankelijkheid | Bewijs | Stand / resterende duur |
|---|---|---|---|
| MET-42 actuele passage/dependencies + scope | MET-40/41 | hierboven beschreven rode→groene caller en kernelpariteit | actief; onbekend |
| MET-43 kort/bounded muteren waar vereist | actuele scopecontracten | dezelfde POST/redirect, lock-/bron-/besluitbehoud | afhankelijkheden in #952 toetsen; onbekend |
| MET-44 bestaand Smetten + eindketen | #951/#952 | originele menselijke besluiten + gemeten live Review/publicatie | nog open; onbekend |

Dit is een voorlopig afhankelijkheidspad, geen berekende CPM-doorlooptijd: duur en externe review/deploymentwacht zijn niet vastgesteld. Volgende blocker: de daadwerkelijk falende dependencycapture en expliciete scope. Geen extra project of acceptatieauthority.
