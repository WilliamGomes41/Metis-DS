# V&VN Data Services Protocol v2.12 — Object Type, Review Binding, and Published Projection

**Status:** Approved for project use  
**Protocol delta version:** 2.12.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.10.0  
**Highest change class:** C3 (retrieve-safety / answerability) spanning C5 (review/publish authorization binding)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.12 records the owner-approved lock of 2026-08-28. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem is semantic classification and the hard binding of review, publication and serving.

Live baseline on `main` before this delta is Protocol v2.10.0 (v2.9 UX is in code). Protocol v2.11 (HTML freeze/locator) remains an OPEN lock in PR #27 and is not live baseline. This delta MUST NOT treat PR #27 as a substitute for this semantic delta. This delta MUST NOT merge, edit or close PR #27. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS).

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0 and this delta jointly form normative baseline v2.12.0. All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules, all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules, and all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules remain in force, except the sequencing and retrieve/publish readings superseded in sections 3–7 and 10. This protocol-only change does not implement extract, API or console changes. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that extraction assigns object meaning, that only `recommendation` MAY be `supported`, that envelope `review_passes` alone authorizes cutover/publish, or that the Product API MAY reconstruct live governance per query. Where this delta and those readings conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.10 §8 set the next implementation as a console follow-up (Documentenhierarchie, waiting-task badges, Accounts). That console follow-up remains required and is not skipped. Where this delta and Protocol v2.10 §8 conflict on which implementation is next, this delta governs. PR #27 remains the v2.11 URL-HTML lock; it is not this file and is not live baseline.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9 and v2.10 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. Every rule in Protocol v2.6.0 remains mandatory, including:

- four rooms that are not four buttons for one person: ingest (mailbox), review (mandatory return loop; the uploader MAY also be a reviewer and MUST NOT be the only required reviewer), publish (a separate authorized act), analytics last;
- identity (researcher, reviewer, publisher); no shared login for review or publish; internal identity, not public signup;
- chat is not a room in this console;
- a care-app frontend, a chatbot as a product surface, an EPD/ECD UI and a public website MUST NOT live in this repository;
- engineers MUST NOT submit sources through the ingest room.

Every rule in Protocol v2.7.0 remains mandatory, including:

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

## 3. Extraction determines structure and provenance only

Extraction MUST determine structure and provenance only, NOT the meaning of a passage.

- A heading MAY become object_type `heading`.
- Everything that is not a heading MUST default to `unclassified`.
- The machine MAY propose a type.
- A human reviewer MUST confirm the definitive `object_type` before publication.
- An unconfirmed proposal MUST NOT be treated as published type.

Extraction MAY record headings, hierarchy, locators, hashes and source fragments. Extraction MUST NOT treat a machine proposal as canonical meaning. `unclassified` is the ingest/review default until a human confirms a type from the closed set in section 4. A confirmed type is bound to that exact object version; a new object version MUST re-open type confirmation.

## 4. Closed object-type set

The minimum closed object-type set is:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

Operators MUST NOT invent types in the MVP. `unclassified` is the default, not a sixth advice type.

- `unclassified` MUST NOT be served as action advice (`handelingsadvies`).
- `unclassified` MUST NOT be treated as a published type.
- A heading is structural. It is not advice.
- `recommendation` is the only type that MAY return as action advice.
- Adding a new object type is a new protocol change, not an operator choice.

Existing schema enums that list other historical types are not a licence to invent MVP serving types. The closed set above is the MVP serving taxonomy once a type is confirmed.

## 5. Answerability joins question type × object type

Answerability MUST join question type × object type. MUST NOT be "only recommendations are supported". MUST be: supported when the available, reviewed object type is suitable for the claimed question.

- Only `recommendation` MAY return as action advice (`handelingsadvies`).
- Other types MAY be supported when they fit the question: a `definition` MAY answer a definition question; `explanation` MAY support explanation; `condition` and `exception` MAY bound advice.
- Those other types MUST NOT receive advice-weight.
- A heading MUST NOT answer as advice, definition or explanation.
- `unclassified` MUST NOT be `supported`.
- An unconfirmed proposal MUST NOT be `supported`.
- A podcast/article still cannot fill a missing guideline (v2.8 class axis unchanged).

Class/weight remains on each object as in Protocol v2.8. Object type is a second axis of answerability, not a replacement of class. Heavier class MUST NOT be filled by lighter class. A matching object type on a lighter class MUST NOT fill a missing heavier class.

A `supported` result still MUST carry V and VN labels. DS MUST NOT generate prose. No LLM in the MVP. Unpublished branch objects MUST still abstain even if the trunk is published.

## 6. Publish binding is the object tuple, not an envelope tick

Cutover/publish MUST NOT trust envelope `review_passes` alone. The minimum binding of published content is:

`object_id` + `object_version` + `canonical_object_hash` + `confirmed_object_type` + `reviewer` + `decision`

Independence rule unchanged (uploader MUST NOT be the only required reviewer). High-risk still needs the required review track. Future `publish()` (still G2-blocked) MUST check this tuple, not an envelope tick.

- Review MUST be bound to that exact object version and that exact `canonical_object_hash`.
- A changed hash, version or confirmed type MUST invalidate a prior publish authorization for that object.
- An envelope-level tick, a captured freeze, or a room badge MUST NOT substitute for the tuple.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

This delta does not implement `publish()`. G2 still blocks actual publish. The tuple is the authorization contract that any future publish path MUST check.

## 7. Serving uses a validated published projection

The Product API remains a derived read-only layer. Serving MUST use a validated published projection. Publish, withdraw and supersede MUST replace that projection atomically. The API MUST read only the current published projection. It MUST NOT reconstruct live governance per query. A stale projection after withdraw is a protocol failure. Capture is not publication.

G2 still blocks actual publish; this delta specifies how serving MUST work once a publish path exists, and MUST apply to any fixture/real projection already in the API.

- A withdrawn or superseded object MUST disappear from the current published projection in the same atomic replace that records the withdraw or supersede.
- Reconstructing review state, envelope `review_passes`, or unpublished objects at query time MUST NOT produce `supported`.
- A fixture projection already served by the API is in scope of this serving rule: it MUST behave as a published projection, not as live governance.
- This does not convert G2 to PASS. Publication remains BLOCKED without an immutable locator, as in existing G2 rules.

## 8. v2.11 URL-HTML lock remains in open PR #27

Ingest URL-HTML remains the v2.11 lock (PR #27, not this file): live URL-HTML MUST NOT be a publishable source; uploaded freeze-HTML MAY; PDF via URL MAY if exact received bytes are stored and hashed immediately.

v2.12 MUST NOT treat #27 as a substitute for this semantic delta. Do not duplicate v2.11 as if it were already on main. Protocol v2.11 is not live baseline. Point to the open PR / the locked rule without claiming v2.11 is live baseline.

This delta MUST NOT implement locators, freeze storage, ingest rejection, Azure Blob, or any G2 claim. Azure/G2 MUST stay out of this delta.

## 9. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement extract, API or console changes. This delta does not implement the new UI.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS.

## 10. Build order

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the kernel defaults non-headings to `unclassified`, binds review to the object tuple, joins answerability to question type × object type, and serves only an atomically replaced published projection.

The next implementation after this protocol (not this PR) MUST be the Implementation engineer on the existing kernel:

- object taxonomy default `unclassified` + proposal/confirm;
- answerability × type;
- review bound to exact object version + hash;
- atomic published projection and correct withdrawal/supersede;

THEN G2/Azure. Do not start Azure in this change. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS).

This protocol-only change does not implement extract/API/console changes. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

That follow-up MUST NOT invent Azure, Vercel or Neon as in-scope. MUST NOT treat an unconfirmed proposal as published type. MUST NOT serve `unclassified` as `supported`. MUST NOT give advice-weight to definition, explanation, condition, exception or heading. MUST NOT trust envelope `review_passes` alone. MUST NOT reconstruct live governance per query. MUST NOT leave a stale projection after withdraw. MUST NOT add chat as a room. MUST NOT design for nurses.

The Documentenhierarchie / waiting-task badge / Accounts console follow-up from Protocol v2.10 remains required and is not skipped; it is not the next implementation after this delta. The v2.11 HTML freeze/locator lock remains in open PR #27; it is not this file, is not live baseline, and MUST NOT be merged, edited or closed by this protocol change.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3** (retrieve-safety / answerability). C5 applies only as review/publish authorization binding. Treat the highest class as **C3 (retrieve-safety / answerability) spanning C5 (review/publish authorization binding)**. This delta does not reopen GD-03.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). Retrospective C5 review of the publish-authorization-binding sentences remains due with that same clinical/technical pair; this delta does not invent a separate named C5 staff. Named reviewers are not staffed.

Any later implementation of unclassified default, proposal/confirm, answerability × type, object-tuple review binding, or atomic published projection remains separately classified, including at least C3 spanning C5.

## 12. Gates and approval effect

Approval of v2.12 establishes extraction as structure/provenance only, the closed object-type set with `unclassified` default, answerability as question type × object type, publish binding to the object tuple, and serving from an atomically replaced published projection. It does not:

- implement extract, taxonomy, proposal/confirm, answerability, review-binding, projection, Product API, console or any other product code;
- redesign the four layers (source/evidence → canonical knowledge → governance → product);
- treat an unconfirmed proposal as published type, or serve `unclassified` as `supported`;
- treat only recommendations as supported, or give advice-weight to non-recommendation types;
- trust envelope `review_passes` alone, or reconstruct live governance per query;
- leave a stale projection after withdraw or supersede;
- treat capture as publication, or convert G2 to PASS;
- implement locators, freeze storage, ingest rejection, Azure Blob, or any G2 claim;
- treat PR #27 / Protocol v2.11 as live baseline, or duplicate v2.11 as if it were already on main;
- merge, edit or close PR #27;
- skip durable immutable storage;
- authorize a mockup, Azure, Vercel or Neon as the next implementation;
- select an identity vendor, provision Azure AD, or convert G0 Azure DEV, G7 or G8 to PASS;
- introduce Vercel, Neon or an LLM vendor;
- publish a source or knowledge object;
- authorize an external consumer or onboard the first paying subscriber;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- design the console for nurses;
- replace ingest, review or publish with Accounts, or treat Accounts as a fifth clinical room;
- open the role set or allow operators to invent new role types or object types;
- allow open registration or shared login;
- let AI, Grok Bot, Metis, the Implementation engineer or the Auditor be created as required reviewers;
- let the uploader be the only required reviewer;
- require clinical re-review for a family move;
- waive review when promoting class;
- let a podcast/article fill a missing guideline;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- pirate fonts or commit unlicensed font files;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
