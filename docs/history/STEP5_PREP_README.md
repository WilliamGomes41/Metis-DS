# Stap 5 voorbereid - opslag en retrieval gate v0.1

## Doel
De technische infrastructuur voorbereiden zodat alleen door experts goedgekeurde kennisobjecten in de publiceerbare kennislaag terechtkomen. Embeddings blijven uitgeschakeld totdat de eerste approved dataset bestaat.

## Wat is voorbereid
1. PostgreSQL-basisschema (`db/schema.sql`).
2. Harde publicatiegate: alleen `validation_status=approved` plus reviewer en validatiedatum.
3. View `approved_knowledge_objects` voor downstream gebruik.
4. Importvoorbereiding (`src/storage_prepare.py`) die approved en blocked objecten scheidt.
5. Deterministische retrievaltekst (`src/build_retrieval_document.py`).
6. Embedding- en retrievalconfiguratie standaard uitgeschakeld (`config/step5.yaml`).
7. Automatische tests voor de publicatiegate.

## Wat gebeurt zodra het expertbestand terugkomt
1. Excel-review verwerken naar de semantische JSONL.
2. `approve` -> governance aanpassen naar approved met reviewer en datum.
3. `revise` -> inhoud corrigeren en opnieuw ter review aanbieden.
4. `reject` -> object buiten publiceerbare dataset houden.
5. `storage_prepare.py` uitvoeren.
6. Approved dataset in PostgreSQL/Azure SQL laden.
7. Pas daarna embeddings genereren en retrieval evalueren.

## Belangrijk ontwerpprincipe
De database is de gezaghebbende bron. Een toekomstige vectorindex is een afgeleide zoekindex en mag nooit objecten bevatten die niet in de approved view staan.
