# PR 3 — A02 letterlijkheidsmeting

Dit PR maakt zichtbaar waar canonieke kandidaattekst afwijkt van de letterlijke bronspans, zonder die tekst te wijzigen. De huidige materialisatie voegt spans samen met een spatie en normaliseert witruimte; dat is strijdig met I2, maar die tekst zit in de reviewhash.

```text
Change class: B
Promise: Voor elke kandidaat is per span aantoonbaar of de canonieke tekst letterlijk uit de bron komt, en zo niet, welk soort afwijking optreedt.
Proof: literal_fidelity_findings rapporteert join_separator- en witruimteafwijkingen op een fixture en niets op een exact-letterlijke kandidaat.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

`resolve_source_selection` bouwt `source_text` als `normalize_visible_prose(" ".join(parts))`. De `source_mapping` legt de scheidingstekens al vast als `kind: join_separator`, dus de afwijking is herleidbaar maar niet gemeten. Zonder meting weten we niet of het om alleen witruimte gaat of ook om betekenisdragende tekens zoals afbreekstreepjes of opsommingstekens.

## Ontwerp

- **Stateless.** `literal_fidelity_findings(candidate, fragments) -> list[Finding]` leest `semantic_passage.source_mapping` en de ruwe fragmenttekst.
- **Afwijkingsklassen:** `join_separator`, `whitespace_collapsed`, `edge_trimmed`, `non_whitespace_mismatch`. Alleen de laatste is een echte schending van de inhoud.
- **Doorgifte.** Bevindingen worden `reason_codes` via de bestaande admissionstap, met ernst uit het register (PR 1); `non_whitespace_mismatch` bedoeld als `block`, de rest `signal`.
- **Afgeleide letterlijke projectie.** Voor review en export levert een functie de spans letterlijk en apart; dit is een leesmodel, geen canonieke tekst.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_a_v1.py` | Nieuw: `literal_fidelity_findings`, `literal_span_projection` |
| `src/admission_gate_v1.py` | Aanroep van de bevindingen; alleen `reason_codes` toevoegen |
| `src/gnc_rule_registry_v1.py` | A02 wijst naar de nieuwe functie, `status: existing` |
| `tests/test_gnc_gate_a_literal_v1.py` | Fixtures voor elke afwijkingsklasse, inclusief Unicode, regeleinden en meerfragmentselectie |

## Wat niet verandert

`source_text`, `clean_text`, `_candidate_identity`, `compute_canonical_object_hash` en elke opgeslagen review. Bestaande kandidaten worden niet herberekend.

## Tests en acceptatie

- [ ] Een exact-letterlijke kandidaat geeft nul bevindingen.
- [ ] Een kandidaat over twee fragmenten geeft precies één `join_separator`.
- [ ] Een gemanipuleerde mapping geeft `non_whitespace_mismatch`.
- [ ] Hashregressie: `canonical_object_hash` van alle fixtures ongewijzigd.

## Besluit dat buiten dit PR valt

Of canonieke tekst letterlijk moet worden (zonder samenvoeging en normalisatie) is een Class A-besluit met `Rewrite risk: high`: het verandert reviewhashes en raakt published state. Dat besluit en de uitvoering staan in [PR 13](pr-13-letterlijke-canonieke-tekst.md); dit PR levert de meetcijfers.
