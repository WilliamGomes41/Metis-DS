Een gestructureerde PG-reparatie kon haar eigen voorbereide reviewbewijs niet lezen en gaf een fout. Alleen de expliciete commandolezer ziet nu het bewijs van de huidige transactie; publieke audit-/polllezers blijven uitsluitend gecommitteerde gebeurtenissen lezen.

## Scope

V&VN Data Services, besluit B-D6-1. Gebaseerd op `codex/d6a-10-processing-routes`. D6b en GNC zijn niet gestart; #695 blijft onafhankelijk en gaat voor bij capaciteitstekort.

## Change class / rewrite risk

Change class: A
Promise: Een brongebonden reparatie kan binnen haar eigen PG-commando worden gevalideerd en blijft atomair.
Proof: Negen gerichte cases plus HTTP-, rollback-, herstart- en D5-regressies; zie evidence/pg-command-review/verification.json.
Touches lifecycle invariants: yes
Rewrite risk: none

Volledig lifecyclecontract: `docs/change-contracts/pg-command-review-evidence.md`. PostgreSQL-schema, publieke read boundary, canonical/Blob-data en autorisatie veranderen niet. Rollback is een revert van deze reparatie.

## Lifecycle

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

## Protocol / schema impact

- [x] No protocol/schema impact

## Infrastructure / cost impact

- [x] Uses an already-declared dependency

PostgreSQL16 is al gedeclareerd. Lokale/testsetup en de meetwijze staan in `docs/agents/postgres-tests.md` en `docs/STACK_SETUP_BASELINE.md`. Geen Azure-provisioning of deployment. CI-minuten worden per portie gemeten; open de stack opeenvolgend zodat #695 voorrang houdt.

## Safety checks

- [x] No secrets or source binaries committed
- [x] Canonical hashes remain deterministic where applicable
- [x] Publication remains fail-closed

## Metis eindrapportage

- **belofte**: productiegetrouw PG-bewijs voor de genoemde wijziging.
- **wijziging**: zie bovenstaande concrete trigger en uitkomst.
- **bewijs**: lokale, gerichte uitvoering; ruwe JUnit-hashes en actuele stack staan in `evidence/d6a/`.
- **onzekerheid**: CI-metingen en de gebruikte Cursor-omgevingen zijn nog niet uitgevoerd. Dit is geen D6a/D6b-voltooiingsclaim.
- **advies**: beoordeel en meet deze portie vóór de volgende; start D6b pas na de afgesproken gates.

## Verification

- [x] `python scripts/repository_preflight.py`
- [x] `python scripts/release_control_preflight.py --base origin/main`
- [x] `python -m compileall -q src tests`
- [ ] CI op deze exacte head

Gewijzigde testbestanden in deze PR: 1. Lokale publicatie is voorbereid; deze beschrijving is nog niet naar GitHub verzonden.
