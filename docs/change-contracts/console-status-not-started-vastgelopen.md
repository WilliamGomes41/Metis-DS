# Console: "nog niet gestart" is not "vastgelopen", and Publiceren names a state once

Change class: B
Promise: Documenten MOET a received document whose processing was never started show as `nog niet gestart`, in the neutral tone, with a notice that links to Vorming to start it. A document that something prevents from being reviewed MOET read `vastgelopen` instead of `geblokkeerd`, in Documenten, in the shared document card and as the Vorming state after a blocked hand-over. Publiceren MOET name the unchecked state once, on the line that carries the action. The derived lifecycle status values, publication eligibility, readiness, review availability, routes and permissions MOGEN NIET change.
Proof: `tests/test_console_status_wording_v1.py`; the existing status tests with only the word updated (`tests/test_pre_review_failure_diagnostics_v1.py`, `tests/test_vsa_meaningful_document_status_v1.py`, `tests/test_worker_handover_v1.py`); a browser pass of Documenten, Vorming and Publiceren with a received, not-started document.
Touches lifecycle invariants: no
Rewrite risk: none

Decided by William (2026-11-10): "Geblokkeerd betekent dat er iets is waardoor je niet kan reviewen. Niet gestart is dat je zelf nog niet gestart bent"; the word `geblokkeerd` is replaced by `vastgelopen`; "Publiceren toont dezelfde status twee keer onder elkaar: dat hoort niet."

## Program-design check

- **Existing mechanism and authority:** receipt writes `publication_eligibility = blocked_pending_pre_review` together with `processing_blocker = source_selection_not_started`. `operations_console_v1` already names that reason a normal, non-blocking one (`NON_BLOCKING_PROCESSING_REASONS`, `stored_processing_blocked`). The list status reader maps every pre-review-blocked document to the derived status `blocked`, whose label was `geblokkeerd`.
- **Intended change:** presentation only. The Documenten row reads the stored `processing_blocker` and, for the not-started reason, shows the label Vorming already uses. The label of `blocked` and the Vorming state word change to `vastgelopen`.
- **Affected functions and call path:** `OperationsConsole.family_tree` (adds the stored `processing_blocker` to each child), `/tree` → `_document_row_summary`; `DOCUMENT_STATUS_LABELS`; `source_selection_v1.projection` and `summary_projection` (state word); `publish_readiness_ui_v1._card` → `_document_card_heading`.
- **State that may mutate:** none. No write, migration or new stored field.
- **Unchanged:** `derive_lifecycle_status`, `list_document_lifecycle_statuses` and `document_status` still return `blocked`; the review workboard's `publication_blocked` work state; the Publiceren state line and its "Volledigheid controleren" action; the tone and wording for a failed pre-review.
- **Smallest observable proof:** a received document shows `nog niet gestart` in Documenten while `console.document_status` is still `blocked`.

## Out of scope

- A document whose processing is running keeps the derived status `blocked` in Documenten, so it now reads `vastgelopen` there until it finishes. The row does not carry the attempt's expiry, so it cannot tell a running attempt from an expired one; correcting that belongs in the list status reader.
- Other uses of the word that name a different thing stay: a blocked candidate (`geblokkeerde kandidaten`), a refused action (`Publiceren is geblokkeerd`), and a blocked account (`Geblokkeerd in Metis`).
