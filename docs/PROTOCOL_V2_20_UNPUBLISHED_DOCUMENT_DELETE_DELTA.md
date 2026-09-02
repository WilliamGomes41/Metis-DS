# V&VN Data Services Protocol v2.20 — Unpublished Document Delete

**Status:** Approved for project use  
**Protocol delta version:** 2.20.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.19.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (PROTOCOL.md is every-guideline law, not Continentie-only; unpublished captured snapshots MAY be removed from the operations console by an authorized operator)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.20 records the owner-approved lock of 2026-09-02 (William Gomes). Owner asked why Continentie is explicit in `PROTOCOL.md`; put a delete button in; he may clean everything (remove unpublished Continentie from the console list so he can try another guideline). Metis is document owner. The Implementation engineer writes code later. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

Live baseline on `main` before this delta is Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. The v2.19 queue/duty wave is now in code (PR #79, merge `9987a976d719`). Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0 and this delta jointly form normative baseline v2.20.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects (except any reading that leftover unpublished Continentie MUST stay on the console until a new extract, and except any reading that PROTOCOL.md / the next freeze is Continentie-only), Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules, Protocol v2.18 once-only card sentence / trailing-clause / identical-`clean_text` rules, Protocol v2.19 review duty / queue presentation (those stay in force), G2, Azure, LLM, or Protocol v2.14 time/lifecycle. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, or delete. This delta’s bar is every-guideline law plus unpublished-snapshot delete, not a new object type.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except any Continentie-as-product-identity or leftover-unpublished-Continentie-must-stay-on-the-console reading superseded here), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, and all Protocol v2.19 review-duty / queue-presentation rules remain in force, except the Continentie-as-product-identity, leftover-unpublished-must-stay, SSH-wipe-as-product-path and next-implementation readings superseded in sections 3–6 and 8. This protocol-only change does not implement console Python, extract, kernel, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. Do not reopen serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, or review-duty / queue presentation except as already required.

This delta is a **scoped supersession** of any reading that (1) `PROTOCOL.md` is Continentie-only law, or that the next freeze MUST be Continentie; (2) unpublished captured snapshots MUST stay on the operations console until publication or a new extract; (3) the product path to remove unpublished capture is SSH or a wipe of `/home/data`; or (4) four-eyes / a second named reviewer is required to delete unpublished capture. Where this delta and those readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain (stamp words as Koppen; 2008 Inhoud cards). Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.19 §8 set the next console implementation as the queue/duty wave (Koppen batch stays; slow lane is proposed `recommendation` + `condition` / `exception` / high-risk; thousands of leftover `unclassified` MUST NOT be the presented duty). That code is now on `main` `9987a976d719` (PR #79). Where this delta and Protocol v2.19 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this unpublished-delete wave (real delete control on the document card / Review chooser for unpublished snapshots only; researcher-Dutch label; confirm before it runs; after-delete lists empty of that `snapshot_id`; objects+envelope gone; optional freeze-bytes of that unpublished source; audit ledger row; MUST NOT touch other snapshots or `/home/data` globally). THEN William MAY remove live unpublished Continentie from the console and ingest another HTML freeze. THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live console. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text` and v2.19 review duty / queue presentation remain required law, except the bounded supersessions in this file.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15, v2.16, v2.17, v2.18 and v2.19 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave, the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave, the v2.17 researcher-surface wave, the v2.18 extract+card wave and the v2.19 queue/duty wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.16.0 remains mandatory, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object and next-implementation readings superseded by Protocol v2.17, the list-only compact-row reading and truncated-sentence reading tightened by Protocol v2.18, the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded here, including:

- The Review page is the page that MUST convince guideline researchers; if they open it and it does not suffice, the project has failed — even if the kernel is fail-closed;
- One door **Beoordeel**; MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- Two named stacks with counts: **Koppen** (real freeze TOC / section titles of the richtlijn body) and **Inhoud**;
- Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status;
- DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not objects and not Koppen rows; extract MUST NOT heading-propose those words;
- Extract MUST NOT emit tiny objects (list-number-only, stamp-only, or a sentence fragment that cannot stand as one meaning unit);
- MUST NOT lie in the UI by hiding stored fragments without a new extract. That forbid remains for a freeze that stays in Review. Whole-unpublished-snapshot delete is not that hide.

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

Every rule in Protocol v2.19.0 remains mandatory, except the next-implementation reading superseded here, including:

- Researchers MUST NOT be required to open 2008 Inhoud cards one by one. That is the same fail as 4000 unclassified: fatigue, not assurance;
- Koppen MAY and MUST be batch-confirmable as structure, never as advice;
- The researcher-required slow review on a freeze is proposed `recommendation`, plus `condition` / `exception` / any high-risk object (four-eyes unchanged);
- Remaining `unclassified` MUST NOT be presented as equal one-by-one work of thousands of cards. Unclassified is never served (`supported` / handelingsadvies), so 2000 clicks on it do not add assurance;
- MUST NOT auto-confirm types; MUST NOT auto-promote ordinary text to `recommendation`; MUST NOT a researcher “zwaar/licht” or “snel/langzaam” switch;
- 2008 unclassified/Inhoud cards on one richtlijn remains a fail of this review surface.

Owner evidence 2026-09-02: Continentie in v2.16–v2.19 is live evidence of those fails (stamp words as Koppen; Koppen 78 / Inhoud 2008 after the v2.18 extract on `main` `4ebfdbb88cdb`, snapshot `snap-ac59cf24f946088e-e402c4d3`). That evidence stays. It is not the product identity. There is no published Continentie.

## 3. PROTOCOL.md is the law for every guideline

`PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol.

- Continentie appears in Protocol v2.16–v2.19 as live evidence of fails (stamp words as Koppen; 2008 Inhoud cards), not as the product identity.
- Those historical evidence sentences MUST remain. This delta MUST NOT strip them.
- The next freeze MUST NOT have to be Continentie. William MAY ingest another HTML freeze after unpublished Continentie is removed from the console.
- Naming Continentie in a historical evidence sentence does not make Continentie the only lawful first-wave source.
- Family / Onderwerp remains a hook the ingest researcher sets. A fresh new ingest MUST still start with empty Onderwerp (Protocol v2.17 unchanged).

This supersedes any reading that `PROTOCOL.md`, the console, or the next freeze is Continentie-only.

## 4. Unpublished captured snapshots MAY be deleted from the console

Unpublished captured snapshots MAY be removed from the operations console by an authorized console operator. That operator is the same class as ingest: a named researcher or reviewer account, not a secret engineer path.

This is owner-authorized cleanup of unpublished capture, not publication, not G2, and not hiding fragments of a freeze that remains in Review.

- Capture remains not publication.
- `publish()` stays G2-BLOCKED. This delta does not implement `publish()` PASS.
- There is no published Continentie. The live unpublished Continentie snapshot MAY be deleted after this law is implemented.
- Four-eyes is not required to delete unpublished capture.
- The uploader MAY delete unpublished they captured.
- A second named reviewer is not required for delete. Delete is not type-confirm.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as the authorized console operator for this delete, MUST NOT approve, and MUST NOT publish.
- Engineers MUST NOT submit sources through the ingest room and MUST NOT use a secret engineer path to delete unpublished capture.

## 5. Delete control, confirmation, after-effects and audit

The operations console MUST have a real delete control on the document card / Review chooser for unpublished snapshots only.

- The control MUST appear on the document card and on the Review chooser for an unpublished snapshot.
- The control MUST NOT appear for a published projection or for anything that has been published.
- The label MUST be researcher Dutch, for example **Verwijder unpublished document**. MUST NOT use "envelope" as a UI term. MUST NOT ask a researcher to type or pick a snapshot id as the primary act.
- The control MUST confirm before it runs. Delete is destructive.
- After delete, that snapshot MUST NOT appear on Inleveren, Review or Documentenhierarchie lists.
- Stored objects and the envelope for that `snapshot_id` are gone.
- Freeze bytes of that unpublished source MAY be removed with it.
- MUST NOT touch other snapshots.
- MUST NOT touch `/home/data` globally.
- MUST append an audit ledger row: who, when, `snapshot_id`, source SHA-256, title.
- The console action is the path. MUST NOT SSH or wipe `/home/data` as the product path.

## 6. Whole unpublished snapshot only; published and hide-fragments stay forbidden

This delete is the whole unpublished snapshot only.

- MUST NOT delete a published projection or anything that has been published.
- MUST NOT use this to hide selected objects inside a freeze that stays in Review. Protocol v2.16 hide-fragments-without-extract remains: MUST NOT lie in the UI by hiding stored fragments without a new extract.
- A new extract of unpublished identities on the same freeze SHA-256 remains lawful (Protocol v2.16–v2.19). Whole-snapshot delete is the other lawful cleanup: remove the unpublished snapshot from the console so another guideline MAY be ingested.
- MUST NOT invent a partial-delete, object-picker-delete, or “hide this card” control as a substitute for extract or for this whole-snapshot delete.

## 7. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Four-eyes is not required to delete unpublished capture. Protocol v2.14 unchanged (not written, not next). Azure unchanged (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication.

Beoordeel timeout / performance (owner reported Beoordeel click hangs on live B1 while loading the fat PDF snapshot) is a separate issue. MUST NOT fold that into this delta.

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

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the console has a real unpublished-delete control on the document card / Review chooser.

Where this delta and Protocol v2.19 conflict on which implementation is next, this delta governs. The v2.19 queue/duty wave is already in code on `main` `9987a976d719`. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this unpublished-delete wave:

1. MUST a real delete control on the document card / Review chooser for unpublished snapshots only;
2. label in researcher Dutch (for example **Verwijder unpublished document**); MUST confirm before it runs (destructive);
3. after delete, that snapshot MUST NOT appear on Inleveren / Review / Documentenhierarchie lists; stored objects+envelope for that `snapshot_id` are gone; freeze bytes of that unpublished source MAY be removed with it;
4. MUST append an audit ledger row (who, when, `snapshot_id`, source SHA-256, title); capture remains not publication;
5. MUST NOT delete a published projection or anything that has been published; MUST NOT hide selected objects inside a freeze that stays in Review; MUST NOT touch other snapshots or `/home/data` globally; MUST NOT SSH or wipe `/home/data` as the product path;
6. four-eyes is not required to delete unpublished capture; the uploader MAY delete unpublished they captured; a second named reviewer is not required for delete (delete is not type-confirm);
7. THEN William MAY remove live unpublished Continentie from the console and ingest another HTML freeze. The next freeze MUST NOT have to be Continentie.

THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live console. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text` and v2.19 review duty / queue presentation remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta. The v2.17 researcher-surface wave is already in code and is not the next implementation after this delta. The v2.18 extract+card wave is already in code and is not the next implementation after this delta. The v2.19 queue/duty wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure deploy, G2 PASS, Protocol v2.14, LLM, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–6, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, auto-confirming types, auto-promoting ordinary text to `recommendation`, a researcher “zwaar/licht” or “snel/langzaam” switch, reopening serving typeset, stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, or review-duty / queue presentation except as already required, hiding stored fragments without a new extract, SSH or wipe of `/home/data` as the product path, Beoordeel timeout / performance (owner reported Beoordeel click hangs on live B1 while loading the fat PDF snapshot — that is a separate issue).

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (PROTOCOL.md is every-guideline law, not Continentie-only; unpublished captured snapshots MAY be removed from the operations console by an authorized operator). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of this unpublished-delete wave, or a later ingest of another HTML freeze after unpublished Continentie is removed, remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 10. Gates and approval effect

Approval of v2.20 establishes that `PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol; that Continentie appears in v2.16–v2.19 as live evidence of fails (stamp words as Koppen, 2008 Inhoud cards), not as the product identity; that those historical evidence sentences MUST remain and MUST NOT be stripped; that the next freeze MUST NOT have to be Continentie; that unpublished captured snapshots MAY be removed from the operations console by an authorized console operator (same class as ingest: named researcher or reviewer account, not a secret engineer path); that this is owner-authorized cleanup of unpublished capture, not publication, not G2, and not hiding fragments of a freeze that remains in Review; that the console MUST have a real delete control on the document card / Review chooser for unpublished snapshots only; that the label MUST be researcher Dutch (for example **Verwijder unpublished document**); that the control MUST confirm before it runs (destructive); that after delete that snapshot MUST NOT appear on Inleveren / Review / Documentenhierarchie lists; that stored objects and the envelope for that `snapshot_id` are gone; that freeze bytes of that unpublished source MAY be removed with it; that MUST NOT touch other snapshots or `/home/data` globally; that MUST append an audit ledger row (who, when, `snapshot_id`, source SHA-256, title); that capture remains not publication; that MUST NOT delete a published projection or anything that has been published; that `publish()` stays G2-BLOCKED; that there is no published Continentie; that MUST NOT use this to hide selected objects inside a freeze that stays in Review (v2.16 hide-fragments-without-extract remains); that this is the whole unpublished snapshot only; that MUST NOT SSH or wipe `/home/data` as the product path; that the console action is the path; that four-eyes is not required to delete unpublished capture; that the uploader MAY delete unpublished they captured; that a second named reviewer is not required for delete (delete is not type-confirm); and that this is a bounded supersession of any reading that `PROTOCOL.md` is Continentie-only, that the next freeze MUST be Continentie, that unpublished capture MUST stay on the console until publication, that SSH / wipe of `/home/data` is the product path, or that four-eyes / a second named reviewer is required to delete unpublished capture. Serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; four-eyes is not required to delete unpublished capture; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this change. Beoordeel timeout / performance is a separate issue and is not this delta. Next implementation is this unpublished-delete wave, THEN William MAY remove live unpublished Continentie and ingest another HTML freeze, THEN William click-through, THEN Azure ZIP, THEN G2. It does not:

- implement console Python, extract, kernel, Product API, or `publish()`;
- convert G2 to PASS;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- skip durable immutable storage;
- staff named reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- require four-eyes or a second named reviewer to delete unpublished capture;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- let Koppen heading accept bypass four-eyes if the object is high-risk or is reclassified onto a high-risk type;
- auto-confirm types;
- auto-promote ordinary text to `recommendation`;
- treat remaining unclassified as equal one-by-one researcher duty of thousands of cards;
- treat 2008 Inhoud cards as an acceptable workload;
- make `definition` / `explanation` the MVP researcher 2000-card duty for handelingsadvies;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, or delete as stored object types;
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
- hide selected objects inside a freeze that stays in Review;
- delete a published projection or anything that has been published;
- touch other snapshots or `/home/data` globally when deleting one unpublished snapshot;
- treat SSH or a wipe of `/home/data` as the product path;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- make the next freeze have to be Continentie;
- treat `PROTOCOL.md` as Continentie-only law;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules beyond forbidding tiny objects, grammatical continuations as separate objects, and identical-`clean_text` duplicates from one freeze;
- reopen Protocol v2.11 freeze/locator except researcher-visible prose derived from those locators;
- reserialize or re-save freeze bytes, or bind locators to reserialized HTML;
- dump raw HTML tag soup, CSS class names or kennisplatform markup as the researcher bronpassage;
- reopen Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except as already superseded by v2.16 stamps, the v2.17 chrome rule, and the v2.19 slow-lane-unclassified-as-equal-one-object-duty reading;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded here;
- reopen Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation or compact-relation-checkbox rules except as already required;
- reopen Protocol v2.18 once-only card sentence, grammatical-continuation-split or identical-`clean_text` rules except as already required;
- reopen Protocol v2.19 review-duty or queue-presentation rules except the next-implementation reading superseded here;
- require or allow “wat een EPD MAG zeggen” or any EPD MAG slogan as Review lead copy;
- claim a single subscriber class on researcher pages;
- allow HELP_ONCE via-negativa on researcher rooms, including collapsed “Over deze console”;
- prefill Onderwerp / family on a fresh new ingest;
- expand empty-Onderwerp to class default;
- invent a locator scheme;
- treat machine classification as published type, or serve `unclassified` as `supported`;
- give advice-weight to heading, or serve headings as handelingsadvies;
- replace the v2.12 publish tuple, or let envelope `review_passes` authorize publish;
- let the uploader be the only required reviewer for type-confirm, or let AI, Grok Bot, Metis, the Implementation engineer or the Auditor count as required reviewers or as the authorized delete operator;
- authorize live URL-HTML, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor;
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–6;
- fold Beoordeel timeout / performance into this delta;
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
