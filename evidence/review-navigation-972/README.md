# Native vervolgnavigatie — #972 / MET-36

Dit is synthetisch native PostgreSQL/HTTP-bewijs, geen productie-replay of
Azure-prestatieacceptatie. De fixture bevat drie bronaanbevelingen, twee
toegelaten kandidaten, incomplete vorming en onvoorbereide kaartgegevens.

De baseline plugt uitsluitend de vorige navigatiefallback terug in: de
bestaande volledige documentreader. De huidige reader gebruikt voor dezelfde
HTTP-GET een geautoriseerde navigatiecapture. Dezelfde echte passage wordt
geopend; bij het einde van de queue blijft dezelfde werkvoorraad bereikbaar.

| HTTP-route | Baseline DB-JSON bytes | Nieuwe capture | Queries voor → na |
| --- | ---: | ---: | ---: |
| Volgende passage | 299381 | 156094 | 39 → 36 |
| Einde van queue | 331518 | 299981 | 31 → 29 |

JSON: [native-http.json](native-http.json) en
[end-of-queue.json](end-of-queue.json). Beide binden aan SHA-256 van de werkelijk
uitgevoerde `src/review/review_passage_read_v1.py`. Duur is een enkele lokale
observatie onder gelijktijdige testbelasting; er wordt geen latencywinst of
nieuw SLO uit afgeleid. Databaseverbindingen en alle benodigde bron-/objectinputs
blijven nodig; gewone POST en het brede documentoverzicht blijven vervolgwerk.

## Uitgevoerde controles

- De nieuwe archive-read-guard faalt op de ongewijzigde baseline doordat
  `read_review_navigation` via `read_review_document` naar
  `store.get_envelope`/`formation_input` gaat.
- Nieuwe native tests: 9 passed. Die dekken beide kaart-/frontiervarianten,
  oorspronkelijke queueparity, de daadwerkelijke vervolgpassage en end-of-queue,
  autorisatie vóór source/objectcapture en behoud van objecthistorie,
  reviewbindings, ledger en volledige documentenvelope.
- Geraakte native navigatie/save-chain/passage/integriteit/read-scope-run:
  77 passed. Deze run overlapt met de nieuwe tests en wordt niet opgeteld.
- Laatste twee HTTP-byteproeven na het bijwerken van de readerdocstring:
  2 passed; JSON hierboven opnieuw geschreven en readerhash gecontroleerd.

Reproductie met een lokale PostgreSQL 16-testserver en de gepinde dev-requirements:

```bash
bash scripts/test_postgres.sh
METIS_NAVIGATION_PROOF_OUTPUT=output/runtime/navigation-972.json \
  python -m pytest -q tests/test_review_navigation_fallback.py
```

De lokale uitvoering gebruikte Python 3.12 en een tijdelijke PostgreSQL
16-container via een Unix-socket. Er zijn geen PostgreSQL-tests overgeslagen.
Volledige suite, exacte CI, productie-readback en live acceptatie zijn hiermee
niet bewezen. Publicatievoorwaarden en mutatie-/herstelowners zijn ongewijzigd.

De CI-opvolging na de main-merge staat in `batch-gc-observation.json` en het
change contract. Deze observatie scheidt de generatie-2-GC van eerdere
ASGI-fixtures van het gemeten GET/POST-scenario. De test houdt automatische GC,
de oorspronkelijke HTTP-flow en alle tijd-/integriteitsgrenzen. Dit is bewijs
voor een benchmark met gecontroleerde heap, geen productie-tailacceptatie.
