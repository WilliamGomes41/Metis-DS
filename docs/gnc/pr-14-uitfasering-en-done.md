# PR 14 — Uitfasering legacy-routes en topologie-diff

Dit PR (in praktijk een korte reeks, één per route) sluit de acht `LEGACY-FROZEN` routes L01–L08 uit `config/legacy_processing_routes.json` af en levert de topologie-diff die het programma afrondt. Het resultaat moet minder actieve topologie zijn dan vóór het programma.

```text
Change class: B (per route; L08 herclassificeren als de klassewijziging lifecycle raakt)
Promise: Geen vervangen formatie-, voorstel- of admissionroute is nog bereikbaar voor nieuwe verwerking; historische data blijven leesbaar.
Proof: per route een aanroepbaarheidstest (API, CLI, retry, fallback, dynamische import, operatorcommando) die faalt als de route bereikbaar is, plus een topologie-diff t.o.v. de baseline van fase A.
Touches lifecycle invariants: no (L08: te bevestigen)
Rewrite risk: none per route; high als een route een durable autoriteit blijkt te zijn
```

## Routes en volgorde

| Route | Code | Na welk PR | Actie | Voorwaarde uit het register |
| --- | --- | --- | --- | --- |
| L03 | `admission_gate_v1._enrich_from_text` (en `_enrich_recommendation`) | 7 | Verwijderen als tweede semantische waarheid; Gate B-regels zijn eigenaar | Geen noodzakelijke v1-admissionaanroepers |
| L01 | `operations_console_v1._spec_from_fragments` | 6 | Verwijderen of terugbrengen tot niet-dubbele verantwoordelijkheid | G0–G5; koppen, reparatie en vergelijkingen losgekoppeld |
| L02 | `pre_review_semantic_v1._proposal_schema(false)` | 6 | Schrijftak weg; historische lezer behouden | G0–G5 en compatibele historische lezers |
| L04 | `passage_formation_policy_v1` v1-modusselectie | 12 | Verwijderen | G0–G5 en rollbackvenster gesloten |
| L05 | `semantic_suppressed`-catalogusomweg | 4 | Vervangen door directe read-only broncatalogus | Catalogus roept geen volledige spec-creatie meer aan |
| L06 | `route_comparison_app_v1.execute_arm` v1-adapters | 12 | Verwijderen | Historische baseline blijft reproduceerbaar |
| L07 | v1-replay-writes in `semantic_replay_v1` | 12 | Nieuwe v1-writes weigeren; lezer behouden | Geen nieuwe v1-writes |
| L08 | `_reextract_objects_for_klasse` directe prozaconversie | 6 | Alleen die tak weg; geautoriseerde klassewijziging en herstel blijven | Regressiebewijs klasseconversie en lifecycle |

Volgorde volgt de afhankelijkheid: een route gaat pas weg nadat het PR in kolom drie haar opvolger heeft geleverd.

## Werkwijze per route

1. Aanroepbaarheid onderzoeken: API, CLI, retry, fallback, dynamische import, subproces, operatorcommando, herstelcommando.
2. Opvolger aantonen met een test die hetzelfde gedrag via de nieuwe route bewijst.
3. Verwijderen, of read-only maken met een expliciet uitfaseringsbesluit als historische data de code nodig hebben.
4. Route-item in het register op `REMOVED` of `READ-ONLY` zetten met commit-verwijzing.

## Beschermlijst (niet verwijderen)

`knowledge_materialisation_v1`, `passage_register_v1`, `source_containers_v1`, `decision_graph_v1`, `decision_unit_construction_v1`, `semantic_replay_v1` (lezer), `source_context_review_v1`, `recommendation_semantics_v1`, `source_bound_fields_v3`, de workflowtransacties en publicatieautoriteit. Al verwijderde code (`construction_spec`, `boom_spec_from_fragments`, `prepare_graph`, `pdf_route_proposals_v1`, de 17 ongebruikte functies) wordt niet opnieuw als werk geteld.

## Buiten dit programma

`storage_prepare.py` (`LEGACY-UNUSED`), `canonical_store.py` en `second_review_workflow_v3.py` (`LEGACY-SUPPORTED`) zijn opslag-opschoning, niet veroorzaakt door GNC. Ze krijgen een eigen spoor; dit programma voegt alleen toe dat geen GNC-PR ze als schrijver mag gebruiken.

## Afsluitcontrole (Definition of Done van het programma)

- [ ] Eén kandidaatmaker: alle formatie-, correctie- en herverwerkingsroutes gebruiken alleen `materialise_knowledge_candidates()`.
- [ ] Geen oude route bereikbaar via API, CLI, retry, fallback, dynamische import of operatorcommando.
- [ ] Geen extra schrijver, opslagtabel, JSONL-statusstore of objectidentiteit.
- [ ] Geen dubbele semantische regel: het register (PR 1) toont één eigenaar per regel.
- [ ] Exacte broninhoud voor nieuwe kandidaten (na PR 13).
- [ ] Bestaande snapshots, bevestigingen en releases verifiëren zonder herberekening.
- [ ] Retry, herstart, verouderde revisies en gelijktijdige opdrachten geven geen dubbele activatie.
- [ ] Topologie-diff t.o.v. de baseline: welke paden verdwenen, welke overblijven, en het aantal actieve paden is gedaald.

Een aangevinkte regel is pas geldig met een verwijzing naar het bewijs (test, rapport of commit).
