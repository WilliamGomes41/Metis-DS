# #974 P4d: een afsluitende keuze sluit de vervolgstappen af (#987)

Branch `ccr-fc816d1f-mljiu0-p4d`, gestapeld op P4c (#983, `08b7799`).

## Wat is veranderd

Kop, type, sterkte en relaties bevestigen alleen een goedkeuring. Een
bronafwijking voedt alleen een correctie. Voor een geschiktheid die die
besluiten niet toelaat (`ALLOWED_FINAL_BY_SUITABILITY`), geldt:

- het formulier verbergt die stappen en toont één zin waarom;
- de kernel negeert antwoorden uit die stappen (`without_closed_follow_up`).

Welke stappen open blijven, komt uit dezelfde regel (`suitabilities_allowing`):

| Geschiktheid | Kop, type, sterkte, relaties | Bronafwijking |
| --- | --- | --- |
| Ja | open | open |
| Nee, ik mis uitleg eromheen | dicht | open |
| Nee, hoort samen met een andere passage | dicht | open |
| Alleen als onderbouwing | open | open |
| Geen zelfstandig stukje kennis | dicht | dicht |

De herstelroute (`DeterministicRepairReviewConsole.review_object`) past na de
rolcontrole dezelfde regel toe. `geen_kenniseenheid` + `goedkeuren_na_correctie`
geeft nu `review_disposition_conflict` met uitleg, in plaats van de herstelpagina.

## Bewijs

- Eerst rood (`399ee56`): 4 tests in `tests/test_review_disposition_choices.py`
  faalden. De stappen waren niet afgebakend, achtergebleven `dit_klopt`-antwoorden
  werden opgeslagen (route prepared én serial), en de correctie opende de herstelpagina.
- `test_revise_keeps_the_structured_repair_flow` dekt de herstelroute nu met
  `mist_context`, waar correctie wél mag.
- Browser (Chromium, 1440 en 390 px, met en zonder JS): per geschiktheid zijn
  precies de verwachte stappen zichtbaar; met JS zijn velden in dichte stappen
  uitgeschakeld en worden ze niet verzonden.

| Bestand | Wat |
| --- | --- |
| `js-no-knowledge-{1440,390}.png` | JS aan, ‘Geen zelfstandig stukje kennis’: alleen afwijzen of later |
| `nojs-no-knowledge-{1440,390}.png` | JS uit, idem via CSS `:has()` |

Zonder `:has()`-ondersteuning blijven alle stappen zichtbaar; de kernel negeert
de antwoorden dan alsnog.
