# V&VN Data Services Protocol v2.15 — Ingest Source Date, Source Version, and Type-Based Review Lanes

**Status:** Approved for project use  
**Protocol delta version:** 2.15.0  
**Approval date:** 2026-09-01  
**Approved by:** Project owner  
**Extends:** Protocol v2.13.0  
**Highest change class:** C3 spanning ingest provenance validation (source date / source version / type-based review lanes)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.15 records the owner-approved lock of 2026-09-01 (William Gomes) after an audit against the live baseline Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0 on `main`, plus live review-list evidence the same day: one richtlijn shows 4000+ knowledge objects whose visible rows (4924–4942) are identical purple link text `unclassified` with subtitle «Nog niet geclassificeerd · wacht op beoordeling» and no source snippet. That is not an acceptable researcher task. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem is herleidbare ingest-provenance of the freeze (source date and source version on ingest page 1) and two-speed review routed by object type, not by a researcher speed switch.

Live baseline on `main` before this delta is Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0 and this delta jointly form normative baseline v2.15.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, G2, Azure, LLM, or Protocol v2.14 time/lifecycle. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page or paragraph. Paragraph is display context, not a stored blob, not a new type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules, all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules, all Protocol v2.12 type/review/projection rules, and all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules remain in force, except the ingest-date, ingest-version, review-lane and next-implementation readings superseded in sections 3–6 and 8. This protocol-only change does not implement ingest UI, version validation, review queues, kernel, console Python, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that the ingest date field MAY be a free-text box, that the date MAY default to today or to the ingest-click timestamp, that display locale MAY leak into stored bytes, that the ingest version field MAY be free text, that a year MAY be a version, that researchers MAY be given a separate “zwaar/licht” or “snel/langzaam” control, that extract MAY auto-promote ordinary text to `recommendation`, that extract MAY leave real source headings as `unclassified`, that the review list MAY use the type name (`unclassified`) as the row title, that four thousand unclassified cards on one richtlijn MAY be accepted as workload, or that the next console implementation after the 2026-08-29 lock remains only the two-column review card (that card is already in code). Where this delta and those readings conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. The 2026-08-29 lock set the next console implementation as only the two-column review card. That card is now in code. Where this delta and that 2026-08-29 sequencing sentence conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console (ingest date calendar + ISO store + required; ingest version dotted-integer validation + required; extract MUST propose `heading` for real source headings so they do not all land as `unclassified`; review list MUST show a source-passage snippet, not the type name as title; review queues/UI routed by type with fast-lane batch-confirm of proposed headings). THEN G2/Azure remains the publication blocker. Do not start Azure in this change. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection and v2.13 atomic objects/relations/four-eyes remain required law.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12 and v2.13 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel and the two-column review card now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

## 3. Ingest page 1 — source date

The ingest date field MUST be a calendar date picker, not a free-text box.

- On screen the researcher MUST see and choose Europe/Amsterdam calendar order `DD-MM-YYYY`.
- Internally the kernel/store/API/hash envelope MUST persist the same day as ISO `YYYY-MM-DD` (no time, no timezone).
- The date MUST be the date printed on the freeze (colofon / publicatiedatum).
- The date MUST NOT default to today.
- The date MUST NOT be the ingest-click timestamp.
- Empty MUST NOT be accepted at ingest. No date = no herleidbare bron.
- Display locale MUST NOT leak into stored bytes. An EPD MUST receive ISO. `01-02-2026` on screen is 1 February 2026, stored `2026-02-01`.

The stored value is a calendar day of the freeze, not a datetime, not a timezone offset, and not the moment the researcher clicked ingest.

## 4. Ingest page 1 — source version

The version field MUST NOT be free text.

- Allowed pattern: one or more non-negative integers separated by dots. Regex conceptually `^[0-9]+(\.[0-9]+)*$`.
- Examples that MUST be accepted: `1`, `1.0`, `2.13`, `1.2.3`.
- MUST reject: `v` prefix, letters, comma, trailing/leading dot, `-beta` / `-rc`, spaces, jaartal-as-version (`2024`). A year belongs in the calendar field, not version.
- Empty MUST NOT be accepted at ingest.
- The machine validates; the researcher fills. No extra UI control for “zwaar/licht” on this field.

## 5. These two fields are freeze source metadata

The ingest date and ingest version are document/source metadata of the freeze being ingested. They are not knowledge-object `object_version` and not Protocol v2.14 `valid_from` / `valid_until`. Operators MUST NOT fuse them into recommendation condition fields. Filling them is not publication. Capture remains not publication.

- Ingest date/version MUST NOT be treated as `object_version`.
- Ingest date/version MUST NOT be treated as serving bounds.
- Ingest date/version MUST NOT be written as Protocol v2.14.
- Filling ingest date/version MUST NOT authorize `publish()`.

## 6. Two-speed review (lane from type, not a switch)

Researchers must not word-by-word re-review structural crumbs. Ingest hashes, bytes, SHA-256, locators, and object identity MUST stay intact. Extract MUST NOT auto-promote ordinary text to `recommendation`. Owner evidence 2026-09-01: a live review list on one richtlijn shows 4000+ objects; visible rows 4924–4942 are identical (`unclassified` as the purple link title; subtitle «Nog niet geclassificeerd · wacht op beoordeling»; no source snippet). That surface is a fail of this delta, not a workload to accept.

- There MUST NOT be a separate researcher control “zwaar/licht” or “snel/langzaam”.
- Confirmed (or, for queue routing only, proposed) `object_type` determines the review lane.
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`. Protocol v2.12 already allows a heading to become `object_type` `heading`; this delta makes that proposal a review-lane prerequisite. Everything that is not a real heading MUST still start `unclassified` and therefore slow until a human confirms a content type.
- Fast lane: proposed or confirmed `heading` (real source headings / TOC / structural crumbs). Fast lane MUST support batch-confirm of proposed headings as structure, not advice, so a researcher does not open 4000 cards. Headings MUST NOT be served as handelingsadvies.
- Slow lane: `definition`, `explanation`, `condition`, `exception`, `recommendation`, and `unclassified` until a human confirms a type. Slow lane stays one-object (type + relations + high-risk four-eyes).
- The review list MUST NOT use the type name (`unclassified`) as the row title. Each row MUST show a source-passage snippet (the freeze text of that object) so a researcher can see what they are looking at. The numeric object id MAY remain secondary.
- Four thousand unclassified cards on one richtlijn is a fail of this delta's review surface, not a workload to accept. MUST NOT fix that by inventing page/paragraph types. MUST NOT silently re-split existing ingested objects in this protocol. Identity of already-hashed objects stays. New ingest after heading-proposal is fine; this protocol MUST NOT re-extract existing Continentie bytes.
- A human MUST be able to reclassify: a heading that is actually advice (“Overweeg verwijzing…”) becomes `recommendation` and MUST then be slow. Demotion to fast MUST only happen by confirming type `heading`, never by a speed toggle.
- Machine classification remains a proposal, never published truth (Protocol v2.12 / v2.13 unchanged).
- High-risk four-eyes law is unchanged: `exception`, high `risk_level`, and listed high-risk fields still require a second named reviewer. Fast-lane heading accept MUST NOT bypass four-eyes if the object is actually high-risk or is reclassified onto a high-risk type.
- The machine MUST NOT decide that something is “light enough to serve”. Serving still requires the Protocol v2.12 tuple + published projection + G2 locator. This delta does not make G2 PASS and does not implement `publish()`.
- MUST NOT add new object types for page/paragraph. Paragraph is display context, not a stored blob, not a new type.

This delta states that heading versus content drives the review lane. It MUST NOT rewrite Protocol v2.13 split rules. Token-budget chunking still MUST NOT define object identity. Fusion of condition into recommendation remains the forbidden default. It MUST NOT silently re-split already-hashed objects.

## 7. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement ingest, extract, review queues, API or console changes. This delta does not implement the new UI.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No Openen-versus-Reviewen extra door. No huisstyle bar-thickness change.

## 8. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before ingest requires a calendar date stored as ISO, ingest requires a dotted-integer version, extract proposes `heading` for real source headings, the review list shows a source-passage snippet, and review queues/UI route by type with fast-lane batch-confirm.

Where this delta and the 2026-08-29 lock conflict on which implementation is next, this delta governs. The two-column review card is already in code. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console:

1. ingest date calendar + ISO store + required;
2. ingest version dotted-integer validation + required;
3. extract MUST propose `heading` for real source headings / TOC / structural crumbs (review-lane prerequisite; not a v2.13 split-rule rewrite; MUST NOT re-extract existing Continentie bytes);
4. review list MUST show a source-passage snippet as the row title, MUST NOT use the type name (`unclassified`) as the title;
5. review queues/UI routed by type (fast heading vs slow content), no speed toggle; fast lane MUST support batch-confirm of proposed headings as structure; slow lane stays one-object;

THEN G2/Azure remains the publication blocker. Do not start Azure in this change. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection and v2.13 atomic objects/relations/four-eyes remain required law. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure, Blob, managed identity, `publish()` PASS, Protocol v2.14, Vercel/Neon, LLM, Openen-versus-Reviewen extra door, huisstyle bar thickness, changing the extract split algorithm beyond stating that heading versus content drives the lane, silently re-splitting already-hashed Continentie objects.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning ingest provenance validation** (source date, source version, type-based review lanes / retrieve-safety). This is not a C5 reopen of four-eyes or publish authorization. Treat the highest class as **C3 spanning ingest provenance validation**. This delta does not reopen GD-03.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of ingest date calendar + ISO store, ingest version dotted-integer validation, heading proposal as a review-lane prerequisite, review-list source-passage snippets, or type-routed review queues with fast-lane batch-confirm remains separately classified, including at least C3 spanning ingest provenance validation.

## 10. Gates and approval effect

Approval of v2.15 establishes that ingest page 1 requires a calendar source date (Europe/Amsterdam `DD-MM-YYYY` on screen; ISO `YYYY-MM-DD` in the kernel/store/API/hash envelope; colofon / publicatiedatum; not today; not ingest-click; empty rejected), that ingest page 1 requires a dotted-integer source version (`^[0-9]+(\.[0-9]+)*$`; empty rejected; no `v` prefix, letters, comma, leading/trailing dot, `-beta`/`-rc`, spaces, or year-as-version), that those two fields are freeze source metadata and not `object_version` and not v2.14 `valid_from`/`valid_until`, and that review lane follows confirmed (or, for queue routing only, proposed) `object_type` (fast `heading` versus slow content; extract MUST propose `heading` for real source headings so they do not all land as `unclassified`; the review list MUST show a source-passage snippet and MUST NOT use the type name as the row title; fast lane MUST support batch-confirm of proposed headings as structure; slow lane stays one-object; four thousand unclassified cards on one richtlijn is a fail of this review surface; no researcher speed toggle; extract MUST NOT auto-promote ordinary text to `recommendation`; four-eyes unchanged). It does not:

- implement ingest UI, date picker, ISO persist, version validation, review queues, extract, kernel, console Python, Product API, or `publish()`;
- convert G2 to PASS;
- skip durable immutable storage;
- staff named reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- fuse ingest date/version into recommendation condition fields, or treat filling them as publication;
- treat ingest date/version as knowledge-object `object_version`;
- let display locale leak into stored bytes;
- accept an empty ingest date or empty ingest version;
- default the ingest date to today or to the ingest-click timestamp;
- accept free-text date or free-text version;
- accept `v` prefix, letters, comma, leading/trailing dot, `-beta`/`-rc`, spaces, or jaartal-as-version as source version;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- let fast-lane heading accept bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type;
- auto-promote ordinary text to `recommendation`;
- add page or paragraph as stored object types;
- accept four thousand unclassified cards on one richtlijn as workload, or use the type name (`unclassified`) as the review-list row title;
- silently re-split already-hashed Continentie objects, or re-extract existing Continentie bytes;
- rewrite Protocol v2.13 split rules;
- reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor;
- implement Blob, managed identity, or an Openen-versus-Reviewen extra door;
- change huisstyle bar thickness;
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
- authorize a mockup, Azure, Vercel or Neon as the next implementation.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
