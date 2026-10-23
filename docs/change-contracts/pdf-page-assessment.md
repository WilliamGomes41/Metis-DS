# Verklaarbare PDF-extractie: pagina's beoordelen, en verantwoorden waar nodig

```text
Change class: B
Promise: bij een prozabron (geen beslisboom) noemt de Docling-extractie in één poging elke pagina met een paginagebonden bevinding, met probleem en herstelactie. Een pagina die de PDF zelf als leeg bewijst, wordt geaccepteerd en verantwoord vastgelegd. Een scan, een pagina met alleen kop- of voettekst of een andere onopgeloste pagina blokkeert de kennisvorming, totdat een onderzoeker of benoemde reviewer haar als pagina zonder kennisinhoud verantwoordt. Daarna laat de extractie precies die pagina in haar geheel weg. Onherstelbare technische fouten en de beslisboomroute blokkeren zoals voorheen.
Proof: tests/test_docling_contract_v1.py (alle bevindingen in één doorgang; alleen een door de PDF bewezen lege pagina zonder verantwoording; scan en kop-/voettekst niet als leeg; verantwoording alleen voor exacte pagina, bevindingen en bron; geen deel van een item over een onbruikbare pagina; onherstelbare fouten blijven fataal; volledige keten afwijzen → diagnose → weigeringen → verantwoorden via HTTP → opnieuw verwerken voorbij de extractie); tests/test_docling_real_pdf.py (echte gescande pagina, alleen in de acceptatieomgeving); bestaande strikte tests ongewijzigd groen.
Touches lifecycle invariants: no
Rewrite risk: none
```

Besluit William 2026-10-22: "Per pagina afschermen", bijgesteld naar zijn voorstel:
vertaling en beoordeling scheiden, onopgeloste inhoud blokkeert de kandidaatvorming
tot ze verantwoord is, en er komt een nieuwe contractversie voor de betekenis van
het extractierecord. Aanleiding: de Conceptrichtlijn Smetten (46 pagina's, op elke
pagina een tekstlaag) kwam drie keer niet voorbij `docling_page_text_unverified`.
Elke reparatie van één pagina legde de volgende blokkade bloot.

## Bestaand mechanisme

- Eigenaar: `src/docling_contract_v1.py::translate`, via
  `src/docling_pdf_v1.py::extract`, aangeroepen door `OperationsConsole._extract`
  en `decision_graph_v1.pdf_fragments`.
- `translate` brak af op de eerste bevinding. Een pagina zonder Docling-bodytekst
  gaf altijd hetzelfde algemene foutsignaal, of het nu een lege pagina, een scan of
  als voettekst geclassificeerde tekst was.

## Gewijzigd gedrag

1. **Vertalen, dan beoordelen.** `translate(..., assess_pages=True)` vangt alleen
   bevindingen af die bij de pagina's van één item horen (`PAGE_SCOPED_CODES`) en
   verzamelt ze per pagina. Een item dat een onbruikbare pagina raakt, maakt al
   zijn pagina's onbruikbaar (`docling_item_spans_set_aside_page`). De vertaling
   herhaalt zich tot die verzameling niet meer groeit, zodat geen fragment of kop
   leunt op een weggelaten pagina.
2. **Benoemde reden per pagina zonder tekst:** `docling_page_non_text_content`
   (afbeelding of scan), `docling_page_text_only_furniture` (alle tekst als kop of
   voet herkend) of `docling_page_text_unverified`.
3. **Drie uitkomsten:**
   - *Afwijzen met concrete fout*: resultaatidentiteit, paginaselectie,
     leesvolgorde, inventaris, onbekend paginanummer, tekst zonder herkomst,
     `docling_no_source_text`. Ongewijzigd.
   - *Accepteren met verantwoording*: navigatie (ongewijzigd), een pagina die de PDF
     zelf als leeg bewijst (0 teken tekstlaag, 0 afbeeldingen, 0 tekeningen, alleen
     bij reden `docling_page_text_unverified`), of een pagina met een vastgelegde
     verantwoording voor precies haar huidige bevindingen en bronhash. Het record
     krijgt `page_assessment: metis-docling-page-assessment-v1` en
     `set_aside_pages` met paginanummer, redenen en grondslag; nooit tekst of de
     vrije toelichting.
   - *Onopgelost*: de poging faalt met `docling_pages_unresolved`. De
     pogingsdiagnose krijgt `page_findings` (pagina en codes). Er worden geen
     kandidaten gevormd.
4. **Verantwoordingshandeling** `OperationsConsole.account_source_page` en
   `POST /inzicht/document/pagina-verantwoorden`.
5. **Documentdiagnose**: per pagina het probleem, de herstelactie en het
   verantwoordingsformulier; daarna welke pagina's buiten de bron zijn gelaten en op
   welke grond.
6. Alleen prozaroutes beoordelen pagina's. `decision_graph_v1` en de
   routevergelijking houden de strikte regel van de eerste bevinding.

## Domein-first (stateful Class B)

```text
Domain entity/aggregate: de bestaande workflow-envelope van één SourceSnapshot (vóór kennisvorming).
Invariant(s): een pagina wordt alleen weggelaten als de PDF haar leeg bewijst of als een verantwoording haar exacte huidige bevindingen en bronhash dekt; geen deel van een weggelaten pagina wordt gebruikt; een verantwoording kan alleen bestaan zolang er geen kennisobject is; het extractierecord bevat nooit brontekst of vrije toelichting.
Durable state before: laatste poging failed met docling_pages_unresolved en page_findings; geen objecten.
Durable state after: envelope.source_page_accountings krijgt één rij erbij (accounting_id, page, reasons, source_sha256, attempt_id, category, note, actor_id, recorded_at). Niets anders verandert.
Transaction boundary: één bestaande _reprocessing_transaction met _commit_prepared_store; controle en schrijven onder dezelfde rijvergrendeling.
Failure/recovery result: weigering laat de envelope ongewijzigd; een volgende verwerkingspoging leest de verantwoordingen via build_formation_context.
Duplicate execution / idempotency result: een tweede verantwoording voor dezelfde pagina, bevindingen en bron wordt geweigerd (source_page_accounting_already_recorded).
Concurrency result: de rijvergrendeling van _reprocessing_transaction serialiseert gelijktijdige verantwoordingen en pogingen.
Audit/evidence requirement: de rij zelf (wie, wanneer, categorie, toelichting, voor welke poging). Het extractierecord verwijst met accounting_id, categorie, actor en tijd en is geen tweede waarheid.
```

Bevoegdheid: dezelfde als verwerken (`source_selection_v1.authorize`: onderzoeker
of benoemde reviewer). Weigeringen: gepubliceerd, bestaande objecten, laatste poging
niet `docling_pages_unresolved`, pagina niet in de bevindingen, ongeldige categorie,
toelichting korter dan 10 of langer dan 500 tekens.

## Ongewijzigd

- Zonder `assess_pages` is het gedrag identiek: dezelfde eerste fout, dezelfde
  volgorde (`docling_no_source_text` vóór `docling_page_text_unverified`) en dezelfde
  `pages` op de fout.
- Geen schema of migratie; de nieuwe velden staan in de bestaande JSON-envelope.
  Bestaande extractierecords hebben geen `page_assessment` en worden niet anders
  gelezen of opnieuw verwerkt. `extractor_contract` blijft gelijk, zodat lopende
  hervattingen niet breken.
- `materialise_knowledge_candidates` blijft de enige kandidaatmaker. Publicatie,
  review en de beslisboomroute zijn ongewijzigd.

## Bewust niet in deze wijziging

- OCR, tabellen over meerdere pagina's en geheugenlimieten: aparte uitbreidingen.
- De mislukte extractie bewaart geen fragmenten om te inspecteren; de diagnose toont
  pagina, probleem en herstelactie.
- De Smetten-poging van 22-10 verliep na 30 minuten in `extraction_started` zonder
  `docling_timeout`. Dat is een aparte oorzaak (procesverlies of geheugen).
- Een verantwoording intrekken: een gewijzigde bevinding maakt de pagina vanzelf weer
  onopgelost; intrekken vóór vorming is nu niet nodig.

## Adversariële controle

| Scenario | Uitkomst |
| --- | --- |
| Lege pagina, PDF toont niets | Geaccepteerd, `pdf_page_without_content` |
| Pagina met tekstlaag die Docling mist | Onopgelost tot verantwoording |
| Scan of afbeelding | Onopgelost, ook als PDF-feiten leeg lijken |
| Alleen kop-/voettekst (Smetten-copyright) | Onopgelost, met eigen reden |
| Tabel over twee pagina's | Beide pagina's onopgelost |
| Alinea over een onbruikbare pagina | Ook de andere pagina onopgelost |
| Verantwoording voor andere bevindingen of bron | Telt niet |
| Verantwoording na vorming | Geweigerd |
| Niet-benoemde reviewer | Geweigerd |
| Alles verantwoord | `docling_no_source_text` |
| Beslisboom-PDF | Ongewijzigd strikt |
