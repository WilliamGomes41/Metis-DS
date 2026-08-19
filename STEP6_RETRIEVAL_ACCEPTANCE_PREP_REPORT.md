# Stap 6 - Golden testset en retrieval projection

Datum: 2026-08-19
Status: TECHNISCH PASS / PRODUCTIE-ACCEPTATIE NOG NIET ACTIEF

## Doel

Stap 6 bereidt de retrieval-acceptatiewerkstroom voor zonder de publicatiegate uit stap 5 te omzeilen. Er zijn nog geen embeddings gemaakt en er is nog geen RAG/chatbot aangesloten.

## Gebouwd

1. `data/golden/fractuurpreventie_page15_golden_v0.1.json`
   - 24 testvragen.
   - 6 feiten (25%).
   - 6 voorwaarden/scores (25%).
   - 4 uitzonderingsvragen (16,7%).
   - 2 versie/publicatieconflicten (8,3%).
   - 6 no-answer/abstention-vragen (25%).
   - Status van de set is voorlopig totdat de onderliggende kennisobjecten klinisch gepubliceerd zijn.

2. `src/validate_golden_set.py`
   - Valideert unieke vraag-ID's, categorieën, gedragsregels en abstention-dekking.

3. `src/retrieval_projection_v2.py`
   - Accepteert uitsluitend expliciete publication envelopes zoals geëxporteerd door `canonical_store.py`.
   - Blokkeert niet-goedgekeurde of onzekere objecten.
   - Maakt alleen zoekrecords voor inhoudelijke objecttypen.
   - `document`, `section` en `supersession` worden niet als zelfstandig zoekresultaat geïndexeerd.
   - Kopieert gekoppelde condition-/parent-context naar de afgeleide retrieval-view.
   - Behoudt object-ID, objectversie, content-hash, release-ID, bronversie en bronlocatie.
   - Genereert een deterministische `projection_hash`.
   - Wijzigt canonieke data niet.
   - Embeddings blijven uitgeschakeld.

## Productierun

De echte canonical store bevat momenteel 0 gepubliceerde objecten.

Resultaat:

- published export: 0 objecten;
- retrieval projection: 0 records;
- blocked records: 0;
- canonical data mutated: false;
- embeddings: disabled.

Dit is het verwachte fail-closed gedrag zolang expertvalidatie en bronintegriteit niet volledig zijn afgerond.

## Geisoleerde fixture-run

Een expliciet als synthetisch gemarkeerde publication fixture is gebruikt om de toekomstige downstream-transformatie te testen.

Resultaat:

- 21 fixture-envelopes;
- 19 zoekbare retrieval-records;
- 0 blocked;
- document/section objecten correct uitgesloten als zelfstandig zoekresultaat;
- gekoppelde klinische context correct meegenomen;
- `>= 3`/`gte 3`-logica behouden in het score-object.

De fixture is uitsluitend testdata en is niet in de canonieke store gepubliceerd.

## Regressietests

Volledige suite:

`32 passed`

De suite controleert nu onder andere:

- Protocol-v2-schema en deterministische semantische transformatie;
- review/publication gates;
- canonical storage, supersession en emergency unpublish;
- alleen published envelopes naar retrieval;
- contextbehoud in retrieval projections;
- deterministische projection hashes;
- bestaan van alle golden-set objectreferenties;
- 25% no-answer-dekking en verplichte abstention.

## Gate

**Stap 6 technische voorbereiding: PASS**

**Retrieval acceptance op echte V&VN-content: BLOCKED** totdat minimaal een eerste release daadwerkelijk `published` is.

## Volgende technische stap

Bouw een deterministische baseline retrieval-engine bovenop de retrieval projection (metadatafilter + lexical search), en voer daarmee de golden set uit. Pas daarna wordt vector/embedding retrieval toegevoegd voor een gecontroleerde vergelijking tegen dezelfde golden set.
