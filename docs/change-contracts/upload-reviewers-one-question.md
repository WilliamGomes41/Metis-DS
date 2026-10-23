# Upload form: one review question

Change class: B
Promise: The HTTP upload form MOET ask one review question ("Wie beoordeelt dit document?": Alleen ik / Eén collega / Twee collega's) with one list of colleagues. Four eyes and readers MOGEN only appear under a collapsed "Meer opties". The form MAG NIET show Reviewdeelname, Verantwoordelijke beoordelaar or a second reviewer list. "Vaststellingsstatus volgens de bron" moves to the document section. A choice with two required reviewers (Eén collega with four eyes, or Twee collega's) MOET store a matching review policy, so the uploader stays eligible under four eyes. A single-reviewer choice MAG NIET get a policy, because a one-reviewer policy overrides the content-driven four-eyes check (`requires_four_eyes`). The kernel ingest and the persisted shape MOGEN NIET change.
Proof: tests/test_review_configuration_upload_v1.py — `test_upload_form_names_reviewers_once`, `test_http_form_requires_choice`, `test_http_choice_reviewers_alone_assign_the_document[legacy]`, `test_http_form_choice_sets_matching_policy[*]`, `test_http_form_choice_with_wrong_count_is_refused`; tests/browser_source_selection_check.cjs uploads through the form with only the choice.
Touches lifecycle invariants: no
Rewrite risk: none

Requested by William (2026-10-23 11:51): "best part is no part, dit onderdeel 'Ingest' heeft teveel parts" and "Het is echt dubbel". Follows `820-upload-reviewers-once.md`.

## Program design (Class B gate)

- **Existing mechanism and authority:** `POST /ingest` turns form fields into `review_choice` and, for `review_mode` other than `legacy`, a `review_policy`. Without a policy, `receive_source` fills `named_reviewers` from the choice and checks it (`review_configuration_policy_conflict`). The uploader is the primary reviewer by default.
- **Intended change:** the form sends `review_mode=choice` and no `primary_reviewer` or `named_reviewers`. The handler derives a policy only for two required reviewers, mirroring `from_review_policy`: Eén collega with four eyes → uploader primary, colleague required; Twee collega's → first colleague primary, second required (four eyes is implied, so the flag is stored as false). Alleen ik and Eén collega without four eyes take the chosen path without a policy, so high-risk and exception objects still demand a second review. A choice with the wrong count gets no policy and the kernel refuses it.
- **Affected call path:** `ingest_form` HTML and `POST /ingest` (`_policy_from_choice`). Other `review_mode` values, direct POSTs and fixtures work unchanged.
- **State that may mutate:** the same envelope fields on a new upload. Two-reviewer choices carry an explicit policy and stay manageable in `/review/participants`. Single-reviewer choices keep today's chosen path, where `review_participation_v1` refuses activation with `review_configuration_chosen_wins`; that limit predates this change and is not widened here.
- **Known limit, out of scope:** on the chosen path without a policy (Alleen ik, Eén collega without four eyes), content that later demands four eyes needs a second named reviewer, and participant activation refuses chosen configurations. This existed before #820 on the legacy form path and is not changed here.
- **Unchanged behavior:** handler, kernel, conflict checks, four-eyes and reader validation, existing documents.
- **Smallest proof:** the tests above.

## Stateful overlay

- Domain entity: source envelope at upload (review membership and configuration).
- Invariant(s): unchanged and kernel-enforced (choice reviewers equal named reviewers; readers never reviewers; uploader_sole without four eyes).
- Durable state before / after: same shape. Two-reviewer form uploads write an `explicit-review-v1` policy that `from_review_policy` maps back to the stored choice; single-reviewer uploads write `review_policy: null`.
- Transaction boundary, failure/recovery, idempotency: unchanged (`receive_source`).
- Concurrency: N/A, no new write path.
- Audit/evidence: unchanged.
