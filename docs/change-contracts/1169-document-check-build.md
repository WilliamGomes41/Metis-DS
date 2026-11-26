# Vorming 3/4 · Bouwen via Documentcontrole voor annotator en reviewer

Change class: A. Rewrite risk: high. Part of MET-146. Refs #1166 and #1169.

Deze slice staat bovenop #1171 (Vorming 1/4) en #1172 (Vorming 2/4). Slice 4 is #1170. Het gedeelde lifecycle-, terugval- en herstelcontract staat in #1166.

## Gedrag

Op de annotatiewerkplek staat **Ik ben klaar met dit document** één keer onder Opgeslagen annotaties. Die actie opent Documentcontrole op dezelfde werkplek en zet de focus op de kop, ook op mobiel. De bron blijft bewerkbaar. **Afronden en bouwen** is de enige zichtbare bouwactie en opent het statusoverzicht van #1171.

Een benoemde reviewer opent via **Aanpassen in de kaart** de exacte annotatie. Na **Aanpassing opslaan** komt de reviewer op dezelfde Documentcontrole uit. Bij **Hele richtlijn** moeten alleen verouderde sectiebevestigingen opnieuw worden vastgelegd.

## Levenscyclus en gezag

| Aspect | Contract |
| --- | --- |
| Entiteit | De documentronde van een open werkrevisie, met annotaties, sectiebevestigingen, bouwverzegeling en bouwpoging. |
| Overgang | Annoteren → Documentcontrole (`checking`) → **Afronden en bouwen** reserveert één bouwpoging. Een reviewercorrectie brengt het document terug in dezelfde Documentcontrole. |
| Bevoegdheid | De annotator of een bevoegde benoemde reviewer, via de bestaande annotatie-API en het bestaande bouwcommando. |
| Validatie | Actuele generatie, volledige dekking bij **Hele richtlijn**, verouderde sectiebevestigingen opnieuw vastgelegd, opdracht-ID en locks tegen dubbel indienen. |
| Transactie | `/annotations/finalize` bewaart de actuele verzegeling en reserveert de poging binnen de bestaande transactie. De worker gebruikt de enige deterministische materialiser en de bestaande revisie-eigenaar. |
| Onveranderlijk | Bron, ongeraakte objecten (ID, versie en oordeel), auditspoor en eerdere releases. |
| Review | Het bestaande beoordelingspad trekt geraakte oordelen in. De gewijzigde versie blijft geblokkeerd voor goedkeuring tot een bouw van precies die generatie slaagt. |
| Fout en herstel | Een verouderde generatie, onvolledige dekking, onbevoegde gebruiker of mislukte bouw leidt nooit tot goedkeuring van de geraakte versie. Correctie en auditspoor blijven bewaard; herstel loopt via dezelfde Documentcontrole. Na herstart blijft de gereserveerde poging herkenbaar. |
| Release en serving | Ongewijzigd. Publicatie loopt via haar eigen bestaande voorwaarden. |

## Herschrijfrisico

De console- en opdrachtgrens voor afsluiten en reviewercorrecties verandert. Afrondknop, documentronde, correctieroute en bouwopdracht veranderen samen, zodat er geen tweede uitvoerbare bouwroute zichtbaar blijft. Er is geen schemawijziging. De oudere technische route blijft beschikbaar voor compatibiliteit en terugval tot #1170; terugval is een code-rollback naar een release die dezelfde records leest. Productie-uitrol en productieterugval vallen buiten deze proef.

## Bewijs

- `tests/test_rebuild_from_card_1064.py` doorloopt de reviewercorrectie via Documentcontrole: twee beoordeelde objecten bij volledige dekking, correctie van één object door een benoemde reviewer, sectieveroudering, blokkade tijdens en na een mislukte bouw, en na een geslaagde bouw exact hetzelfde ID, dezelfde versie en hetzelfde oordeel voor het ongeraakte object.
- `tests/test_annotation_document_check_postgres.py` bewaakt de documentronde in beide PostgreSQL-opslagvormen, met een verouderd formulier, een onbevoegde gebruiker, een herhaalde aanvraag en herstart na reservering.
- `tests/browser_annotation_document_check.cjs` en `tests/browser_human_review_check.cjs` volgen de bediening in Chromium op 390 en 1440 px.
