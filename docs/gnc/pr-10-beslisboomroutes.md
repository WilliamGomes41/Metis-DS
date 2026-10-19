# PR 10 — Beslisboom: routeverzameling vergelijken

Dit PR voegt de sterkste end-to-endtoets voor beslisbomen toe: alle routes van start tot uitkomst opsommen en die verzameling vergelijken met de geverifieerde bron. Eén vergelijking vangt verkeerde richting, ontbrekende takken, verloren padvoorwaarden en samengevoegde alternatieven.

```text
Change class: B
Promise: Voor elke beslisboom is zichtbaar welke bronroutes ontbreken, welke routes zijn toegevoegd en welke routes een andere uitkomst geven.
Proof: op de vier foutvoorbeelden uit v1.2 (§5.6) geeft route_set_findings respectievelijk route_extra, route_missing, route_condition_lost en route_merged.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

`graph_issues` controleert lokale eigenschappen goed (antwoorden per knoop, eindpunten, entrypoints, cycli). Het ziet niet dat de hele graaf andere routes oplevert dan de bron. `ordered_paths` en `route_contexts` bestaan al en geven de bouwstenen.

## Ontwerp

- **Stateless.** `route_set(graph, objects) -> set[Route]` op basis van `decision_graph_v1.ordered_paths`; een route = geordende knopen met antwoordlabels en eindtekst.
- **Referentie:** in schaduw en experiment de golden-setroutes (PR 2); in productie, waar geen referentie bestaat, alleen interne controles: elke `single`/`multiple`-knoop draagt bij aan minstens twee routes, elke `terminal` is bereikbaar, geen route draagt een padvoorwaarde die halverwege verdwijnt (G06, G08, G10).
- **Bevindingen:** `route_missing`, `route_extra`, `route_outcome_differs`, `route_condition_lost`, `route_merged` (G11). G04, G06 en G10 bedoeld als `block`.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_b_decision_tree_v1.py` | Nieuw: `route_set`, `route_set_findings`, interne padcontroles |
| `src/gnc_contracts_v1.py` | Beslisboomcontract verwijst naar de nieuwe regels naast `graph_issues` |
| `src/gnc_rule_registry_v1.py` | G04, G06, G08, G10–G12 |
| `tests/test_gnc_route_set_v1.py` | De vier foutvoorbeelden, een correcte boom, een boom met meervoudige keuze |

## Wat niet verandert

Het grafcontract `source-decision-graph-v1`, `graph_issues`, `graph_hash` en de publicatiecontrole `publication_issues`.

## Tests en acceptatie

- [ ] Elk foutvoorbeeld geeft precies één verwachte bevinding.
- [ ] Op alle bestaande beslisboomfixtures blijft `graph_issues` ongewijzigd.

## Open besluit: legitieme herhaling

`graph_issues` geeft bij elke cyclus `decision_graph_cycle_unresolved`. Een boom met "herbeoordeel na 48 uur" is daardoor niet publiceerbaar zonder de lus te breken. Een expliciet randtype `repeat` (met verplichte bronverwijzing en eindvoorwaarde) zou dit oplossen, maar wijzigt het grafcontract, `graph_hash` en mogelijk publicatiebewijs. Dat is Class A, `Rewrite risk: high`, en valt buiten dit PR. Eerst meten: telt de golden set (PR 2) herhalingsranden in echte bomen?
