# Bronpassages en objectvoorstellen (#595)

Change class: B. Rewrite risk: none.

Een bronpassage is herleidbaar bronbewijs: tekst uit een specifieke bronversie,
met vindplaats en structurele context. Een kennisobject is een afzonderlijk te
beoordelen uitspraak, onderbouwd door bronfragmenten. Een passage kan meerdere
objecten onderbouwen; een object kan meerdere fragmenten nodig hebben. Een zin
is geen bewijs van één claim. Dit document verduidelijkt de implementatiegrens;
het vervangt geen protocol, admission-, review- of publicatiecontract.

## Bestaande verantwoordelijkheden

- Bronvastlegging: bestaande extractie/Docling-contracten en opgeslagen
  fragmenten; hergebruik via `OperationsConsole._read_source_fragments`.
- Mechanisch herstel van een afgebroken bronzin:
  `source_reconstruction_v1.reconstruct_source_fragments`, met behoud van de
  oorspronkelijke fragment-ID's. Dit is geen semantische bevestiging.
- Objectvoorstellen: `OperationsConsole._spec_from_fragments` roept
  `split_context_aware_units` aan. `atomic_split_v1` berekent grenzen;
  de contextsplitter koppelt exacte tekstbereiken aan bestaande bronfragmenten.
- Voorsteltoelating: bestaande eligibility/admission-contracten. Een
  splitteruitkomst is niet automatisch een geschikt kennisobject.
- Relaties: bestaande `serving_relations_v1` en `knowledge_relations_v1`.
  Review bevestigt exacte versies; de splitter bevestigt niets.
- Duurzame writes, concurrentie, recovery, canonieke hashes, audit en serving:
  de bestaande kernel-eigenaren. De splitter heeft geen I/O of lifecycle.

Het semantische passagevormingspad heeft daarnaast zijn eigen brongebonden
contract. Deze wijziging vervangt dat pad niet en voegt geen tweede semantische
authority toe. De gewijzigde taxonomy-helper wordt ook door bestaande
reconstructie- en toelatingshelpers gebruikt; hun bestaande tests blijven nodig.

## Begrensde correctie

`split_meaning_unit_spans` levert genormaliseerde voorsteltekst plus offsets
in de exact aangeleverde tekst. Daarmee hoeft de contextsplitter niet een
genormaliseerde zin terug te zoeken of bij mislukking naar offset nul te vallen.
Koppen blijven intact; afkortingen en aanhalingstekens worden meegenomen.
Puntkomma's splitsen alleen wanneer alle clausules een expliciete zelfstandige
adviesstart hebben en als aanbeveling worden voorgesteld. Onbekende of
afhankelijke clausules blijven samen. Lege tekst geldt niet als één claim.

Een vervolgstarter zoals `Eventueel` is onvoldoende om een nieuwe aanbeveling
aan een eerdere zin te plakken. Een expliciete adviesstart na de starter blijft
apart; voorbeelden en grammaticale hangers behouden de bestaande behandeling.
Dit is een heuristiek, geen volledige grammaticale analyse.

`relation_proposals_for_units` rekent op een kopie. De bestaande in-place API
blijft als adapter beschikbaar. Nieuwe `applies_if`/`except_if`-voorstellen
gelden uitsluitend voor aangrenzende objecten in dezelfde sectie. Koprelaties
mogen geen andere sectie oversteken. Toevoegen is idempotent en wijzigt geen
bestaande bevestigingen. Nabijheid is uitsluitend voorstelbewijs, niet bewijs
van inhoudelijke toepasselijkheid. Verder reikende context blijft een taak voor
de bestaande context- en reviewmechanismen.

## Opslag en herstel

Alleen uitvoer van nieuw aangeroepen objectvorming verandert. Bestaande
bronbytes, opgeslagen fragmenten, objectversies, beoordelingen en publicaties
worden niet herschreven. Geen migratie, backfill, automatische herverwerking,
nieuwe toestand, databasewijziging of productiehandeling. De berekening vindt
plaats vóór de bestaande workflow-commit; opslagfouten, CAS en recovery blijven
bij diezelfde authority. Rollback bestaat uit terugdraaien van de code voor
nieuwe vorming, zonder eerder gevormde objecten te wissen of opnieuw te vormen.

## Bewijs en beperking

`tests/test_atomic_split_source_boundaries.py` bewijst quotes/afkortingen,
zelfstandige adviesclausules versus geïntegreerde beperkingen, exacte offsets,
bronfragmentkoppeling, inputimmutabiliteit, sectiegrenzen, tussenliggende
objecten en dubbele uitvoering. Bestaande ingest/review-, reconstructie- en
architectuurtests bewaken de aansluiting.

Niet gerealiseerd: volledige semantische herkenning van claims, alle vormen
van ontkenning/kwalificatie, verre contextafhankelijkheden, of bewezen betere
extractiekwaliteit op echte richtlijnen. Daarvoor zijn het bestaande
brongebonden passagevormingscontract, inhoudelijke referentiebeoordeling en
eventueel afzonderlijke slices nodig. Tokenvensters mogen modelaanroepen
ondersteunen, maar bepalen geen objectidentiteit.
