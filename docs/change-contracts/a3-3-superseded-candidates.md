# Change contract: A3-3 superseded candidates

Change class: B
Promise: Na een contractwijziging MOET een verse poging de bestaande kandidaten van die revisie als `superseded` markeren; zichtbaar, NOOIT verwijderd. Goedkeuringen MOGEN NIET meegaan. De publicatiepoort MOET een goedgekeurde `superseded` kandidaat weigeren met precies één reden `superseded_candidate_refused`.
Taalregel: B18. Alleen MOET / MAG NIET / NOOIT; open punten als OPENVRAAG.

## Gebouwd
- `src/candidate_supersession_v1.py` (nieuw): `supersede_for_contract_change` (append-only opvolger via `revise_object`, idempotent), `refuses_superseded` (alleen-lezen).
- `src/operations_console_v1.py:4774-4779`: twee poortcontroles naast elkaar, na het 2b-3 review_configuration-blok en buiten het reviewer-count-blok; ze voegen alleen toe aan blockers (`superseded_candidate_refused` r4774-4776, `superseded_not_reproduced` r4777-4779).
- Tests: `tests/test_candidate_supersession_v1.py` (6), waarvan 3 poorttests fail-first faalden zonder de poortregel.

## Trigger (na merge van main met #628/#630)
- `src/operations_console_v1.py:2544-2552` (re-extract, niet-resume): bij een verse poging MOET `supersede_if_contract_changed` de bestaande kandidaten van de revisie als `superseded` markeren wanneer de opgeslagen volledige contractidentifier verschilt van die van de actieve modus (`semantic_contract_version_for_mode`, #630). Zonder opgeslagen of actieve identifier MAG NIET gesuperseded worden.
- Poortcontrole staat nu op `operations_console_v1.py:4766-4768`, na het 2b-3 review_configuration-blok; dat blok en het reviewer-blok zijn ongewijzigd.
- Fail-first: `test_fresh_attempt_after_contract_change_supersedes_existing_candidates` rood zonder trigger, groen met.

## OPENVRAAG
- OPENVRAAG-A3-3-1: opgelost. De trigger staat in `reextract_unpublished` r2544-2552 (#628/#630 op main); de weigering bij review-werk is besloten als A33-3 hieronder.

## Besluiten Metis (15-10-2026)

- **A33-1 (optie b):** een superseded kandidaat die de verse poging NIET reproduceert, MOET publicatie blokkeren met precies één reden `superseded_not_reproduced` (`src/candidate_supersession_v1.py::superseded_not_reproduced`, poort r4777-4779). Alleen supersessie met de lineage-reden `contract change supersession` telt; een gewone same-source retirement MAG NIET dit blok geven.
- **A33-2:** deterministic-v1 heeft geen semantische contractversie en supersedeert daarom NOOIT (gedekt door `test_legacy_replay_without_contract_supersedes_nothing`).
- **A33-3:** A3-3 geldt in deze PR alleen vóór review. Een automatische re-extract MOET geweigerd blijven zodra bindings of review_passes bestaan (`pre_review_retry_existing_work`); er wordt dan NOOIT iets gesupersedeerd. De Publisher-actie voor reviewed documenten volgt in een latere PR.
