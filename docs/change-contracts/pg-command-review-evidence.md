# Reviewreparatie leest haar eigen voorbereide bewijs

Change class: A
Promise: een geautoriseerde atomaire onderbouwingsreparatie kan haar eigen voorbereide reviewbewijs lezen, commit beide betrokken objecten en audit samen, en blijft na herstart gelijk.
Proof: echte PostgreSQL/HTTP-onderbouwingsreparatie, hashketen, herstart, late fout met exacte rollback; geneste buffers en een onafhankelijke verbinding/thread.
Touches lifecycle invariants: yes
Rewrite risk: none

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
Er is geen nieuwe schrijver, cacheautoriteit, identiteit, schema, migratie,
transactiegrens of vervanging van een gedeeld leescontract; daarom geen rewrite.

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
