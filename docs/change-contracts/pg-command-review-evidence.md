# Reviewreparatie leest haar eigen voorbereide bewijs

Change class: A
Promise: een geautoriseerde atomaire onderbouwingsreparatie kan haar eigen voorbereide reviewbewijs lezen, commit beide betrokken objecten en audit samen, en blijft na herstart gelijk.
Proof: echte PostgreSQL/HTTP-onderbouwingsreparatie, hashketen, herstart, late fout met exacte rollback; geneste buffers en een onafhankelijke verbinding/thread.
Touches lifecycle invariants: yes
Rewrite risk: high
Rewrite target: de leesgrens van `_latest_review_signal` (closed_review_loop_v1), die van de gecommitteerde ledgerweergave naar een commandlokale weergave gaat: gecommitteerde PG-events plus de voorbereide events van de huidige commandbuffer.
Why local patching is insufficient: het `revise`-bewijs van `submit_review_resolution` staat binnen hetzelfde commando alleen in de PG-eventbuffer; zonder lezer die die buffer ziet faalt de atomaire onderbouwingsreparatie altijd met `support_disposition_required`, en committen vóór het lezen zou de atomaire commandgrens breken.
Current authority/writer/reader map: autoriteit is `workflow.review_events` in PostgreSQL (hashketen). Schrijvers: alleen `PostgresWorkflowReviewStore.append_event` via `buffered()`/`_flush_buffer`, ongewijzigd. Lezers: `read_events`, `read_events_after`, `verify_ledger`, audit-export, polling, startup, publicatie en recovery blijven gecommitteerd; de enige nieuwe lezer `read_command_events` wordt alleen aangeroepen door `_latest_review_signal` (brongebonden correctie en support-resolutie). Buiten een commando geeft hij exact `read_events` terug.
Supported runtime topologies: PostgreSQL-productieconsole lokaal en op Azure (beide in de proef); de bestandsledger zonder PG-backend valt via `review_ledger.read_command_events` terug op `read_events` en houdt het oude gedrag.
Persisted-state impact: geen; geen schema, migratie, backfill, identiteit of nieuw persistent formaat. Voorbereide events worden alleen als kopieën gelezen en pas bij de bestaande buitenste flush gecommitteerd.
Compatibility/migration plan: additief; de oude gecommitteerde lezers blijven naast de nieuwe bestaan en houden hun contract. Geen dual-write, geen tweede autoriteit: de buffer is een uncommitted voorbereiding binnen één transactie, geen cache.
Rollback/recovery plan: terugdraaien is een code-revert van 4cd6f62 zonder datawerk, omdat er geen persistente toestand bij komt. Na revert faalt de support-reparatie weer met `support_disposition_required` (het oorspronkelijke defect) zonder half commando; gecommitteerde relaties en audit blijven geldig en door de oude code leesbaar.
Cutover trigger: deploy van de commit; geen flag, geen datamigratie. Elk volgend commando gebruikt de nieuwe lezer, geen lopend commando overspant de deploy.
Cleanup/decommission criteria: niets uit te faseren; de gecommitteerde lezers blijven de publieke auditgrens. Als de bestandsledger-fallback verdwijnt, vervalt de `read_events`-terugval in `review_ledger.read_command_events`.
Failure blast radius: beperkt tot commando's die `_latest_review_signal` aanroepen. Een fout in de lezer weigert dat commando (geen commit); een te ruime lezer zou bewijs van een ander commando kunnen zien, wat de thread-/verbindingsproef uitsluit. Andere commando's, publicatie, serving en recovery lezen niet via deze lezer.
Adversarial proof matrix: (1) andere thread/verbinding ziet geen voorbereide events; (2) mislukte nested buffer is na afbreken onzichtbaar, geslaagde child verschijnt eenmaal in parent; (3) gelezen events zijn kopieën, mutatie raakt de buffer niet; (4) late auditfout rolt objecten, envelope, bindings en audit exact terug; (5) herstart geeft identieke gecommitteerde toestand; (6) rol-, named-reviewer-, revision- en doelguards weigeren zonder PG-schrijfactie; (7) `read_events`/`verify_ledger` blijven alleen gecommitteerd lezen; (8) beide productieklassen (lokaal en Azure). Zie `tests/test_pg_command_review_evidence.py`.

Dit is een afzonderlijke voorwaarde die D6a blootlegt, geen onderdeel van de
Class C-testmigratie of de D6b-cutover. De reproductie op de productieklasse
faalt met `support_disposition_required`: `submit_review_resolution` schrijft
het `revise`-bewijs in de bestaande commandbuffer; `resolve_support_relation`
zoekt het via `_latest_review_signal`, die alleen gecommitteerde events ziet.
De proef gebruikt geen bestandsautoriteit of gefingeerde workflowstore.

Bestaand mechanisme: `_PostgresWorkflowReviewMixin._store_command` bezit de PG-
transactie en geneste eventbuffers. `PostgresWorkflowReviewStore.append_event`
hasht voorbereide events en flusht alleen de buitenste geslaagde buffer. Een
mislukte nested buffer wordt verworpen. `review_ledger.read_events` en
`read_events_after` zijn gecommitteerde audit-lezers en blijven dat.

De correctie voegt uitsluitend een expliciete commandlezer toe: dezelfde
gecommitteerde PG-events plus de eventbuffer van de huidige ContextVar-context,
in parent-naar-child-volgorde en als kopieën. Alleen `_latest_review_signal`
gebruikt deze lezer (aanroepen: brongebonden correctie en support-resolutie).
Een ander commando, een andere thread/verbinding, audit-export, polling,
ledgerverificatie, startup, publicatie en recovery krijgen geen nieuwe leeswijze.
De bestandsbackend blijft tijdens D6a haar bestaande gecommitteerde lezer gebruiken.
Er is geen nieuwe schrijver, cacheautoriteit, identiteit, schema, migratie of
transactiegrens. De gedeelde reviewleesgrens van `_latest_review_signal` en de
uitkomst van een lifecycle-reparatie veranderen wel; daarom is dit volgens
AGENTS.md `Rewrite risk: high` (Codex P1 op #803) met de mitigatie hierboven.

Lifecycle entity: de bestaande WorkingRevision, twee reviewobjecten en hun reviewbewijs.
Lifecycle transition: de bestaande `alleen_onderbouwing`-reparatie registreert `supported_by` en heropent beide objecten voor review, atomair.
Initial durable state: één ongepubliceerde snapshot, twee bestaande bronpassages, een bevoegde aangewezen reviewer; geen support-relatie.
Trigger: POST `/review/resolve` met het bestaande support-repair-kind, de actuele revision en een expliciet doelobject.
Authorization: bestaande reviewerrol, named-reviewercontrole en published-immutabilitycontrole, ongewijzigd.
Validation: bestaande bron-, doel-, revision-, suitability- en commandvalidatie; geen gate wordt overgeslagen.
Mutable entities: uitsluitend bestaande workflowobjecten, bindings en audit-events van dit commando.
Immutable entities: source-bytes, SourceSnapshot-identiteit, historische objectversies en alle canonieke releases.
Workflow state before: open reviewwerk op beide passages.
Workflow state after: beide betrokken passages opnieuw `needs_review`; support-relatie en exact auditbewijs zijn samen gecommitteerd; publicatie blijft ongereed.
Release state before: geen publicatie voor de nieuwe fixture; bestaande releases in andere scenario's ongewijzigd.
Release state after: gelijk aan vóór het commando; dit commando publiceert niets.
Serving state before: bestaande publication registry.
Serving state after: identiek; geen serving-schrijver wordt aangeroepen.
Expected API result: bestaande Product API en serving blijven gelijk; reparatie maakt geen publiceerbare release.
Expected UI result: de bestaande resolve-route slaagt en toont opnieuw reviewwerk; geen nieuwe UI.
Failure result: bij validatiefout of late schrijffout exact dezelfde PG-objecten, envelope, bindings en audit als vóór de poging; geen zichtbaar half commando.
Restart result: committed objecten/relaties en audit blijven gelijk; afgewezen commandbuffers verdwijnen.
Recovery result: bestaande PG-backup/recovery blijft voldoende; geen nieuw persistenteel formaat.
Legacy-data result: geen backfill, bron- of geschiedeniswijziging; bestaande file-only unitproeven blijven uitvoerbaar tijdens D6a.
Required black-box scenario: echt ingest → HTTP support-reparatie → beide objecten opnieuw reviewplichtig → audit/PG-readback → nieuwe productieconsole → identieke relaties/objects/audit; daarna een late-foutvariant met exacte rollback.
Explicit non-goals: D6b, publicatie-/withdrawal-/lineageregels, algemene audit-read-your-writes, bulk-readoptimalisatie en wijzigingen aan herstelbestanden.

GIVEN twee ongepubliceerde reviewpassages op PostgreSQL met een geldige reviewer
WHEN die reviewer één onderbouwingsreparatie via de bestaande HTTP-route bevestigt
THEN zijn relatie, reviewheropening en audit één commit; andere verbindingen zien
geen voorbereide events, falen laat geen deelresultaat achter en herstart bewaart
dezelfde gecommitteerde toestand.

Lokaal bewijs: 120 unieke scenario-/regressiecases groen, nul skips, plus
zes architectuurcases. De negen nieuwe cases toetsen HTTP-succes en late rollback
op beide productieklassen, geneste/afgebroken buffers, kopieveiligheid, een andere
thread en rol/named-reviewer/revision/doel-validatie. De bestaande publicatie-seal
blijft groen. De D5-gifrun voltooit voor beide productieklassen alle vijftien fasen
met nul mirror-accesses en identieke PG-toestand voor control/guarded/poisoned.
Loghashes en verificatiegrenzen staan in `evidence/pg-command-review/verification.json`.
Een volledige vastgepinde lokale meting en CI blijven afzonderlijk vereist.

## Adversariële review (na herclassificatie, #803 P1)

Achteraf uitgevoerd op main na merge van #803, gericht op breken in plaats van
bevestigen. Uitkomst: geen nieuwe bevinding.

- Alternatieve ingangen: `read_command_events` heeft één aanroeper
  (`_latest_review_signal`); die heeft twee aanroepers (`correct_object`,
  support-resolutie). Buiten `buffered()` is de uitkomst gelijk aan `read_events`.
- Override/fallback: de bestandsledger heeft geen `read_command_events` en valt
  terug op de gecommitteerde lezer; geen pad leest buffers van een ander object.
- Topologieën: lokaal en Azure-productieklasse in de HTTP-, rollback- en
  herstartproeven.
- Verouderde lokale toestand: elke aanroep leest PG opnieuw; er is geen cache.
- Dubbele autoriteit: de buffer wordt alleen bij de bestaande buitenste flush
  gecommitteerd en is daarbuiten onzichtbaar.
- Gedeeltelijke cutover: geen datacutover; een revert herstelt het oude gedrag.
- Concurrency: ContextVar per context; de threadproef bewijst isolatie.
- Herstart/rollback: late auditfout en herstart zijn in de proeven gedekt.

Een onafhankelijke adversariële review van deze herclassificatie blijft nodig
op de PR die haar vastlegt.
