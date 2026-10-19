# PR 2 — Golden set v2: context, voorwaarden, routes

Dit PR breidt het golden-setformaat uit met wat Gate B moet meten: welke context een kenniseenheid veilig maakt, welke voorwaarden en uitzonderingen erbij horen, en welke routes een beslisboom heeft. Het annotatiewerk zelf loopt parallel en bepaalt waarschijnlijk de doorlooptijd van het hele programma.

```text
Change class: B
Promise: Recall van aanbevelingen, voorwaarden, uitzonderingen, scope en beslisboomroutes is meetbaar tegen onafhankelijke expertannotatie.
Proof: validate_golden_set accepteert een geannoteerde v2-richtlijn en v2-beslisboom en weigert een set zonder tweede annotator.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

De bestaande sets in `data/golden` meten extractie en objecttypen, niet contextvolledigheid. Zonder deze meetlat kan geen enkele latere PR aantonen dat er minder klinisch relevante omissies zijn.

## Ontwerp

- **Stateless, offline data.** Bestanden in `data/golden/v2/`, nooit gelezen door productieroutes.
- **Richtlijn-annotatie per aanbeveling:** kernspan; slots doelgroep, indicatie, richting, sterkte (`explicit`, `not_stated`, `unmapped`); lijst voorwaarden en uitzonderingen als bronspans; scope (`own_span`, `inherited_from` met kopspan, of `not_in_source`); per voorwaarde in dezelfde scope het besluit `applies` of `not_applicable`.
- **Beslisboom-annotatie:** de volledige verzameling routes van start naar uitkomst, elk als geordende lijst knoop-ID's met antwoordlabels, plus herhalingsranden apart gemarkeerd.
- **Twee annotatoren per document.** Verschillen worden opgeslagen, niet weggemiddeld; een beslissing op een verschil legt de reden vast.
- **Holdout.** Minstens één richtlijn en één beslisboom in `data/holdout/`, nooit gebruikt om regels af te stellen.

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `schemas/golden_set_v2.schema.json` | Nieuw schema voor richtlijn- en beslisboomannotatie |
| `src/evaluation/validate_golden_set.py` | v2-validatie: spans bestaan in de gepinde bron, twee annotatoren aanwezig, verschillen expliciet |
| `src/evaluation/gnc_metrics_v1.py` | Nieuw: recall per categorie, klinisch gewogen omissies, overeenstemming tussen annotatoren |
| `docs/gnc/annotation-guide.md` | Annotatiehandleiding voor verpleegkundige experts |
| `tests/test_golden_set_v2.py` | Schema- en metriektests op een kleine synthetische set |

## Wat niet verandert

Bestaande v0.1-sets en hun validatie blijven werken. Geen productiecode leest `data/golden`.

## Tests en acceptatie

- [ ] Een set zonder tweede annotator of met een span buiten de bron wordt geweigerd.
- [ ] Metrieken op de synthetische set geven vooraf berekende waarden.
- [ ] Acceptatienormen per maat (minimale recall voorwaarden en uitzonderingen) staan vast in `docs/gnc/acceptance.md` vóór de eerste meting.

## Open vragen

- Welke twee richtlijnen en welke beslisboom worden de eerste set? Voorkeur: een met veel contra-indicaties en een met modulebrede doelgroep.
- Wie zijn de twee annotatoren, en hoeveel uur per document is beschikbaar? Dit bepaalt het kritieke pad.
