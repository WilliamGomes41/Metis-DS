# Inleveren: readable upload form

Change class: C
Promise: The Inleveren form MOET read as one column of at most 60rem, with Bron, Document and Reviewers as real h2 section headings. "Wie beoordeelt dit document?" MOET show its four options as one row of large click targets, and "Is het vierogenprincipe verplicht?" its two options the same way, and the selected option MOET be visibly marked. "Alleen ik" MOET hide and disable the colleague list, so no colleagues are sent for a choice that needs none. The colleague list MOET explain how to pick a second colleague. The file button MOET follow the console button style. Field names, values, required attributes, the review choice semantics, `POST /ingest` and the kernel MOGEN NIET change.
Proof: `tests/test_console_ingest_readability_v1.py` and the existing upload tests (`tests/test_review_configuration_upload_v1.py`, `tests/test_console_ingest_names_review_labels.py`); screenshots at 1440 and 390px.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23), page-by-page readability series. Follows `console-header-readability.md` and `console-heading-contrast.md`.

The "Uitleg bij deze taak" link gets space below it on every page that has one, because it touched the first card. CSS is appended as overrides at the end of `console.css`.
