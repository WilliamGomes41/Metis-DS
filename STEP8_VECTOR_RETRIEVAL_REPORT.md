# Stap 8 - Lokale vector retrieval baseline

## Status
PASS voor technische pilotvoorbereiding. Niet vrijgegeven als productie-embeddinglaag.

## Doel
Testen of een afgeleide vectorindex retrieval verbetert ten opzichte van de lexical baseline, zonder abstention te verslechteren en zonder canonieke data te muteren.

## Implementatie
- Engine: `local-char-tfidf-vector-v1.0.0`
- Vectorisatie: karakter n-gram TF-IDF (`char_wb`, 3-5)
- Similarity: cosine
- Top-k: 5
- Voorlopige abstention threshold: 0.23
- Input: uitsluitend retrieval projection records uit de published view
- Canonieke knowledge objects worden niet gewijzigd
- Index signature is deterministisch op basis van projection hashes + configuratie

Deze implementatie is bewust **geen pretrained semantic embedding model**. Zij valideert de vector-retrievalarchitectuur lokaal en reproduceerbaar voordat een externe embeddingprovider wordt toegevoegd.

## Resultaten op voorlopige golden set
- Published-corpus vragen: 22
- Retrievalvragen: 16
- Verwachte bron in top-5: 15/16 = 93.75%
- Micro expected-object recall@5: 94.44%
- No-answer vragen: 6
- Correcte abstention: 6/6 = 100%
- Projection content integrity: 24/24 = 100%

Vergelijking lexical baseline:
- Lexical retrieve-any-hit@5: 68.75%
- Vector retrieve-any-hit@5: 93.75%
- Verbetering: +25 procentpunt
- Abstention: 100% -> 100%

## Bekende retrievalfout
`FP-F05` (achtergrond/aandoeningen) krijgt het verwachte definition-object niet in top-5. De topmatch is score-rule 08. Dit wordt niet weggetuned op de huidige golden set; het blijft een expliciete fout voor de volgende hybrid/embeddingvergelijking.

## Belangrijke methodologische beperking
De similarity threshold is voorlopig gekalibreerd op dezelfde kleine preliminary golden set. De 93.75%/100%-scores zijn daarom ontwikkelmetingen, geen onafhankelijke acceptatieclaim. Voor een echte acceptance gate is een uitgebreidere of afzonderlijke holdoutset nodig.

## Echte dataset
De actuele productieview bevat 0 published objecten. De lokale vectorindex bouwt daarom geen echte index en abstaint op iedere query met reden `empty_published_corpus`. Dit is het gewenste fail-closed gedrag zolang validatie/publicatie niet gereed is.

## Regressie
Volledige projectsuite: 43 tests passed.

## Volgende technische stap
Bouw een hybrid retrieval comparator (lexical + local vector) en daarna een pluggable embedding-provider interface. Een extern/pretrained embeddingmodel mag pas worden beoordeeld tegen dezelfde vaste benchmark en mag abstention niet verslechteren.
