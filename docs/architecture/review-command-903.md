# WP6 — begrensde Review-command

Change class: B. Rewrite risk: high. Touches lifecycle invariants: no.
Issue: #903 / MET-24. Basis: `7adb588`, inclusief WP5 / #914.

## Probleem en gebruik

De bestaande `review_object`-MRO blijft de domeineigenaar. PostgreSQL bezit
objecthistorie, exacte bindings, documentbeleid en de hashgeketende audit.
HTTP bezit uitsluitend formulierinvoer en verliesbare presentatiestate.

```python
# Nieuwe passageformulieren: direct de compacte precondition controleren.
console.review_object(actor_id=actor, snapshot_id=sid, object_id=oid,
    expected_revision=generation_token, decision="approve", ...)
# Bestaande kernelcallers blijven hun m2-token en lijstresultaat gebruiken.
console.review_object(actor_id=actor, snapshot_id=sid, object_id=oid,
    expected_revision=legacy_objectset_token, decision="reject", comment=reason)
```

Een compacte formulierprecondition, strikte command-equality en disjuncte
storage-merge zijn drie verschillende contracten. De nieuwe POST vertaalt
generatie niet via de volledige historie naar m2. De expliciete legacyadapter
mag voor oude m2-callers de volledige gelijkheidscontrole behouden; hij mag
geen fallback van de compacte route worden.

## Onderzochte werking

`ReviewClosureConsole` controleert mutability; `DeterministicRepairReviewConsole`
onderschept gestructureerde revise vóór writes; `ClosedLoopReviewConsole` doet
aanvullende reopen/repair/auditwrites; de basiskernel voert het besluit uit.
De command moet deze volledige keten omvatten. De huidige storecommand herlaadt
globale maps, de tokenadapter leest alle historie en `write_bundle` vervangt
de volledige objectset. Deze stappen worden op de overgezette route vervangen.

## Vorm en eigenaarschap

`ReviewCommandInputs` is een expliciete, losgekoppelde baseline: owner,
snapshot, precondition, compacte envelope/counters, volledige historie van de
benodigde objectidentiteiten, bindings en vooraf geverifieerde broninputs.
`ReviewChangeSet` bezit de veranderlijke werkstate van één command en de
gestagede object-, binding- en envelopewijzigingen. Een owner-gecontroleerde
ContextVar verbindt bestaande kernelgetters met die state. Shared
`_bindings`/`_envelopes` worden niet tijdelijk vervangen of als werkbuffer gebruikt.

De bestaande MRO en validators blijven actief. De bestaande commitoperatie
stageert binnen deze command. Eén native deltawrite volgt nadat ook het
postprocessingwerk is geslaagd; de bestaande ledgerbuffer houdt audit atomair.
Ontbrekende dependencies worden expliciet verzameld, nooit door een verborgen
volledige documentread aangevuld.

Dependencyverzameling begint bij doel en expliciet gekozen relaties/ouders.
Zij omvat actuele/verwijderde kinderen die een ouderbevestiging kan raken,
broncontextrecords, inkomende support en noodzakelijke structuurvalidatie.
De GET-picker en alle documentkoppen vormen geen commandclosure. Een gedeelde
ouder is geen reden om alle onafhankelijke kinderen te laden. Historie behoudt
appendvolgorde, legacy occurrences, predecessors en bestaande immutabilitychecks.

## Varianten en actuele context

| Gegeven | Eigenaar en geldigheid |
| --- | --- |
| Bronbytes, extractie en mapping | Bestaande onveranderlijke bronowner; voorbereiding vóór storelock/transactie, gepind aan sha256/versie/contract. |
| Rol en named reviewer | Bestaande identity-/documentowner; actuele rol met FOR SHARE en documentbeleid binnen command controleren. |
| Objecten en context | Volledige historie van betrokken identiteiten onder de documentgrens; geen hoogste-semverprojectie. |
| Bindinggeldigheid | Actuele gerichte PostgreSQL-read; documentgeneratie vervangt deze controle niet. |
| Interaction-ID | Globale identitycheck via gerichte ID-query inclusief pending events; geen payloaddeduplicatie. |
| Audit | Bestaande globale hashketen en late flushvalidatie; geen automatisch herbaseren bij chain conflict. |

Een normale save commit alleen bestaande semantisch vereiste wijzigingen.
Validatie en stale/conflict laten geen half besluit achter; rollback gooit de
commandstate weg en herstart leest dezelfde PostgreSQL-authority.
`later` behoudt zijn expliciete commit/generatie-effect zodat het oude formulier
409 blijft geven; een exact semantic-duplicate fastpath blijft zonder write.
Oude lijstresultaten worden expliciet behouden; de HTTP-route gebruikt een
compact resultaat en de GET verzorgt de volgende taak.

## Lockvolgorde en mitigatie

Gekozen familie: authorization advisory → documentrij → relevante accountlocks
→ ledger. Dit sluit aan op de bestaande bindingwriter en headingbatch.
Context/exclusion en lock-row-storecommands moeten authorization vóór hun
documentlock nemen. Compatibiliteitswriters/global restore blijven onderdeel
van de lockinventaris; document-FK-locks na een globale authorizationlock zijn
een reden om niet alleen de gewone reviewwriter naar de omgekeerde orde te zetten.
Bron-I/O en reconstructie vinden vóór deze locks plaats. Er is geen nieuwe lockowner.

Rewrite target: bestaande gedeelde command en opslaggrens, niet publicatiebeleid.
Lokale HTTP-only reparatie is onvoldoende wegens kernelreload/full-set writes.
Authority/writers/readers: `WRITERS-902.md`, de genoemde MRO, review/second/batch,
context/repair/participatie, vormingsactivatie en publicatie blijven leidend.
Topologieën: beide FastBadge CompleteWorkflow PostgreSQL-composities met lokale
of Azure-bronadapter en onafhankelijke processen; geen filefallback.
Persisted impact: geen nieuwe authority of historische backfill; gerichte writes
behouden bestaande rijen/posities. Eventuele additieve index wordt afzonderlijk
gespecificeerd vóór toevoeging. Rollback gebruikt de bestaande compatibele writer;
geen revisiereset, blind compensating write of destructieve migratie.

Cutover vereist native verschilbewijs, concurrency/restart/publicatierace,
alle repositorychecks en een afzonderlijke adversariële review. Opruiming verwijdert
de full-set reads/save en next-task-bronlus uit de overgezette POST; oude expliciete
compatibiliteitsingangen blijven benoemd. Foutbereik is de betrokken ongepubliceerde
WorkingRevision; andere en gepubliceerde documenten blijven beschermd.

## Vergelijking en uitvoering

Twee afzonderlijke agents onderzochten A (expliciete commandinputs/changeset) en
B (scoped store-unit-of-work/consoleview), met dezelfde broncode en opdracht.
Dit zijn afzonderlijke agentanalyses, geen cross-model consensus of runtimetests.
A is gekozen wegens expliciet ownership, zichtbare dependencysets en behoud van
de bestaande MRO. B verliest: tijdelijke maps, lazy getters of een consoleclone
verbergen queries en delen/copyen TLS, locks en bound-methodstate. Na noodzakelijke
aanpassingen is B feitelijk complexer dan A. Er komt geen nieuwe servicefaçade.

Veilige subtractie: geen losse cleanup vóór gedrag/pariteit bewezen is.
Noodzakelijke basis: alleen commandtypes, gerichte capture/delta en lookupinterfaces.
Daarna kerneladapters, compacte POST/foutrespons, lockorde en expliciete cutover.
Agree: uitvoering is door William opgedragen; geen extra ontwerpgoedkeuring nodig.
Scrap: terug naar ontwerp bij ontbrekende closure, tweede authority, gewijzigde
lifecyclebetekenis of herhaalde workarounds voor verkeerd ownership.

## Bewijsplan en actuele status

| Claim | Beslissende proef |
| --- | --- |
| Dezelfde betekenis | Volledige WP5-matrix: success/400/409, binding-only, rol/context, revise/reject/later/second/batch. |
| Atomaire opslag | P9021/P9022 en faults tussen object/binding/audit; durable state/generatie en verse compositie. |
| Begrensd werk | Vaste doel/dependencies bij 32/128 kandidaten: geen onaangeraakte payloadread of full-set DELETE/reinsert. |
| Geen lockcyclus | Onafhankelijke native processen, bindingdelta plus negatieve controle; account-/publicatierace. |
| Kosten | Bestaande WP5 observer en inputhashes; POST ≤3000ms, lockhold ≤250ms, transactie ≤500ms als technische doelen. |
| Geen semantische bypass | Legacy m2, storage merge, bron/closure/publicatieguards; adversariële controle vóór afronding. |

Uitgevoerd vóór productiewijzigingen: vier native WP5-referentiegevallen groen
(beide lockkarakteriseringen en complete/incomplete task-v1). De positieve
lockkarakterisering vereist nog de bestaande40P01 en is dus geen veiligheidsbewijs.
Implementatie en nieuwe acceptatieproeven volgen; geen WP6-afronding geclaimd.

## Vooraf gespecificeerd toegangspad voor globale interaction-identiteit

De bestaande identityregel vergelijkt een interaction-ID ook met audit uit andere
snapshots. `read_review_command_events` behoudt die globale vergelijking via
`event_payload#>>'{details,review_interaction,interaction_id}'`; uitsluitend op
snapshot filteren zou een bestaande conflictcontrole verwijderen. De huidige
schema-indexen dekken deze expressie niet. De OR met de object/snapshot-lookup kan
daardoor alle globale auditpayloads laten inspecteren.

Migratie `025_review_interaction_identity_lookup.sql` voegt daarom uitsluitend de
niet-unieke B-tree-index `workflow_review_events_interaction_identity` toe op
`workflow.review_events ((event_payload#>>'{details,review_interaction,interaction_id}'))`,
met partial predicate dezelfde expressie `IS NOT NULL`. Geen uniquenessregel,
receipt, tweede identityautoriteit, gewijzigde auditpayload of historische
backfill. De bestaande globale ledger en validator blijven eigenaar.

De migratie is idempotent en wordt geregistreerd in de bestaande gecontroleerde
migratielijst; zij hangt alleen af van de reeds bestaande event_payload-kolom.
Schema-expansie gaat vóór cutover; de oude writer/readers kunnen deze index laten
staan bij code-rollback. Production/Azure-apply blijft buiten deze opdracht.
Native verificatie toetst ongewijzigde globale conflictuitkomst, behouden events
en een PostgreSQL-plan met indexgebruik bij veel onafhankelijke auditrecords.
Er wordt geen object-position-index toegevoegd: het huidige MAX(position) levert
slechts de appendpositie zonder objectpayloads over te dragen; noodzaak voor een
extra index is nog niet aangetoond.

Expliciete parentbevestiging en impliciete `documentpositie_action=dit_klopt`
gebruiken alle huidige headings als structurele afhankelijkheid: de bestaande
TOC/body-inferentie hangt ook van voorafgaande headings af. Deze set groeit met
het aantal headings. De commandlookup selecteert eerst de laatste appendpositie
per object, controleert dan heading/path-typevelden en laadt uitsluitend van die
identiteiten de volledige, opnieuw gevalideerde historie. Oude headingrevisies
van huidige niet-headings maken de commandset niet groter. De conservatieve
GET-lookup blijft ongewijzigd.
