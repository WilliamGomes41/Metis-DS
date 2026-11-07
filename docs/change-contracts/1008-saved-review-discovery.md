# Opgeslagen kennisobject terugvinden

Change class: B
Rewrite risk: none
Promise: Een reviewer kan een opgeslagen kennisobject vanaf de bon en het documentoverzicht terugvinden en bekijken, ook zolang ander beoordelingswerk openstaat.
Proof: Werkelijke HTTP-opslag gevolgd door bon, terugkeer naar het werkoverzicht, volledige passage-inventaris en heropenen van het goedgekeurde object; de GET-route wijzigt geen fysieke object-/bindingsrijen of documenttoestand.
Touches lifecycle invariants: no

## Bestaande route en begrensde wijziging

`review_workboard_v1._workboard_card` toont de inventarislink uitsluitend wanneer geen persoonlijke vervolgactie bestaat. `ko_receipt_ui_v1.render_receipt_page` verwijst naar volgende passage en werkoverzicht. `_review_inventory` laat afgehandelde titels de bronpassage openen. Daardoor is een opgeslagen KO moeilijk opnieuw te vinden.

De wijziging houdt de bestaande inventaris altijd zichtbaar, voegt aan de bon een link naar de huidige KO-weergave toe en laat afgehandelde KO-titels diezelfde bestaande route openen. De inventaristaak rendert daar een leesweergave: huidige inhoud, versie, status, bronpositie en context, zonder nieuw beoordelingsformulier. Expliciete N/A wordt uitsluitend via de bestaande pure recorded_not_applicable-helper uit exacte geldige bindingen getoond. De afzonderlijke bronlink blijft bestaan. Structurele/bronrecords behouden hun bestaande bronroute.

Goedkeuring blijft de bestaande exacte binding en audit. De bon blijft de exacte opgeslagen handeling en versie; de nieuwe link opent de huidige objectversie, zonder die twee te verwarren. `/review` behoudt bestaande account-, rol-, document- en broncontroles. Er komt geen nieuwe status, opslag, query, transactie, autorisatieregel of publicatieactie bij. GET schrijft geen reviewbesluit. Gepubliceerde objecten en bestaande reviewervereisten veranderen niet.

## Acceptatie

- Na één akkoord blijft ander open werk bereikbaar én is de volledige inventaris zichtbaar.
- Het opgeslagen object staat in de inventaris en opent met inhoud, actuele toestand en documentcontext.
- De bon biedt een directe herkenbare link naar die huidige objectweergave.
- Bekijken wijzigt geen objecten, bindingen of documenttoestand; een voltooid akkoord wordt niet opnieuw aangeboden als gewone goedkeuring.
- De bestaande reviewer-/documentisolatie en exacte historische bon blijven behouden.
- Desktop en mobiel tonen de links leesbaar en met toetsenbordbediening.

Uitvoering: #1008. Onderdeel van #995/MET-56 en productacceptatie #990. Geen merge of deployment in deze opdracht.
