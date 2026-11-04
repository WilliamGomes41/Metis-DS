# Incident #974: Review opslaan breekt worker af; Vorming en Review openen traag

Issue: #974
Change class: C
Rewrite risk: none
Promise: De projectlead kan met één alleen-lezen commando de Azure-telemetrie verzamelen. Daarmee zijn de exitreden van de afgebroken Review-opslag en de kosten van de trage Vorming- en Review-reads per verzoek vast te stellen. Een tweede alleen-lezen commando stelt per afgebroken opslag vast of de beslissing is vastgelegd.
Proof: `tests/test_check_review_save_outcome_postgres.py` (PostgreSQL 16, read-only uitkomst zonder ids of details); droge run van `scripts/collect_worker_abort_evidence.sh` met een nagebootste `az` (zes secties volledig ingevuld; weigert een verkeerde subscription, een ongeldige tijd en uitvoer in de repo).
Touches lifecycle invariants: no

Deze slice voegt alleen diagnose toe. Er verandert geen productiegedrag, schema, autorisatie of lifecycle. De fixes volgen als aparte PR's per onderdeel. Een fix kan een andere klasse krijgen: het Vorming-leespad is Class B.

## Waarneming (telemetrie, projectlead, 2026-11-04)

| Onderdeel | Vastgesteld |
|---|---|
| Review opslaan | 5 × `POST /review` zonder `request_finished`; telkens een nieuw workerproces na circa 39–43 s |
| Vorming openen | tot 49 s; één verzoek: 945 × `source_reconstruction`, samen 25,8 s |
| Review openen | tot 14,9 s; één documentverzoek: 31,4 MB `db_json_bytes` |
| `review_disposition_conflict` | HTTP 400 na 3,87 s |

## Oorzaakanalyse (code op `main` 1f9deea)

### 1. Review opslaan: hypothese, nog niet bewezen
- `scripts/azure_console_startup.sh` start gunicorn zonder `--timeout`, dus met de standaard van 30 s. Productie draait met `WEB_CONCURRENCY=1`.
- De arbiter stuurt SIGABRT als de uvicorn-worker meer dan 30 s geen hartslag geeft. Die hartslag komt uit de event loop.
- Een vaste 30 s plus de opstarttijd van de worker verklaart de herhaalde 39–43 s beter dan een OOM-kill met wisselende duur.
- Voorbehoud: `review_post` is een synchrone handler in de threadpool. Alleen een lange C-aanroep die de GIL vasthoudt, of blokkerend werk op de event loop, laat de hartslag wegvallen.
- **Beslissend bewijs:** het verloop van de `request_running`-heartbeats, de `WORKER TIMEOUT`- of `SIGKILL`-regel en de faulthandler-dump van alle threads. Dit staat in `worker_lifecycle.json`.
- **Schrijfgrens:** de beslissing wordt in één PG-transactie geschreven (`src/review/review_command_v1.py`). Een afbraak vóór de COMMIT betekent een rollback. Een afbraak erna betekent dat de beslissing bewaard is maar de gebruiker een fout zag. Het systeem laat de flock en de advisory locks vrij wanneer het proces eindigt.

### 2. Vorming openen: bevestigd
- `formation_problems_v1.collect` leest de bron via `stored_extraction(envelope)`. Dat geeft een gewone lijst terug, niet de voorbereide `SourceFragments`-drager die Review gebruikt.
- Daardoor vergelijkt elke `_read_source_blocks`-aanroep per object, ook bij een cache-hit, de volledige fragmentenlijst met de bewaarde kopie. Getallen zitten daarin in `_SourceNumber`, dus de vergelijking loopt via Python-`__eq__`.
- De fase `source_reconstruction` telt deze aanroepen mee.
- Micro-benchmark (lokaal, synthetisch): 7 ms per hit bij 1.000 fragmenten en 20 ms bij 3.000. Bij circa 4.000 fragmenten geeft 945 aanroepen ongeveer 25 s.
- Telemetrische bevestiging in `slow_reads.json`: `source_reconstruction_reused` ongeveer gelijk aan `source_input_compared`, terwijl `source_reconstruction_built` laag blijft.

### 3. Review openen: query nog niet toegewezen
- `db_json_bytes` is alleen een totaal per verzoek.
- Kandidaten: `console._envelope` (de volledige envelope, zie MET-38), de overzichtsredirect aan het eind van de wachtrij (14,6 MB) en `read_review_participation_events`.
- De `phase_tree` in `slow_reads.json` bepaalt welke het is.

### `review_disposition_conflict`
- Terechte weigering volgens `ALLOWED_FINAL_BY_SUITABILITY`.
- De statische invoercontrole draait pas na de volledige commandovoorbereiding (`review_closure_v1.review_object` → `execute_review_command`). Daar komen de 3,87 s vandaan.

## Gegevensregels
Uitvoer blijft privé, buiten de repo, met modus 700. Naar GitHub of Linear gaan alleen tellingen, foutcodes, pids, tijdstippen en SHA's. `check_review_save_outcome.py` toont nooit document-ids, object-ids, actoren of eventdetails.

## Vervolg (aparte PR's, na het bewijs)

Het uitgewerkte oplossingsontwerp met prototypebewijs staat in [974-solution-plan.md](974-solution-plan.md).

1. Review opslaan: blokkade of geheugen wegnemen in het aangewezen frame. Een expliciete `--timeout` is géén fix, maar maskeert alleen.
2. Vorming: de voorbereide bronweergave één keer per verzoek doorgeven (Class B, met een gate voor de programmastructuur).
3. Review openen: bytes per query toewijzen en daarna de envelope-read begrenzen.
