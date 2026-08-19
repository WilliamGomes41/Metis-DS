# V&VN extraction rules v0.1 — Osteoporose en fractuurpreventie

## Doel
Zet de bron om naar herleidbare kennisobjecten zonder klinische betekenis, voorwaarden, scorelogica of bronstructuur te verliezen.

## Bronnen voor pilot
1. V&VN Kennisplatform-pagina: Osteoporose en fractuurpreventie.
2. Onderliggende richtlijnpagina's.
3. Interactieve beslisboom zodra technisch uitleesbaar.
4. PDF/Word-brondocument zodra beschikbaar.

## Basisregels
1. Bewaar altijd `raw_text` naast `clean_text`.
2. Maak een nieuw knowledge object bij een inhoudelijk zelfstandige aanbeveling, beslissing, actie, definitie, score-regel of tabel.
3. Gebruik kopstructuur als `section_path`; verzin geen ontbrekende koppen.
4. Verwijder alleen presentatie-ruis. Verander geen klinische formuleringen tijdens cleaning.
5. Bewaar voorwaarden samen met de aanbeveling waarop ze van toepassing zijn.
6. Splits een scorelijst niet in willekeurige tokenchunks. Modelleer ieder criterium als `score_rule` en de beslisdrempel als afzonderlijke logica.
7. Modelleer expliciete drempels (`>=`, `<=`, leeftijd, score, periode) als machine-leesbare `logic` naast de oorspronkelijke tekst.
8. Bewaar een aanbeveling met direct noodzakelijke toelichting in hetzelfde object wanneer loskoppeling betekenisverlies veroorzaakt.
9. Een tabel krijgt een zelfstandig object als rijen/kolommen inhoudelijke betekenis dragen.
10. Beslisboomrelaties worden als branches/edges opgeslagen; nooit alleen als platte tekst.
11. Alleen broninhoud mag in `raw_text`/`clean_text`. Afgeleide labels komen in metadata.
12. AI-afgeleide classificaties starten als `needs_review`; zij zijn niet automatisch klinisch gevalideerd.

## Objecttyperegels
- `recommendation`: expliciet advies of handelingsaanwijzing.
- `decision`: vraag/keuzepunt met twee of meer vervolgroutes.
- `action`: concrete vervolghandeling na conditie/beslissing.
- `condition`: toepassingsvoorwaarde zonder zelfstandige actie.
- `score_rule`: criterium dat punten/score toevoegt of een score interpreteert.
- `definition`: begripsdefinitie.
- `table`: tabel waarvan structuur behouden moet blijven.
- `background`: toelichting/onderbouwing die geen directe handelingsaanwijzing is.
- `patient_information`: tekst expliciet gericht op patient/client.

## Chunkingregels v0.1
- Structure-first, niet token-first.
- Richtwaarde retrievalchunk: 300–700 tokens.
- Hard maximum voor pilot: 1.000 tokens, tenzij splitsing klinische samenhang verbreekt.
- Kleine logisch verbonden objecten mogen voor retrieval worden samengevoegd; de bronobjecten blijven afzonderlijk bestaan.
- Overlap alleen wanneer verwijzing/context anders verloren gaat.
- Een aanbeveling en haar toepassingsvoorwaarde worden nooit van elkaar gescheiden in retrievalcontext.

## Quality gates
Een object mag pas naar `approved` wanneer:
1. bron-URL/titel aanwezig zijn;
2. section_path aanwezig is;
3. raw_text en clean_text inhoudelijk overeenkomen;
4. numerieke drempels en scores exact zijn overgenomen;
5. relaties naar parent/target objects bestaan indien van toepassing;
6. menselijke inhoudelijke validatie is geregistreerd.

## Pilot acceptance criteria
- 100% van expliciete aanbevelingen uit de geselecteerde pilotsecties geïdentificeerd.
- 100% van expliciete scorecriteria en beslisdrempels behouden.
- 100% van gemodelleerde objecten herleidbaar naar bron en sectie.
- 0 klinische drempels of condities gewijzigd door cleaning/chunking.
- Geen object wordt `approved` zonder menselijke validatie.
