# PG-sleutellijst zonder volledige receipts

Change class: B
Promise: de bestaande bronselectie-sleutellijst bouwt geen volledige documentreceipts; de gekozen documenten en toegangsregels blijven gelijk.
Proof: een PG-regressie weigert elke receiptconstructie binnen de leesscope; de bestaande HTML-golden- en verse-leesproeven blijven groen.
Touches lifecycle invariants: no
Rewrite risk: none

Het bestaande pad is `source_selection_ui_v1.document_keys` →
`_PostgresWorkflowDocumentsMixin.list_snapshot_ids`. Binnen een lege requestscope
riep dit `list_envelopes` aan: die leest dezelfde PG-store, maar bouwt bovendien
voor ieder document een volledige `_receipt`. De filevariant had die extra
kopie niet. De reeds bestaande bronselectie-kostproef legt dit bloot zodra zij
op de productieklasse draait.

`refresh_workflow_documents` is de bestaande authority-reader, met dezelfde
foutvertaling. De sleutellijst gebruikt die reader nu rechtstreeks en bewaart
de ruwe enveloppen in de bestaande requestscope. Alleen de leesprojectie
verandert: er vindt geen write, nieuwe cachegrens, autorisatiebeslissing,
reviewtransitie, releasewijziging of herstelwijziging plaats. De scope blijft
requestgebonden; volgende verzoeken lezen opnieuw PostgreSQL.
