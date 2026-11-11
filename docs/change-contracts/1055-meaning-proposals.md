# Eén selectie, een betekenisvoorstel, menselijke controle

Change class: B
Promise: Na één volledige bronselectie stelt Metis type en brongebonden betekenisvelden voor; de gebruiker controleert en corrigeert vóór afronden.
Proof: Native PostgreSQL/API- en browserproeven voor exacte bronankers, voorstel/correctie/hervatten, stale input, ontbrekende tekst en providerfout.
Touches lifecycle invariants: no
Rewrite risk: none

Part of MET-73. GO William, 11 november 2026: schrijf het nieuwe ontwerp en implementeer het.

## Bediening en uitkomst

Markeer de volledige uitspraak, eventueel met een vooraf gekozen type. Eén
hoofdknop ‘Betekenis voorstellen’ bevestigt de kern en vraagt het voorstel aan.
Metis toont type en betekenisvelden met letterlijke bronverwijzingen. De
gebruiker controleert, past alleen onjuiste/ontbrekende onderdelen aan en rondt
via de bestaande controle af. Handmatig aanwijzen blijft beschikbaar bij
uitval en voor correcties. Geen tweede verplichte selectie van dezelfde woorden.

Voorstelvelden worden als concept opgeslagen, nooit automatisch als gereed.
Ontbrekende/ambigue tekst blijft expliciet onzeker. Onderbouwing ‘niet van
toepassing’, contextessentialiteit en publicatie worden niet automatisch gekozen.
De bronweergave toont het gekozen citaat; de controle toont type, betekenis en
bronverwijzingen samen. De documentbrede eindcontrole blijft intact. Het
herontwerpen van Documentoverzicht/Vormingsproblemen valt buiten deze slice.

## Eigenaarschap en uitvoering

De huidige route is bronblok → captureSelection/pending_range → bindRange →
annotations.save → inspect_annotation → bestaande deterministic materialisation.
Het nieuwe voorstel is een stateless backendquery naast deze route. De bestaande
LLM-configuratie en begrensde transportfunctie worden hergebruikt. Alleen de
gekozen kerntekst gaat naar de provider: broninhoud is data, geen instructie.
De provider levert type en letterlijke quotes; de backend bindt uitsluitend
unieke exacte matches aan bestaande codepoint-spans en hergebruikt bind_fields.
Geen vrije veldproza, nieuwe kandidaatmaker, identiteit, schema of jobautoriteit.

Domain entity/aggregate: annotatie binnen bestaande annotatieset.
Invariant(s): immutable bron, exacte bronspans, draft tot menselijke afronding, bestaande toelating/review/publicatievoorwaarden.
Durable state before: opgeslagen draft met kernselectie.
Durable state after: via bestaande save een draft met voorgestelde/corrigeerbare betekenisvelden.
Transaction boundary: voorstelquery schrijft niets; draft-save houdt dezelfde atomische kerneltransactie/CAS/receipts. Geen DB-transactie tijdens provider-I/O.
Failure/recovery result: kern en bestaande velden blijven bewaard bij fout/timeout; handmatig corrigeren of expliciet opnieuw proberen. Geen automatische retries of verborgen fallback.
Duplicate execution / idempotency result: query is readonly; maximaal één call per verzoek; save houdt bestaande commandreceipts.
Concurrency result: basis bevat snapshot, werkrevisie, extractie, normalisatie, annotatie/revision, generatie en objectrevision; backend controleert vóór/na provider, client weigert gewijzigde input en save blijft CAS.
Audit/evidence requirement: bestaande immutable annotatieversies, bronankers en receipts; operationele providertelemetrie hergebruiken, geen parallelle auditwaarheid.

## Alternatieven en bewijsgrens

Afgewezen: browserregex die semantiek gokt; opnieuw selecteren als normale route;
de volledige AI-documentvorming starten voor één keuze; een tweede opslag/joblaag.
Gekozen: begrensd voorstel op één opgeslagen keuze, maximaal 8 kernbereiken en
8.000 codepoints, één providercall (45 seconden, geen automatische retries).
Onzekere modeluitvoer mag niets verzinnen of bestaand werk overschrijven.

Proeven gebruiken gecontroleerde provideruitvoer voor het koppelen aan de echte
HTTP/PostgreSQL-route. Dat bewijst integratie en foutgrenzen, geen klinische
betrouwbaarheid van live modelinterpretatie. Inhoudelijke praktijkacceptatie
blijft nodig; geen betaalde calls of deployment binnen deze opdracht.
Afhankelijkheid: PR #1054 verwijdert eerst het dubbele tekstselectiehulpvak.

## CI-regressie: lockvolgorde van de heartbeat-test

Na herstel van de proxy-installatie ontdekte één volledige Python 3.12-partitie
op head 98e01be8 een bestaande testfixture-deadlock. De fixture wijzigde
processing_attempts rechtstreeks (attempt → document via de trigger), terwijl
de gelijktijdige echte heartbeat document → attempt lockt. De PostgreSQL-
deadlocktrace toont precies die twee transacties. De fixture gebruikt nu
worker_handover_v1.locked, dezelfde bestaande document-eerst-eigenaar.
Productiecode, lease-/deadlinevoorwaarden en assertions worden niet gewijzigd.
De echte heartbeat moet nog steeds committen, de lease verlengen zonder de
harde deadline te verlengen en de drie providerstappen succesvol afronden.
Een vroege native CI-proef herhaalt deze concrete regressie vijfmaal vóór de
volledige matrix. De lokale werkruimte is tijdens herstel niet beschikbaar;
verificatie van deze wijziging loopt daarom via de native PostgreSQL-runner in CI.
