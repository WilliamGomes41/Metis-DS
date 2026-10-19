# PR 8 — Richtlijn: tweerichtingssluiting voorwaarden en uitzonderingen

Dit PR maakt R08–R10 sluitbaar: elke voorwaarde en uitzondering moet een doel hebben, en elke aanbeveling in dezelfde scope moet per voorwaarde of uitzondering een expliciet besluit hebben. Zo valt een verweesde contra-indicatie niet meer weg.

```text
Change class: B
Promise: Geen voorwaarde of uitzondering in een scope blijft onopgemerkt ongekoppeld aan de aanbevelingen in die scope.
Proof: een fixture met een contra-indicatie zonder except_if naar de aanbeveling in dezelfde module geeft orphan_exception en closure_decision_missing.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

"Alle aangetroffen voorwaarden zijn gekoppeld" toetst alleen wat de selectie zelf vond. De tegenrichting maakt het sluitbaar: vanuit elke voorwaarde en uitzondering wordt gekeken of ze ergens aan hangt, en vanuit elke aanbeveling of over elke kandidaat in haar scope is beslist.

## Ontwerp

- **Stateless.** `closure_findings(document_objects, scopes) -> list[Finding]`, met scopes uit PR 7.
- **Richting 1 (C02, X02):** elk object van type `condition` of `exception` heeft minstens één `applies_if` of `except_if` uit `knowledge_relations_v1`; zo niet: `orphan_condition` / `orphan_exception`.
- **Richting 2 (R08–R10):** voor elk paar (aanbeveling, voorwaarde of uitzondering) in dezelfde scope bestaat óf een relatie, óf een expliciet besluit `not_applicable`; zo niet: `closure_decision_missing`.
- **Waar het besluit staat:** `not_applicable` heeft nog geen plek in de bestaande contracten; zie het open besluit hieronder.
- **Ernst:** `orphan_exception` en `closure_decision_missing` voor uitzonderingen zijn bedoeld als `block` (veiligheidskritiek); voor voorwaarden `signal` tot meting.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_b_guideline_v1.py` | `closure_findings` |
| `src/gnc_rule_registry_v1.py` | R08–R10, C02, X02 met ernst |
| `tests/test_gnc_gate_b_closure_v1.py` | Verweesde uitzondering, ontbrekend besluit, correct gekoppeld, voorwaarde over meerdere aanbevelingen |

## Wat niet verandert

Bestaande relaties, hun identiteit (`relation_id_for`) en hun bevestigingsstatus.

## Tests en acceptatie

- [ ] De drie foutfixtures geven precies de verwachte bevindingen; de correcte fixture geen.
- [ ] Op de golden set: recall van uitzonderingen en contra-indicaties vóór en na, gerapporteerd per document.

## Open besluit

Hoe wordt "niet van toepassing" vastgelegd? Opties: (a) een nieuw semantisch relatietype `not_applicable_to` in `knowledge_relations_v1`, dat door review bevestigd wordt; of (b) een reviewbesluit in `source_context_review_v1` zonder relatie. Optie (a) verandert het relatiecontract en de relatie-identiteit en is daarmee stateful; dat vraagt de domain-first overlay voordat dit deel gebouwd wordt. Tot het besluit valt, levert dit PR alleen Richting 1 en de bevinding `closure_decision_missing` als `signal`.
