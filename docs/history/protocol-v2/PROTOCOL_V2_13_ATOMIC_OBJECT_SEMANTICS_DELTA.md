# V&VN Data Services Protocol v2.13 — Atomic Object Semantics, Classification Rules, Closed Relations, and High-Risk Four-Eyes

**Status:** Approved for project use  
**Protocol delta version:** 2.13.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.12.0  
**Highest change class:** C3 (retrieve-safety / answerability / knowledge model) spanning C5 (high-risk four-eyes review/publish authorization)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.13 records the owner-approved lock of 2026-08-28 after an audit against the live baseline Protocol v2.12.0 plus Protocol v2.11.0 on `main`. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem is atomic object identity, per-type classification, closed relations, and high-risk four-eyes authorization.

Live baseline on `main` before this delta is Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0 and this delta jointly form normative baseline v2.13.0. The v2.12 closed serving typeset is UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. Historical schema enums (`document`, `section`, `score_rule`, `decision`, `action`, `out_of_scope`, `supersession`, `table`, `background`, `patient_information`, and any other non-serving enum) are not a licence to serve those types. Protocol v2.12 already said this; this delta makes `docs/extraction_rules_v0.1.md` yield.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules, all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules, and all Protocol v2.12 type/review/projection rules remain in force, except the extraction-size, fusion, classification-rule, relation, and high-risk readings superseded in sections 3–7 and 10. This protocol-only change does not implement extract, relations, console “open original”, schema, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that token-budget chunking defines object identity, that a recommendation MAY contain its condition as undifferentiated text in the same object when those can be separate objects linked by relations, that fusion of condition into recommendation is the default, that machine classification is published type, that schema v1.2 relation names are serving law, that unconfirmed relations bind serving, that envelope `review_passes` or a single reviewer authorizes high-risk publish, or that `docs/extraction_rules_v0.1.md` remains serving taxonomy. Where this delta and those readings conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.12 §10 set the next implementation as unclassified default, proposal/confirm, answerability × type, object-tuple review binding and atomic published projection. That kernel work is now in code. Where this delta and Protocol v2.12 §10 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel (atomic split, closed relations, per-type confirm, high-risk four-eyes, open-original). THEN G2/Azure. Do not start Azure in this change. The v2.10 console follow-up is already in code (including PR #31 UI spelling Documentenhiërarchie) and MUST NOT be reopened by this delta. v2.11 freeze/locator and v2.12 type/projection remain required law.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11 and v2.12 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock and the v2.12 kernel now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.12.0 remains mandatory, except the extraction-size, fusion, classification-rule, relation and high-risk readings superseded here, including:

- Extraction MUST determine structure and provenance only, NOT the meaning of a passage;
- A heading MAY become object_type `heading`; everything that is not a heading MUST default to `unclassified`;
- The machine MAY propose a type; a human reviewer MUST confirm the definitive `object_type` before publication; an unconfirmed proposal MUST NOT be treated as published type;
- Operators MUST NOT invent types in the MVP; `unclassified` is the default, not a sixth advice type;
- Answerability MUST join question type × object type; only `recommendation` MAY return as action advice (`handelingsadvies`); other types MUST NOT receive advice-weight; `unclassified` MUST NOT be `supported`;
- Cutover/publish MUST NOT trust envelope `review_passes` alone; the minimum binding remains `object_id` + `object_version` + `canonical_object_hash` + `confirmed_object_type` + `reviewer` + `decision`;
- Serving MUST use a validated published projection; publish, withdraw and supersede MUST replace that projection atomically; the API MUST NOT reconstruct live governance per query.

## 3. Architecture principle

One knowledge object MUST be one confirmable meaning. Context MUST live in reviewed relations, not in a blob.

The canonical store MUST be the only source of truth. Retrieval index, embeddings and projections MUST be derived and disposable. Operators MUST NOT reverse that direction: a retrieval index, embedding or projection MUST NOT become the source of truth.

## 4. Atomic objects

A knowledge object MUST be one confirmable meaning unit: small enough that a reviewer can confirm `object_type` and relations on one screen; large enough that splitting would break a single grammatical claim.

- Extraction MUST split at meaning boundaries, not token budgets.
- Token-budget chunking (including the 300–700 / 1000-token guidance in `docs/extraction_rules_v0.1.md`) MUST NOT define object identity.
- A recommendation MUST NOT contain its condition, exception, negation, or qualifier as undifferentiated text in the same object when those can be separate objects linked by relations.
- Fusion of condition into recommendation is the default FORBIDDEN pattern. The only exception: MUST NOT split when splitting would break a single grammatical claim (the sentence is the claim).
- `parent`/`child` is structural (heading tree). It MUST NOT be used to dump siblings into one blob.
- A new object version is required when bytes, extract, confirmed type, or confirmed relations change. Metadata-only changes MUST NOT silently reuse a reviewed semantic version. This delta states that distinction; it MUST NOT be read as a four-track versioning product.

## 5. Per-type classification rules

Machine classification is a proposal, never truth. `unclassified` remains the default until a human confirms a type from the closed set on that exact object version. Unconfirmed proposals MUST NOT be published type and MUST NOT be `supported`.

From every knowledge object the reviewer MUST be able to open the exact source passage. Type confirmation without that flow is not acceptable. Source locators remain Protocol v2.11 law; this delta MUST NOT invent a locator scheme. Implementation of that open-original flow belongs in the v2.13 kernel follow-up, not in this protocol change.

For each type the following is law: what it means, which source passages belong, what does not belong, and which ambiguities ALWAYS require human judgement.

### heading

- Means: a source heading that structures the document. Structural, not advice.
- In: actual headings from the freeze/PDF outline.
- Out: a bold sentence that is running text; a recommendation phrased as a title; a definition lemma used as body text.
- Human always: heading vs recommendation when an H2 is itself an instruction (“Overweeg verwijzing …”).
- MUST NOT answer as advice, definition or explanation. MUST NOT be `supported` as those.

### definition

- Means: names or delimits a term.
- In: “onder X wordt verstaan”, “X is gedefinieerd als”, glossary entries.
- Out: “X is geïndiceerd” (recommendation); mechanism “X treedt op wanneer” when that is explanation; action-triggering diagnostic criteria (condition or recommendation, human).
- Human always: “X is …” sentences; operational definitions that also instruct.
- MAY be `supported` for a definition question. MUST NOT receive advice-weight.

### explanation

- Means: rationale, mechanism, or background without instructing action.
- In: why, how, non-action evidence summary.
- Out: “daarom moet de verpleegkundige …” (recommendation); applicability limits (condition).
- Human always: mixed “omdat … daarom doen” sentences.
- MAY be `supported` for an explanation question. MUST NOT receive advice-weight.

### condition

- Means: an applicability constraint, not the action itself.
- In: population, setting, if/when, thresholds that gate advice.
- Out: the advice itself; carve-outs (exception); the definition of a population term.
- Human always: “bij X doen Y” as one sentence; numeric thresholds; score items. There is NO `score_rule` serving type in MVP; a score item stays `unclassified` until a human confirms `condition` (or another closed type).
- MAY bound advice only via confirmed `applies_if`. MUST NOT receive advice-weight.

### exception

- Means: a carve-out from a recommendation or condition.
- In: tenzij, niet bij, contra-indication relative to a parent claim.
- Out: a standalone negative instruction (“doe X niet” may be recommendation, human).
- Human always: negation vs exception vs negative recommendation.
- MAY bound advice only via confirmed `except_if`. MUST NOT receive advice-weight.
- ALWAYS high-risk (four-eyes).

### recommendation

- Means: action advice (`handelingsadvies`).
- In: aanbevolen, dient te, moet, overweeg (weak recommendation is still recommendation), forbidden acts as negative recommendation.
- Out: definitions, background, headings, unclassified text.
- Human always: “kan overwogen worden”; “is gebruikelijk”; mixed sentences.
- ONLY type that MAY return as action advice. Other types MUST NOT receive advice-weight.
- High-risk when `risk_level` is high or any high-risk field in section 7 is present.

### unclassified

- Default until human confirmation.
- MUST NOT be served as action advice.
- MUST NOT be treated as a published type.
- MUST NOT be `supported`.

Ambiguities that ALWAYS require human confirmation (not only the per-type list): mixed sentences; negations; tables/figures (do not auto-type; leave unclassified); any score/threshold/dose/age boundary.

Until the first table-heavy official source exists, tables and figures MUST remain `unclassified`. Operators MUST NOT auto-type them. Operators MUST NOT extend the closed typeset to add `table` or `figure` as serving types. A later thin lock (canonical representation + review) MAY follow after that source exists; that lock is not this delta.

## 6. Closed relations

MVP closed relation set (operators MUST NOT invent relation types; adding one is a protocol change):

- `applies_if` — source (typically recommendation or explanation) applies if target condition holds
- `except_if` — source does not apply if target exception holds
- `defines` — source is defined by target definition
- `explains` — source is explained by target explanation
- `supported_by` — source claim is backed by target object (object graph only; this is NOT Product API `supported`)
- `supersedes` — source replaces target at object level (alongside existing withdraw/supersede projection rules)
- `parent` / `child` — structural heading tree

Serving-law names are `parent` and `child`. Schema v1.2 `child_of` is the later implementation mapping; this protocol change MUST NOT edit the schema. `parent`/`child` is equivalent to `child_of` / parent; implementation later aligns the schema name.

Schema v1.2 names (`conditioned_by`, `exception_to`, `supports`, `child_of`, `supersedes`, `superseded_by`) are not the serving law. This delta is the serving law. Implementation later aligns the schema. Unconfirmed relations MUST NOT be treated as binding.

Relations MUST be confirmed by a reviewer on the exact object version, bound with the same publish tuple as Protocol v2.12 (`object_id` + `object_version` + `canonical_object_hash` + `confirmed_object_type` + reviewer + decision). A changed confirmed relation set MUST invalidate prior publish authorization for that object (hash/version change as in Protocol v2.12).

Context preservation: a published recommendation MUST be served together with its published `applies_if` / `except_if` targets when those exist in the published projection. Serving the recommendation without those bounds is a protocol failure. Operators MUST NOT fuse objects to preserve context; relations preserve context.

Answerability remains question type × object type (Protocol v2.12). Relations bound advice; they MUST NOT give advice-weight to `condition`, `exception`, `explanation`, `definition` or `heading`.

## 7. High-risk four-eyes

Independence rule unchanged: uploader MUST NOT be the only required reviewer. AI / Grok Bot / Metis / Implementation engineer / Auditor MUST NOT count as required reviewers, MUST NOT approve, MUST NOT publish.

Four-eyes (second named reviewer on the exact object tuple) MUST be required when any of:

- confirmed type is `exception`;
- `risk_level` is high;
- any of these risk fields is present: `age_boundary`, `dosage`, `unit`, `score_points`, `score_threshold`, `operator`, `contraindication`, `exception`, `escalation_decision`;
- confirmed type is `recommendation` AND any of the above fields is present.

Why: a wrong dose, age boundary, score threshold, contraindication or exception served as (or bounding) advice is patient-harm. This is why four-eyes is authorization (C5) as well as retrieve-safety (C3).

Envelope `review_passes` still MUST NOT authorize publish. High-risk four-eyes does not replace the Protocol v2.12 tuple; it is an additional required reviewer on that tuple.

G2 still blocks actual `publish()`. This delta specifies the authorization contract any future publish path MUST check.

## 8. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement extract, relations, API or console changes. This delta does not implement the new UI.

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

## 9. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the kernel splits at meaning boundaries, confirms type from the closed set, binds closed relations on the object tuple, requires high-risk four-eyes, and lets a reviewer open the exact source passage.

Where this delta and Protocol v2.12 §10 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel:

- atomic split;
- closed relations;
- per-type confirm;
- high-risk four-eyes;
- open-original (v2.11 locators; reviewer MUST open the exact source passage);

THEN G2/Azure. Do not start Azure in this change. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS).

v2.11 freeze/locator and v2.12 type/projection remain required law. The v2.10 console follow-up is already in code (including PR #31 UI spelling Documentenhiërarchie); this delta MUST NOT reopen it.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as the next protocol, not this file. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 10. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3** (retrieve-safety / answerability / knowledge model). C5 applies as high-risk four-eyes review/publish authorization. Treat the highest class as **C3 (retrieve-safety / answerability / knowledge model) spanning C5 (high-risk four-eyes review/publish authorization)**. This delta does not reopen GD-03.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). Retrospective C5 review of the four-eyes authorization sentences remains due with that same clinical/technical pair; this delta does not invent a separate named C5 staff.

Any later implementation of atomic split, closed relations, per-type confirm, high-risk four-eyes, or open-original remains separately classified, including at least C3 spanning C5.

## 11. Gates and approval effect

Approval of v2.13 establishes atomic objects as one confirmable meaning unit, per-type classification rules on the unchanged v2.12 closed serving typeset, the closed relation set, high-risk four-eyes as additional required reviewer on the v2.12 tuple, the architecture principle (canonical store as only source of truth; derived indexes disposable), and that `docs/extraction_rules_v0.1.md` yields for serving taxonomy, object size/chunking, and fusion of condition into recommendation. It does not:

- implement extract, relations, console “open original”, schema, Product API, or `publish()`;
- convert G2 to PASS;
- skip durable immutable storage;
- staff named reviewers;
- dump the rest of the 2026-08-28 catalog into law (source registry entity, `valid_from`/`valid_until` productization, release-id/rollback, schema migration, holdouts, IAM/secrets/DR/SLA/retention/cost);
- write Protocol v2.14;
- extend the closed serving typeset, or auto-type tables/figures;
- invent a locator scheme, or reopen Protocol v2.11 locators;
- treat schema v1.2 relation names as serving law, or treat unconfirmed relations as binding;
- fuse objects to preserve context;
- let token-budget chunking define object identity;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to condition, exception, explanation, definition or heading;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor;
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
