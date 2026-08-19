# V&VN Data Service - Validatieprotocol v0.1

## Doel
Zorgen dat geen klinisch kennisobject als `approved` wordt gepubliceerd zonder expliciete menselijke beoordeling.

## Reviewbeslissingen
- `approve`: inhoud, context, logica, bronverwijzing en formulering kloppen met de bron.
- `revise`: object moet inhoudelijk of technisch worden aangepast; gebruik `review_comment` om exact te beschrijven wat moet wijzigen.
- `reject`: object hoort niet in de kennisset of is niet betrouwbaar te reconstrueren; commentaar is verplicht.
- leeg: nog niet beoordeeld.

## Minimale controle per object
1. Vergelijk `content` met de genoemde bronpagina.
2. Controleer dat geen klinische betekenis is toegevoegd, weggelaten of veranderd.
3. Controleer bij voorwaarden en scoreregels operator, drempel, eenheid en scorepunten.
4. Controleer de relatie met het parent-object.
5. Controleer doelgroep, setting en onderwerp alleen voor zover de bron die ondersteunt.
6. Kies daarna `approve`, `revise` of `reject`.

## Beslisregels
IF `review_decision = approve`, THEN het script zet `validation_status = approved`, vult validator en datum in en valideert opnieuw tegen het JSON-schema.

IF `review_decision = reject`, THEN is een reviewcomment verplicht.

IF `review_decision = revise` of leeg, THEN blijft het object buiten de approved dataset.

IF een object na goedkeuring niet tegen het schema valideert, THEN wordt het niet gepubliceerd.

## Kritieke pilotvragen
Voor pagina 15 moet de expert expliciet controleren:
- of leeftijdsgrenzen en fractuurtermijnen exact zijn;
- of glucocorticoidenvoorwaarden exact zijn;
- of de verwijzingsdrempel `>= 4 punten` correct is;
- hoe overlappende leeftijdsscores moeten worden geinterpreteerd (bijv. >=60 en >=70 jaar);
- of alle 8 scoreregels afzonderlijk juist zijn overgenomen.

## Publicatiegate
Een object mag pas naar embeddings/retrieval wanneer `governance.validation_status = approved`.
