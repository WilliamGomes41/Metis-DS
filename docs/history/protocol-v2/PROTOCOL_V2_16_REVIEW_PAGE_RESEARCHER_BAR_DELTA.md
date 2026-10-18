# V&VN Data Services Protocol v2.16 — Review Page Researcher Bar

**Status:** Approved for project use  
**Protocol delta version:** 2.16.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.15.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (a messy review page biases assessment)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.16 records the owner-approved lock of 2026-09-02 (William Gomes) after an audit against the live baseline Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0 on `main`, plus live Review-page evidence the same day from the Azure console on Continentie (`snap-baf3c28513f82858-c248c67b`): (1) Koppen (structuur) list with three-column spread and one-word DOEN/OVERWEEG as heading rows; (2) unclassified fragments including split sentences, a raw timestamp, and a lone `1.`; (3) earlier 4000 identical unclassified titles. Those surfaces MUST NOT remain acceptable. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem is the Review page as the researcher task: if researchers open it and it does not suffice, the project has failed — even if the kernel is fail-closed.

The Review page is the page that MUST convince guideline researchers to work in this system. Two frustrations MUST NOT remain; both bias assessment:

1. **Unclear:** the researcher does not know what to click or why (two doors, rows split across the page, DOEN/OVERWEEG without explanation).
2. **Too-small objects:** one word, one number, half a sentence — context gone, judgement rests on a stamp or a number.

Live baseline on `main` before this delta is Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0 and this delta jointly form normative baseline v2.16.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, G2, Azure, LLM, or Protocol v2.14 time/lifecycle. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, or GRADE. Paragraph is display context, not a stored blob, not a new type. DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not types.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules, all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules, all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, and all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules remain in force, except the heading-proposal, stamp, tiny-object, one-door, compact-row, next-implementation and unpublished-Continentie-re-extract readings superseded in sections 3–8 and 10. This protocol-only change does not implement console Python, extract, kernel, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that the next console work after Protocol v2.15 is only ingest date/version/heading-lanes (that code is on `main`), that two doors **Openen** plus **Reviewen** MAY both lead to object lists, that DOEN/OVERWEEG/NIET DOEN MAY be rows in Koppen or standalone knowledge objects, that extract MAY propose `heading` for those words even when the freeze wraps them in heading tags, that extract MAY emit a knowledge object whose confirmable text is only a list number, only a strength stamp, or a sentence fragment that cannot stand as one meaning unit, that list rows MAY stretch status / checkbox / text into disconnected columns across the viewport, that the type name (`unclassified`) or a kernel document id MAY be the row title, that a page of thousands of identical `unclassified` titles MAY be accepted as workload, that unpublished Continentie bytes MUST NOT be re-extracted, or that the UI MAY hide stored fragments without a new extract. Where this delta and those readings conflict, this delta governs. Lane still follows type (Protocol v2.15), except the v2.16 heading-proposal and stamp rules below supersede v2.15 where they conflict. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.15 §8 set the next console implementation as ingest date calendar + ISO store, ingest version dotted-integer validation, extract heading-proposal for real source headings, review-list source-passage snippet, and type-routed queues with fast-lane batch-confirm. That code is now on `main`. Where this delta and Protocol v2.15 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console (one door **Beoordeel**; two named stacks with counts Koppen / Inhoud; compact one-line rows with source text; DOEN/OVERWEEG/NIET DOEN as stamps on `recommendation`, with a researcher help sentence; extract MUST NOT heading-propose those words; extract MUST NOT emit number-only / stamp-only / truncated-sentence objects; new extract of the unpublished Continentie freeze so the page can pass the bar). THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes and v2.15 ingest date/version/type-lanes remain required law, except the bounded supersessions in this file.

Index/conflict pointer: Protocol v2.28.0 SUPERSEDES any reading of this file that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm. Where this file and Protocol v2.28 conflict on the Sterkte gate, Protocol v2.28 governs: Sterkte visible and active ONLY when stored/confirmed type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`; a machine proposal `recommendation` MUST NOT activate/show Sterkte. v2.16 stamp-on-recommendation law remains (DOEN/OVERWEEG/NIET DOEN are stamps on `recommendation`, not objects, not Koppen rows, not a new type); the gate becomes confirmed/stored type. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

Index/conflict pointer: Protocol v2.30.0 SUPERSEDES any reading of this file that type UI MAY start from only “nog niet bevestigd” without a Metis proposal + evidence, or that admission MAY be subjective. Where this file and Protocol v2.30 conflict on admission or type UI, Protocol v2.30 governs: a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; type UI MUST show the Metis proposal + Dit klopt / Type wijzigen. v2.16 one-door / stacks / stamps / tiny-objects law remains. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13 and v2.15 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card and the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.9.0 remains mandatory, including:

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
- Capture remains not publication. The G2 locator still required to publish.

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

Every rule in Protocol v2.15.0 remains mandatory, except the heading-proposal, stamp, tiny-object, one-door, compact-row, next-implementation and unpublished-Continentie-re-extract readings superseded here, including:

- The ingest date field MUST be a calendar date picker stored as ISO `YYYY-MM-DD`; empty rejected; not today; not ingest-click; display locale MUST NOT leak into stored bytes;
- The ingest version field MUST be dotted non-negative integers; empty rejected; no `v` prefix, letters, year-as-version;
- Those two fields are freeze source metadata, not `object_version` and not Protocol v2.14 `valid_from` / `valid_until`;
- There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam”; lane follows confirmed (or, for queue routing only, proposed) `object_type`;
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`, except the v2.16 stamp rule in section 7: Extract MUST NOT propose `heading` for DOEN/OVERWEEG/NIET DOEN;
- Fast lane MUST support batch-confirm of proposed headings as structure, not advice; headings MUST NOT be served as handelingsadvies;
- Slow lane stays one-object (type + relations + high-risk four-eyes);
- The review list MUST NOT use the type name (`unclassified`) as the row title; Protocol v2.16 section 6 tightens the row to one compact source-text line;
- Extract MUST NOT auto-promote ordinary text to `recommendation`;
- Four-eyes unchanged; the machine MUST NOT decide that something is light enough to serve.

## 3. Researcher bar (first screen)

The Review page is the page that MUST convince guideline researchers to work in this system. If they open it and it does not suffice, the project has failed — even if the kernel is fail-closed.

Within one screen the researcher MUST know: which document this is, what to do now, and why (this becomes what an EPD may say). UI copy MUST be researcher language. Primary action MUST be visually obvious. Kernel ids MUST NOT be the row title.

Owner evidence 2026-09-02 (Azure console, Continentie): Koppen rows stretched across the viewport with a metadata line, a lone checkbox, and a one-word purple **DOEN** / **OVERWEEG**; unclassified rows that are split sentences, a timestamp, or a lone `1.`; earlier 4000 identical `unclassified` titles. These MUST NOT be acceptable.

- The first Review screen MUST name the document in researcher language (title / family / class / version), not a kernel snapshot id as the heading.
- The first Review screen MUST say what to do now (which stack, which primary button) and why it matters (this becomes what an EPD may say).
- Via-negativa MUST NOT be the primary on-screen copy (Protocol v2.9 unchanged).
- Kernel document ids, snapshot ids and object ids MUST NOT be the row title. They MAY remain secondary, never the thing the researcher is asked to judge.

## 4. One door

MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists.

- One document card, one primary button **Beoordeel**.
- Openen-as-a-second-path to the same list is forbidden.
- Secondary inspection that is not the assessment path MAY exist only if it cannot be confused with **Beoordeel** and does not open the same object list as a parallel door.
- Protocol v2.15 listed “Openen-versus-Reviewen extra door” as out of scope for that delta. Where this delta and that out-of-scope sentence conflict, this delta governs: the extra door is now forbidden.

## 5. Two named stacks with counts

Researcher language, not kernel jargon. Counts MUST be visible on each stack.

- **Koppen** — real table-of-contents / section titles from the freeze (structure). Batch-confirm as structure, never as advice. Headings MUST NOT be served as handelingsadvies.
- **Inhoud** — `definition`, `explanation`, `condition`, `exception`, `recommendation`, and `unclassified` until typed. One-object card (existing two-column object | bronpassage). High-risk four-eyes unchanged.

MUST NOT present a page of thousands of identical `unclassified` titles. There MUST NOT be a researcher control “zwaar/licht”. Lane follows type (Protocol v2.15), except the v2.16 heading-proposal and stamp rules in section 7 supersede v2.15 where they conflict.

- Koppen is the v2.15 fast lane under a researcher name. Inhoud is the v2.15 slow lane under a researcher name. This delta MUST NOT invent a third lane or a speed toggle.
- A human MUST be able to reclassify: a heading that is actually advice becomes `recommendation` and MUST then sit in Inhoud. Demotion to Koppen MUST only happen by confirming type `heading`, never by a speed toggle.
- Fast-lane / Koppen heading accept MUST NOT bypass four-eyes if the object is actually high-risk or is reclassified onto a high-risk type.
- MUST NOT add new object types for page/paragraph. Paragraph is display context, not a stored blob, not a new type.

## 6. Compact rows

Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status. MUST NOT stretch status / checkbox / text into disconnected columns across the viewport. MUST NOT use the type name (`unclassified`) or a kernel document id as the title.

- The row title MUST be the freeze source sentence of that object, or the real heading text for Koppen.
- A short status MAY sit on the same line (waiting / classified / confirmed). Status MUST NOT become a third disconnected column.
- A checkbox MAY sit on the same compact line for Koppen batch-confirm. It MUST NOT float in a centre column with empty white space to the title and to the stamp.
- Protocol v2.15 already forbids the type name as the row title and requires a source-passage snippet. This delta tightens that to one compact source-text line and forbids the three-column spread in the 2026-09-02 Koppen evidence.

## 7. DOEN / OVERWEEG / NIET DOEN are stamps, not objects

These words are V&VN recommendation-strength language. MUST NOT invent GRADE jargon on this screen. MUST NOT add a new object type. MUST NOT be rows in Koppen. MUST NOT be standalone knowledge objects.

Preferred lock: stamp on the following recommendation. The review card MUST show one sentence in researcher language, e.g. “Sterkte van de aanbeveling: DOEN — dit moet de zorgverlener doen.” Closed values on type `recommendation` only: `doen` | `overweeg` | `niet_doen`. This is NOT fusion of condition into recommendation and MUST NOT reopen that Protocol v2.13 forbid. Human confirms strength together with the advice sentence.

- Extract MUST NOT propose `heading` for DOEN/OVERWEEG/NIET DOEN even if the freeze wraps them in heading tags. Where this sentence and Protocol v2.15 “Extract MUST propose `heading` for real source headings / TOC / structural crumbs” conflict for those words, this delta governs.
- A heading that is actually advice (“Overweeg verwijzing…”) remains the Protocol v2.13 / v2.15 human-reclassify case: it becomes `recommendation` and MUST then sit in Inhoud. A bare strength word is not that case; it is a stamp, not a heading and not an object.
- Strength is a field (or equivalent stamp) on the `recommendation` object, not a sibling object, not a Koppen row, not a new type.
- MUST NOT introduce GRADE English labels (`strong`, `weak`, `conditional`) as UI copy on this screen.
- Serving remains Protocol v2.12: only confirmed `recommendation` MAY return as action advice (`handelingsadvies`). A stamp without a confirmed advice sentence MUST NOT be `supported`.

## 8. No tiny objects

Extract MUST NOT emit a knowledge object whose confirmable text is only a list number (`1.`), only a strength stamp, or a sentence fragment that cannot stand as one meaning unit (Protocol v2.13 meaning-boundary split). A lone trailing word of a previous sentence is forbidden.

Freeze source bytes and SHA-256 stay. Existing published objects are not silently rewritten (there is no published projection). Continentie is unpublished: a new extract of the same freeze bytes is REQUIRED so the review page can meet this bar; source hash stays, unpublished object identities MAY be replaced by that new extract. MUST NOT lie in the UI by hiding stored fragments without a new extract.

- Owner evidence 2026-09-02: unclassified fragments include a split sentence (“Hoelang de cliënt dit dagboek moet bijhouden hangt af van zijn specifieke” / “problemen.”), a raw timestamp (“Gemaakt op 31-08-2026 19:52:55”), and a lone `1.`. Those MUST NOT be confirmable objects.
- Protocol v2.15 said this protocol MUST NOT re-extract existing Continentie bytes and MUST NOT silently re-split already-hashed Continentie objects. Continentie is unpublished and there is no published projection. Where this delta and that v2.15 sentence conflict for unpublished Continentie, this delta governs: a new extract of the same freeze bytes is REQUIRED so the Review page can pass this bar. Source hash of the freeze stays. Unpublished object identities MAY be replaced by that new extract.
- MUST NOT hide stored fragments in the UI without that new extract. Hiding is lying; a new extract is the lawful fix.
- Published objects, if any later exist, MUST NOT be silently rewritten. Identity of published hashed objects stays until a new source version / snapshot under existing v2.7 / v2.12 / v2.13 rules.
- This delta MUST NOT rewrite Protocol v2.13 split rules except to forbid tiny objects that cannot stand as one meaning unit. Token-budget chunking still MUST NOT define object identity. Fusion of condition into recommendation remains the forbidden default.

## 9. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged. G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob.

The following rules remain mandatory and are not relaxed by this delta:

- Canonical source binaries (HTML, PDF and other official source bytes) MUST NOT be committed to Git.
- Secrets, API keys, passwords, certificates and private keys MUST NOT be committed.
- `config/tenants.v1.json` MUST remain an empty tenant list in the repository.
- Confidential review artefacts MUST NOT be committed.
- Runtime databases and local runtime state MUST NOT be committed.
- GD-03 remains ESTABLISHED as written. This delta does not reopen GD-03.
- Holdout B MUST NOT be tuned from console analytics or any other operational metric.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

`.gitignore` already covers the source, secret, tenant, review and runtime classes and MUST be kept.

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–8.

## 10. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the Review page has one door **Beoordeel**, two named stacks with counts, compact source-text rows, stamps on recommendation, and an extract that does not emit tiny objects or heading-propose DOEN/OVERWEEG/NIET DOEN.

Where this delta and Protocol v2.15 conflict on which implementation is next, this delta governs. The v2.15 ingest-date / ingest-version / heading-lanes wave is already in code on `main`. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console:

1. one door **Beoordeel**;
2. two named stacks with counts (Koppen / Inhoud);
3. compact one-line rows with source text;
4. DOEN/OVERWEEG/NIET DOEN as stamps on recommendation, with researcher help sentence; extract MUST NOT heading-propose those words;
5. extract MUST NOT emit number-only / stamp-only / truncated-sentence objects; new extract of unpublished Continentie freeze so the page can pass the bar;

THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes and v2.15 ingest date/version/type-lanes remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure deploy, G2 PASS, Protocol v2.14, LLM, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–8, `publish()` PASS, Blob, managed identity, app settings.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (a messy review page biases assessment). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of one door **Beoordeel**, two named stacks with counts, compact source-text rows, stamps on recommendation, extract heading-proposal exclusion for DOEN/OVERWEEG/NIET DOEN, tiny-object suppression, or a new extract of unpublished Continentie remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 12. Gates and approval effect

Approval of v2.16 establishes that the Review page MUST convince guideline researchers (if it does not suffice, the project has failed even if the kernel is fail-closed), that two frustrations MUST NOT remain (unclear: two doors, rows split across the page, DOEN/OVERWEEG without explanation; too-small objects: one word, one number, half a sentence), that within one screen the researcher MUST know which document this is, what to do now, and why (this becomes what an EPD may say), that UI copy MUST be researcher language, that the primary action MUST be visually obvious, that kernel ids MUST NOT be the row title, that there MUST be one door **Beoordeel** (MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists), that there MUST be two named stacks with counts (**Koppen** = real freeze TOC / section titles, batch-confirm as structure, never as advice, headings MUST NOT be served as handelingsadvies; **Inhoud** = definition, explanation, condition, exception, recommendation, and unclassified until typed, one-object card, high-risk four-eyes unchanged), that MUST NOT present a page of thousands of identical `unclassified` titles, that there MUST NOT be a researcher control “zwaar/licht”, that each list row MUST be one compact line (freeze source sentence or real heading text plus a short status; MUST NOT stretch status / checkbox / text into disconnected columns; MUST NOT use the type name or a kernel document id as the title), that DOEN / OVERWEEG / NIET DOEN are stamps not objects (V&VN recommendation-strength language; MUST NOT invent GRADE jargon; MUST NOT add a new object type; MUST NOT be rows in Koppen; MUST NOT be standalone knowledge objects; preferred lock: stamp on the following recommendation; review card shows one researcher sentence; closed values on type `recommendation` only: `doen` | `overweeg` | `niet_doen`; NOT fusion of condition into recommendation; human confirms strength together with the advice sentence; extract MUST NOT propose `heading` for those words even if the freeze wraps them in heading tags), and that extract MUST NOT emit tiny objects (only a list number, only a strength stamp, or a sentence fragment that cannot stand as one meaning unit; a lone trailing word of a previous sentence is forbidden; freeze source bytes and SHA-256 stay; existing published objects are not silently rewritten; Continentie is unpublished so a new extract of the same freeze bytes is REQUIRED; source hash stays; unpublished object identities MAY be replaced by that new extract; MUST NOT lie in the UI by hiding stored fragments without a new extract). Serving / G2 unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged; G2 remains the publication blocker. It does not:

- implement console Python, extract, kernel, Product API, or `publish()`;
- convert G2 to PASS;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- skip durable immutable storage;
- staff named reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- let Koppen heading accept bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type;
- auto-promote ordinary text to `recommendation`;
- add page, paragraph, stamp, strength or GRADE as stored object types;
- invent GRADE English labels on this screen;
- keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- present a page of thousands of identical `unclassified` titles, or use the type name (`unclassified`) or a kernel document id as the review-list row title;
- stretch status / checkbox / text into disconnected columns across the viewport;
- treat DOEN/OVERWEEG/NIET DOEN as Koppen rows or standalone knowledge objects;
- propose `heading` for DOEN/OVERWEEG/NIET DOEN even if the freeze wraps them in heading tags;
- emit number-only, stamp-only, or truncated-sentence objects;
- fuse condition into recommendation, or reopen that Protocol v2.13 forbid;
- lie in the UI by hiding stored fragments without a new extract;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules beyond forbidding tiny objects that cannot stand as one meaning unit;
- reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except the heading-proposal and stamp rules superseded here;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor;
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–8;
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
- authorize a mockup, Azure, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
