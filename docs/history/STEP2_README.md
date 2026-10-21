# Stap 2 - bronextractie MVP v0.1

## Doel
Een V&VN-bron reproduceerbaar omzetten naar ruwe knowledge objects die voldoen aan `knowledge_object.schema.json`.

## Pilotbron
`V&VN Richtlijn Osteoporose en fractuurpreventie`, versie augustus 2024.

## Implementatie
`src/extract_pdf.py` gebruikt PyMuPDF voor layout-aware block extraction, voert conservatieve cleaning uit, classificeert blokken en schrijft JSONL.

## Uitvoeren
```bash
python src/extract_pdf.py data/raw/VVN-RL-Osteoporose-1.3.pdf \
  --schema schemas/knowledge_object.schema.json \
  --out output/fractuurpreventie_page15_raw.jsonl \
  --report output/fractuurpreventie_page15_report.json \
  --source-url 'https://kennisplatform.venvn.nl/wp-content/uploads/richtlijnen/VVN-RL-Osteoporose-1.3.pdf' \
  --title 'V&VN Richtlijn Osteoporose en fractuurpreventie' \
  --document-id 'vvn-osteoporose-fractuurpreventie-2024' \
  --version 'augustus-2024' \
  --pages 15
```

## Kwaliteitsregels
- Raw text blijft bewaard.
- Afbreekstreepjes door regeleinden worden gerepareerd.
- Klinisch relevante objecten krijgen standaard `needs_review`.
- De extractor vult ontbrekende klinische voorwaarden niet zelf aan.
- Elk object wordt tegen JSON Schema v0.1 gevalideerd.

## Bekende beperking uit de pilot
De tekstlaag van de PDF bevat enkele slecht extraheerbare vergelijkingstekens/tekstdelen. De gerenderde pagina is visueel correct, maar de machinale tekstlaag is op enkele plaatsen incompleet. Daarom mag de huidige output nog niet als klinisch gevalideerde dataset worden gepubliceerd.

## Volgende technische verbetering
De blokken moeten in stap 3 semantisch worden samengevoegd tot complete aanbevelingen en score-regels. Voor tabellen/scorelijsten is row-level parsing nodig.
