# Stap 4 - Klinische validatielaag

Deze stap voegt een harde menselijke validatiegate toe tussen semantische structurering en embeddings/retrieval.

## Bestanden
- `src/validation_workflow.py` - verwerkt reviewbeslissingen.
- `docs/validation_protocol_v0.1.md` - reviewprotocol en beslisregels.
- `output/fractuurpreventie_page15_validation_form.csv` - invulformulier voor de reviewer.
- `output/validation/*_approved.jsonl` - uitsluitend expliciet goedgekeurde objecten.
- `output/validation/*_rejected.jsonl` - expliciet afgewezen objecten.
- `output/validation/*_pending.jsonl` - nog niet beoordeelde of te reviseren objecten.
- `output/validation/*_validation_report.json` - controleverslag.

## Status van deze pilotrun
Er zijn nog geen menselijke reviewbeslissingen ingevuld. Daarom zijn 0 objecten approved en blijven alle 20 objecten pending. Dit is gewenst gedrag.

## Gebruik door reviewer
Vul in de CSV per object `review_decision` in met `approve`, `revise` of `reject`. Voeg bij `reject` altijd een commentaar toe. Vul ook reviewer en reviewdatum in voor auditdoeleinden. Daarna draait het validatiescript opnieuw.

## Publicatiegate
Alleen objecten met `validation_status = approved` mogen door naar embeddings en retrieval.
