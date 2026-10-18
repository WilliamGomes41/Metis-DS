# V&VN Data Services Protocol v2.24 — Console / retrieval deploy-package split

**Status:** Approved for project use  
**Protocol delta version:** 2.24.0  
**Approval date:** 2026-09-03  
**Approved by:** Project owner  
**Extends:** Protocol v2.23.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (split the deploy package, not the product idea; thin console ZIP; MUST NOT vendor numpy/sklearn/scipy into vvn-metis-console; one shared kernel; Product API later, not this wave; split does not open publish/G2)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.24 records the owner lock of 2026-09-03 (William Gomes): **split the deploy package, not the product idea.** Two doors already exist (operations console vs Product API). Tonight B1 died because one `requirements.txt` vendored numpy/sklearn/scipy into `vvn-metis-console`. Owner addendum 2026-09-03 (same lock): the temporary deploy split MUST NOT become two systems.

**Runtime-scheiding mag veranderen; protocol- en publicatiegrenzen niet.**

**Bounded supersession of any reading that (1) the Azure operations-console ZIP MAY include numpy, sklearn, scipy, or scikit-learn; (2) `console_asgi` MAY import `embedding_provider` / vector retrieval / hybrid retrieval at process start; (3) Product API MUST be deployed in the same App Service worker as the Review console; (4) this split opens `publish()` or G2; (5) console accounts are API tenants; (6) unpublished review snapshots are shared with the Product API; (7) the temporary deploy split MAY become two systems or a second law in the API; (8) shared kernel modules MAY import numpy/sklearn/scipy; (9) “we don’t do that” is enough to keep unpublished review store or researcher console accounts off Product API credentials; or (10) the thin B1 console MAY accrete subscriber/retrieval features as one more small thing.** Where this delta and those readings conflict, this delta governs. Owner lock 2026-09-03: split the deploy package, not the product idea. First DELETE cut remains done/law on `main` `50ec689` (PR #89). Two Cloud Shell ZIPs of different SHAs still refused. A later thin ZIP of the v2.24 implementation SHA is the one live ZIP.

Live baseline on `main` before this delta is Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. First DELETE cut is already in code on `main` `50ec689` (PR #89; nine zero-caller src modules + integrity-sprint fixture retarget). Waves A, C and D remain in code. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0 and this delta jointly form normative baseline v2.24.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects, Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules, Protocol v2.19 review duty / queue presentation, Protocol v2.20 every-guideline law / unpublished-snapshot delete, Protocol v2.21 wave A / wave B / wave C / wave D **definitions**, Protocol v2.22 one-ZIP-then-B **except** as already superseded by Protocol v2.23, or Protocol v2.23 first DELETE cut / keep list / two products / CLI review-queue plan / PR #82 closed / `HANDOFF.md` MUST NOT be recreated. It MAPS, and does NOT rewrite, existing law. It SUPERSEDES the v2.23 reading that the next Cloud Shell ZIP MAY be of the post-DELETE SHA while that package still vendors numpy/sklearn/scipy into `vvn-metis-console`, and the reading that next code is only the already-landed deletion PR then ZIP that SHA. Historical v2.21 wave definitions remain law. Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`. Protocol v2.19 is duty-queue. Protocol v2.20 unpublished-delete remains on main, not a fifth wave. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, wave, splitter, reject, leftover, door, or deploy-package. This delta’s bar is the thin console ZIP and one shared kernel, not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules, all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), and all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules remain in force, except the readings superseded in sections 3–9. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.23 files except index/conflict pointers. MUST NOT implement the requirements split in this PR. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete, wave A/B/C/D definitions, or the first DELETE cut except as already required.

This delta also sets the next concrete **code** implementation after this protocol. Protocol v2.23 §3 and §10 set the next code as one deletion PR then one ZIP of that SHA. That deletion PR is already on `main` `50ec689`. Where this delta and Protocol v2.23 conflict on whether a Cloud Shell ZIP of that post-DELETE SHA MAY happen while the console package still vendors numpy/sklearn/scipy, this delta governs: it MUST NOT. The next **code** implementation MUST be: split console vs retrieval requirements, prove `console_asgi` import graph has no sklearn/numpy, one thin console ZIP. Cloud Shell of that ZIP is a later live step, not tonight. MUST NOT implement the requirements split in this PR. Wave B still after a healthy console ZIP + ingest. G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication. This split does not open `publish()` or G2. Protocol v2.14 is still not written and is still not the next step. PR #82 stays closed/unmerged.

G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1` and a report-only preflight. G2 is still BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

Index/conflict pointer: Protocol v2.25.0 SUPERSEDES any reading that kennisplatform `story.html` boom players MUST stay entirely out of the MVP / first console as a knowledge class, any reading that the only MVP document classes are guideline HTML/PDF without a boom path, and any reading that Inleveren needs a separate path control distinct from Klasse. Where this file and Protocol v2.25 conflict on those readings, or on which implementation is next, Protocol v2.25 governs: beslisboom class is in MVP for researcher ingest+review; the Storyline player package is not the Product API surface and MUST NOT be the nurse console; closed Klasse set MUST include `beslisboom`; Klasse choice selects review path; next code is Forge on the existing kernel/console for exactly the beslisboom path wave (Klasse includes beslisboom; Klasse choice selects review path). Thin console ZIP, one shared kernel, Product API later, split does not open publish/G2, and HANDOFF.md MUST NOT be recreated remain.

## 2. Unchanged v2.6 through v2.23 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. `service_app.py` is not a protocol room. `service_app.py` AND `product_api_v1.py` are two products (inspection vs Product API), not leftovers. Wave A splitter + `reject_candidate` remain. The `operations_console_v1.py` versus `operations_console_app.py` split remains; no template engine. Live ingest uses `extract_pdf_v2`, `extract_html_v1`, `semantic_transform_generic_v1`, `prepublication_gate_v3`. Every rule in Protocol v2.6.0 through Protocol v2.23.0 remains mandatory as already written, except the readings superseded here.

Wave A, wave B, wave C and wave D definitions in Protocol v2.21 remain law. Protocol v2.23 first DELETE cut / keep list remain law. This delta does not rewrite those wave bodies, does not undo the first DELETE cut, and does not move wave B before a healthy thin console ZIP + ingest.

v2.20 unpublished-delete remains on main, not a fifth wave. `HANDOFF.md` MUST NOT be recreated.

## 3. Live path: thin console ZIP, then ingest, then wave B

Owner lock 2026-09-03 SUPERSEDES any reading that a fat vendor ZIP (numpy/sklearn/scipy) MAY go to `vvn-metis-console`, and any reading that Cloud Shell ZIP of the current post-DELETE SHA happens tonight while that package still vendors those libraries.

Next live path:

1. This protocol PR (no product code, no Cloud Shell, no Azure ZIP);
2. Next CODE (not this PR): split console vs retrieval requirements; prove `console_asgi` import graph has no sklearn/numpy; one thin console ZIP;
3. Later live step (not tonight): Cloud Shell of that thin ZIP of the v2.24 implementation SHA;
4. then ingest a freeze;
5. then wave B (G2 evidence).

MUST NOT Cloud Shell tonight. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR. Two Cloud Shell ZIPs of different SHAs still refused. A later thin ZIP of the v2.24 implementation SHA is the one live ZIP. PR #82 stays closed/unmerged. Wave B still after a healthy console ZIP + ingest. G2 still BLOCKED. `publish()` still G2-BLOCKED. This split does not open publication. This split does not open `publish()` or G2.

MUST NOT G2 PASS. MUST NOT publish PASS. MUST NOT hide fragments. MUST NOT SSH wipe.

## 4. Console deploy package MUST stay thin

The live Review console (`vvn-metis-console`, `console_asgi` / `operations_console_*`) Azure deploy package MUST NOT vendor numpy, sklearn, scipy, or scikit-learn.

Console ZIP MAY include FastAPI, gunicorn, uvicorn, python-multipart, PyMuPDF, jsonschema, azure-identity, azure-storage-blob (G2 client remains fail-closed).

Oryx `output.tar.zst` of a fat vendor tree on B1 is refused; console deploy MUST stay small enough that B1 starts without a 136MB tar extract.

`console_asgi` MUST NOT import `embedding_provider` / vector retrieval / hybrid retrieval at process start.

## 5. Two doors, one shared kernel, later Product API runtime

Product API / TF-IDF / `LocalCharTfidfEmbeddingProvider` stays in the repo with its own requirements/runtime later. MUST NOT go live in this wave. No new App Service in this PR. Product API MUST NOT be deployed in the same App Service worker as the Review console.

Keep `service_app.py` AND `product_api_v1.py` (two products).

The temporary deploy split MUST NOT become two systems. PROTOCOL, object formats, freeze rules, and publish logic are one shared kernel. Console MUST NOT interpret review/object/freeze/publish rules differently from Product API. No second law in the API.

Shared across doors: PROTOCOL, freeze bytes (SHA-256), and later G2 published objects. MUST NOT share unpublished review store or console login accounts as API entitlement.

Console classification remains closed taxonomy + context-aware splitter (rules), not sklearn.

## 6. Dependency drift and package-boundary law

Console light requirements vs Product API heavier set. Shared kernel modules MUST NOT import numpy, sklearn, scipy, or scikit-learn. A console import of shared code MUST NOT pull those in. Package boundaries are law.

Tests in this protocol PR MUST fail if `console_asgi` / `operations_console_*` import graph includes numpy, sklearn, scipy, or scikit-learn. Implementation later proves the requirements split; this PR writes the MUST and the test hooks. MUST NOT implement the requirements split in this PR.

## 7. Data boundary MUST be technically enforceable

When Product API goes live, the data boundary MUST be technically enforceable: separate access, credentials, and storage rights. Unpublished review store and researcher console accounts MUST NOT be reachable with Product API credentials. “We don’t do that” is not enough. Do not build the API App Service in this PR; write the fail-closed rule.

Console accounts are not API tenants. Unpublished review snapshots are not shared with the Product API.

## 8. Thin B1 console MUST NOT accrete subscriber/retrieval features

The thin B1 console MUST NOT accrete subscriber/retrieval features as “one more small thing”. Functional boundary: review work (ingest, tree, Beoordeel, unpublished delete, four-eyes) in the console runtime. Retrieval and subscriber functions outside that runtime.

## 9. Dual live path: CLI review-queue versus console duty queue

Do not silent-delete CLI review-queue. Console remains the researcher duty queue.

MUST NOT silent-delete `review-queue` / `build_review_queue_v3`. A later plan MAY retire the CLI path; that is not this protocol PR.

## 10. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the requirements split, the ZIP, G2 evidence, pipeline or backup. This delta does not build a new App Service.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–9.

## 11. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement the requirements split in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.23 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (console vs retrieval requirements split) after this protocol merges.

Where this delta and Protocol v2.23 conflict on whether a Cloud Shell ZIP of the post-DELETE SHA MAY include numpy/sklearn/scipy, or whether next code is only that already-landed deletion PR then ZIP that SHA, this delta governs: next code is the thin-console requirements split; Cloud Shell of that thin ZIP is later, not tonight. First DELETE cut remains done/law. After this protocol merges:

1. Next code: split console vs retrieval requirements, prove `console_asgi` import graph has no sklearn/numpy, one thin console ZIP. MUST NOT implement that split in this PR.
2. Then later (not tonight) ONE Cloud Shell ZIP of that v2.24 implementation SHA. Two Cloud Shell ZIPs of different SHAs still refused.
3. Then ingest a freeze, then wave B (G2 evidence). G2 still BLOCKED; `publish()` still G2-BLOCKED. ZIP does not open publication. This split does not open `publish()` or G2.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete, v2.21 wave definitions, v2.22 ZIP-then-B live path and v2.23 first DELETE cut remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. Wave A splitter/reject is already in code. Waves C and D are already in code. The first DELETE cut is already in code.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing console/extract/Azure, implementing the requirements split, merging product code, G2 PASS, Protocol v2.14, LLM, nurse UI, SSH wipe, hiding fragments without extract, treating Metis / Implementation engineer / Auditor as GD-03 reviewers, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–9, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except as already required, rewriting v2.16–v2.23 files except index/conflict pointers, creating or activating a test App Service, claiming G2 PASS, taking this protocol PR as the Cloud Shell ZIP, live-URL ingest, Cloud Shell tonight, a fat vendor ZIP to `vvn-metis-console`, two Cloud Shell ZIPs of different SHAs, merging PR #82, silent-deleting CLI `review-queue`, splitting high-CC fail-closed functions, recreating `HANDOFF.md`, building the API App Service in this PR, going live with Product API in this wave, treating console accounts as API tenants, sharing unpublished review snapshots with the Product API, a second law in the API, accreting subscriber/retrieval features onto the thin B1 console as one more small thing.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 12. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (split the deploy package, not the product idea; thin console ZIP; MUST NOT vendor numpy/sklearn/scipy into vvn-metis-console; one shared kernel; Product API later, not this wave; split does not open publish/G2). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later implementation of the console vs retrieval requirements split, the thin console ZIP, or wave B remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 13. Gates and approval effect

Approval of v2.24 establishes that the owner locked split the deploy package, not the product idea; that two doors already exist (operations console vs Product API); that tonight B1 died because one `requirements.txt` vendored numpy/sklearn/scipy into `vvn-metis-console`; that **Runtime-scheiding mag veranderen; protocol- en publicatiegrenzen niet.**; that the temporary deploy split MUST NOT become two systems; that PROTOCOL, object formats, freeze rules, and publish logic are one shared kernel; that Console MUST NOT interpret review/object/freeze/publish rules differently from Product API; that No second law in the API; that Shared kernel modules MUST NOT import numpy, sklearn, scipy, or scikit-learn; that A console import of shared code MUST NOT pull those in; that Package boundaries are law; that tests in this protocol PR MUST fail if `console_asgi` / `operations_console_*` import graph includes those packages; that when Product API goes live the data boundary MUST be technically enforceable (separate access, credentials, and storage rights); that Unpublished review store and researcher console accounts MUST NOT be reachable with Product API credentials; that “We don’t do that” is not enough; that the thin B1 console MUST NOT accrete subscriber/retrieval features as “one more small thing”; that Functional boundary: review work (ingest, tree, Beoordeel, unpublished delete, four-eyes) in the console runtime; that Retrieval and subscriber functions outside that runtime; that the live Review console (`vvn-metis-console`, `console_asgi` / `operations_console_*`) Azure deploy package MUST NOT vendor numpy, sklearn, scipy, or scikit-learn; that Console ZIP MAY include FastAPI, gunicorn, uvicorn, python-multipart, PyMuPDF, jsonschema, azure-identity, azure-storage-blob (G2 client remains fail-closed); that Product API / TF-IDF / `LocalCharTfidfEmbeddingProvider` stays in the repo with its own requirements/runtime later and MUST NOT go live in this wave; that No new App Service in this PR; that Product API MUST NOT be deployed in the same App Service worker as the Review console; that Shared across doors: PROTOCOL, freeze bytes (SHA-256), and later G2 published objects; that MUST NOT share unpublished review store or console login accounts as API entitlement; that Console classification remains closed taxonomy + context-aware splitter (rules), not sklearn; that `console_asgi` MUST NOT import `embedding_provider` / vector retrieval / hybrid retrieval at process start; that Oryx `output.tar.zst` of a fat vendor tree on B1 is refused; that console deploy MUST stay small enough that B1 starts without a 136MB tar extract; that `service_app.py` AND `product_api_v1.py` remain (two products); that MUST NOT silent-delete CLI review-queue; that Console remains the researcher duty queue; that next CODE after this protocol (not this PR) is split console vs retrieval requirements, prove `console_asgi` import graph has no sklearn/numpy, one thin console ZIP; that Cloud Shell of that ZIP is a later live step, not tonight; that Two Cloud Shell ZIPs of different SHAs still refused; that a later thin ZIP of the v2.24 implementation SHA is the one live ZIP; that PR #82 stays closed/unmerged; that Wave B still after a healthy console ZIP + ingest; that first DELETE cut remains done/law; that `HANDOFF.md` MUST NOT be recreated; that this protocol MUST NOT claim G2 PASS; that G2 remains BLOCKED; that `publish()` remains G2-BLOCKED; that this split does not open `publish()` or G2; that MUST NOT implement the requirements split in this PR; that MUST NOT rewrite v2.16–v2.23 files except index/conflict pointers; that this delta MAPS, and does NOT rewrite, existing law; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement the requirements split in this PR;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- take this protocol PR as the Cloud Shell ZIP;
- Cloud Shell tonight;
- take two Cloud Shell ZIPs of different SHAs;
- treat this split as opening publication, `publish()`, or G2;
- merge PR #82;
- silent-delete CLI `review-queue`;
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
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, splitter, reject, leftover, door, or deploy-package as stored object types;
- lie in the UI by hiding stored fragments without a new extract;
- treat SSH or a wipe of `/home/data` as the product path;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- treat Protocol v2.20 unpublished-delete as a fifth wave;
- rewrite Protocol v2.16–v2.23 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
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
- treat Protocol v2.14 as this file or as the next step;
- build the API App Service in this PR;
- go live with Product API / TF-IDF / `LocalCharTfidfEmbeddingProvider` in this wave;
- treat console accounts as API tenants;
- share unpublished review snapshots with the Product API;
- write a second law in the API;
- accrete subscriber/retrieval features onto the thin B1 console as one more small thing.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
