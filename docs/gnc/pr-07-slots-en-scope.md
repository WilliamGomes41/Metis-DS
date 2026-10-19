# PR 7 — Richtlijn: slotschema en scope-overerving

Dit PR geeft elke richtlijnkandidaat een verplicht slotschema per objecttype, waarin elk slot een expliciete status heeft, en legt vast hoe scope van een module naar onderliggende aanbevelingen doorerft.

```text
Change class: B
Promise: Voor elke aanbeveling is per slot (doelgroep, indicatie, richting, sterkte, scope) zichtbaar of het gevuld, geërfd of niet in de bron aanwezig is.
Proof: op de golden set geeft slot_findings voor elke aanbeveling een volledige slotstatus, en een doelgroep uit een modulezin erft door naar alle aanbevelingen in die subboom.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

V1.2 beschrijft R01–R14 maar niet hoe "volledig" wordt vastgesteld. Een slotschema maakt dat deterministisch: of elk slot een status heeft, is controleerbaar; of de vulling klopt, blijft semantisch en wordt gemeten tegen PR 2. Scope-overerving lost het grootste deel van de verre context structureel op.

## Ontwerp

- **Stateless.** `slot_findings(candidate, document_objects) -> list[Finding]`.
- **Slots per type:** aanbeveling = doelgroep, indicatie, richting, sterkte, scope (R04–R07, R12); definitie = begrip, definiens (D01–D02); voorwaarde en uitzondering = doel (C02, X02). Hergebruik van `source_bound_fields_v3.TYPE_FIELDS` en `recommendation_semantics_v1`; geen tweede veldcontract.
- **Slotstatus:** `bound` (bronspan), `inherited` (verwijzing naar scopespan), `not_in_source` of `unmapped`. Een leeg slot zonder status geeft `UNRESOLVED`.
- **Scope-overerving, positieve regel:** alleen een expliciete scopeverklaring als bronspan erft door, binnen de structurele subboom van haar sectie, tot een lager niveau haar overschrijft. Een kopwoord alleen ("Kinderen") erft niet.
- **Bron van scopeverklaringen:** hergebruik `recommendation_coverage_v1.inventory().scope_cue` en de `source_role_review` uit `source_context_review_v1`.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_b_guideline_v1.py` | Nieuw: slotschema, `slot_findings`, `scope_inheritance(objects)` |
| `src/gnc_contracts_v1.py` | Richtlijncontract verwijst naar de nieuwe regels |
| `src/gnc_rule_registry_v1.py` | R04–R07, R12, D01–D02, C02, X02 registreren |
| `tests/test_gnc_gate_b_slots_v1.py` | Slotstatussen, overerving binnen subboom, stop bij overschrijving, geen overerving uit kopwoord |

## Wat niet verandert

De bestaande velden in kandidaten en hun waarden. Geërfde scope is een afgeleide projectie, geen nieuw opgeslagen veld; zij wordt bij elke evaluatie opnieuw berekend.

## Tests en acceptatie

- [ ] Elke aanbeveling in de fixtures heeft een status voor elk verplicht slot.
- [ ] Overerving stopt aan de sectiegrens en bij een lagere scopeverklaring.
- [ ] Op de golden set: scope-recall en het aandeel `unmapped` gerapporteerd (doel vastgesteld in PR 2).
