# Documenten: compact rows and aligned actions

Change class: C
Promise: Each document on Documenten (`/tree`) MOET show as one compact row: title, then version and class, with the status as a label on the right; a blocked document's label MOET stand out as a warning. An opened document MOET show its actions in one column of labelled rows (Onderwerp, Klasse, Diagnose, or Wijzigen for a published version), each showing the current value. Deleting an unpublished document MOET sit behind its own closed "Document verwijderen" disclosure. Checkboxes MOETEN sit directly beside their text with a 44px row. The delete control and field placeholders MOETEN reach 4.5:1 contrast in light and dark. The class explanation MOET be at most 65ch. A blocked document's notice MOET link researchers to Bronselectie for that document. An empty search MOET name the query and offer "Wis zoekopdracht". "pagina 1 van 1" MOET NIET show on Documenten. Field names, routes (`/tree/move`, `/tree/promote`, `/documents/delete`), who sees which action, the protocol-fixed delete label and confirmation copy, and the kernel MOGEN NIET change.
Proof: `tests/test_console_documents_readability_v1.py`; existing Documenten tests (`tests/test_console_cleanup_v1.py`, `tests/test_tree_mutability_v1.py`, `tests/test_v220_unpublished_document_delete.py`, `tests/test_v227_unpublished_delete_documentenhierarchie_type_confirm.py`, `tests/test_v226_klasse_wijzigen.py`, `tests/test_v232_console_documenten_landing_b.py`); screenshots at 1440 and 390px, light and dark, approved by William before the PR; impeccable critique before (20/40) and after.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-24), page-by-page readability series; impeccable critique and definition of done agreed in the project thread before implementation.

The delete button keeps "Verwijder unpublished document" and its confirmation sentence: Protocol v2.20 fixes that label and the tests pin it. Renaming it needs a protocol change.

CSS is appended as overrides at the end of `console.css`, scoped to `#documents`.
