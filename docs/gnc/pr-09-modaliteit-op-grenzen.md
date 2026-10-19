# PR 9 — Modaliteit en ontkenning op spangrenzen

Dit PR vangt de foutklasse waarbij een spangrens "niet", "alleen bij" of "tenzij" afsnijdt zonder dat er één teken wijzigt. Het is een goedkope, deterministische controle voor een gevaarlijke fout.

```text
Change class: B
Promise: Een kandidaat waarvan de spangrens een ontkenning of modaliteitsmarker vlak buiten de span laat liggen, krijgt een bevinding.
Proof: een span die begint na "niet" in "niet routinematig toedienen" geeft modality_cut_at_boundary; dezelfde zin met "niet" binnen de span geeft niets.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

I2 voorkomt tekstmutatie, maar niet een verkeerd gekozen grens. R11 (modaliteit), X03 (negatie in uitzonderingen) en O04 ("geen actie" in uitkomsten) vragen precies dit. Bestaande regexen in `admission_gate_v1` (`_EXCEPTION_RE`, `_CONDITION_RE`) en `object_taxonomy_v1` kijken naar de tekst binnen de kandidaat, niet naar wat ernaast is weggevallen.

## Ontwerp

- **Stateless.** `boundary_modality_findings(candidate, source_blocks) -> list[Finding]`.
- **Venster:** een vast aantal tokens direct vóór en na elke span in hetzelfde bronblok, plus een afgebroken zin binnen de span.
- **Markers:** ontkenning (niet, geen, nooit), beperking (alleen, uitsluitend, slechts), voorwaarde (indien, mits, bij, tenzij, behalve), voorzichtigheid (overweeg, kan, terughoudend). Eén lijst, gedeeld met de signaalwoorden uit PR 5 via het register.
- **Uitkomst:** `modality_cut_at_boundary` (bedoeld `block` voor ontkenning, `signal` voor de rest), `sentence_truncated` (`signal`).
- **Beslisbomen:** dezelfde controle op knoop- en uitkomstteksten (O04).

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_b_common_v1.py` | Nieuw: grenscontrole, gedeeld door richtlijn- en beslisboomcontract |
| `src/gnc_rule_registry_v1.py` | R11, X03, O04 en de markerlijst |
| `tests/test_gnc_boundary_modality_v1.py` | Positieve en negatieve gevallen per markergroep, meerspanselectie, zinsafbreking |

## Wat niet verandert

De spans zelf en de selectie. Het PR repareert geen grens; een correctie gaat terug door de bestaande selectie en materialisatie.

## Tests en acceptatie

- [ ] Elke markergroep heeft een positief en negatief geval.
- [ ] Vals-positief-aandeel op de golden set gerapporteerd vóór `enforced` aangaat voor ontkenning.
