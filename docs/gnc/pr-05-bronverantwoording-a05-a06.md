# PR 5 — A05/A06 bronverantwoording en signaalwoorden

Dit PR maakt de sluiting van het passageregister meetbaar over álle geëxtraheerde bereiken, legt vast dat alleen mensen kunnen uitsluiten, en markeert open of uitgesloten passages die klinische signaalwoorden bevatten.

```text
Change class: B
Promise: Per document is zichtbaar welk aandeel bronbereik verantwoord is, en elke open of uitgesloten passage met een klinisch signaalwoord wordt voor review gemarkeerd.
Proof: accountability_findings geeft op een fixture het juiste open-aandeel en markeert een uitgesloten passage met "tenzij"; een machine-uitsluiting laat de test falen.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

De second opinion noemde "relevant bronbereik" circulair. De code doet het al beter dan het voorstel: `excluded_with_reason` komt alleen via menselijke review (`geen_kenniseenheid`), en machineblokkades gaan terug naar `not_yet_assessed`. Dat gedrag is nu impliciet en niet beschermd door een test. Signaalwoorden ontbreken.

## Ontwerp

- **Stateless.** `accountability_findings(objects) -> list[Finding]` leest `metadata.passage_register` en schrijft niets.
- **Sluiting over alle bereiken:** aandeel `not_yet_assessed` per sectierol (hergebruik `extract_coverage_v1.coverage_by_section_role`).
- **Uitsluitingsbron vastleggen:** eigenschapstest dat `_initial_status` nooit `excluded_with_reason` oplevert; alleen `apply_register_from_review` mag dat.
- **Getypeerde reden:** de review-suitability `geen_kenniseenheid` krijgt een verplichte subreden uit een gesloten lijst (literatuurlijst, methodiek, colofon, inhoudsopgave, overig met toelichting). Dit raakt de reviewinvoer en is daarom de enige stateful stap in dit PR.
- **Signaalwoorden:** Nederlandse lijst in het register (niet, geen, tenzij, behalve, uitgezonderd, alleen bij, indien, mits, contra-indicatie, maximaal, doses en eenheden). Een treffer in een open of uitgesloten passage geeft bevinding `accountability_signal_word`.

**Stateful overlay (alleen voor de subreden).**

```text
Domain entity/aggregate: passage_register-record van een passage
Invariant(s): excluded_with_reason heeft altijd een subreden uit de gesloten lijst
Durable state before: status + suitability
Durable state after: idem + exclusion_reason
Transaction boundary: bestaande reviewtransactie van apply_register_from_review
Failure/recovery result: ontbrekende subreden = review-commando geweigerd, niets geschreven
Duplicate execution / idempotency result: zelfde commando twee keer = zelfde record
Concurrency result: bestaande optimistische versiecontrole van de review
Audit/evidence requirement: subreden in het bestaande review-event
```

Bestaande uitsluitingen zonder subreden blijven geldig en tonen `exclusion_reason: legacy_unspecified`; ze worden niet herschreven.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_gate_a_v1.py` | `accountability_findings`, signaalwoordlijst |
| `src/passage_register_v1.py` | `exclusion_reason` in `passage_register_record`; validatie in `apply_register_from_review` |
| `src/review_cockpit_v1.py` | Keuzelijst subreden bij `geen_kenniseenheid` |
| `tests/test_gnc_gate_a_accountability_v1.py` | Sluiting, signaalwoorden, eigenschapstest machine-uitsluiting, legacy-weergave |

## Wat niet verandert

De vijf registerstatussen, de mapping van suitability naar status, bestaande menselijke uitsluitingen en hun reviewhash.

## Tests en acceptatie

- [ ] Geen codepad buiten review levert `excluded_with_reason` op.
- [ ] Uitsluiten zonder subreden wordt geweigerd; met subreden slaagt.
- [ ] Een open passage met "tenzij" of een dosering geeft een signaal.
- [ ] Bestaande fixtures met uitsluiting laden ongewijzigd.
