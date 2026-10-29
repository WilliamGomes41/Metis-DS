# WP6 / MET-24 — begrensde Review-command

Change class: B. Rewrite risk: high. Touches lifecycle invariants: no.
Issue: #903. Productiecode: `982c0458bc0c5fa6df461b75cac1fa1a2a3001ff`.
Ontwerp: [ownership en migratie](../../docs/architecture/review-command-903.md).

## Werking en grenzen

De bestaande Review-MRO beslist; PostgreSQL blijft de duurzame authority.
ReviewCommandInputs/ReviewChangeSet bezitten de requeststate. De compacte POST
controleert generatie onder de documentgrens en schrijft uitsluitend betrokken
objecthistorie, bindingdelta, review-pass-projectie en bestaande audit atomair.
Legacy m2-command-equality en disjuncte storage-merge behouden hun eigen contract.

Bronvoorbereiding gebeurt vóór de locks; actieve getters gebruiken gepinde inputs.
De kernel bepaalt ook bij ontbrekende bron of het besluit bronvalidatie nodig heeft.
Lockvolgorde: authorization advisory → document → relevante account → ledger.
303 navigeert naar een GET die de volgende passage kiest.400 behoudt de escaped
draft;409 bewaart invoer zonder een nieuwe mutatieprecondition uit te geven.

Bij ouderbevestiging zijn alle huidige koppen noodzakelijke TOC-context. Kosten
kunnen dus groeien met de werkelijke dependencygraph. Historische, vervallen
relaties/koppen vergroten die set niet. Expliciete oude token-/lijst-/batchadapters,
de200-herstelspecificatie en de resolve-command blijven compatibiliteitsingangen.

Index025 is uitsluitend een additieve niet-unieke globale interaction-ID-lookup.
Geen nieuw receiptbeleid, lifecycletriggerwijziging, backfill of productieapply.
Vorige readers/writers blijven bruikbaar; de index kan bij code-rollback blijven.

## Afzonderlijke adversariële controle en tegenvoorbeelden

Afzonderlijke agents en de normale suite onderzochten MRO/alternatieve ingangen,
beide broncomposities, auth, stale state, partial writes, concurrency en herstart.
Zes gedemonstreerde bevindingen zijn opgelost:

| Bevinding | Herstel / bewijs |
| --- | --- |
| Eager bronvalidatie blokkeerde veilige source-disposition reject. | Vastgelegde bronfout alleen door de oorspronkelijke kernel laten gebruiken indien nodig; veilige reject blijft mogelijk, contentapproval faalt zonder write, ook na herstart. |
| Historische inkomende relaties vergrootten de commandset. | Eerst huidige appendpositie selecteren; oude relatie uitgesloten, dezelfde actuele relatie inclusief volledige historie behouden. |
| Expliciete ouderkeuze miste TOC-inferentiecontext. | Alle huidige structurele koppen meenemen; dezelfde bestaande validator weigert dezelfde TOC-ouder. |
| Compacte envelope miste kwaliteitsherkomst. | Laatste run-ID en uitsluitend betrokken oorspronkelijke candidatefingerprints/herkomst behouden. Exacte gelijkheid met bestaande review_evidence, inclusief duplicate-volgorde, audit en herstart. |
| Herstelformulier kreeg interne scoped revisie. | Oorspronkelijke formulierprecondition overdragen. Werkelijke200-specificatie→303-bevestiging en herstart; oude review409/resolve400 zonder write. Negatieve controle zonder herstel faalt. |
| Optionele foutweergave maskeerde domeinfout bij legacylocator. | Directe callers doen geen presentatieprobe; HTTP-probe faalt gesloten en bewaart de oorspronkelijke domeinfout. Bestaande blocked/no-duty-controles groen. |

Geen verdere concrete blocker gevonden in de onderzochte grens. Dit is een
afzonderlijke inspectie met native tegenvoorbeelden, geen bewijs van foutvrijheid.

## Uitgevoerde lokale verificatie

Python3.12.14, echte PostgreSQL16.15, productiecomposities en geauthenticeerde ASGI;
provider-/broninputs zijn synthetisch. Geen productie-SLO of live-incidentreplay.

De definitieve referentiematrix: **40 passed, nul fouten/skips**. Deze omvat
de volledige WP5-matrix plus nieuwe state/storage/index/HTTP/source/dependency/
quality/repair-handoff-controls. Verder afzonderlijk groen: A08 **94** incl.Azure,
autorisatie/opslag665 **98**, R2 **18**, compatibiliteitsrun **78**,
code-rollback **2**, volledige herstel-UI **16**, invariant/discrepancy/HTTP **29**,
form-bound **6**, stale-UX **4**, verpakking **14**, architectuur **6**.
Deze groepen overlappen; hun aantallen worden niet opgeteld als unieke tests.

Repositorypreflight, release-control-preflight, compileall, architecture boundaries
en diff-check zijn lokaal geslaagd. Een volledige diagnostische run leidde tot de
bovenstaande fixes; de betrokken modules zijn opnieuw groen uitgevoerd.
De aansluitende schone volledige run op6265 verzamelde tests was nog foutloos
bezig toen de managed uitvoeromgeving wegviel. Daarvoor bestaat **geen afgerond
groen eindoordeel**. De volledige schone verificatie wordt daarom via de PR-CI
uitgevoerd; MET-24 wordt niet als Done geclaimd zolang dat bewijs ontbreekt.
Lokale ruwe artifacts in de verdwenen werkruimte zijn niet als repositorybewijs
gepubliceerd. De PR-CI levert opnieuw native JUnit/JSON-artifacts.

De oude rollbackproef vergelijkt objectversies/hashes, bindings, audit, publicatie
en product-API exact. Alleen de fysieke document_objects.revision-writecounter
wordt apart als positieve integer gecontroleerd: deltawrites verhogen behouden
rijen, terwijl de gepinde oude full-set writer ze met counter1 herinsert.
Onaangeraakte fysieke rijen en gewijzigde counters hebben eigen native controls.
De CLI/HTTP-statusvergelijking gebruikt één observatietijdstip om een echte
cooldowngrens tussen reads niet als fout te tellen; transportdeadlines zijn gelijk.

## Gematchte engineeringmetingen

Behoud van WP5-harness, configuratie, bronhash, doel, twee historykandidaten,
historiediepte2 en één gedeelde kop. De128-fixture heeft130 actuele objecten,
138 opgeslagen versies,5 bindings,129 bronfragmenten en20642 bronbytes; SHA256
`e56d5ddab6ae2099308159113eec01a95898d1334d5dd494edf405b4f317c9da`.
WP5 ec1241cf en WP6-start7adb588 zijn onder src/db identiek.

| Kandidaten | Uitvoering | Approval POST ms | Lockhold ms | Transactie ms | Object-read SQL-resultaatrijen | Objectwrite geraakte rijen |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 32 | WP5 | 1095.3 | 704.0 | 704.0 | 467 | 86 |
| 32 | WP6 | 237.7 | 135.4 | 135.4 | 9 | 2 |
| 128 | WP5 | 12080.6 | 10977.7 | 10977.7 | 1523 | 278 |
| 128 | WP6 | 461.5 | 210.5 | 210.5 | 9 | 2 |

Alle303/400/409-samples in beide definitieve schaalproeven bleven binnen
POST≤3000ms, lockhold≤250ms, transactie≤500ms. Bij128: semantische400339.2ms
met56.4ms hold; oude-formulier409238.7ms/15.6ms; concurrent-stale409251.4ms/19.0ms.
Geïnjecteerde waits worden afzonderlijk geteld. Eerste compositielezing en warme
herhalingen zijn onderscheiden; OS-/PG-caches zijn niet geflusht. Geen p95.

Dezelfde begrensde HTTP-proef faalt op7adb588 bij list_document_objects.
De nieuwe no-deadlockharness faalt daar met een echte40P01; op de gewijzigde
code blijven beide controles zonder cyclus, met precies één duurzame winnaar,
rollback van verliezende audit en dezelfde toestand na herstart.

## Status bij overdracht aan CI

Bij aanmaak van de concept-PR: CI_PENDING na verlies van de managed
uitvoeromgeving. De actuele eindstatus staat bij de PR-checks en in de
PR-beschrijving; dit document bewaart de uitgevoerde lokale waarnemingen.
Menselijke review en repositorychecks bepalen merge.
