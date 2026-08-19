# Stap 7 - Deterministische lexical retrieval baseline

Datum: 2026-08-19
Status: BASELINE TECHNISCH PASS / PRODUCTIE-ACCEPTATIE GEBLOKKEERD TOT PUBLICATIE

## Doel

Een auditeerbare retrieval-baseline vastleggen voordat embeddings/vector search worden toegevoegd. De baseline gebruikt BM25, exacte bigram-bonus en een fail-closed abstentionregel op basis van score + query-dekking.

## Gebouwd

- `src/lexical_retrieval_v1.py` - deterministische BM25 retrieval-engine.
- `src/evaluate_retrieval_baseline.py` - golden-set evaluator.
- `config/retrieval_baseline_v1.json` - expliciete ranking/abstentionconfiguratie.
- `scripts/run_retrieval_baseline_v1.sh` - reproduceerbare runner.
- Retrieval projection uitgebreid met `structured_logic`, zodat operatoren/drempels downstream machineleesbaar blijven.
- Repository-consistentie hersteld: ontbrekende protocol-v2 validatiescripts, proposal-schema en retrieval-projection regressietests teruggezet uit de eerder gegenereerde protocolpakketten.

## Veiligheidsmodel

Een lexical match is niet automatisch een antwoord. De engine retourneert alleen resultaten wanneer:

1. top BM25-score boven de minimumscore ligt;
2. IDF-gewogen query-dekking minimaal 0,30 is;
3. minimaal twee betekenisvolle termen matchen.

Anders volgt `abstain`.

## Golden-set baseline op synthetische publication fixture

De fixture is uitsluitend testdata en publiceert niets in de canonieke store.

- corpus: 19 zoekbare records;
- published-corpus vragen: 22;
- retrievalvragen: 16;
- `retrieve_any_hit@5`: 68,75%;
- micro expected-object recall@5: 66,67%;
- no-answer vragen: 6;
- abstention accuracy: 100%;
- projection content/logic integrity: 100% (24/24 checks).

Vijf retrievalvragen worden bewust geabstaind door de veiligheidsdrempel. Voor drie daarvan is de correcte bron wel de hoogste lexical kandidaat, maar de query-dekking is onvoldoende. Dit is nuttige benchmarkinformatie: semantische/vector retrieval moet deze vragen verbeteren zonder de 100% abstention op de no-answer-set te verslechteren.

## Echte huidige V&VN-dataset

De echte canonical store heeft nog 0 gepubliceerde objecten. De productieroute levert daarom correct:

- published envelopes: 0;
- retrieval records: 0;
- blocked projection records: 0;
- embeddings: disabled.

Er wordt dus geen synthetische fixture gebruikt als productiebron.

## Volledige regressiegate

`37 passed`

De tests omvatten nu informatiemodel, deterministische semantic transform, review/snapshot, 4-ogen, publication/supersession/emergency-unpublish, retrieval projection, structured logic, lexical baseline en abstention.

## Beslissing

De lexical baseline is vastgesteld als comparator; hij is niet de eind-retrieval-engine.

Volgende technische werkstroom: semantische/vector retrieval toevoegen achter dezelfde `published` projection en exact dezelfde golden set. Een nieuwe methode mag abstention safety niet verslechteren.
