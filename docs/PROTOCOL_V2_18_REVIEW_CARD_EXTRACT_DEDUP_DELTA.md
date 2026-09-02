# V&VN Data Services Protocol v2.18 — Review Card Once and Extract Dedup

**Status:** Approved for project use  
**Protocol delta version:** 2.18.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.17.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (duplicate card sentence, truncated-sentence split, and identical freeze prose as extra objects bias assessment)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.18 records the owner-approved lock of 2026-09-02 (William Gomes) after a click-through of the live v2.17 console on `main` `3e811bf0fc9f` (merge of PR #75), snapshot `snap-ac59cf24f946088e-6538b559` of the same Continentie freeze (V&VN kennisplatform HTML, SHA-256 `ac59cf24f946088ef4e9529dffa43b59e2087ca1ab943b2f24cadf67451b5a2a`). Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem after the v2.17 researcher-surface wave is duplication plus truncated-sentence split. Owner: “De dubbeling is niet opgelost.” Those MUST NOT remain acceptable.

Live evidence the same day:

- The open review card titled the object **Eventueel met hulp van de mantelzorger.** and repeated that identical sentence as the object body. Bronpassage showed the full recommendation: “Overweeg om bij ouderen met urine-incontinentie én een cognitieve beperking het advies te geven om op vaste tijden te gaan plassen. Eventueel met hulp van de mantelzorger.”
- Extract split that recommendation into two unclassified objects: (1) the Overweeg-sentence (2) the trailing clause “Eventueel met hulp van de mantelzorger.”
- That pair is emitted THREE times in one freeze (indices ~92/93, 769/770, 2510/2511) because kennisplatform HTML repeats samenvatting/module text.
- 22 trailing-clause objects starting Eventueel / Bijvoorbeeld / Zoals.
- Chrome Tools/Home is gone (v2.17 held). Slogan gone (v2.17 held). This fail is duplication + truncated-sentence split.

Live baseline on `main` before this delta is Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0 and this delta jointly form normative baseline v2.18.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator, Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes (except the bounded continuation-split tightening in section 4, which restates Protocol v2.16 tiny-objects), Protocol v2.15 ingest-date/version/type-lanes, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects (except the compact-row reading that bound only the list, and the truncated-sentence reading that the v2.17 Continentie re-extract still failed), Protocol v2.17 slogan / help / Onderwerp / bronpassage-prose / chrome / stamp-UI / relation-checkbox rules (those held on this click-through), G2, Azure, LLM, or Protocol v2.14 time/lifecycle. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, or chrome. Paragraph is display context, not a stored blob, not a new type. DOEN / OVERWEEG / NIET DOEN remain stamps on `recommendation`, not types.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules, all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the list-only compact-row reading and the truncated-sentence reading tightened here), and all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules remain in force, except the duplicate-card-sentence, grammatical-continuation-split, identical-`clean_text` and next-implementation readings superseded in sections 3–5 and 8. This protocol-only change does not implement console Python, extract, kernel, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that (1) the review card MAY repeat the same freeze sentence as both heading and body, including a reading that Protocol v2.16 compact rows bind only the list and not the open card; (2) extract MAY split a grammatical continuation / trailing clause into a new object, including a reading that the v2.16 truncated-sentence / tiny-object forbid is already satisfied by the v2.17 Continentie re-extract (that re-extract still failed it); or (3) extract MAY emit identical `clean_text` passages as multiple objects because the freeze HTML repeats them (samenvatting versus module). Where this delta and those readings conflict, this delta governs. Distinct real headings in different sections MAY remain (`1.1 Inleiding` versus `2. Inleiding` are not identical strings). Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.17 §12 set the next console implementation as the researcher-surface wave (no slogans, empty Onderwerp, bronpassage prose, no chrome objects, stamp UI only on `recommendation`, compact relation checkboxes, re-extract unpublished Continentie). That code is now on `main` `3e811bf0fc9f`. Chrome Tools/Home is gone. Slogan gone. Where this delta and Protocol v2.17 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this extract+card wave (open card shows the freeze sentence once; extract does not split a grammatical continuation; extract does not emit a second object with identical `clean_text` from this freeze; re-extract unpublished Continentie). THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects and v2.17 researcher-surface rules remain required law, except the bounded supersessions in this file.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15, v2.16 and v2.17 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave, the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave and the v2.17 researcher-surface wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.15.0 remains mandatory, except the heading-proposal, stamp, tiny-object, one-door, compact-row, next-implementation and unpublished-Continentie-re-extract readings already superseded by Protocol v2.16, including:

- The ingest date field MUST be a calendar date picker stored as ISO `YYYY-MM-DD`; empty rejected; not today; not ingest-click; display locale MUST NOT leak into stored bytes;
- The ingest version field MUST be dotted non-negative integers; empty rejected; no `v` prefix, letters, year-as-version;
- Those two fields are freeze source metadata, not `object_version` and not Protocol v2.14 `valid_from` / `valid_until`;
- There MUST NOT be a researcher control “zwaar/licht” or “snel/langzaam”; lane follows confirmed (or, for queue routing only, proposed) `object_type`;
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`, except the v2.16 stamp rule and the v2.17 chrome rule;
- Fast lane MUST support batch-confirm of proposed headings as structure, not advice; headings MUST NOT be served as handelingsadvies;
- Slow lane stays one-object (type + relations + high-risk four-eyes);
- Four thousand unclassified cards on one richtlijn is a fail of this review surface.

Every rule in Protocol v2.16.0 remains mandatory, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object and next-implementation readings superseded by Protocol v2.17, and except the list-only compact-row reading and the truncated-sentence reading tightened here, including:

- The Review page is the page that MUST convince guideline researchers; if they open it and it does not suffice, the project has failed — even if the kernel is fail-closed;
- One door **Beoordeel**; MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- Two named stacks with counts: **Koppen** (real freeze TOC / section titles of the richtlijn body) and **Inhoud** (`definition`, `explanation`, `condition`, `exception`, `recommendation`, and `unclassified` until typed);
- Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status;
- DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not objects and not Koppen rows; extract MUST NOT heading-propose those words;
- Extract MUST NOT emit tiny objects (list-number-only, stamp-only, or a sentence fragment that cannot stand as one meaning unit);
- Unpublished Continentie: a new extract of the same freeze bytes is REQUIRED so the review page can pass the bar; source hash stays; unpublished object identities MAY be replaced; MUST NOT lie in the UI by hiding stored fragments without a new extract.

Every rule in Protocol v2.17.0 remains mandatory, except the next-implementation reading superseded here, including:

- UI copy MUST be researcher language; MUST NOT be slogans; MUST NOT say “wat een EPD MAG zeggen”; the entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg;
- Via-negativa MUST NOT appear on researcher rooms, including collapsed help;
- Onderwerp / family MUST be empty on a fresh new ingest;
- Bronpassage MUST show the same readable sentence as the knowledge object, without HTML tags, CSS class names, or kennisplatform markup, on every object / the whole freeze; v2.11 freeze bytes and locators stay exact;
- Extract MUST NOT emit kennisplatform chrome as knowledge objects or Koppen, including one-word Tools/Home/Richtlijnen/Meedenken;
- Recommendation-strength UI MUST NOT appear except on type `recommendation`;
- Relation checkbox and its label MUST be adjacent.

Owner click-through of live v2.17 (`main` `3e811bf0fc9f`): Chrome Tools/Home is gone (v2.17 held). Slogan gone (v2.17 held). Those MUST remain gone. This fail is duplication + truncated-sentence split.

## 3. Review object card shows the freeze sentence once

The review object card MUST show the freeze sentence once. MUST NOT duplicate it as both h3/title and body.

Owner evidence 2026-09-02 (`main` `3e811bf0fc9f`, snapshot `snap-ac59cf24f946088e-6538b559`): the open card heading and the object body were the identical sentence “Eventueel met hulp van de mantelzorger.” Owner: “De dubbeling is niet opgelost.” That MUST NOT remain.

- Compact row / card: one source sentence plus short status.
- The Protocol v2.16 compact-row bar applies to the open card, not only the list.
- The card MAY keep a short status line (wacht / huidig type) next to that one sentence. Status MUST NOT become a second copy of the freeze sentence.
- The right-column bronpassage remains the readable source passage (Protocol v2.17). Bronpassage MAY show more surrounding freeze prose than the object sentence. That is not a second copy of the object body on the left.
- Kernel ids MUST NOT be the card title (Protocol v2.16 unchanged).
- MUST NOT render the same `clean_text` twice as heading and as body on one card.

Non-binding implementer hunch (MUST be verified in the later implementation, not in this protocol change): `review_row_title` equals `clean_text`, so one-sentence objects always look doubled. This hunch is not a protocol requirement of those field names.

## 4. Extract MUST NOT split a grammatical continuation

Extract MUST NOT split a grammatical continuation of the previous sentence into a new object. Trailing clauses MUST stay in the same knowledge object as the sentence they complete.

Owner evidence 2026-09-02: extract split the full recommendation into (1) “Overweeg om bij ouderen met urine-incontinentie én een cognitieve beperking het advies te geven om op vaste tijden te gaan plassen.” and (2) “Eventueel met hulp van de mantelzorger.” Twenty-two trailing-clause objects in that freeze start Eventueel / Bijvoorbeeld / Zoals. Those MUST NOT remain separate objects.

- This restates and tightens the Protocol v2.16 truncated-sentence / tiny-object forbid. A trailing clause that cannot stand as one meaning unit is a tiny object. The v2.17 Continentie re-extract still failed it.
- Examples of trailing clauses that MUST stay with the preceding sentence: “Eventueel met hulp van de mantelzorger.”, “Bijvoorbeeld …”, “Zoals …”. Those starters are evidence, not a closed list.
- A lone trailing clause of a previous sentence is forbidden as its own knowledge object.
- This is NOT fusion of condition into recommendation and MUST NOT reopen that Protocol v2.13 forbid. A true separate meaning unit (a later sentence that can stand alone) MAY remain a separate object.
- Extraction still MUST split at meaning boundaries, not token budgets (Protocol v2.13 unchanged). Token-budget chunking still MUST NOT define object identity.
- Where this sentence and a reading that the v2.16 tiny-object forbid is already satisfied by the v2.17 Continentie re-extract conflict, this delta governs: that re-extract still failed; a new extract after this law is REQUIRED.

Non-binding implementer hunch (MUST be verified in the later implementation, not in this protocol change): the HTML parser splits on period / `p` tags even when the next `p` is a continuation. This hunch is not a protocol requirement of those tag names.

## 5. Extract MUST NOT emit identical freeze prose twice

Extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical to an object already emitted from this freeze. Repeated HTML (samenvatting versus module) is not extra knowledge.

Owner evidence 2026-09-02: the Overweeg / Eventueel pair is emitted THREE times in one freeze (indices ~92/93, 769/770, 2510/2511) because kennisplatform HTML repeats samenvatting/module text. That MUST NOT remain.

- Visible freeze prose for this rule is the object `clean_text` after ordinary whitespace normalisation. Identical strings are identical knowledge for this freeze.
- Distinct real headings in different sections MAY remain (`1.1 Inleiding` versus `2. Inleiding` are not identical strings).
- Chrome remains not stored (Protocol v2.17 unchanged). This rule does not revive chrome as objects in order to deduplicate them.
- MUST NOT hide stored fragments without a new extract. Hiding is lying; a new extract is the lawful fix.
- Unpublished Continentie MAY be re-extracted after this law; source SHA-256 stays; unpublished identities MAY be replaced.
- Published objects, if any later exist, MUST NOT be silently rewritten. Identity of published hashed objects stays until a new source version / snapshot under existing v2.7 / v2.12 / v2.13 rules.
- This delta MUST NOT rewrite Protocol v2.13 split rules except to forbid splitting a grammatical continuation into a new object and to forbid a second object with identical `clean_text` from the same freeze. Fusion of condition into recommendation remains the forbidden default.

## 6. Unclassified bar unchanged; unpublished Continentie re-extract

Thousands of unclassified cards on one richtlijn remains a fail of the review surface. Duplicate identical `clean_text` objects and trailing-clause objects count toward that fail. The Protocol v2.15 / v2.16 / v2.17 bar is unchanged on that point: a page of thousands of identical `unclassified` titles, tiny objects, chrome-as-objects, duplicated freeze sentences, or split trailing clauses MUST NOT be accepted as workload.

Freeze source bytes and SHA-256 stay. Existing published objects are not silently rewritten (there is no published projection). Continentie is unpublished: a new extract of the same freeze bytes is REQUIRED so the review page can meet this bar (one sentence on the open card; no trailing-clause objects; no identical-`clean_text` duplicates from repeated HTML). Source hash of the freeze stays. Unpublished object identities MAY be replaced by that new extract. MUST NOT hide stored fragments without a new extract.

- MUST NOT lie in the UI by hiding stored fragments without that new extract. Hiding is lying; a new extract is the lawful fix.
- Published objects, if any later exist, MUST NOT be silently rewritten.
- 2641 unclassified on one richtlijn remains a fail. Duplicate triples of the same pair remain a fail even if the unclassified count later drops.

## 7. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged. Protocol v2.14 unchanged (not written, not next). Azure unchanged (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–5.

## 8. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the Review card shows the freeze sentence once, extract does not split a grammatical continuation, and extract does not emit identical `clean_text` twice from one freeze.

Where this delta and Protocol v2.17 conflict on which implementation is next, this delta governs. The v2.17 researcher-surface wave is already in code on `main` `3e811bf0fc9f`. Chrome Tools/Home is gone. Slogan gone. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this extract+card wave:

1. the open review object card MUST show the freeze sentence once (MUST NOT duplicate it as both h3/title and body; compact row / card: one source sentence plus short status; the v2.16 compact-row bar applies to the open card, not only the list);
2. extract MUST NOT split a grammatical continuation of the previous sentence into a new object; trailing clauses (e.g. “Eventueel met hulp van de mantelzorger.”, “Bijvoorbeeld …”) MUST stay in the same knowledge object as the sentence they complete;
3. extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical to an object already emitted from this freeze; repeated HTML (samenvatting versus module) is not extra knowledge; distinct real headings in different sections MAY remain;
4. re-extract unpublished Continentie on the same freeze SHA-256 so the page can pass this bar; unpublished object identities MAY be replaced; MUST NOT hide stored fragments without that extract;

THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects and v2.17 researcher-surface remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta. The v2.17 researcher-surface wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure deploy, G2 PASS, Protocol v2.14, LLM, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–5, `publish()` PASS, Blob, managed identity, app settings, rewriting freeze bytes, treating `1.1 Inleiding` and `2. Inleiding` as identical, hiding stored fragments without a new extract.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (duplicate card sentence, truncated-sentence split, and identical freeze prose as extra objects bias assessment). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of a once-only card sentence, continuation-preserving extract, identical-`clean_text` suppression, or a new extract of unpublished Continentie remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 10. Gates and approval effect

Approval of v2.18 establishes that the review object card MUST show the freeze sentence once and MUST NOT duplicate it as both h3/title and body; that compact row / card is one source sentence plus short status; that the Protocol v2.16 compact-row bar applies to the open card, not only the list; that extract MUST NOT split a grammatical continuation of the previous sentence into a new object; that trailing clauses (e.g. “Eventueel met hulp van de mantelzorger.”, “Bijvoorbeeld …”) MUST stay in the same knowledge object as the sentence they complete; that this restates and tightens the Protocol v2.16 truncated-sentence / tiny-object forbid (the v2.17 Continentie re-extract still failed it); that extract MUST NOT emit a second knowledge object whose visible freeze prose (`clean_text`) is identical to an object already emitted from this freeze; that repeated HTML (samenvatting versus module) is not extra knowledge; that distinct real headings in different sections MAY remain (`1.1 Inleiding` versus `2. Inleiding` are not identical strings); that MUST NOT hide stored fragments without a new extract; that unpublished Continentie MAY be re-extracted after this law on the same source SHA-256; that unpublished object identities MAY be replaced; that Chrome Tools/Home remains gone (v2.17 held) and slogan remains gone (v2.17 held); and that this fail is duplication + truncated-sentence split. Serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this change. Next implementation is this extract+card wave, THEN William click-through, THEN Azure ZIP, THEN G2. It does not:

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
- add page, paragraph, stamp, strength, GRADE or chrome as stored object types;
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
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except the heading-proposal rules superseded by v2.16 stamps and by the v2.17 chrome rule;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except the list-only compact-row reading and the truncated-sentence reading tightened here;
- reopen Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation or compact-relation-checkbox rules except the next-implementation reading superseded here;
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
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–5;
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
