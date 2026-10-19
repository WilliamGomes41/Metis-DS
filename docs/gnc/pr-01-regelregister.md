# PR 1 — Regelregister en grensbewaking

Dit PR maakt elke Gate A- en Gate B-regel traceerbaar naar precies één eigenaar, één test en één ernstniveau, zonder gedrag te veranderen.

```text
Change class: B
Promise: Elke GNC-regel heeft aantoonbaar één eigenaar, één test en één bedoeld ernstniveau.
Proof: tests/test_gnc_rule_registry_v1.py faalt bij een ontbrekende eigenaar, test of dubbele regel-ID.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

V1.2 eist dat elke regel één eigenaar heeft, maar maakt dat niet controleerbaar. Zonder register is niet te zien welke regels al bestaan (zoals `graph_issues`) en welke ontbreken. Alle latere PR's registreren hier hun regels.

## Ontwerp

- **Stateless.** Het register is onveranderlijke data plus een validatiefunctie; het schrijft niets.
- **Vorm.** Per regel: `rule_id`, `gate` (A/B), `document_type`, `object_type`, `owner` (`module:functie`), `test` (pytest-node), `metric` (golden-setmaat of `none`), `intended_severity` (`block` of `signal`), `status` (`existing` of `proposed`), `enforced` (standaard `false`).
- **Scheiding bedoeld en afgedwongen.** `intended_severity` legt de ernstmatrix vast; `enforced` gaat pas per regel aan na schaduwcijfers (PR 11).
- **Startvulling:** bestaande eigenaren, onder meer A02 → `knowledge_materialisation_v1.validate_materialised_candidate`, A05 → `passage_register_v1.apply_passage_register`, R06/R07 → `recommendation_semantics_v1.validate_recommendation_semantics`, R13 → `source_bound_fields_v3.validate_object_fields`, G03/G06/G07/G09 → `decision_graph_v1.graph_issues`.

**Bedoelde ernst (uit de second opinion):** `block` voor A01–A03, A08, A12, R09–R11, X03, O04, G04, G06, G10; `signal` voor beschrijvende regels zoals R02, R03, D04 en E02. De rest start als `signal` tot meting anders aangeeft.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_rule_registry_v1.py` | Nieuw: `RuleSpec`, `RULES`, `registry_errors()`, CLI `--markdown` die de tabel rendert |
| `scripts/check_architecture_boundaries.py` | Nieuwe module toevoegen aan de lijst van SDK-onafhankelijke contractmodules |
| `tests/test_gnc_rule_registry_v1.py` | Nieuw: eigenaren importeerbaar en aanroepbaar, testnodes bestaan, geen dubbele ID's, elke `block`-regel heeft een test |
| `docs/agents/abstraction-boundaries.md` | Eén rij: GNC-regelregister als eigenaar van de regel-naar-eigenaarkoppeling |

## Wat niet verandert

Geen admission-, register- of materialisatiegedrag. Geen opgeslagen data. Geen nieuwe reason codes.

## Tests en acceptatie

- [ ] `registry_errors()` is leeg op `main`.
- [ ] Een regel met een niet-bestaande eigenaar of test laat de test falen (negatieve test).
- [ ] De grenscheck weigert een HTTP- of database-import in het register.
- [ ] Volledige testsuite groen; geen wijziging in `canonical_object_hash` van fixtures.
