# Werkelijke inhoudelijke acceptatie van #471

De technische ketentests gebruiken gecontroleerde providerfixtures. Ze bewijzen
bronbinding en lifecyclegedrag, geen betere selectiedekking. Een echte menselijke
referentie en een daadwerkelijke modelcall op de oorspronkelijke PDF blijven
voorwaarden voor het afronden en mergen van #471.

Het script `scripts/verify_eenzaamheid_semantic.py` schrijft alleen lokale
bewijsbestanden. Het verbindt niet met PostgreSQL, maakt geen Metis-accounts en
verandert geen productiegegevens of publicaties. Gebruik de PR-branch in een
aparte tijdelijke werkmap, niet als deployment over de actieve applicatie.

1. Gebruik de oorspronkelijke PDF met SHA-256
   `2185b6502a76b76e942db2352d746a5f1193645091844fd84241dfb94ac51064`.
2. Maak een referentiebestand:

   ```bash
   python scripts/verify_eenzaamheid_semantic.py draft \
     --pdf /pad/eenzaamheid-ouderen-v1.pdf \
     --reference /pad/eenzaamheid-reference.csv
   ```

   Het script verifieert ook exact de historische invoerhash: 202 kandidaatblokken
   en 283 bewijsblokken. Het CSV-bestand is uitdrukkelijk **UNREVIEWED**.
3. Een inhoudelijke reviewer beoordeelt iedere rij tegen de oorspronkelijke bron.
   Vul `expected_type`, `reviewed_by` en `reviewed_at` in. Toegestane waarden:
   recommendation, definition, explanation, condition, exception, context, label,
   non_knowledge. Splits rijen zo nodig met exacte start/end-offsets; bewaar de
   letterlijke tekst. Geen betekenisvolle brontekst mag uit de referentie verdwijnen.
4. Voer de echte modelproef uit waar `METIS_LLM_API_KEY` en `METIS_LLM_MODEL`
   al beschikbaar zijn. Deel de sleutel niet in chat of in een bestand.

   ```bash
   python scripts/verify_eenzaamheid_semantic.py run \
     --pdf /pad/eenzaamheid-ouderen-v1.pdf \
     --reference /pad/eenzaamheid-reference.csv \
     --output /pad/eenzaamheid-acceptance
   ```

Het resultaat bevat het aangeboden request, de zichtbare providerrespons, de
brongebonden spec en `acceptance-report.json`. Transportheaders en reasoning
worden niet opgeslagen. Ook de bestaande production-transform, admission gate
en passage-register worden zonder opslag aangeroepen; `review-objects.json`
bevat de gevormde reviewpassages. Een geselecteerd maar geblokkeerd voorstel
(bijvoorbeeld type_evidence_missing) telt niet als geslaagde herstelproef.
Een leeg/onvolledig referentiebestand wordt vóór een
betaalde modelcall geweigerd. Providerconfiguratie wordt uit bestaande
omgevingsvariabelen gelezen, niet uit opdrachtargumenten.

Een PASS vereist dat ieder menselijke kennisfragment letterlijk geselecteerd is
met het verwachte type en dat label/context/overige tekst geen zelfstandig
kennisvoorstel wordt. Bewaarde coverage_remainders tellen niet als correcte
modelselectie. Een niet-voltooid/ongeldig voorstel en afwijkende referentie geven
geen PASS. Publicatieacceptatie blijft afzonderlijk vermeld als NOT_TESTED: dit
script verleent geen review- of publicatiegoedkeuring.

Ontbrekend modelbewijs is geen onbekende API-fout: in de ontwikkelomgeving is geen
modelsleutel beschikbaar. De agent mag eigen beoordelingen of fixtures niet als
menselijke of werkelijke modelacceptatie aanmerken. Eerst deze proef beoordelen,
bevindingen herstellen en CI op het definitieve hoofd van #471 controleren; daarna
mergen en één deploymentpakket van die merge maken.
