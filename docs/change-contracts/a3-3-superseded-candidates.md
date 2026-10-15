# Change contract: A3-3 superseded candidates

Change class: B
Promise: Na een contractwijziging MOET een verse poging de bestaande kandidaten van die revisie als `superseded` markeren; zichtbaar, NOOIT verwijderd. Goedkeuringen MOGEN NIET meegaan. De publicatiepoort MOET een goedgekeurde `superseded` kandidaat weigeren met precies één reden `superseded_candidate_refused`.
Taalregel: B18. Alleen MOET / MAG NIET / NOOIT; open punten als OPENVRAAG.

## Gebouwd
- `src/candidate_supersession_v1.py` (nieuw): `supersede_for_contract_change` (append-only opvolger via `revise_object`, idempotent), `refuses_superseded` (alleen-lezen).
- `src/operations_console_v1.py:4699-4701`: één poortcontrole, direct na het reviewer/review_policy-blok; dat blok is ongewijzigd.
- Tests: `tests/test_candidate_supersession_v1.py` (6), waarvan 3 poorttests fail-first faalden zonder de poortregel.

## Trigger (na merge van main met #628/#630)
- `src/operations_console_v1.py:2544-2552` (re-extract, niet-resume): bij een verse poging MOET `supersede_if_contract_changed` de bestaande kandidaten van de revisie als `superseded` markeren wanneer de opgeslagen volledige contractidentifier verschilt van die van de actieve modus (`semantic_contract_version_for_mode`, #630). Zonder opgeslagen of actieve identifier MAG NIET gesuperseded worden.
- Poortcontrole staat nu op `operations_console_v1.py:4766-4768`, na het 2b-3 review_configuration-blok; dat blok en het reviewer-blok zijn ongewijzigd.
- Fail-first: `test_fresh_attempt_after_contract_change_supersedes_existing_candidates` rood zonder trigger, groen met.

## OPENVRAAG
- OPENVRAAG-A3-3-1 (deels opgelost): de aanroep van `supersede_for_contract_change` op het pad "verse poging na contractwijziging" MOET wachten op #628 (helper `resume_contract_current`/volledige contractidentifier staat daar). Het re-extractpad weigert nu bij bestaande bindingen/review_passes (`pre_review_retry_existing_work`); of die weigering bij een contractwijziging MOET wijken, beslist Forge/Metis.
- PR MAG NIET geopend worden voordat 2b-3 gemerged is (Forge).
