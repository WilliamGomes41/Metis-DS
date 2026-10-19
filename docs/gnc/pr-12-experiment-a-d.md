# PR 12 — Experimentharnas varianten A–D

Dit PR vergelijkt de vier formatievarianten offline op dezelfde gepinde bronnen en de golden set. Het beantwoordt de GNC-vraag met data: voegt contextbewuste correctie (C) iets toe boven structuur-eerst (D)?

```text
Change class: B
Promise: Voor elke variant zijn recall van aanbevelingen, voorwaarden en uitzonderingen, klinisch gewogen omissies en spreiding over herhaalde runs vergelijkbaar gerapporteerd.
Proof: het harnas draait de vier varianten op de golden set, drie keer per AI-variant, en levert één rapport met de maten uit PR 2 en hun spreiding.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

V1.2 §12 vraagt deze vergelijking, met de eis dat C beter moet zijn dan B. Nu bepaalt de golden set ook of D (structuur-eerst, AI alleen voor impliciete relaties) de eenvoudigere winnaar is.

## Ontwerp

- **Varianten:** A = bestaande deterministische selectie; B = huidige semantische selectie; C = B plus begrensde correctieronde op basis van Gate B-bevindingen; D = structuur-eerst, AI alleen voor relaties en `unmapped` slots.
- **Eén kandidaatmaker:** alle varianten leveren selectiebeslissingen aan dezelfde `materialise_knowledge_candidates()`; het harnas vormt nooit zelf tekst.
- **Offline:** geen workflowopslag, geen productieroute; output naar `output/gnc_experiment/`. Modelaanroepen via bestaande `bounded_model_call_v1` en vastgelegd via `semantic_replay_v1` (v2-identiteit), zodat elke run herspeelbaar is.
- **Geen nieuwe legacy-adapters.** Het harnas gebruikt de versiegebonden gedeelde producers. Het hergebruikt niet de V1-adapters in `route_comparison_app_v1.execute_arm` (L06); dat maakt L06 juist verwijderbaar.
- **Statistiek:** per AI-variant drie runs; rapport toont gemiddelde en spreiding. Acceptatiecriteria staan vast vóór de eerste run (PR 2).
- **Correctiebudget voor C:** maximaal één correctieronde per voorstel; uitputting geeft een getypeerde onopgeloste bevinding.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/evaluation/gnc_experiment_v1.py` | Nieuw: varianten, runner, rapport |
| `src/evaluation/gnc_metrics_v1.py` | Spreiding en gewogen omissies toevoegen (uit PR 2) |
| `tests/test_gnc_experiment_v1.py` | Varianten roepen dezelfde materialisator aan; geen schrijfactie buiten `output/` |

## Wat niet verandert

De productie-formatieroute en `passage_formation_policy_v1`. Alleen een aantoonbaar betere variant wordt daarna, in een eigen PR, in de bestaande route opgenomen.

## Tests en acceptatie

- [ ] Een topologietest bewijst dat elk variantpad `materialise_knowledge_candidates()` gebruikt.
- [ ] Het rapport bevat per maat waarde en spreiding voor A–D.
- [ ] Besluit over C vastgelegd: overnemen alleen als C significant beter is dan B én D.
