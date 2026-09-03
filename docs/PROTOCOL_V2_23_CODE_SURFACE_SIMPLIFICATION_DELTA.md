# V&VN Data Services Protocol v2.23 — Code-surface simplification

**Status:** Approved for project use  
**Protocol delta version:** 2.23.0  
**Approval date:** 2026-09-03  
**Approved by:** Project owner  
**Extends:** Protocol v2.22.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (Auditor REQUEST SIMPLIFICATION after A+C+D on main; first DELETE cut of unused src modules; ZIP of a566af56 remains before this wave)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.23 records the owner-asked Auditor code-surface review at `main` HEAD `a566af56c8c88e76cb4de7fa51642b408705da02` (William Gomes asked Auditor; Auditor handed the result to Metis as PROTOCOL/ROADMAP owner). Auditor verdict: **REQUEST SIMPLIFICATION**. This is not GD-03. This is not publication. G2 remains BLOCKED.

**Bounded supersession of any reading that (1) code-surface simplification is the next live step instead of William Cloud Shell ZIP of A+C+D SHA `a566af56`; (2) the first DELETE cut includes `semantic_transform_v2.py`, `prepublication_gate_v2.py`, `validation_workflow_v2.py`, `apply_second_review.py`, `canonical_store.py`, or `service_app.py`; (3) `service_app.py` MAY be deleted as a leftover; (4) PR #82 MAY be merged; or (5) this review is GD-03 or a publication decision.** Where this delta and those readings conflict, this delta governs.

Live baseline on `main` before this delta is Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Waves A, C and D are already in code on `main` `a566af56c8c88e76cb4de7fa51642b408705da02` (wave A PR #85; waves C and D PR #87). Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0 and this delta jointly form normative baseline v2.23.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects, Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules, Protocol v2.19 review duty / queue presentation, Protocol v2.20 every-guideline law / unpublished-snapshot delete, Protocol v2.21 wave A / wave B / wave C / wave D **definitions**, or Protocol v2.22 ZIP-then-B **live path**. It MAPS, and does NOT rewrite, existing law. Historical v2.21 wave definitions remain law. Protocol v2.22 live path remains law: William Cloud Shell ZIP of A+C+D SHA `a566af56`, then ingest a freeze, then wave B (G2 evidence). Simplification is AFTER that ZIP, not instead of it. Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`. Protocol v2.19 is duty-queue. Protocol v2.20 unpublished-delete remains on main, not a fifth wave. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, wave, splitter, reject, or leftover. This delta’s bar is the first DELETE cut after that ZIP, not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules, all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, and all Protocol v2.22 ZIP-then-B live-path rules remain in force, except the readings superseded in sections 3–9. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.22 files except index/conflict pointers. MUST NOT implement the deletion PR in this PR. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, or wave A/B/C/D definitions except as already required.

This delta also sets the next concrete implementation after the Cloud Shell ZIP. Protocol v2.22 §3 and §9 set the next implementation as wave C then wave D then ZIP then B. Waves C and D are already in code on `main` `a566af56c8c88e76cb4de7fa51642b408705da02`. The next **live** step remains William Cloud Shell ZIP of that SHA, then ingest a freeze, then wave B. Where this delta and Protocol v2.22 conflict on whether simplification MAY replace that ZIP, this delta governs: it MUST NOT. The next **code** implementation AFTER that ZIP (and only then) MUST be one deletion PR on the existing kernel/repo, existing pytest only, MUST NOT touch the splitter or console in that PR. G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication. Protocol v2.14 is still not written and is still not the next step. PR #82 stays closed/unmerged.

G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1` and a report-only preflight. G2 is still BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

## 2. Unchanged v2.6 through v2.22 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. `service_app.py` is not a protocol room. `service_app.py` AND `product_api_v1.py` are two products (inspection vs Product API), not leftovers. Wave A splitter + `reject_candidate` remain. The `operations_console_v1.py` versus `operations_console_app.py` split remains; no template engine. Live ingest uses `extract_pdf_v2`, `extract_html_v1`, `semantic_transform_generic_v1`, `prepublication_gate_v3`. Every rule in Protocol v2.6.0 through Protocol v2.22.0 remains mandatory as already written, except the readings superseded here.

Wave A, wave B, wave C and wave D definitions in Protocol v2.21 remain law. Protocol v2.22 live path (ZIP of the controlled A+C+D SHA, then ingest, then wave B) remains law. This delta does not rewrite those wave bodies and does not move wave B before the ZIP. It records the Auditor first DELETE cut that MAY run only after that ZIP, and the keep/do-not-delete list for that cut.

v2.20 unpublished-delete remains on main, not a fifth wave. `HANDOFF.md` MUST NOT be recreated.

## 3. Live path unchanged: ZIP of a566af56 then ingest then wave B

This delta MUST NOT change the live path.

Next live step remains:

1. William Cloud Shell ZIP of A+C+D SHA `a566af56c8c88e76cb4de7fa51642b408705da02`;
2. then ingest a freeze;
3. then wave B (G2 evidence).

Simplification is AFTER that ZIP, not instead of it. This protocol PR is not that ZIP. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR. PR #82 stays closed/unmerged. Waves C and D are already in code on that SHA. Live still runs pre-wave-A extract until that ZIP. Ingest of a new freeze MUST be after that ZIP, not before. Wave B (G2 evidence/smoke) AFTER that ZIP. G2 still BLOCKED. `publish()` still G2-BLOCKED. ZIP does not open publication.

MUST NOT G2 PASS. MUST NOT publish PASS. MUST NOT hide fragments. MUST NOT SSH wipe.

## 4. Auditor verdict REQUEST SIMPLIFICATION

Owner asked Auditor for a code-surface review at `main` HEAD `a566af56c8c88e76cb4de7fa51642b408705da02` and to hand the result to Metis (PROTOCOL/ROADMAP owner). Auditor verdict REQUEST SIMPLIFICATION. Not GD-03. Not publication. G2 remains BLOCKED.

Auditor found unused `src/` modules with no live product callers at that SHA. Live ingest uses `extract_pdf_v2`, `extract_html_v1`, `semantic_transform_generic_v1`, `prepublication_gate_v3`. Implementation MUST re-prove no live callers before each delete. If a named file still has a live caller, leave it and report; do not force-delete.

This protocol does not delete files. This protocol does not implement product code.

## 5. Keep (MUST NOT merge or delete in the simplification wave)

The simplification wave MUST NOT merge or delete:

- `operations_console_v1.py` versus `operations_console_app.py` split; no template engine;
- Wave A splitter + `reject_candidate`;
- `integrity_kernel`, `g2_source_store`, `object_taxonomy_v1`, `four_eyes_v1`, `serving_relations_v1`, `eligibility_policy`;
- Product API separate from the console;
- `test_protocol_v2_*` and `test_v2*` both kept;
- console kernel / HTML / ASGI stack;
- `service_app.py` AND `product_api_v1.py` (inspection vs Product API; two products, not leftovers);
- `src/canonical_store.py` (tested SQLite publication kernel, `test_storage_publication_v2.py`).

New eligibility rules go only in `eligibility_policy`. MUST NOT split high-CC fail-closed functions. MUST NOT touch the splitter or console in the first deletion PR.

## 6. First DELETE cut, zero-caller src/ modules only

First DELETE pass, zero-caller `src/` modules only:

- `extract_pdf.py`
- `semantic_transform.py`
- `validation_workflow.py`
- `build_second_review_queue.py`
- `pre_step5_gate.py`
- `import_expert_validation.py`
- `reconcile_legacy_review.py`
- `evaluate_safe_retrieval.py`
- `build_retrieval_document.py`

That is the first DELETE cut, zero-caller src/ modules only. A wider module list is not this cut.

Do NOT delete in the first pass (still subprocess-locked by `tests/test_protocol_v2.py` until that v2.0 lock is an explicit follow-up):

- `src/semantic_transform_v2.py`
- `src/prepublication_gate_v2.py`
- `src/validation_workflow_v2.py`
- `src/apply_second_review.py`

Do NOT delete `src/canonical_store.py`. Do NOT delete `service_app.py`. Do NOT delete `product_api_v1.py`.

The first deletion PR MUST use existing pytest only. MUST NOT touch the splitter or console in that PR. Implementation MUST re-prove no live callers before each delete. If a named file still has a live caller, leave it and report; do not force-delete.

Same or next change: point `scripts/run_integrity_sprint.sh` at committed fixtures instead of `python -m src.semantic_transform_v21`. Do not merge v2/v21/generic in that PR.

## 7. Dual live path: CLI review-queue versus console duty queue

Also blocking as dual live path (plan, do not silent-delete): CLI `review-queue` (`build_review_queue_v3`) versus console `review_stacks` / `slow_review_duty`. Console is the researcher duty queue.

MUST NOT silent-delete `review-queue` / `build_review_queue_v3` in the first deletion PR. A later plan MAY retire the CLI path; that is not this first DELETE cut.

## 8. Later, non-blocking (NOT in the first deletion PR)

NOT in that first deletion PR (later, non-blocking):

- flatten `review_object` restamp;
- split `review_get` into local functions in the same file (no Jinja);
- reuse `integrity_kernel` helpers then delete `canonical_store.py` wrapper;
- `retrieval_projection_v2` / `build_synthetic_fixture` only if unused;
- explicit follow-up of the `tests/test_protocol_v2.py` v2.0 lock before deleting `semantic_transform_v2.py`, `prepublication_gate_v2.py`, `validation_workflow_v2.py`, or `apply_second_review.py`.

## 9. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the deletion PR, the ZIP, G2 evidence, pipeline or backup.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol.

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.
- GD-03 remains ESTABLISHED as written. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.
- Holdout B MUST NOT be tuned from console analytics or any other operational metric.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

`.gitignore` already covers the source, secret, tenant, review and runtime classes and MUST be kept.

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–8.

## 10. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement the deletion PR in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.22 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the ZIP of `a566af56`.

Where this delta and Protocol v2.22 conflict on whether simplification MAY replace the ZIP of `a566af56`, this delta governs. Waves A, C and D are already in code on `main` `a566af56c8c88e76cb4de7fa51642b408705da02`. After this protocol merges:

1. Live path unchanged: William Cloud Shell ZIP of A+C+D SHA `a566af56`, then ingest a freeze, then wave B (G2 evidence). G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication.
2. AFTER that ZIP (and only then): one deletion PR, existing pytest only, first DELETE cut in section 6, MUST NOT touch the splitter or console in that PR. Implementation MUST re-prove no live callers before each delete.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete, v2.21 wave definitions and v2.22 ZIP-then-B live path remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. Wave A splitter/reject is already in code and MUST NOT be touched in the first deletion PR. Waves C and D are already in code and are not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing console/extract/Azure, implementing the deletion PR, merging product code, G2 PASS, Protocol v2.14, LLM, nurse UI, SSH wipe, hiding fragments without extract, treating Metis / Implementation engineer / Auditor as GD-03 reviewers, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–8, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except as already required, rewriting v2.16–v2.22 files except index/conflict pointers, creating or activating a test App Service, claiming G2 PASS, taking this protocol PR as the Cloud Shell ZIP, live-URL ingest, ingest of a new freeze before the ZIP of `a566af56`, merging PR #82, deleting `semantic_transform_v2.py` / `prepublication_gate_v2.py` / `validation_workflow_v2.py` / `apply_second_review.py` / `canonical_store.py` / `service_app.py` / `product_api_v1.py` in the first deletion PR, merging v2/v21/generic, silent-deleting CLI `review-queue`, splitting high-CC fail-closed functions, recreating `HANDOFF.md`.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (Auditor REQUEST SIMPLIFICATION after A+C+D on main; first DELETE cut of unused src modules; ZIP of a566af56 remains before this wave). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later implementation of the first deletion PR, the Cloud Shell ZIP, or wave B remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 12. Gates and approval effect

Approval of v2.23 establishes that the owner asked Auditor for a code-surface review at `main` HEAD `a566af56c8c88e76cb4de7fa51642b408705da02` and handed the result to Metis; that Auditor verdict is REQUEST SIMPLIFICATION; that this is not GD-03 and not publication; that G2 remains BLOCKED; that this delta MUST NOT change the live path; that the next live step remains William Cloud Shell ZIP of A+C+D SHA `a566af56`, then ingest a freeze, then wave B (G2 evidence); that simplification is AFTER that ZIP, not instead of it; that PR #82 stays closed/unmerged; that waves A, C and D are already in code on that SHA; that the first DELETE cut is zero-caller `src/` modules only (`extract_pdf.py`, `semantic_transform.py`, `validation_workflow.py`, `build_second_review_queue.py`, `pre_step5_gate.py`, `import_expert_validation.py`, `reconcile_legacy_review.py`, `evaluate_safe_retrieval.py`, `build_retrieval_document.py`); that the first pass MUST NOT delete `src/semantic_transform_v2.py`, `src/prepublication_gate_v2.py`, `src/validation_workflow_v2.py`, or `src/apply_second_review.py` (subprocess-locked by `tests/test_protocol_v2.py` until that v2.0 lock is an explicit follow-up); that MUST NOT delete `src/canonical_store.py`; that `service_app.py` AND `product_api_v1.py` remain (inspection vs Product API; two products, not leftovers); that live ingest uses `extract_pdf_v2`, `extract_html_v1`, `semantic_transform_generic_v1`, `prepublication_gate_v3`; that the keep list in section 5 MUST NOT be merged or deleted in the simplification wave; that `scripts/run_integrity_sprint.sh` MAY in the same or next change point at committed fixtures instead of `python -m src.semantic_transform_v21`; that MUST NOT merge v2/v21/generic in that PR; that CLI `review-queue` versus console `review_stacks` / `slow_review_duty` is a dual live path (plan, do not silent-delete); that console is the researcher duty queue; that the next code implementation AFTER that ZIP (and only then) MUST be one deletion PR, existing pytest only, MUST NOT touch the splitter or console in that PR; that Implementation MUST re-prove no live callers before each delete; that if a named file still has a live caller, leave it and report; that `HANDOFF.md` MUST NOT be recreated; that this protocol MUST NOT claim G2 PASS; that MUST NOT hide fragments; that MUST NOT SSH-wipe `/home/data`; that MUST NOT rewrite v2.16–v2.22 files except index/conflict pointers; that MUST NOT implement the deletion PR in this PR; that this delta MAPS, and does NOT rewrite, existing law; that Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`; that Protocol v2.19 is duty-queue; that `PROTOCOL.md` is every-guideline law, not Continentie-only (Protocol v2.20); that Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain; that G2-readiness (PR #69) already pinned `azure-identity` / `azure-storage-blob` and a report-only preflight; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement the deletion PR in this PR;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- take this protocol PR as the Cloud Shell ZIP of `a566af56`;
- replace the ZIP of `a566af56` with simplification;
- ingest a new freeze before that ZIP;
- treat the ZIP as opening publication or as wave B;
- merge PR #82;
- delete `semantic_transform_v2.py`, `prepublication_gate_v2.py`, `validation_workflow_v2.py`, `apply_second_review.py`, `canonical_store.py`, `service_app.py`, or `product_api_v1.py` in the first deletion PR;
- merge v2/v21/generic in the deletion PR;
- silent-delete CLI `review-queue`;
- split high-CC fail-closed functions;
- touch the splitter or console in the first deletion PR;
- recreate `HANDOFF.md`;
- skip durable immutable storage;
- staff named reviewers;
- treat Metis, the Implementation engineer or the Auditor as GD-03 reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- auto-confirm types;
- auto-promote ordinary text to `recommendation`;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, splitter, reject, or leftover as stored object types;
- lie in the UI by hiding stored fragments without a new extract;
- treat SSH or a wipe of `/home/data` as the product path;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- treat Protocol v2.20 unpublished-delete as a fifth wave;
- rewrite Protocol v2.16–v2.22 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- reopen Protocol v2.22 ZIP-then-B live path except as already required that simplification MUST NOT replace that ZIP;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor in this protocol PR;
- let G2 status depend on a stale static JSON field;
- open the publication gate because an app-setting is present;
- treat capture as publication;
- reopen or alter GD-03;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- add a care-app frontend, chatbot, EPD/ECD-UI or public website;
- put chat in the console;
- design the console for nurses;
- open the role set or allow operators to invent new role types, object types or relation types;
- allow open registration or shared login;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- silently add a new quality metric as a protocol gate;
- authorize a mockup, Azure ZIP as this PR, Cloud Shell of this protocol PR, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
