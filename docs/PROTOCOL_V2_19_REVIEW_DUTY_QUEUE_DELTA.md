# V&VN Data Services Protocol v2.19 — Review Duty and Queue Presentation

**Status:** Approved for project use  
**Protocol delta version:** 2.19.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.18.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (presenting thousands of unclassified/Inhoud cards as the researcher-required one-by-one duty is fatigue, not assurance)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.19 records the owner-approved lock of 2026-09-02 (William Gomes) after a click-through of the live v2.18 console on `main` `4ebfdbb88cdb` (merge of PR #77), snapshot `snap-ac59cf24f946088e-e402c4d3` of the same Continentie freeze (V&VN kennisplatform HTML, SHA-256 `ac59cf24f946088ef4e9529dffa43b59e2087ca1ab943b2f24cadf67451b5a2a`). Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). Owner said it looks better, then asked whether researchers must do the 2008 Inhoud objects by hand. Owner then: “zet dat in protocol.” Live evidence: **Koppen 78 / Inhoud 2008** on Continentie after the v2.18 extract. Researchers MUST NOT be required to open 2008 Inhoud cards one by one. That is the same fail as 4000 unclassified: fatigue, not assurance.

Live baseline on `main` before this delta is Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0 and this delta jointly form normative baseline v2.19.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version (except the slow-lane reading that every `unclassified` object MUST be a one-object card the researcher must open), Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects (except the Inhoud-as-thousands-of-equal-one-object-cards reading), Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules (those stay in force), G2, Azure, LLM, or Protocol v2.14 time/lifecycle. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, or “light/heavy” review. Paragraph is display context, not a stored blob, not a new type. DOEN / OVERWEEG / NIET DOEN remain stamps on `recommendation`, not types. This delta’s bar is review DUTY and queue presentation, not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded here), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded here), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, and all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules remain in force, except the slow-lane unclassified one-object duty, 2008-Inhoud-as-acceptable-workload and next-implementation readings superseded in sections 3–6 and 8. This protocol-only change does not implement console Python, extract, kernel, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, or relation-checkbox adjacency except as already required.

This delta is a **scoped supersession** of any reading that (1) every `unclassified` object MUST be a slow-lane one-object card the researcher must open; or (2) 2008 Inhoud cards on one richtlijn is an acceptable workload. Where this delta and those readings conflict, this delta governs. Koppen MAY and MUST remain batch-confirmable as structure, never as advice (Protocol v2.15 / v2.16 unchanged). Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.18 §8 set the next console implementation as the extract+card wave (open card shows the freeze sentence once; extract does not split a grammatical continuation; extract does not emit identical `clean_text` twice from one freeze; re-extract unpublished Continentie). That code is now on `main` `4ebfdbb88cdb`. Owner click-through of that live console: it looks better; Koppen 78 / Inhoud 2008 remains. Where this delta and Protocol v2.18 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this queue/duty wave (Koppen batch stays; slow lane is proposed `recommendation` + `condition` / `exception` / high-risk; thousands of leftover `unclassified` MUST NOT be the presented duty). THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface and v2.18 once-only card / trailing-clause / identical-`clean_text` rules remain required law, except the bounded supersessions in this file.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

Index/conflict pointer: Protocol v2.30.0 SUPERSEDES any reading of this file that every assertive sentence MUST enter the ordinary review queue. Where this file and Protocol v2.30 conflict on admission into the ordinary queue, Protocol v2.30 governs: a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; missing required field → gate_result=blocked; there is no duty to objectify every sentence; there is a duty to assess normative/application-critical knowledge. v2.19 Koppen-batch / slow-duty recommendation+condition+exception+high-risk / leftover-unclassified-MUST-NOT-be-equal-one-by-one-cards law remains. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15, v2.16, v2.17 and v2.18 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave, the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave, the v2.17 researcher-surface wave and the v2.18 extract+card wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.15.0 remains mandatory, except the heading-proposal, stamp, tiny-object, one-door, compact-row, next-implementation and unpublished-Continentie-re-extract readings already superseded by Protocol v2.16, and except the slow-lane-unclassified-as-equal-one-object-duty reading superseded here, including:

- The ingest date field MUST be a calendar date picker stored as ISO `YYYY-MM-DD`; empty rejected; not today; not ingest-click; display locale MUST NOT leak into stored bytes;
- The ingest version field MUST be dotted non-negative integers; empty rejected; no `v` prefix, letters, year-as-version;
- Those two fields are freeze source metadata, not `object_version` and not Protocol v2.14 `valid_from` / `valid_until`;
- There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam”; lane follows confirmed (or, for queue routing only, proposed) `object_type`;
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`, except the v2.16 stamp rule and the v2.17 chrome rule;
- Fast lane MUST support batch-confirm of proposed headings as structure, not advice; headings MUST NOT be served as handelingsadvies;
- Four thousand unclassified cards on one richtlijn is a fail of this review surface.

Every rule in Protocol v2.16.0 remains mandatory, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object and next-implementation readings superseded by Protocol v2.17, the list-only compact-row reading and truncated-sentence reading tightened by Protocol v2.18, and except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded here, including:

- The Review page is the page that MUST convince guideline researchers; if they open it and it does not suffice, the project has failed — even if the kernel is fail-closed;
- One door **Beoordeel**; MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- Two named stacks with counts: **Koppen** (real freeze TOC / section titles of the richtlijn body) and **Inhoud**;
- Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status;
- DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not objects and not Koppen rows; extract MUST NOT heading-propose those words;
- Extract MUST NOT emit tiny objects (list-number-only, stamp-only, or a sentence fragment that cannot stand as one meaning unit);
- Unpublished Continentie: a new extract of the same freeze bytes is REQUIRED so the review page can pass the bar; source hash stays; unpublished object identities MAY be replaced; MUST NOT lie in the UI by hiding stored fragments without a new extract.

Every rule in Protocol v2.17.0 remains mandatory, except the next-implementation reading superseded by Protocol v2.18, including:

- UI copy MUST be researcher language; MUST NOT be slogans; MUST NOT say “wat een EPD MAG zeggen”; the entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg;
- Via-negativa MUST NOT appear on researcher rooms, including collapsed help;
- Onderwerp / family MUST be empty on a fresh new ingest;
- Bronpassage MUST show the same readable sentence as the knowledge object, without HTML tags, CSS class names, or kennisplatform markup, on every object / the whole freeze; v2.11 freeze bytes and locators stay exact;
- Extract MUST NOT emit kennisplatform chrome as knowledge objects or Koppen, including one-word Tools/Home/Richtlijnen/Meedenken;
- Recommendation-strength UI MUST NOT appear except on type `recommendation`;
- Relation checkbox and its label MUST be adjacent.

Every rule in Protocol v2.18.0 remains mandatory, except the next-implementation reading superseded here, including:

- The review object card MUST show the freeze sentence once; MUST NOT duplicate it as both h3/title and body;
- Extract MUST NOT split a grammatical continuation of the previous sentence into a new object; trailing clauses MUST stay in the same knowledge object as the sentence they complete;
- Extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical to an object already emitted from this freeze; repeated HTML (samenvatting versus module) is not extra knowledge; distinct real headings in different sections MAY remain.

Owner click-through of live v2.18 (`main` `4ebfdbb88cdb`, snapshot `snap-ac59cf24f946088e-e402c4d3`): it looks better. Chrome Tools/Home remains gone (v2.17 held). Slogan remains gone (v2.17 held). Once-only card sentence, no trailing-clause split, no identical-`clean_text` duplicates remain required (v2.18 held). Remaining fail is 2008 Inhoud cards presented as one-by-one researcher duty.

## 3. Researchers MUST NOT open 2008 Inhoud cards one by one

Researchers MUST NOT be required to open 2008 Inhoud cards one by one. That is the same fail as 4000 unclassified: fatigue, not assurance.

Owner evidence 2026-09-02 (`main` `4ebfdbb88cdb`, snapshot `snap-ac59cf24f946088e-e402c4d3`): live Continentie after the v2.18 extract showed **Koppen 78 / Inhoud 2008**. Owner said it looks better, then asked whether researchers must do the 2008 objects by hand. Owner then: “zet dat in protocol.” That MUST NOT remain.

- 2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface (same bar as Protocol v2.15 / v2.16).
- Presenting those cards as equal one-by-one work the researcher MUST complete is fatigue, not assurance.
- This supersedes any reading that every `unclassified` object MUST be a slow-lane one-object card the researcher must open, and any reading that 2008 Inhoud cards is an acceptable workload.
- Koppen 78 on that freeze is not this fail. Koppen remain the fast structure lane (section 4).

## 4. Koppen MAY and MUST be batch-confirmable as structure

Koppen MAY and MUST be batch-confirmable as structure, never as advice. Protocol v2.15 / v2.16 on this point are unchanged.

- Fast lane remains proposed `heading` (real freeze TOC / section titles of the richtlijn body).
- Batch-confirm is structure confirmation, not advice confirmation.
- Headings MUST NOT be served as handelingsadvies.
- Fast heading accept MUST NOT bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type.
- There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam” (Protocol v2.15 unchanged). Lane follows confirmed (or, for queue routing only, proposed) `object_type`.
- The machine MUST NOT decide that something is light enough to serve.

## 5. Researcher-required slow review on a freeze

The researcher-required slow review on a freeze is: proposed `recommendation`, plus `condition` / `exception` / any high-risk object (four-eyes unchanged). Those bound the advice. That is what they MUST do by hand.

- Proposed `recommendation` MUST be reviewed by hand before it MAY become confirmed type and, later, `supported` / handelingsadvies.
- `condition` and `exception` bound that advice and MUST be reviewed by hand when they are the objects that bound a proposed or confirmed recommendation.
- Any high-risk object remains four-eyes (Protocol v2.13 unchanged): confirmed type `exception`, `risk_level` high, or a listed high-risk field.
- That slow lane stays one-object for those objects (type + relations + high-risk four-eyes). This delta does not make recommendation batch-confirmable as advice.
- Machine classification remains a proposal, never published type. MUST NOT auto-confirm types. MUST NOT auto-promote ordinary text to `recommendation`.
- Serving stays fail-closed: only confirmed `recommendation` MAY be `supported` / handelingsadvies. The machine MUST NOT decide something is light enough to serve.

## 6. Remaining unclassified MUST NOT be the presented duty

Remaining `unclassified` MUST NOT be presented as equal one-by-one work of thousands of cards. Unclassified is never served (`supported` / handelingsadvies), so 2000 clicks on it do not add assurance.

- `unclassified` MUST NOT be `supported`. Two thousand clicks on leftover unclassified cards do not add serving assurance.
- Thousands of leftover `unclassified` MUST NOT be the presented duty on the Review page.
- `definition` / `explanation` MAY exist and MAY later answer non-advice questions once confirmed; they are NOT the MVP researcher 2000-card duty for handelingsadvies.
- Stored unclassified objects MAY remain in the store. Hiding stored fragments without a new extract remains forbidden. Presentation of duty is not deletion.
- Extract SHOULD still get coarser (kennisplatform HTML is too chatty) but this delta’s bar is review DUTY and queue presentation, not a new object type.
- Protocol v2.16 tiny-objects, Protocol v2.17 chrome, and Protocol v2.18 no-duplicate-sentence / trailing-clause / identical `clean_text` stay in force.

Non-binding implementer hunch (MUST be verified in the later implementation, not in this protocol change): the Inhoud stack currently enumerates every leftover unclassified object as an equal slow-lane card; the presented duty queue should be proposed `recommendation` plus `condition` / `exception` / high-risk, with leftover unclassified not shown as equal one-by-one work. This hunch is not a protocol requirement of those field names.

## 7. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged. Protocol v2.14 unchanged (not written, not next). Azure unchanged (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication.

Freeze source bytes and SHA-256 stay. Existing published objects are not silently rewritten (there is no published projection). Continentie is unpublished: unpublished Continentie MAY be re-extracted after this law; source SHA-256 stays; unpublished identities MAY be replaced; MUST NOT hide stored fragments without a new extract. Hiding is lying; a new extract is the lawful fix.

2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface (same bar as v2.15/v2.16). Duplicate identical `clean_text` objects and trailing-clause objects still count toward that fail (Protocol v2.18 unchanged).

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–6.

## 8. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the Review page presents Koppen as batch-confirmable structure and the researcher-required slow duty as proposed `recommendation` plus `condition` / `exception` / high-risk, without presenting thousands of leftover unclassified as equal one-by-one work.

Where this delta and Protocol v2.18 conflict on which implementation is next, this delta governs. The v2.18 extract+card wave is already in code on `main` `4ebfdbb88cdb`. Owner click-through: it looks better; Koppen 78 / Inhoud 2008 remains. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this queue/duty wave:

1. Koppen batch stays (batch-confirm as structure, never as advice);
2. slow lane is proposed `recommendation` plus `condition` / `exception` / any high-risk object (four-eyes unchanged); that is the researcher-required hand work;
3. thousands of leftover `unclassified` MUST NOT be the presented duty; unclassified is never served, so 2000 clicks on it do not add assurance;
4. MUST NOT auto-confirm types; MUST NOT auto-promote ordinary text to `recommendation`; MUST NOT add a researcher “zwaar/licht” or “snel/langzaam” switch;
5. unpublished Continentie MAY be re-extracted on the same freeze SHA-256 so the page can pass this bar; unpublished object identities MAY be replaced; MUST NOT hide stored fragments without that extract;

THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface and v2.18 once-only card / trailing-clause / identical-`clean_text` remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta. The v2.17 researcher-surface wave is already in code and is not the next implementation after this delta. The v2.18 extract+card wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure deploy, G2 PASS, Protocol v2.14, LLM, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–6, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, or relation-checkbox adjacency except as already required, hiding stored fragments without a new extract.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (presenting thousands of unclassified/Inhoud cards as the researcher-required one-by-one duty is fatigue, not assurance). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of this queue/duty wave, leftover-unclassified presentation, or a new extract of unpublished Continentie remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 10. Gates and approval effect

Approval of v2.19 establishes that researchers MUST NOT be required to open 2008 Inhoud cards one by one; that that is the same fail as 4000 unclassified (fatigue, not assurance); that live evidence is Inhoud (2008) / Koppen 78 on Continentie after the v2.18 extract (`main` `4ebfdbb88cdb`, snapshot `snap-ac59cf24f946088e-e402c4d3`); that owner said it looks better, then asked whether researchers must do the 2008 objects by hand, then “zet dat in protocol.”; that Koppen MAY and MUST be batch-confirmable as structure, never as advice (v2.15/v2.16 unchanged); that the researcher-required slow review on a freeze is proposed `recommendation`, plus `condition` / `exception` / any high-risk object (four-eyes unchanged); that those bound the advice and that is what they MUST do by hand; that remaining `unclassified` MUST NOT be presented as equal one-by-one work of thousands of cards; that unclassified is never served (`supported` / handelingsadvies), so 2000 clicks on it do not add assurance; that serving stays fail-closed: only confirmed `recommendation` MAY be `supported` / handelingsadvies; that the machine MUST NOT decide something is light enough to serve; that there MUST NOT be a researcher “zwaar/licht” or “snel/langzaam” switch (v2.15 unchanged); that machine classification remains a proposal, never published type; that MUST NOT auto-confirm types; that MUST NOT auto-promote ordinary text to `recommendation`; that `definition` / `explanation` MAY exist and MAY later answer non-advice questions once confirmed, and they are NOT the MVP researcher 2000-card duty for handelingsadvies; that extract SHOULD still get coarser (kennisplatform HTML is too chatty) but this delta’s bar is review DUTY and queue presentation, not a new object type; that v2.16 tiny-objects, v2.17 chrome, and v2.18 no-duplicate-sentence / trailing-clause / identical `clean_text` stay in force; that 2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface (same bar as v2.15/v2.16); that unpublished Continentie MAY be re-extracted after this law; that source SHA-256 stays; that unpublished identities MAY be replaced; that MUST NOT hide stored fragments without a new extract; and that this is a bounded supersession of any reading that every unclassified object MUST be a slow-lane one-object card the researcher must open, or that 2008 Inhoud cards is an acceptable workload. Serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this change. Next implementation is this queue/duty wave, THEN William click-through, THEN Azure ZIP, THEN G2. It does not:

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
- auto-confirm types;
- auto-promote ordinary text to `recommendation`;
- treat remaining unclassified as equal one-by-one researcher duty of thousands of cards;
- treat 2008 Inhoud cards as an acceptable workload;
- make `definition` / `explanation` the MVP researcher 2000-card duty for handelingsadvies;
- add page, paragraph, stamp, strength, GRADE, chrome, or light/heavy as stored object types;
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
- emit kennisplatform chrome (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated nav) as knowledge objects or Koppen;
- fuse condition into recommendation, or reopen that Protocol v2.13 forbid;
- lie in the UI by hiding stored fragments without a new extract;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules beyond forbidding tiny objects, grammatical continuations as separate objects, and identical-`clean_text` duplicates from one freeze;
- reopen Protocol v2.11 freeze/locator except researcher-visible prose derived from those locators;
- reserialize or re-save freeze bytes, or bind locators to reserialized HTML;
- dump raw HTML tag soup, CSS class names or kennisplatform markup as the researcher bronpassage;
- reopen Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except the slow-lane-unclassified-as-equal-one-object-duty reading superseded here and the heading-proposal rules already superseded by v2.16 stamps and by the v2.17 chrome rule;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded here;
- reopen Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation or compact-relation-checkbox rules except as already required;
- reopen Protocol v2.18 once-only card sentence, grammatical-continuation-split or identical-`clean_text` rules except the next-implementation reading superseded here;
- require or allow “wat een EPD MAG zeggen” or any EPD MAG slogan as Review lead copy;
- claim a single subscriber class on researcher pages;
- allow HELP_ONCE via-negativa on researcher rooms, including collapsed “Over deze console”;
- prefill Onderwerp / family on a fresh new ingest;
- expand empty-Onderwerp to class default;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor;
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–6;
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
