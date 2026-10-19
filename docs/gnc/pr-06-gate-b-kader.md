# PR 6 — Gate B-kader, ernstmatrix en doorgifte

Dit PR legt het skelet waar alle Gate B-regels in hangen: expliciete contractselectie per documenttype, één bevindingenformaat voor A en B, en doorgifte via de bestaande admission. Nog zonder nieuwe inhoudelijke regels.

```text
Change class: B
Promise: Elk object wordt beoordeeld tegen precies één expliciet gekozen Gate B-contract, en een onbekend documenttype krijgt een UNRESOLVED-bevinding in plaats van richtlijnregels.
Proof: een beslisboom krijgt decision-tree-semantics-v1, een richtlijn guideline-semantics-v1, en een handreiking zonder contract gate_b_contract_missing.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

`review_path_for_klasse()` groepeert meerdere documentklassen onder de richtlijnroute. Zonder expliciete selectie valt een protocol of handreiking stil onder richtlijnregels. Ook ontbreekt één plek waar `PASS`, `BLOCK` en `UNRESOLVED` naar bestaande admission worden vertaald.

## Ontwerp

- **Stateless.** `select_gate_b_contract(klasse) -> ContractId | None` en `evaluate_gates(candidate, context) -> list[Finding]`.
- **Bevinding** (dataclass): `rule_id`, `outcome` (`PASS`/`BLOCK`/`UNRESOLVED`), `reason_code`, `refs` (bronlocators), `contract_version`. Geen eigen opslag.
- **Doorgifte:** één functie in `admission_gate_v1` zet bevindingen om in `reason_codes`. Alleen regels met `enforced: true` in het register (PR 1) mogen `gate_result` op `blocked` zetten; de rest is signaal.
- **Alleen strenger:** een gate kan `allowed` naar `blocked` brengen, nooit andersom.
- **Contractversie gebonden aan de poging:** de gekozen contract-ID en versie gaan mee in de bestaande admissionrecord, zodat replay dezelfde regels gebruikt.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_contracts_v1.py` | Nieuw: contractselectie, `Finding`, `evaluate_gates`, lijst ondersteunde documentklassen |
| `src/admission_gate_v1.py` | `apply_gate_findings`: bevindingen naar `reason_codes`, alleen-strenger-regel |
| `src/gnc_rule_registry_v1.py` | Contract-ID per regel |
| `tests/test_gnc_contracts_v1.py` | Selectie per klasse, onbekende klasse, eigenschapstest alleen-strenger, replay met vaste contractversie |

## Wat niet verandert

`review_path_for_klasse()` en de reviewroutes; bestaande admissionrecords; de bestaande regels in admission blijven werken tot hun eigenaar in het register is overgezet (opruimen gebeurt in PR 14).

## Tests en acceptatie

- [ ] Elke klasse in `object_taxonomy_v1` is gekoppeld aan een contract of expliciet aan "geen contract".
- [ ] Geen combinatie van bevindingen maakt een `blocked` object `allowed` (property-based test).
- [ ] Met alle regels `enforced: false` is de admissionuitkomst op alle fixtures identiek aan `main`.
