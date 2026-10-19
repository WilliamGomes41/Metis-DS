# PR 13 — Letterlijke canonieke tekst voor nieuwe kandidaten

Dit PR haalt `normalize_visible_prose(" ".join(parts))` weg als vorm van canonieke kandidaattekst: nieuwe kandidaten bewaren hun spans letterlijk en apart, en worden exact vergeleken met de gepinde bron. Bestaande kandidaten blijven onder hun eigen versie geldig en verifieerbaar.

```text
Change class: A
Promise: Elke nieuw gevormde kandidaat bestaat uit bronspans die teken voor teken gelijk zijn aan de gepinde extractierepresentatie, zonder ingevoegde scheidingstekens of normalisatie.
Proof: een nieuwe kandidaat over twee fragmenten heeft twee letterlijke spans en nul A02-bevindingen; een bestaande kandidaat van de vorige versie verifieert ongewijzigd en houdt dezelfde canonical_object_hash.
Touches lifecycle invariants: yes
Rewrite risk: high
```

## Waarom

De materialisator voegt fragmenten samen en normaliseert, en `validate_materialised_candidate` vergelijkt ná normalisatie (r. 315). Daarmee wordt genormaliseerde tekst als letterlijk identiek behandeld. [PR 3](pr-03-letterlijkheid-a02.md) levert eerst de cijfers over hoe vaak en hoe dit afwijkt.

## Waarom Class A en hoog risico

Kandidaattekst zit in `compute_canonical_object_hash`, die gelijk is aan de reviewsnapshot-hash. De wijziging raakt dus persisted identity-semantiek, reviewgeldigheid en elke lezer van `text` en `clean_text` (review-UI, retrieval, publicatie, export). Volgens `docs/agents/continuous-development.md` §2 vraagt dat alle mitigatievelden en een adversariële review vóór merge.

## Ontwerp (alleen na besluit)

- **Zelfde kandidaatmaker, nieuwe versie.** `materialise_knowledge_candidates()` blijft de enige; zij schrijft `semantic_passage.version` = nieuwe versie met `literal_spans` (letterlijke tekst per span) als canonieke inhoud.
- **Weergavetekst is een projectie.** Een samengevoegde leesweergave voor UI en zoeken wordt afgeleid, met zichtbare spangrenzen, en is nooit canoniek.
- **Versiegebonden lezer.** `validate_materialised_candidate` kiest de vergelijking op basis van de opgeslagen versie: exact voor de nieuwe versie, de huidige vergelijking alleen voor bestaande objecten. Dit is een lezer, geen tweede maker.
- **Geen herberekening.** Bestaande kandidaten, reviews en releases worden nooit opnieuw gevormd (I8). Herverwerking van een bron volgt de bestaande successorroute en levert nieuwe objecten op.
- **Identiteit:** `_candidate_identity` is al spangebaseerd en blijft gelijk; de canonieke hash van nieuwe objecten volgt de nieuwe inhoud.

**Lifecycle-velden (verplicht vóór code):** welke snapshots en reviews onder welke versie vallen; cutover-moment (vanaf een nieuwe verwerkingspoging, nooit midden in een poging); rollback (terugschakelen van de versie voor nieuwe pogingen, al gevormde nieuwe objecten blijven leesbaar); herstart en retry (een poging houdt de versie waarmee zij begon); adversariële scenario's (gemengde versies in één document, oude snapshot opnieuw gereviewd, retrieval die `clean_text` vergelijkt).

## Wijzigingen (indicatief)

| Bestand | Wijziging |
| --- | --- |
| `src/knowledge_materialisation_v1.py` | Nieuwe versie zonder join en normalisatie; versiegebonden validatie |
| `src/integrity_kernel.py` | Canonieke payload voor de nieuwe versie expliciet vastgelegd |
| Lezers van `text`/`clean_text` | Afgeleide weergave gebruiken; inventaris uit fase A van de topologiekaart |
| `docs/adr/` | ADR met het besluit en de mitigatievelden |

## Voorwaarden om te starten

- [ ] PR 3 heeft cijfers over afwijkingsklassen op productie-snapshots.
- [ ] Volledige lezerinventaris van `text` en `clean_text`.
- [ ] Besluit genomen en ADR goedgekeurd door de eigenaar van de lifecycle-contracten.
