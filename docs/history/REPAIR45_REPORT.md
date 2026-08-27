# Reparatiestap 4.5 - technisch rapport

## Doel
Herstel de pilot vóór stap 5 zodat de keten reproduceerbaar, herleidbaar, testbaar en fail-closed is.

## Uitgevoerde reparaties
1. Expliciete, versieerbare semantische specificatie toegevoegd (`data/semantic_page15_spec.json`).
2. Bronmanifest toegevoegd met de bekende runtimebeperking rond het ontbreken van de lokale PDF-binary.
3. Klinische operator gecorrigeerd: `Roken en/of alcohol >= 3 eenheden per dag` is gemodelleerd als `gte`, threshold `3`.
4. Schema v0.3 toegevoegd met provenancevelden voor spec- en extract-hashes.
5. `semantic_transform.py` herschreven zodat output reproduceerbaar uit de spec ontstaat en integriteitschecks worden gerapporteerd.
6. Adapter toegevoegd voor het reeds verstuurde expert-Excel (`import_expert_validation.py`). Het Excel hoeft niet opnieuw te worden uitgezet.
7. Review-snapshotbescherming toegevoegd: een expertbesluit mag niet stil worden toegepast op een inhoudelijk gewijzigd object met hetzelfde ID.
8. Revisies worden nooit automatisch toegepast; ze komen in een revision queue.
9. Storage-gate aangescherpt: schema, hash, reviewer, datum en approved-parent worden gecontroleerd.
10. Persistente pytest-tests toegevoegd.
11. Pre-step-5 release gate toegevoegd; stap 5 blijft geblokkeerd zolang klinische review niet volledig en foutloos is.

## Regressieresultaat
- 20 semantische objecten opnieuw gegenereerd.
- Schema v0.3: geldig.
- Object-ID's: uniek.
- Parent-relaties: geldig.
- Content hashes: geldig.
- Embeddings: niet aanwezig.
- 10 geautomatiseerde tests: geslaagd.
- Bestaand expert-Excel: 20 regels importeerbaar.

## Belangrijke bescherming voor reeds verstuurd Excel
Het verstuurde Excel bevat voor score-regel 07 nog de oude `> 3` tekst. De actuele canonieke dataset gebruikt `>= 3` / `gte`. Daarom blokkeert de validation workflow een eventueel besluit op die regel met `review_snapshot_mismatch`; het besluit wordt niet stil op het gecorrigeerde object toegepast.

## Open afhankelijkheid
De oorspronkelijke PDF-binary is in deze runtime niet opnieuw op te halen vanwege een verificatiepagina. De keten is daarom reproduceerbaar vanaf de behouden ruwe extractie (`output/fractuurpreventie_page15_raw.jsonl`). Zodra de PDF intern beschikbaar is, moet die als immutable raw source worden toegevoegd en kan stap 2 volledig vanaf de binary worden gereproduceerd.

## Gate voor stap 5
Stap 5 mag pas starten als:
- semantic schema + integriteitschecks groen zijn;
- alle expertbesluiten zijn verwerkt;
- geen validation errors bestaan;
- pending/revise = 0;
- pre-step-5 gate = PASS.
