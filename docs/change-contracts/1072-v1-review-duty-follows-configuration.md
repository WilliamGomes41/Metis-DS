# #1072 — De reviewplicht volgt een v1-configuratie met twee goedkeuringen

Change class: A
Promise: Een document met reviewconfiguratie v1 die twee goedkeuringen vraagt, vraagt na de eerste goedkeuring de tweede persoon om een review, en wordt na beide goedkeuringen publiceerbaar; een v1-keuze met één goedkeuring blijft ongewijzigd.
Proof: Black-box op native PostgreSQL, van inname tot publicatiegereedheid, voor v1 `two_others` zonder en met vierogenvink en v1 `one_other` met vierogenvink; faalt op `main` (`aae99d6`).
Touches lifecycle invariants: yes
Rewrite risk: none

Part of MET-78. Besluit William, 14 november 2026: optie A (“A”). Vastgelegd in #1072 en MET-78.

## Huidige toestand (op `main`)

- De publicatiecontrole (`four_eyes_v1.publish_authorization_contract`, via `configured_approval`) eist bij een
  gekozen v1-configuratie:
  - `two_others`: een goedkeuring van **beide** benoemde reviewers, met of zonder vierogenvink (B10);
  - `one_other` met vierogenvink: de reviewer **en** de uploader.
- De inname zet alleen een v2-keuze om in een reviewbeleid (`policy_for_configuration`). Voor v1 ontstaat geen
  beleid.
- De reviewplicht (`review_duty_v1.review_stage`) leest het beleid op het object. Zonder beleid kijkt zij alleen naar
  de inhoud. Na de eerste goedkeuring sluit zij de taak.
- Gevolg, gereproduceerd op `main`:
  - de tweede benoemde reviewer wordt geweigerd met `content_duty_required`;
  - de uploader wordt geweigerd met `reviewer_not_named_on_snapshot`;
  - de publicatie blijft geblokkeerd met `review_configuration_approval_missing`.

  Het document is dus nooit publiceerbaar. v1 is de standaard als een keuze zonder contract binnenkomt.

## Wijziging

- `review_configuration_v1.policy_for_configuration` geeft ook voor v1 het beleid dat precies `configured_approval`
  uitdrukt:
  - `two_others`: de eerste benoemde reviewer is de hoofdreviewer, de tweede is verplicht;
  - `one_other` met vierogenvink: de reviewer is de hoofdreviewer, de uploader is verplicht;
  - elke andere v1-keuze: geen beleid, zoals voorheen.
- De inname leidt dat beleid af voor v2 én voor een v1-keuze die het oplevert. Een meegestuurd beleid moet gelijk
  zijn. Het beleid komt via de bestaande projectie op elk object. De reviewplicht leest het daar.
- De consistentiecontrole van H2-1 laat bij `two_others` de vierogenvink buiten beschouwing. Volgens B10 vraagt
  `two_others` met en zonder vink dezelfde plicht.

Eén regel, één bron: de reviewplicht leert niets nieuws, en alleen de inname en de publicatiecontrole lezen de
configuratie (`test_only_ingest_and_publish_gate_read_the_configuration`).

## Lifecycle-specificatie (§14)

```text
Lifecycle entity: WorkingRevision (de kennisobjectversies van een document met een v1-configuratie)
Lifecycle transition: in review → tweede review → (beide goedkeuringen) klaar voor publicatie
Initial durable state: een nieuw ingenomen document met een gekozen v1-configuratie die twee goedkeuringen vraagt.
Trigger: de eerste verplichte persoon keurt een kennisobjectversie goed.
Authorization: ongewijzigd; de tweede verplichte persoon is deelnemer van het beleid (bij one_other met vier ogen
  is dat de uploader) en mag de tweede review doen; de onafhankelijkheidscontrole blijft gelden.
Validation: ongewijzigd (exacte versie, snapshotrevisie, toelating).
Mutable entities: de envelop krijgt bij de inname het afgeleide reviewbeleid; de objecten krijgen het via de
  bestaande projectie; reviewbindingen en reviewlogboek zoals bij elke goedkeuring.
Immutable entities: de gekozen configuratie, bron, annotaties, bouwbewijs, releases, publicatieregister.
Workflow state before: in_review.
Workflow state after: tweede review na de eerste goedkeuring; klaar voor publicatie na beide.
Release state before: geen release.
Release state after: ongewijzigd tot publicatie.
Serving state before: niet uitgeleverd.
Serving state after: niet uitgeleverd tot publicatie.
Expected API result: ingest met een v1-keuze die twee goedkeuringen vraagt slaagt en legt het afgeleide beleid vast;
  een tegenstrijdig meegestuurd beleid geeft review_configuration_policy_conflict.
Expected UI result: de reviewkaart toont na de eerste goedkeuring de tweede review aan de tweede persoon.
Failure result: een tegenstrijdige keuze wordt bij de inname geweigerd; niets wordt half opgeslagen.
Restart result: het beleid staat in de envelop en op de objecten; na herstart geldt dezelfde plicht.
Recovery result: niet nodig voor nieuwe documenten.
Legacy-data result: documenten die al met v1 zijn ingenomen, hebben geen beleid in hun envelop en blijven zoals ze
  zijn. Herstel vraagt een migratie met auditspoor; dat is een apart besluit (#1072).
Required black-box scenario: GIVEN een document met v1 two_others (zonder of met vierogenvink) of v1 one_other met
  vierogenvink; WHEN de eerste persoon goedkeurt; THEN staat het object in de tweede review en blokkeert de review de
  publicatie; WHEN de tweede persoon goedkeurt; THEN blokkeert de review de publicatie niet meer. En: een v1-keuze
  met één goedkeuring krijgt geen beleid.
Explicit non-goals: bestaande v1-documenten migreren; v2-gedrag; de vierogenregel van de inhoud.
```

## Bewijs

- `tests/test_review_configuration_v1_duty_1072.py`: drie black-box gevallen van inname tot publicatiegereedheid
  (falen op `main`) en de twee ongewijzigde v1-keuzes met één goedkeuring.
- De bestaande tests rond reviewconfiguratie, reviewbeleid, vier ogen, tweede review en inname.
