# #820: upload form names reviewers once

Change class: B
Promise: In the HTTP upload form the uploader MOET name required reviewers only once, in the B10 review choice (`review_reviewers`). For participation mode `required` an empty `named_reviewers` MOET be filled from that choice. Optional participants (`optional` mode) MOETEN keep their own list, shown only for that mode. The kernel ingest, its conflict checks and the persisted shape MOGEN NIET change.
Proof: tests/test_review_configuration_upload_v1.py — `test_upload_form_names_reviewers_once`, `test_http_choice_reviewers_alone_assign_the_document[legacy|required]`, `test_http_optional_participants_stay_separate_from_choice_reviewers`, and the unchanged `test_http_non_legacy_mode_disagreeing_with_choice_is_refused`.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23): "1 x de reviewers selecteren is voldoende".

## Program design (Class B gate)

- **Existing mechanism and authority:** `POST /ingest` (`src/operations_console_app.py`) turns form fields into `named_reviewers`, an optional `review_policy` (from `review_mode`, `primary_reviewer` and `named_reviewers`) and a `review_choice`. `OperationsConsole.ingest` → `receive_source` (`src/operations_console_v1.py`) is the only writer; it already fills `named_reviewers` from the choice when no policy is given (legacy) and refuses a policy whose required reviewers or four-eyes differ from the choice (`review_configuration_policy_conflict`). Readers MOGEN NOOIT be reviewers (`review_configuration_reader_is_reviewer`).
- **Intended change:** the form drops the general "Aanvullende beoordelaars" list. For `required`, the handler fills `named_reviewers` from `review_reviewers` before building the policy. For `optional`, a separate list stays, because an optional participant is neither a reviewer nor a reader in the choice.
- **Affected call path:** `ingest_form` HTML and the `POST /ingest` handler only. `receive_source`, `from_review_policy`, `validate_configuration` and the stores are unchanged.
- **State that may mutate:** the same envelope fields as before (`named_reviewers`, `review_policy`, `review_configuration`) on a new upload, now derived from one input.
- **Unchanged behavior:** legacy and `single` mapping; direct POSTs and kernel calls that pass `named_reviewers`; every conflict refusal; existing documents.
- **Smallest proof:** the tests above.

## Stateful overlay

- Domain entity: source envelope at upload (review membership and configuration).
- Invariant(s): policy required reviewers equal choice reviewers; readers are never reviewers; four-eyes agrees between policy and choice. Enforced by the kernel, untouched.
- Durable state before / after: same shape; only the HTTP input that feeds `named_reviewers` for `required` changes.
- Transaction boundary: unchanged (`receive_source`).
- Failure/recovery: a disagreeing choice is still refused before anything is written.
- Duplicate execution / idempotency: unchanged.
- Concurrency: N/A, no new write path.
- Audit/evidence: unchanged.
