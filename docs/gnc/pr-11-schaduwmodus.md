# PR 11 — Schaduwmodus over bestaande objecten

Dit PR draait alle Gate A- en B-regels read-only over opgeslagen snapshots en levert een rapport, zonder enige statuswijziging. Het rapport is het bewijs waarop per regel `enforced: true` wordt besloten, en het laat zien of eerder goedgekeurde kennis onder het scherpere contract gaten heeft.

```text
Change class: B
Promise: Per regel, documenttype en snapshot is zichtbaar hoe vaak de regel zou blokkeren of signaleren, zonder dat er iets in de workflowopslag verandert.
Proof: shadow_report op de fixturesnapshots geeft een rapport, en een vergelijking van de opslag vóór en na de run toont nul gewijzigde bytes.
Touches lifecycle invariants: no
Rewrite risk: none
```

## Waarom

De second opinion vroeg om schaduwmodus bij elke nieuwe Gate B-versie. Zonder cijfers zijn ernstniveaus gokwerk, en een `BLOCK`-regel die onverwacht veel bestaande kennis raakt, overspoelt de review.

## Ontwerp

- **Stateless en offline.** CLI `python -m src.gnc_shadow_v1 --snapshot <id>`; leest via de bestaande read-boundary, schrijft alleen naar `output/gnc_shadow/`.
- **Geen schrijfrechten.** Het script krijgt een read-only store-handle; een poging tot schrijven faalt hard (test).
- **Rapport per regel:** aantal `BLOCK`, `UNRESOLVED`, `signal`; uitgesplitst naar documenttype, objecttype en reviewstatus (vooral: al gepubliceerde objecten).
- **Golden-setvergelijking:** waar een document in de golden set zit, precisie en recall van de regel tegen de annotatie.
- **Beslisregel voor `enforced`:** opgenomen in `docs/gnc/acceptance.md`; per regel een GO met verwijzing naar een concreet rapport (commit, snapshot, datum).

## Wijzigingen

| Bestand | Wijziging |
| --- | --- |
| `src/gnc_shadow_v1.py` | Nieuw: read-only runner en rapport (JSON en Markdown) |
| `tests/test_gnc_shadow_v1.py` | Read-only garantie, rapportvorm, determinisme bij twee runs |
| `docs/gnc/acceptance.md` | Beslisregel en sjabloon voor de GO per regel |

## Wat niet verandert

Alle opgeslagen objecten, reviews en publicaties. Bevindingen op al gepubliceerde objecten leiden niet automatisch tot actie; ze gaan als lijst naar de bestaande revisieroute, waar een mens beslist.

## Tests en acceptatie

- [ ] Twee runs op dezelfde snapshot geven byte-identieke rapporten.
- [ ] Schrijfpoging via de handle faalt.
- [ ] Eerste rapport over productie-snapshots gedeeld vóór welke `enforced`-wijziging dan ook.
