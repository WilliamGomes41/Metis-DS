# Stap 3 - semantische structurering v0.1

Doel: ruwe PDF-layoutblokken omzetten naar betekenisvolle, bronherleidbare kennisobjecten zonder klinische logica te raden.

## Input
- `data/raw/VVN-RL-Osteoporose-1.3.pdf`
- pagina 15 render als visuele controlebron
- `data/semantic_page15_spec.json`: visueel gecontroleerde pilottranscriptie

## Verwerking
`src/semantic_transform.py` bouwt een generieke semantische objectlaag:
- 3 condition/scenario-objecten
- 7 recommendation-objecten
- 1 table-object
- 8 score_rule-objecten
- 1 background-object (voetnoot)

## Schemawijziging
`schemas/knowledge_object.schema.v0.2.json` voegt `logic.score_points` toe. Dit voorkomt dat een risicoscore kunstmatig in `threshold` of platte tekst moet worden verstopt.

## Veiligheidsregel
Geen klinisch relevant teken of getal wordt uit ontbrekende PDF-tekst afgeleid. Waar de tekstlaag tekens verliest, wordt de gerenderde bron visueel gecontroleerd en blijft het object `needs_review`.

## Output
- `output/fractuurpreventie_page15_semantic.jsonl`
- `output/fractuurpreventie_page15_semantic_report.json`
- `output/fractuurpreventie_page15_review.csv`

## Kwaliteitsgates
- JSON Schema valide
- 3 scenario's aanwezig
- 8 scoreregels aanwezig
- verwijzingsdrempel >= 4 punten machine-leesbaar aanwezig
- bronpagina op ieder object aanwezig
- embeddings bewust nog afwezig
- alle klinische objecten blijven `needs_review`

## Bekende open punten
1. Klinische expert moet de 20 objecten valideren.
2. De twee leeftijdsregels (>=60 = 1 en >=70 = 2) zijn als afzonderlijke bronregels opgeslagen; er wordt nog niet geïnterpreteerd of deze cumulatief of exclusief zijn.
3. De lange voetnoot bij onderliggende aandoeningen is nog niet opgesplitst in afzonderlijke condities.
4. De huidige pilot gebruikt een visueel gecontroleerde semantic spec. Een volgende iteratie kan meer van de samenvoeging automatisch uit layoutcoordinaten afleiden.
