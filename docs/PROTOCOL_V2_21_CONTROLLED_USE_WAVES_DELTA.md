# V&VN Data Services Protocol v2.21 — Controlled-Use Waves

**Status:** Approved for project use  
**Protocol delta version:** 2.21.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.20.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (knowledge-object bounds; G2 status MUST be live evidence not a stale static JSON field; isolated test/release; recoverability)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.21 records the owner-approved lock of 2026-09-02 (William Gomes). Owner paused Cloud Shell and locked a four-wave program for controlled use with real guideline sources. Priority: source integrity, clear knowledge objects, safe environment isolation, recoverability. Order MUST be A then B then C then D. Cloud Shell / production ZIP stay off until wave A is on a controlled SHA. Metis is document owner. The Implementation engineer writes code later. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

Live baseline on `main` before this delta is Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. The v2.20 unpublished-delete wave is now in code on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e` (PR #81). Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0 and this delta jointly form normative baseline v2.21.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects, Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules, Protocol v2.19 review duty / queue presentation, or Protocol v2.20 every-guideline law / unpublished-snapshot delete (those stay in force). It MAPS, and does NOT rewrite, existing law. Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`. Protocol v2.19 is duty-queue. Protocol v2.20 unpublished-delete is already on `main` (`ba3c85cec8e100e289e25e6a33fbf9440676c26e`) and is NOT a fifth wave. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, wave, splitter, or reject. This delta’s bar is a four-wave controlled-use program (knowledge-object bounds, G2 status evidence, isolated test/release, recoverability), not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, and all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules remain in force, except the next-implementation and Azure-ZIP-of-v2.20-now readings superseded in sections 3–8 and 9. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, or unpublished-snapshot delete except as already required.

This delta is a **scoped supersession** of any reading that (1) the next implementation after Protocol v2.20 is Azure ZIP of v2.20, Cloud Shell, or G2 activation; (2) G2 status MAY depend on a stale static JSON field or an app-setting being present; (3) PR #82 MAY be activated before the four known faults are fixed AND an Azure test App Service exists; or (4) knowledge-object bounds are already satisfied without a context-aware splitter and a testable reject function. Where this delta and those readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain (stamp words as Koppen; 2008 Inhoud cards). Those sentences are live evidence of fails, not the product identity. PROTOCOL.md is every-guideline law, not Continentie-only (Protocol v2.20). Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.20 §8 set the next console implementation as the unpublished-delete wave (real delete control; confirm; audit ledger; then William MAY remove live unpublished Continentie). That code is now on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e` (PR #81). Where this delta and Protocol v2.20 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/extract for exactly wave A only (context-aware splitter + testable reject function + Continentie regression fixtures). Then B, then C, then D. Not Azure ZIP of v2.20 until A is on a controlled SHA unless the owner re-opens Cloud Shell. Do not start Azure in waves A or B. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation and v2.20 every-guideline law / unpublished-snapshot delete remain required law, except the bounded supersessions in this file.

G2-readiness (PR #69) already pinned `azure-identity==1.25.3` / `azure-storage-blob==12.30.1` and a report-only preflight. G2 is still BLOCKED. `publish()` remains G2-BLOCKED. RBAC Storage Blob Data Contributor on `aidataservice/canonical-sources` for the `vvn-metis-console` managed identity is external. This protocol does not claim G2 PASS.

PR #82 (`ci: isolated test deploy + manual production`) is OPEN and MUST NOT be activated until the four faults are fixed AND an Azure test app exists. This protocol MUST NOT create or activate that test App Service.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15, v2.16, v2.17, v2.18, v2.19 and v2.20 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave, the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave, the v2.17 researcher-surface wave, the v2.18 extract+card wave, the v2.19 queue/duty wave and the v2.20 unpublished-delete wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

- four rooms that are not four buttons for one person: ingest (mailbox), review (mandatory return loop; the uploader MAY also be a reviewer and MUST NOT be the only required reviewer), publish (a separate authorized act), analytics last;
- identity (researcher, reviewer, publisher); no shared login for review or publish; internal identity, not public signup;
- chat is not a room in this console;
- a care-app frontend, a chatbot as a product surface, an EPD/ECD UI and a public website MUST NOT live in this repository;
- engineers MUST NOT submit sources through the ingest room.

Every rule in Protocol v2.7.0 remains mandatory, except the undifferentiated URL-ingest sentence superseded by Protocol v2.11, including:

- first-wave official files MUST be the HTML page and the PDF only; kennisplatform `story.html` boom players MUST be out of the first wave;
- the official file MUST be the kennisplatform freeze, not a living Word document;
- a new guideline version MUST create a new snapshot and an object-level differential comparison; the old release MUST stay live until cutover publish;
- The Product API MUST retrieve at object level only; unpublished branch objects MUST abstain even if the trunk is published;
- a `supported` result MUST carry V and VN labels; DS MUST NOT generate prose; No LLM in the MVP;
- the default product MUST be a live retrieve-and-abstain subscription; training MAY exist only as a second licence with a live published-status check.

Every rule in Protocol v2.8.0 remains mandatory, including:

- primary DS users are guideline researchers (console) and B2B subscribers (an EPD, an institution, or their bot);
- nurses are not primary users; the console MUST NOT be designed for nurses and MUST NOT be a nurse decision tree;
- class/weight on each object: `richtlijn` > `handreiking` > `artikel` > `transcript` / `podcast`; heavier class MUST NOT be filled by lighter class;
- Family is a hook, not a new file; the ingest researcher MUST set family; moving a source between families MUST NOT require clinical re-review; promoting class MUST require review;
- the console tree MUST be family × class; RAG on kennisplatform HTML is not the product.

Every rule in Protocol v2.9.0 remains mandatory, except the short-help via-negativa reading superseded by Protocol v2.17, including:

- The console MUST be a task-oriented researcher surface, not a dump of the kernel data model;
- via-negativa MUST NOT be the primary on-screen copy;
- UI vocabulary MUST be researcher language; MUST NOT use "envelope" as a UI term; MUST NOT ask a researcher to type or pick a "snapshot" id;
- Login MUST ask for gebruikersnaam AND wachtwoord; no shared login; no open registration; the password field MUST be `type=password`;
- the console MUST use the V&VN digital stylesheet.

Every rule in Protocol v2.10.0 remains mandatory, including:

- the console room heading MUST be Documentenhierarchie, not Familieboom; the kernel model remains family × class;
- each top nav heading MUST show a visible waiting-task badge of real kernel work for the current user, absent or zero-hidden when nothing waits; the Publish badge MUST NOT imply that publication passed G2;
- the console MUST include an Accounts room with a CLOSED role set (`researcher`, `reviewer`, `publisher`); no open registration; no shared login; the uploader MUST NOT be the only required reviewer.

Every rule in Protocol v2.11.0 remains mandatory, including:

- official first-wave HTML MUST be an uploaded freeze file (exact bytes); live URL-HTML MUST be rejected at ingest;
- knowledge objects MUST carry enough source context to return to the exact place in that hashed original;
- The Product API MUST NOT return `supported` if the object's source locator is missing or empty; fail-closed; abstain (catalog sentence, no LLM);
- Capture remains not publication. The G2 locator still required to publish;
- Reserializing, pretty-printing, or re-saving the freeze bytes MUST NOT be used as ingest. A locator bound to reserialized HTML is not a locator into the hashed original.

Every rule in Protocol v2.12.0 remains mandatory, including:

- Extraction MUST determine structure and provenance only, NOT the meaning of a passage;
- A heading MAY become object_type `heading`; everything that is not a heading MUST default to `unclassified`;
- The machine MAY propose a type; a human reviewer MUST confirm the definitive `object_type` before publication; an unconfirmed proposal MUST NOT be treated as published type;
- Operators MUST NOT invent types in the MVP; `unclassified` is the default, not a sixth advice type;
- Answerability MUST join question type × object type; only `recommendation` MAY return as action advice (`handelingsadvies`); other types MUST NOT receive advice-weight; `unclassified` MUST NOT be `supported`;
- Cutover/publish MUST NOT trust envelope `review_passes` alone; the minimum binding remains `object_id` + `object_version` + `canonical_object_hash` + `confirmed_object_type` + `reviewer` + `decision`;
- Serving MUST use a validated published projection; publish, withdraw and supersede MUST replace that projection atomically; the API MUST NOT reconstruct live governance per query.

Every rule in Protocol v2.13.0 remains mandatory, including:

- One knowledge object MUST be one confirmable meaning unit; context MUST live in reviewed relations, not in a blob;
- The canonical store MUST be the only source of truth; retrieval index, embeddings and projections MUST be derived and disposable;
- Extraction MUST split at meaning boundaries, not token budgets; fusion of condition into recommendation is the default FORBIDDEN pattern;
- Machine classification is a proposal, never published truth; `unclassified` remains the default until a human confirms a type from the closed set on that exact object version;
- Closed relation set remains `applies_if`, `except_if`, `defines`, `explains`, `supported_by`, `supersedes`, `parent` / `child`; unconfirmed relations MUST NOT bind;
- High-risk four-eyes (second named reviewer on the exact object tuple) MUST be required when confirmed type is `exception`, `risk_level` is high, or a listed high-risk field is present;
- From every knowledge object the reviewer MUST be able to open the exact source passage; this delta MUST NOT invent a locator scheme.

Every rule in Protocol v2.15.0 remains mandatory, except the heading-proposal, stamp, tiny-object, one-door, compact-row, next-implementation and unpublished-Continentie-re-extract readings already superseded by Protocol v2.16, and except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19, including:

- The ingest date field MUST be a calendar date picker stored as ISO `YYYY-MM-DD`; empty rejected; not today; not ingest-click; display locale MUST NOT leak into stored bytes;
- The ingest version field MUST be dotted non-negative integers; empty rejected; no `v` prefix, letters, year-as-version;
- Those two fields are freeze source metadata, not `object_version` and not Protocol v2.14 `valid_from` / `valid_until`;
- There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam”; lane follows confirmed (or, for queue routing only, proposed) `object_type`;
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`, except the v2.16 stamp rule and the v2.17 chrome rule;
- Fast lane MUST support batch-confirm of proposed headings as structure, not advice; headings MUST NOT be served as handelingsadvies;
- Four thousand unclassified cards on one richtlijn is a fail of this review surface.

Every rule in Protocol v2.16.0 remains mandatory, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object and next-implementation readings superseded by Protocol v2.17, the list-only compact-row reading and truncated-sentence reading tightened by Protocol v2.18, the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20, including:

- The Review page is the page that MUST convince guideline researchers; if they open it and it does not suffice, the project has failed — even if the kernel is fail-closed;
- One door **Beoordeel**; MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- Two named stacks with counts: **Koppen** (real freeze TOC / section titles of the richtlijn body) and **Inhoud**;
- Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status;
- DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not objects and not Koppen rows; extract MUST NOT heading-propose those words;
- Extract MUST NOT emit tiny objects (list-number-only, stamp-only, or a sentence fragment that cannot stand as one meaning unit);
- MUST NOT lie in the UI by hiding stored fragments without a new extract.

Every rule in Protocol v2.17.0 remains mandatory, except the next-implementation reading superseded by Protocol v2.18, including:

- UI copy MUST be researcher language; MUST NOT be slogans; MUST NOT say “wat een EPD MAG zeggen”; the entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg;
- Via-negativa MUST NOT appear on researcher rooms, including collapsed help;
- Onderwerp / family MUST be empty on a fresh new ingest;
- Bronpassage MUST show the same readable sentence as the knowledge object, without HTML tags, CSS class names, or kennisplatform markup, on every object / the whole freeze; v2.11 freeze bytes and locators stay exact;
- Extract MUST NOT emit kennisplatform chrome as knowledge objects or Koppen, including one-word Tools/Home/Richtlijnen/Meedenken;
- Recommendation-strength UI MUST NOT appear except on type `recommendation`;
- Relation checkbox and its label MUST be adjacent.

Every rule in Protocol v2.18.0 remains mandatory, except the next-implementation reading superseded by Protocol v2.19, including:

- The review object card MUST show the freeze sentence once; MUST NOT duplicate it as both h3/title and body;
- Extract MUST NOT split a grammatical continuation of the previous sentence into a new object; trailing clauses MUST stay in the same knowledge object as the sentence they complete;
- Extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical to an object already emitted from this freeze; repeated HTML (samenvatting versus module) is not extra knowledge; distinct real headings in different sections MAY remain.

Every rule in Protocol v2.19.0 remains mandatory, except the next-implementation reading superseded by Protocol v2.20, including:

- Researchers MUST NOT be required to open 2008 Inhoud cards one by one. That is the same fail as 4000 unclassified: fatigue, not assurance;
- Koppen MAY and MUST be batch-confirmable as structure, never as advice;
- The researcher-required slow review on a freeze is proposed `recommendation`, plus `condition` / `exception` / any high-risk object (four-eyes unchanged);
- Remaining `unclassified` MUST NOT be presented as equal one-by-one work of thousands of cards. Unclassified is never served (`supported` / handelingsadvies), so 2000 clicks on it do not add assurance;
- MUST NOT auto-confirm types; MUST NOT auto-promote ordinary text to `recommendation`; MUST NOT a researcher “zwaar/licht” or “snel/langzaam” switch;
- 2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface.

Every rule in Protocol v2.20.0 remains mandatory, except the next-implementation and Azure-ZIP-of-v2.20-now readings superseded here, including:

- `PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol;
- Continentie appears in Protocol v2.16–v2.19 as live evidence of fails (stamp words as Koppen; 2008 Inhoud cards), not as the product identity;
- Those historical evidence sentences MUST remain. This delta MUST NOT strip them;
- The next freeze MUST NOT have to be Continentie;
- Unpublished captured snapshots MAY be removed from the operations console by an authorized console operator;
- MUST a real delete control on the document card / Review chooser for unpublished snapshots only; MUST confirm before it runs;
- MUST NOT delete a published projection; MUST NOT hide selected objects inside a freeze that stays in Review; MUST NOT SSH or wipe `/home/data` as the product path;
- Four-eyes is not required to delete unpublished capture.

Owner evidence 2026-09-02: Continentie in v2.16–v2.19 is live evidence of those fails (stamp words as Koppen; Koppen 78 / Inhoud 2008 after the v2.18 extract on `main` `4ebfdbb88cdb`, snapshot `snap-ac59cf24f946088e-e402c4d3`). That evidence stays. It is not the product identity. There is no published Continentie.

## 3. Four-wave program; order A then B then C then D

Owner paused Cloud Shell and locked a four-wave program for controlled use with real guideline sources. Priority: source integrity, clear knowledge objects, safe environment isolation, recoverability.

- Order MUST be A then B then C then D.
- Cloud Shell / production ZIP stay off until wave A is on a controlled SHA.
- Wave A is knowledge-object bounds (section 4). No infrastructure in wave A.
- Wave B is G2 status evidence (section 5). After A. MUST NOT start Azure in waves A or B.
- Wave C is the test/release pipeline (section 6). After B. Finish PR #82; do not activate until a test App Service exists.
- Wave D is backup/recoverability (section 7). After C.
- Protocol v2.20 unpublished-delete is already on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e` and is NOT a fifth wave.
- This delta MAPS existing v2.16–v2.20 law. It does NOT rewrite that law.

This supersedes any reading that the next implementation after Protocol v2.20 is Azure ZIP of v2.20, Cloud Shell, or G2 activation.

## 4. Wave A — knowledge-object bounds

Wave A is the next implementation after this protocol merges. Implement a context-aware splitter plus a testable reject function. No infrastructure in wave A.

An inhoudelijk knowledge object MUST be one complete, independently readable meaning unit. It MUST have bronpassage plus locator to the freeze. It MUST NOT be only a number, label, kopwoord, nav, stamp, or sentence fragment. It MUST NOT duplicate identical `clean_text` from the same freeze.

Real source headings MAY exist as `heading`, structure only, never advice, no recommendation stamp, batch-confirmable as structure.

DOEN / OVERWEEG / NIET DOEN are not objects and not Koppen; they are a property of a full recommendation together with the advice sentence. This maps Protocol v2.16; it does not invent a new type.

The splitter MUST:

- attach trailing / dependent clauses to the previous meaningful sentence;
- attach a stamp to the immediately following advice sentence;
- filter chrome / nav / list numbers / loose labels / empty / too-short BEFORE object creation;
- prevent duplicate `clean_text` in the same snapshot;
- keep freeze bytes and locators exact (derived extract only).

The reject function MUST reject:

- not a standalone meaning;
- below a documented minimum meaning threshold;
- stamp / number / nav-only;
- grammatical continuation of the previous sentence;
- identical to an earlier object from the same freeze.

Exceptions MUST be explicit and tested: short real definitions and official headings MUST NOT be dropped.

MUST NOT treat “Inleiding” as chrome. Home / Tools / Richtlijnen / Meedenken are chrome. Inleiding as a real section title MAY remain `heading`.

Regression fixtures MUST come from real Continentie fail patterns:

- stamps plus advice sentence;
- “Eventueel met hulp van de mantelzorger.”;
- list numbers;
- Home / Tools;
- duplicate samenvatting / module;
- short valid definitions;
- real headings at different levels;
- HTML repeated modules;
- PDF versus HTML difference.

Acceptance: none of those fail patterns land as standalone inhoudelijk objects in the review duty queue.

Wave A MAPS Protocol v2.16 tiny-objects, Protocol v2.17 chrome, and Protocol v2.18 trailing-clause / identical-`clean_text`. It does not rewrite those files. It adds a context-aware splitter and a testable reject function as the next implementation of that already-locked law.

## 5. Wave B — G2 status evidence (after A)

Wave B is after A. G2 status MUST NOT depend on a stale static JSON field.

Read-only preflight MUST show:

- Blob container reachable;
- managed identity usable;
- required Blob role present or access actually proven;
- container matches the active environment;
- a source can be stored and read back byte-identical.

Controlled SHA-256 smoke. Machine-readable evidence MUST include timestamp, environment, container, SHA-256, and outcome.

G2 PASS only after a successful controlled test; else BLOCKED. The publication gate MUST NOT open because an app-setting is present.

Do not claim G2 PASS in this protocol. RBAC grant remains external. `publish()` remains G2-BLOCKED. G2-readiness (PR #69) already pinned `azure-identity` / `azure-storage-blob` and a report-only preflight; that is readiness, not PASS.

MUST NOT start Azure in wave B.

## 6. Wave C — test/release pipeline (after B)

Wave C is after B. Finish PR #82. Do not activate until a test App Service exists.

- Invoke the packaging script via bash or make it executable.
- The Azure ZIP MUST build dependencies or the artifact MUST be fully deployable (git-archive-only is not enough; live Oryx-during-deploy caused HTTP_504 on B1).
- Storage account / container per environment via safe app settings; no secrets in Git.
- Separate deployment identities: the test identity MAY only deploy to test; the production identity MAY only deploy to production.
- Production is manual: only a full SHA already on `main`, after protection / approval.
- MUST NOT deploy runtime data from Git.
- MUST NOT overwrite `/home/data`.
- Merge to `main` MAY deploy only to test; production requires an explicit release action of the exact same tested SHA.

Known PR #82 faults to fix:

1. `create_azure_deploy_package.sh` invoked without bash and may not be executable;
2. package is git archive HEAD only, no dependencies;
3. workflows do not configure per-environment storage;
4. one Entra app is not enough if it can deploy to both — identities MUST be scoped so test cannot production and production cannot test.

MUST NOT create or activate a test App Service in this protocol PR. MUST NOT start Azure in waves A or B. PR #82 is OPEN and MUST NOT be activated until those four faults are fixed AND an Azure test app exists.

## 7. Wave D — backup/recoverability (after C)

Wave D is after C.

Inventory of `/home/data/metis-console` MUST include:

- accounts / roles;
- document snapshots;
- review decisions and audit ledger;
- canonical objects;
- derived projections.

MUST have an export / backup procedure; a controlled restore to a clean environment; an integrity check after restore; and a test proving a deployment does not delete existing runtime data.

No large database migration. MUST document the migration boundary: a managed database becomes required before multiple App Service instances or concurrent multi-reviewer writes.

## 8. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the new splitter, reject function, G2 evidence, pipeline or backup.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol.

Cloud Shell / production ZIP stay off until wave A is on a controlled SHA unless the owner re-opens Cloud Shell.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–7.

## 9. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before wave A has a context-aware splitter, a testable reject function, and Continentie regression fixtures.

Where this delta and Protocol v2.20 conflict on which implementation is next, this delta governs. The v2.20 unpublished-delete wave is already in code on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e`. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/extract for exactly wave A only:

1. context-aware splitter + testable reject function;
2. an inhoudelijk knowledge object MUST be one complete, independently readable meaning unit; MUST have bronpassage+locator to freeze; MUST NOT be only a number, label, kopwoord, nav, stamp, or sentence fragment; MUST NOT duplicate identical `clean_text` from the same freeze;
3. real source headings MAY exist as `heading`, structure only, never advice, no recommendation stamp, batch-confirmable as structure;
4. DOEN / OVERWEEG / NIET DOEN are not objects and not Koppen; they are a property of a full recommendation together with the advice sentence;
5. splitter MUST attach trailing/dependent clauses to the previous meaningful sentence; MUST attach a stamp to the immediately following advice sentence; MUST filter chrome/nav/list numbers/loose labels/empty/too-short BEFORE object creation; MUST prevent duplicate `clean_text` in the same snapshot; MUST keep freeze bytes and locators exact (derived extract only);
6. reject function MUST reject: not a standalone meaning; below a documented minimum meaning threshold; stamp/number/nav-only; grammatical continuation of previous; identical to an earlier object from the same freeze; exceptions MUST be explicit and tested: short real definitions and official headings MUST NOT be dropped;
7. MUST NOT treat “Inleiding” as chrome; Home/Tools/Richtlijnen/Meedenken are chrome; Inleiding as a real section title MAY remain `heading`;
8. regression fixtures from real Continentie fail patterns (stamps+advice sentence, “Eventueel met hulp van de mantelzorger.”, list numbers, Home/Tools, duplicate samenvatting/module, short valid definitions, real headings at different levels, HTML repeated modules, PDF vs HTML difference); acceptance: none of those fail patterns land as standalone inhoudelijk objects in the review duty queue;
9. no infrastructure in wave A.

THEN wave B (G2 status evidence). THEN wave C (finish PR #82; do not activate until a test App Service exists). THEN wave D (backup/recoverability). Not Azure ZIP of v2.20 until A is on a controlled SHA unless the owner re-opens Cloud Shell. Do not start Azure in waves A or B. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation and v2.20 every-guideline law / unpublished-snapshot delete remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta. The v2.17 researcher-surface wave is already in code and is not the next implementation after this delta. The v2.18 extract+card wave is already in code and is not the next implementation after this delta. The v2.19 queue/duty wave is already in code and is not the next implementation after this delta. The v2.20 unpublished-delete wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing console/extract/Azure, merging, G2 PASS, Protocol v2.14, LLM, nurse UI, SSH wipe, hiding fragments without extract, treating Metis / Implementation engineer / Auditor as GD-03 reviewers, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–7, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, or unpublished-snapshot delete except as already required, creating or activating a test App Service, starting Azure in waves A or B, claiming G2 PASS.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 10. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (knowledge-object bounds; G2 status MUST be live evidence not a stale static JSON field; isolated test/release; recoverability). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later implementation of wave A (splitter + reject function + Continentie regression fixtures), wave B, wave C or wave D remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 11. Gates and approval effect

Approval of v2.21 establishes that the owner paused Cloud Shell and locked a four-wave program for controlled use with real guideline sources; that priority is source integrity, clear knowledge objects, safe environment isolation, recoverability; that order MUST be A then B then C then D; that Cloud Shell / production ZIP stay off until wave A is on a controlled SHA; that this delta MAPS, and does NOT rewrite, existing law; that Protocol v2.16–v2.18 already forbid tiny objects, stamp-as-heading/object, truncated/trailing clauses, chrome objects, and identical `clean_text`; that Protocol v2.19 is duty-queue; that Protocol v2.20 unpublished-delete is already on `main` `ba3c85cec8e100e289e25e6a33fbf9440676c26e` and is NOT a fifth wave; that `PROTOCOL.md` is every-guideline law, not Continentie-only (Protocol v2.20); that Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain; that G2-readiness (PR #69) already pinned `azure-identity` / `azure-storage-blob` and a report-only preflight; that G2 is still BLOCKED; that `publish()` remains G2-BLOCKED; that RBAC Storage Blob Data Contributor on `aidataservice/canonical-sources` for `vvn-metis-console` is external; that PR #82 is OPEN and MUST NOT be activated until the four faults are fixed AND an Azure test app exists; that wave A MUST implement a context-aware splitter plus a testable reject function; that an inhoudelijk knowledge object MUST be one complete, independently readable meaning unit; that it MUST have bronpassage+locator to freeze; that it MUST NOT be only a number, label, kopwoord, nav, stamp, or sentence fragment; that it MUST NOT duplicate identical `clean_text` from the same freeze; that real source headings MAY exist as `heading`, structure only, never advice, no recommendation stamp, batch-confirmable as structure; that DOEN / OVERWEEG / NIET DOEN are not objects and not Koppen; that they are a property of a full recommendation together with the advice sentence; that the splitter MUST attach trailing/dependent clauses to the previous meaningful sentence; that the splitter MUST attach a stamp to the immediately following advice sentence; that the splitter MUST filter chrome/nav/list numbers/loose labels/empty/too-short BEFORE object creation; that the splitter MUST prevent duplicate `clean_text` in the same snapshot; that the splitter MUST keep freeze bytes and locators exact (derived extract only); that the reject function MUST reject not-a-standalone-meaning, below a documented minimum meaning threshold, stamp/number/nav-only, grammatical continuation of previous, and identical to an earlier object from the same freeze; that exceptions MUST be explicit and tested; that short real definitions and official headings MUST NOT be dropped; that MUST NOT treat “Inleiding” as chrome; that Home/Tools/Richtlijnen/Meedenken are chrome; that Inleiding as a real section title MAY remain `heading`; that regression fixtures MUST come from real Continentie fail patterns; that acceptance is that none of those fail patterns land as standalone inhoudelijk objects in the review duty queue; that no infrastructure in wave A; that wave B G2 status MUST NOT depend on a stale static JSON field; that read-only preflight MUST show Blob container reachable, MI usable, required Blob role present or access actually proven, container matches active environment, and source stored and read back byte-identical; that controlled SHA-256 smoke and machine-readable evidence (timestamp, environment, container, SHA-256, outcome) are required; that G2 PASS only after a successful controlled test, else BLOCKED; that the publication gate MUST NOT open because an app-setting is present; that this protocol does not claim G2 PASS; that RBAC grant remains external; that wave C MUST invoke the packaging script via bash or make it executable; that the Azure ZIP MUST build dependencies or the artifact MUST be fully deployable; that git-archive-only is not enough; that live Oryx-during-deploy caused HTTP_504 on B1; that storage account/container per environment via safe app settings, no secrets in Git; that separate deployment identities MUST be scoped so test cannot production and production cannot test; that production is manual (only a full SHA already on `main`, after protection/approval); that MUST NOT deploy runtime data from Git; that MUST NOT overwrite `/home/data`; that merge to `main` MAY deploy only to test; that production requires an explicit release action of the exact same tested SHA; that the four known PR #82 faults MUST be fixed; that MUST NOT create or activate a test App Service in this protocol PR; that MUST NOT start Azure in waves A or B; that wave D MUST inventory `/home/data/metis-console` (accounts/roles, document snapshots, review decisions and audit ledger, canonical objects, derived projections); that wave D MUST have export/backup, controlled restore to a clean environment, integrity check after restore, and a test proving a deployment does not delete existing runtime data; that no large database migration; that MUST document the migration boundary (a managed database becomes required before multiple App Service instances or concurrent multi-reviewer writes); and that the next implementation after this protocol merges MUST be Implementation engineer wave A only (splitter + reject function + Continentie regression fixtures), then B, then C, then D. Serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- start Azure in waves A or B;
- create or activate a test App Service in this protocol PR;
- activate PR #82 before the four faults are fixed AND an Azure test app exists;
- skip durable immutable storage;
- staff named reviewers;
- treat Metis, the Implementation engineer or the Auditor as GD-03 reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- let Koppen heading accept bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type;
- auto-confirm types;
- auto-promote ordinary text to `recommendation`;
- treat remaining unclassified as equal one-by-one researcher duty of thousands of cards;
- treat 2008 Inhoud cards as an acceptable workload;
- make `definition` / `explanation` the MVP researcher 2000-card duty for handelingsadvies;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, splitter, or reject as stored object types;
- invent GRADE English labels on this screen;
- keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- present a page of thousands of identical `unclassified` titles, or use the type name (`unclassified`) or a kernel document id as the review-list row title;
- stretch status / checkbox / text into disconnected columns across the viewport;
- treat DOEN/OVERWEEG/NIET DOEN as Koppen rows or standalone knowledge objects;
- propose `heading` for DOEN/OVERWEEG/NIET DOEN even if the freeze wraps them in heading tags;
- emit number-only, stamp-only, or truncated-sentence objects;
- emit a trailing clause (“Eventueel …”, “Bijvoorbeeld …”, “Zoals …”) as its own knowledge object;
- emit identical `clean_text` as a second knowledge object from the same freeze because the HTML repeats samenvatting/module text;
- treat `1.1 Inleiding` and `2. Inleiding` as identical strings;
- treat “Inleiding” as chrome;
- emit kennisplatform chrome (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated nav) as knowledge objects or Koppen;
- drop short real definitions or official headings;
- fuse condition into recommendation, or reopen that Protocol v2.13 forbid;
- lie in the UI by hiding stored fragments without a new extract;
- hide selected objects inside a freeze that stays in Review;
- delete a published projection or anything that has been published;
- treat SSH or a wipe of `/home/data` as the product path;
- overwrite `/home/data` on deploy;
- deploy runtime data from Git;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- make the next freeze have to be Continentie;
- treat `PROTOCOL.md` as Continentie-only law;
- treat Protocol v2.20 unpublished-delete as a fifth wave;
- rewrite Protocol v2.16–v2.20 files except index pointers;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules beyond mapping the already-locked tiny-object, grammatical-continuation, and identical-`clean_text` forbids into a splitter plus reject function;
- reopen Protocol v2.11 freeze/locator except researcher-visible prose derived from those locators;
- reserialize or re-save freeze bytes, or bind locators to reserialized HTML;
- dump raw HTML tag soup, CSS class names or kennisplatform markup as the researcher bronpassage;
- reopen Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except as already superseded by v2.16 stamps, the v2.17 chrome rule, and the v2.19 slow-lane-unclassified-as-equal-one-object-duty reading;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except as already required;
- reopen Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation or compact-relation-checkbox rules except as already required;
- reopen Protocol v2.18 once-only card sentence, grammatical-continuation-split or identical-`clean_text` rules except as already required;
- reopen Protocol v2.19 review-duty or queue-presentation rules except as already required;
- reopen Protocol v2.20 every-guideline-law or unpublished-snapshot-delete rules except the next-implementation and Azure-ZIP-of-v2.20-now readings superseded here;
- require or allow “wat een EPD MAG zeggen” or any EPD MAG slogan as Review lead copy;
- claim a single subscriber class on researcher pages;
- allow HELP_ONCE via-negativa on researcher rooms, including collapsed “Over deze console”;
- prefill Onderwerp / family on a fresh new ingest;
- expand empty-Onderwerp to class default;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer for type-confirm, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor in this protocol PR;
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–7;
- let G2 status depend on a stale static JSON field;
- open the publication gate because an app-setting is present;
- treat capture as publication;
- reopen or alter GD-03;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- design the console for nurses;
- open the role set or allow operators to invent new role types, object types or relation types;
- allow open registration or shared login;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- silently add a new quality metric as a protocol gate;
- authorize a mockup, Azure ZIP of v2.20, Cloud Shell, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
