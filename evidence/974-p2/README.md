# JSON-bytes per fase — #974 P2 / MET-48

Dit is synthetisch native PostgreSQL/HTTP-bewijs via de productie-ASGI-app,
geen productie-replay of Azure-acceptatie. Trunk is `origin/main` op `1f9deea`;
head is deze branch. De trunkboom is een kopie van head met de twee gewijzigde
bronbestanden van `main` teruggezet, zodat alleen deze wijziging verschilt.

## Toegewezen bytes bij het openen van een Reviewdocument

`GET /review?document=<sid>` op de fixture van 2.000 alinea's
(`attributed_request` in [perf.json](perf.json), en
[lanes/review-document.json](lanes/review-document.json)):

```json
{"_none": 4, "authorization": 4, "document_load": 8928649,
 "review_render": 8626491, "review_render/source_views_read_records": 6460749}
```

Som 24.015.897 = `db.db_json_bytes`. Dit verzoek doet 15 queries en 2.018
JSON-loads ([load-count.json](load-count.json)). Ruim een derde van de bytes leest
`review_render` zelf, buiten `source_views_read_records`; dat is de eerste
aanwijzing voor P5. Bij `/source-selection` staat 9.959.568 bytes onder `_none`:
een ongefaseerde read ([lanes/formation.json](lanes/formation.json)).

## Prestatie

Tien rondes; per ronde draaien trunk en head elk in een eigen pytest-proces na
elkaar, en de volgorde wisselt per ronde. Elk proces bouwt de fixture, doet één
opwarmverzoek en meet vijf verzoeken. Per kant zijn dat dus 50 verzoeken.

| | mediaan per ronde (ms) | p25–p75 | min–max |
| --- | ---: | ---: | ---: |
| trunk | 1480,1 | 1426,5–1503,2 | 1372,9–1535,6 |
| head | 1438,1 | 1411,0–1469,7 | 1388,6–1487,7 |

Gepaarde verhouding head/trunk per ronde: −2,63 % (mediaan). Het 95%-bootstrap-
interval loopt van −5,21 % tot +2,05 %. De ruis per ronde is ±10 %. Daarom is de
2%-regel over HTTP **niet beslist**. De uitkomst is `inconclusive`, geen pass.

Begrenzing van de kosten zelf ([microbench_attribution.py](microbench_attribution.py),
[microbench.json](microbench.json)): één `diagnostic_json_bytes`-aanroep, drie
fasen diep, kost ongeveer 154 ns. Bij 2.018 loads is dat ongeveer 0,3 ms per
Review-open: ongeveer 0,02 % van 1.440 ms.

## Live lanes

`run_probe.py --mode lanes` maakt de bonnen in [lanes/](lanes/). De ruwe
samenvattingen per boom staan in `lanes/raw/`.

| Lane | Bon | Uitkomst |
| --- | --- | --- |
| 1 regressie | `regression.json` | pass: trunk en head 24.015.897 bytes; alleen head heeft de map |
| 2 Reviewdocument | `review-document.json` | pass: noemt `review_render/source_views_read_records` en `document_load`, som = totaal |
| 3 Vorming | `formation.json` | pass: som = totaal |
| 4 Review-save | `save.json` | pass: 303 op trunk en head, som = totaal (apart klein document; de grote fixture heeft geen reviewbaar object) |
| 5 geen JSON | `no-json.json` | pass: `GET /login`, map `{}`, totaal 0 |
| 6 afkapping | `truncated.json` | pass: 81 geforceerde fasepaden op een gemeten app met de echte loader op dezelfde PostgreSQL. 64 sleutels, `_overflow` 19, `_none` 2, beide truncatievlaggen, som = totaal 83. Geen productieroute heeft meer dan 64 paden |
| 7 fout | `error.json` | pass: `unknown_snapshot` (ConsoleError, afgehandeld) met de map. De Review-POST-fouten in dezelfde bon (409/400) leggen zelf geen foutcode vast; dat is al zo op trunk |
| 8 privacy | `privacy.json` | pass: request-events bevatten geen snapshot-id, object-id (2.006 gecontroleerd) of SQL. `processing_checkpoint` bevat al op trunk het snapshot-id; de hub zet dat om naar `doc_ref` |
| 9 gelijktijdig | `concurrent.json` | pass: `/review` en `/source-selection` tegelijk, elke map = eigen totaal |
| 10 KQL | — | niet uitgevoerd: geen Kusto-engine lokaal, en `worker-abort-incident.kql` staat nog niet op `main` |

## Reproductie

```bash
PYTHON=python bash scripts/test_postgres.sh   # print de DSN
export METIS_TEST_POSTGRES_DSN=<dsn>
python evidence/974-p2/run_probe.py --trunk <boom op main> --head . --mode lanes --out evidence/974-p2/lanes
PROBE_REQUESTS=5 python evidence/974-p2/run_probe.py --trunk <boom op main> --head . --mode perf --rounds 10 --out evidence/974-p2
PYTHONPATH=. python evidence/974-p2/microbench_attribution.py
```
