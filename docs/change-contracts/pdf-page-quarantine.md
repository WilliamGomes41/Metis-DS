# Niet-controleerbare PDF-pagina's apart zetten in plaats van het hele document te blokkeren

```text
Change class: B
Promise: bij een prozabron (geen beslisboom) zet de Docling-vertaling elke pagina met een paginagebonden bevinding in één keer apart, gebruikt geen enkel deel van die pagina's, legt paginanummers en redenen vast in het extractierecord en blokkeert publicatie zolang er een apart gezette pagina is; documentbrede bevindingen en de beslisboomroute blijven het hele document blokkeren.
Proof: tests/test_docling_contract_v1.py (alle bevindingen in één doorgang, geen gedeeltelijke pagina, item over een apart gezette pagina, documentbrede fouten blijven fataal, alles apart gezet is docling_no_source_text, verwerking slaagt zonder de pagina en publicatie blokkeert met source_pages_quarantined, zichtbaar in de documentdiagnose); tests/test_docling_real_pdf.py (echte gescande pagina, acceptatieomgeving); bestaande strikte tests ongewijzigd groen.
Touches lifecycle invariants: no
Rewrite risk: none
```

Besluit William 2026-10-22: "Per pagina afschermen". Aanleiding: de Conceptrichtlijn
Smetten (46 pagina's) kwam drie keer niet voorbij de extractie
(`docling_page_text_unverified`). Elke reparatie van één pagina legde de volgende
blokkade bloot, omdat `translate` bij de eerste bevinding stopte.

## Bestaand mechanisme

- Eigenaar: `src/docling_contract_v1.py::translate`, aangeroepen via
  `src/docling_pdf_v1.py::extract` door `OperationsConsole._extract` en
  `decision_graph_v1.pdf_fragments`.
- `translate` brak het hele document af op de eerste bevinding: een tabel over
  meerdere pagina's, een ongeldige charspan, onvolledige tekstdekking, een ongeldige
  kopniveau- of geometriewaarde, of een geselecteerde pagina zonder tekst.
- Het extractierecord wordt in dezelfde envelope-commit duurzaam
  (`quality_evidence_v1.record_processing`) en via `stored_fragments` teruggelezen.
- Publicatie loopt via `technical_publication_readiness` en
  `publication_readiness`.

## Gewijzigd gedrag

1. `translate(..., quarantine_pages=True)` loopt alle items door en vangt alleen
   bevindingen af die bij de pagina's van één item horen (`PAGE_SCOPED_CODES`).
   Die pagina's, en geselecteerde pagina's zonder tekst, komen in een verzameling
   apart gezette pagina's.
2. Een item dat ook maar één apart gezette pagina raakt, zet al zijn pagina's
   apart (`docling_item_spans_quarantined_page`). De vertaling loopt opnieuw
   totdat de verzameling niet meer groeit. Zo hangt geen fragment, kop of
   samengevoegde alinea af van een pagina die niet gebruikt wordt.
3. Het record krijgt `quarantined_pages: [{"page", "reasons"}]`: alleen
   paginanummers en codes, nooit brontekst.
4. Documentbrede bevindingen blijven fataal: resultaatidentiteit,
   paginaselectie, leesvolgorde, inventaris, onbekend paginanummer
   (`docling_page_invalid`), tekst zonder herkomst. Als alles apart gezet is, volgt
   `docling_no_source_text`.
5. Alleen prozaroutes zetten `quarantine_pages=True`: verwerking
   (`_fragments_and_spec`-checkpoint voor niet-beslisboom,
   `pre_review_semantic_v1`, de deterministische route) en de herextractie
   van `source_context_review_v1`, zodat die hetzelfde fragmentbeeld opnieuw
   opbouwt. `decision_graph_v1` en de routevergelijking blijven strikt.
6. `technical_publication_readiness` voegt `source_pages_quarantined` toe zolang
   het geaccepteerde extractierecord apart gezette pagina's heeft. Ongeldig
   opgeslagen bewijs geeft de bestaande DoclingError-code als blocker (fail-closed).
7. De documentdiagnose (`/inzicht/document`) noemt de pagina's en redenen. De
   publicatiekamer toont het blockerlabel.

## Ongewijzigd

- Standaard (`quarantine_pages=False`) is het gedrag identiek: dezelfde eerste
  fout, dezelfde volgorde (`docling_no_source_text` vóór
  `docling_page_text_unverified`) en dezelfde `pages` op de fout.
- Geen schema, migratie of backfill. Bestaande extractierecords hebben geen
  `quarantined_pages` en lezen als "niets apart gezet".
- `materialise_knowledge_candidates` blijft de enige kandidaatmaker. Apart
  gezette pagina's leveren geen fragmenten, dus geen kandidaten.
- Bronbytes, SHA-256, OCR uit, limieten, workerisolatie en de
  beslisboomroute.

## Muterende en onveranderlijke staat

Alleen het voorbereide extractierecord krijgt een veld. Dat veld valt binnen
de bestaande `record_hash` en `prepared_fragments_hash`. Er komt geen nieuwe
schrijver, autoriteit of toestand bij.

## Bekende beperkingen en vervolg

- Er is nog geen reviewhandeling om een apart gezette pagina te accepteren.
  Een document met zo'n pagina is reviewbaar maar niet publiceerbaar. Herstel
  gaat nu via een betere bron of een volgende wijziging die een expliciete
  menselijke afhandeling toevoegt (Class A-besluit, niet in deze wijziging).
- De Smetten-poging van 22-10 verliep na 30 minuten in `extraction_started`
  zonder `docling_timeout`. Dat is een aparte oorzaak (procesverlies of
  geheugen); deze wijziging lost dat niet op.
- De echte Docling-test draait alleen in de acceptatieomgeving
  (`METIS_DOCLING_REAL_ACCEPTANCE=1`).

## Adversariële controle

| Scenario | Uitkomst |
| --- | --- |
| Pagina zonder tekst naast goede pagina's | Pagina apart, rest verwerkt, publicatie geblokkeerd |
| Tabel over twee pagina's | Beide pagina's apart |
| Alinea over pagina 2 en 3, pagina 2 apart | Ook pagina 3 apart; geen halve alinea |
| Tekst zonder herkomst | Hele document geblokkeerd (niet toe te wijzen) |
| Alle pagina's apart | `docling_no_source_text` |
| Beslisboom-PDF met lege pagina | Ongewijzigd: `docling_page_text_unverified` |
| Bestaand record zonder veld | Geen blocker, geen herverwerking |
| Gemanipuleerd record | `docling_stored_evidence_invalid` als blocker |
