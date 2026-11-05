# Dispositieconflict vóór voorbereiding — #974 P3 / MET-48

Synthetisch native PostgreSQL/HTTP-bewijs op een document van 2.000 alinea's
(200 definitiekandidaten), geen productie-replay. Gemeten: `elapsed_ms` en
`db_queries` uit `request_finished` van een conflicterende `POST /review`
(`geen_kenniseenheid` + goedkeuren), 10 runs per modus, trunk en head
afwisselend op hetzelfde document.

"Trunk" is head met alleen `review_command_v1._refuse_static_disposition`
uitgeschakeld; dat herstelt exact de volgorde van trunk. Een aparte run op een
echte trunk-checkout van beide gewijzigde bronbestanden gaf dezelfde waarden
(`trunk_checkout` in `perf.json`).

| Pad | Trunk mediaan | Head mediaan | Queries trunk → head |
| --- | ---: | ---: | ---: |
| Serieel (`review_command_window` = None, bestaande-data-tak) | 1.551 ms | 97 ms | 48 → 9 |
| Voorbereid (verse data) | 851 ms | 97 ms | 26 → 9 |

Regel: serieel head zonder `store_transaction` en zonder bronvoorbereiding,
maximaal 300 ms (max 123 ms); voorbereid head strikt minder queries. PASS.

Lanes 1–9 staan in `lanes.json` (alle PASS). Lane 7 is herformuleerd: verouderd
token plus conflict geeft een 4xx-weigering zonder event (trunk 409-herweergave,
head 400 `review_disposition_conflict`). Lane 10: er bestaat geen MCP-reviewroute;
`src/settings/metis_mcp_v1.py` biedt alleen read-only tools.

Duur is een lokale observatie; er wordt geen productie-SLO uit afgeleid.

Opnieuw draaien (de probe schrijft `probe-<label>.json`; `perf.json` en
`lanes.json` zijn daaruit samengesteld):

    cp evidence/974-p3/probe_disposition_conflict.py tests/probe_974_p3_tmp.py
    python -m pytest -q -s -p no:logging tests/probe_974_p3_tmp.py; rm tests/probe_974_p3_tmp.py
