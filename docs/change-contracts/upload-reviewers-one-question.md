# Upload form: one review question

Change class: B
Promise: The HTTP upload form MOET ask one review question ("Wie beoordeelt dit document?": Alleen ik / Eén collega / Twee collega's) with one list of colleagues. Four eyes and readers MOGEN only appear under a collapsed "Meer opties". The form MAG NIET show Reviewdeelname, Verantwoordelijke beoordelaar or a second reviewer list. "Vaststellingsstatus volgens de bron" moves to the document section. The POST handler, the kernel ingest and the persisted shape MOGEN NIET change.
Proof: tests/test_review_configuration_upload_v1.py — `test_upload_form_names_reviewers_once`, `test_http_form_requires_choice`, `test_http_choice_reviewers_alone_assign_the_document[legacy]`; tests/browser_source_selection_check.cjs uploads through the form with only the choice.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23 11:51): "best part is no part, dit onderdeel 'Ingest' heeft teveel parts" and "Het is echt dubbel". Follows `820-upload-reviewers-once.md`.

## Program design (Class B gate)

- **Existing mechanism and authority:** `POST /ingest` turns form fields into `review_choice` and, for `review_mode` other than `legacy`, a `review_policy`. Without a policy, `receive_source` fills `named_reviewers` from the choice and checks it (`review_configuration_policy_conflict`). The uploader is the primary reviewer by default.
- **Intended change:** the form no longer sends `review_mode`, `primary_reviewer` or `named_reviewers`, so every form upload takes the legacy path with the choice as the single source of reviewers.
- **Affected call path:** `ingest_form` HTML and its inline script only. The handler still accepts all fields, so direct POSTs and fixtures that send a policy work unchanged.
- **State that may mutate:** the same envelope fields on a new upload. Form uploads no longer create `review_policy` assignments; participants can still be added or replaced after upload via `/review/participants`.
- **Unchanged behavior:** handler, kernel, conflict checks, four-eyes and reader validation, existing documents.
- **Smallest proof:** the tests above.

## Stateful overlay

- Domain entity: source envelope at upload (review membership and configuration).
- Invariant(s): unchanged and kernel-enforced (choice reviewers equal named reviewers; readers never reviewers; uploader_sole without four eyes).
- Durable state before / after: same shape. Form uploads write `review_policy: null`.
- Transaction boundary, failure/recovery, idempotency: unchanged (`receive_source`).
- Concurrency: N/A, no new write path.
- Audit/evidence: unchanged.
