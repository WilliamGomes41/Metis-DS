# V&VN Data Services Protocol v2.17 — Review Page Researcher Surface

**Status:** Approved for project use  
**Protocol delta version:** 2.17.0  
**Approval date:** 2026-09-02  
**Approved by:** Project owner  
**Extends:** Protocol v2.16.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (slogan copy, via-negativa help, raw-HTML bronpassage, site chrome as objects, stamp UI on non-recommendation, and stretched relation checkboxes bias assessment)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.17 records the owner-approved lock of 2026-09-02 (William Gomes) after a local click-through of `main` `2b760b293b9a` following ingest of the real Continentie freeze (V&VN kennisplatform HTML, SHA-256 `ac59cf24f946088ef4e9529dffa43b59e2087ca1ab943b2f24cadf67451b5a2a`, snapshot `snap-ac59cf24f946088e-58ecef28`). Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). The problem is the researcher surface after the v2.16 bar was implemented: slogans, via-negativa help, a prefilled Onderwerp, raw HTML as bronpassage, and kennisplatform chrome extracted as objects. Those MUST NOT remain acceptable.

Live evidence the same day:

- 2833 objects: 1 document, 191 heading, 2641 unclassified.
- Review document picker had one door **Beoordeel** (good; Protocol v2.16 §4 remains).
- Object card two-column (good; 2026-08-29 lock remains).
- Researcher-facing slogan still on Review: “Wat jij bevestigt, wordt wat een EPD MAG zeggen.” / “Dit wordt wat een EPD MAG zeggen.” Owner: MAG eruit. EPD is not the only subscriber; a chatbot may also sit on Metis. Avoid slogans.
- Collapsed help “Over deze console” with HELP_ONCE via-negativa (“Interne operations console voor richtlijnonderzoekers… Chat is geen kamer…”) MAG eruit from researcher pages. Protocol v2.9 already said via-negativa MUST NOT be the primary on-screen copy.
- Ingest field Onderwerp is hardcoded `value="continentie"` in GET `/ingest`. Owner: the field MUST be empty on a fresh new ingest. This is not browser cache. Class MAY still default to `richtlijn` (closed set); this delta MUST NOT expand scope to class.
- Bronpassage right column rendered freeze HTML as `<pre>` of raw bytes (`</h3><div class="brxe-faadvp brxe-text"><p>…`). The researcher MUST see the same readable sentence as the knowledge object, without HTML tags, CSS class names, or kennisplatform markup. Protocol v2.11 freeze bytes and locators stay exact (MUST NOT reserialize or re-save the freeze). The researcher surface is visible prose derived from that locator, not the raw tag soup. Open-origineel remains required before type confirm.
- Extract emitted kennisplatform chrome as objects/headings (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated). Those MUST NOT be knowledge objects and MUST NOT land in Koppen. Koppen = real guideline TOC/section titles of the richtlijn body, not site nav.
- Owner photos the same day after PR #74 opened: (1) a review card titled **Tools**, unclassified, snippet the single word Tools, right column raw HTML of the kennisplatform nav (`<li class="menu-item … bricks-menu-item"><a href="https://kennisplatform.venvn.nl/tools/">Tools</a></li>`), and **Sterkte van de aanbeveling** (DOEN/OVERWEEG/NIET DOEN picker) on that Tools object; owner: “Je krijgt soms nogsteeds 1 woord”; (2) relations layout “Dit kennisobject is onderliggend aan:” with a checkbox far left and the label **Inleiding** far right, huge empty gap; owner: vinkje and Inleiding still lie very far apart; (3) bronpassage for the doelgroep sentence still shows `</h3><div class="brxe-faadvp brxe-text"><p>De richtlijn is bedoeld voor …`; owner asked “Is dat hoe het definitief eruit gaat zien?” — recorded answer NO. Owner: “Ik zie inleiding, doel, doelgroep en aanleiding vaker voorkomen; ik ga ervanuit dat dit voor meerdere delen geldt.” These MUST NOT remain. One-word chrome remains a fail (Protocol v2.16 tiny-objects plus this chrome rule). Stamps exist only on type `recommendation`. The v2.16 compact-row bar MUST also bind relation checkboxes. Bronpassage prose is per-object / whole freeze, not one card. Inleiding, Doel, Doelgroep and Aanleiding are examples of sections the law covers, not a closed list.
- 2641 unclassified on one richtlijn remains a fail of the review surface (Protocol v2.15 / v2.16 bar unchanged).
- Serving fail-closed unchanged: only confirmed `recommendation` MAY be `supported`. Four-eyes unchanged. `publish()` remains G2-BLOCKED. Capture is not publication. Unpublished Continentie MAY be re-extracted after this law; source SHA-256 stays; unpublished object identities MAY be replaced. MUST NOT hide stored fragments without a new extract.

Live baseline on `main` before this delta is Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0 and this delta jointly form normative baseline v2.17.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It does NOT reopen Protocol v2.11 freeze/locator (except the researcher-visible prose derived from those locators), Protocol v2.12 types/projection, Protocol v2.13 atomic objects/relations/four-eyes, Protocol v2.15 ingest-date/version/type-lanes, Protocol v2.16 one-door / stacks / compact-rows / stamps / tiny-objects (except the copy, help, Onderwerp, bronpassage-display, chrome-extract, stamp-UI-on-non-recommendation, stretched-relation-checkbox and next-implementation readings superseded here), G2, Azure, LLM, or Protocol v2.14 time/lifecycle. It does NOT reopen four-eyes or publish as C5. The v2.12 closed serving typeset remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types. Adding a type is a new protocol change. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, or chrome. Paragraph is display context, not a stored blob, not a new type. DOEN / OVERWEEG / NIET DOEN remain stamps on `recommendation`, not types.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession), all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded in section 4), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in section 6), all Protocol v2.12 type/review/projection rules, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules, and all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules remain in force, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object, stamp-UI-on-non-recommendation, stretched-relation-checkbox and next-implementation readings superseded in sections 3–9 and 12. This protocol-only change does not implement console Python, extract, kernel, Product API or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of any reading that (1) required or allowed the EPD MAG slogan as Review lead copy, including Protocol v2.16 §3 “why it matters (this becomes what an EPD may say)” and the entire sentence “Dit wordt wat een EPD MAG zeggen.”; (2) allowed HELP_ONCE via-negativa on researcher rooms, including Protocol v2.9 §4 “they MAY appear once in a short help”; (3) allowed a prefilled Onderwerp / family on a fresh new ingest; (4) allowed bronpassage to show raw HTML freeze slices as the researcher right column, including as a one-card exception; (5) allowed site chrome to be extracted as `heading` / `unclassified` objects or to land in Koppen, including a one-word **Tools** object; (6) allowed **Sterkte van de aanbeveling** / DOEN/OVERWEEG/NIET DOEN picker on a non-`recommendation` object; (7) allowed relation checkbox and target title to stretch to opposite edges of the viewport; or that the next console work after Protocol v2.16 is only the v2.16 door/stacks/rows/stamps/tiny-objects wave (that code is on `main`). Where this delta and those readings conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.16 §10 set the next console implementation as one door **Beoordeel**, two named stacks, compact rows, stamps, no tiny objects, and a new extract of unpublished Continentie. That code is now on `main`. Where this delta and Protocol v2.16 conflict on which implementation is next, this delta governs. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this wave (researcher copy without slogans; empty Onderwerp on a fresh ingest; bronpassage readable prose on every object; no chrome objects including one-word Tools/Home/Richtlijnen/Meedenken; recommendation-strength UI only on `recommendation`; compact relation checkboxes with label adjacent to the checkbox; re-extract unpublished Continentie). THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Protocol v2.14 is still not written and is still not the next step. v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes and v2.16 one-door/stacks/rows/stamps/tiny-objects remain required law, except the bounded supersessions in this file.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker.

Index/conflict pointer: Protocol v2.28.0 SUPERSEDES any reading of this file that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm, including the reading that recommendation-strength UI MAY appear on a machine-proposed `recommendation`. Where this file and Protocol v2.28 conflict on the Sterkte gate, Protocol v2.28 governs: Sterkte visible and active ONLY when stored/confirmed type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`; live UI before submit; previously chosen strength MUST NOT be actively saved after type changes away. v2.17 stamp-UI-on-recommendation and nav-word-MUST-NOT-get-a-picker law remain; the gate becomes confirmed/stored type. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

Index/conflict pointer: Protocol v2.30.0 SUPERSEDES any reading of this file that primary Relatie bevestigen is a mandatory chain, that the primary UI MUST always show a TOC list + full parent list, that Open volledige richtlijn / open-original MAY merely enlarge the same truncated card sentence, or that type UI MAY start from only “nog niet bevestigd” without a Metis proposal + evidence. Where this file and Protocol v2.30 conflict on reviewer passage-flow, Protocol v2.30 governs: primary UI MUST use ordinary language only (Gevonden onder / Dit klopt / Andere kop kiezen); Open volledige richtlijn / broncontext MUST show surrounding page/paragraph context with the exact span marked. v2.17 bronpassage-prose / chrome / compact-relation-checkbox law remain. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9, v2.10, v2.11, v2.12, v2.13, v2.15 and v2.16 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. The v2.10 console follow-up now exists in code. The v2.11 ingest lock, the v2.12 kernel, the v2.13 kernel, the two-column review card, the v2.15 ingest-date / ingest-version / heading-proposal / review-list-snippet / type-lane wave and the v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave now exist in code. Every rule in Protocol v2.6.0 remains mandatory, including:

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

Every rule in Protocol v2.9.0 remains mandatory, except the short-help via-negativa reading superseded in section 4, including:

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
- Extract MUST propose `heading` for real source headings / TOC / structural crumbs so they do not all land as `unclassified`, except the v2.16 stamp rule and the v2.17 chrome rule in section 7;
- Fast lane MUST support batch-confirm of proposed headings as structure, not advice; headings MUST NOT be served as handelingsadvies;
- Slow lane stays one-object (type + relations + high-risk four-eyes);
- Four thousand unclassified cards on one richtlijn is a fail of this review surface; 2641 unclassified on one richtlijn remains a fail (bar unchanged).

Every rule in Protocol v2.16.0 remains mandatory, except the slogan, HELP_ONCE via-negativa, prefilled-Onderwerp, raw-HTML-bronpassage, site-chrome-object and next-implementation readings superseded here, including:

- The Review page is the page that MUST convince guideline researchers; if they open it and it does not suffice, the project has failed — even if the kernel is fail-closed;
- One door **Beoordeel**; MUST NOT keep two doors **Openen** plus **Reviewen** that both lead to object lists;
- Two named stacks with counts: **Koppen** (real freeze TOC / section titles of the richtlijn body) and **Inhoud** (`definition`, `explanation`, `condition`, `exception`, `recommendation`, and `unclassified` until typed);
- Each list row MUST be one compact line: the freeze source sentence (or real heading text) plus a short status;
- DOEN / OVERWEEG / NIET DOEN are stamps on `recommendation`, not objects and not Koppen rows; extract MUST NOT heading-propose those words;
- Extract MUST NOT emit tiny objects (list-number-only, stamp-only, or a sentence fragment that cannot stand as one meaning unit);
- Unpublished Continentie: a new extract of the same freeze bytes is REQUIRED so the review page can pass the bar; source hash stays; unpublished object identities MAY be replaced; MUST NOT lie in the UI by hiding stored fragments without a new extract.

## 3. Researcher UI copy — no slogans

UI copy MUST be researcher language. MUST NOT be slogans. MUST NOT say “wat een EPD MAG zeggen”. MUST NOT claim a single subscriber class. EPD is not the only subscriber; a chatbot MAY also sit on Metis as a later Product API consumer. That fact MUST NOT become on-screen copy.

Lead copy MUST say what to do on this screen, without marketing. On Review that is: Beoordeel **Koppen** as structure, **Inhoud** as knowledge objects.

Owner evidence 2026-09-02 (`main` `2b760b293b9a`, Continentie): Review still showed “Wat jij bevestigt, wordt wat een EPD MAG zeggen.” and “Dit wordt wat een EPD MAG zeggen.” Those MUST NOT remain. The entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg. Keep this forbid; do not weaken it.

- Within one screen the researcher MUST know which document this is and what to do now (which stack, which primary button). The Protocol v2.16 “why it matters (this becomes what an EPD may say)” reading is superseded: lead copy MUST NOT add a slogan or a single-subscriber claim as the reason.
- Primary action MUST remain visually obvious. Kernel ids MUST NOT be the row title.
- On-screen copy MUST still say what the researcher can do here, what happens next, and what is expected of them (Protocol v2.9 §4 task copy), without slogans.
- MUST NOT use marketing statements, product promises, or subscriber-class claims as room lead copy.
- Example of lawful Review lead copy: “Beoordeel Koppen als structuur en Inhoud als kennisobjecten.” Example of forbidden copy: “Wat jij bevestigt, wordt wat een EPD MAG zeggen.” Forbidden also: the entire sentence “Dit wordt wat een EPD MAG zeggen.”

## 4. No via-negativa on researcher rooms

Via-negativa MUST NOT be the primary on-screen copy (Protocol v2.9 unchanged). This delta tightens that for researcher pages: via-negativa MUST NOT appear on researcher rooms at all, including collapsed help.

Owner evidence 2026-09-02: collapsed help “Over deze console” with HELP_ONCE via-negativa (“Interne operations console voor richtlijnonderzoekers… Chat is geen kamer…”) on researcher pages. MAG eruit.

- Researcher rooms are ingest, review (including the document picker and the object card), and Documentenhierarchie.
- Collapsed help titled “Over deze console” that explains what this is not, what does not happen, or who it is not for MUST NOT appear on those rooms.
- Protocol v2.9 §4 “Protocol constraints … MAY appear once in a short help, not as the heading of every room” is superseded for researcher rooms: that short help MUST NOT be the on-screen carrier of via-negativa there.
- Protocol constraints (not a nurse app, not chat, not the Product API, not publication) remain law off-screen. They MUST NOT be the researcher-facing copy.
- Too much protocol-prose on every room MUST NOT replace a short task heading and a visible next step (Protocol v2.9 unchanged).

## 5. Empty Onderwerp on a fresh ingest

The ingest field Onderwerp (researcher label for kernel family) MUST be empty on a fresh new ingest. The ingest researcher MUST set family (Protocol v2.8 unchanged). MUST NOT prefill `continentie` or any other family value.

Owner evidence 2026-09-02: GET `/ingest` hardcoded `value="continentie"`. This is not browser cache. MAG eruit.

- A new document ingest form MUST render Onderwerp / family empty.
- Empty family MUST NOT be accepted at ingest submit; the researcher fills it (Protocol v2.8: the ingest researcher MUST set family).
- This delta does not change class. Class MAY still default to `richtlijn` from the closed set unless a prior protocol already forbids that; this delta MUST NOT expand scope to class.
- Moving a source between families MUST NOT require clinical re-review; promoting class MUST require review (Protocol v2.8 unchanged).

## 6. Bronpassage is readable prose, not raw HTML

The researcher right column MUST show the same readable sentence as the knowledge object. MUST NOT show raw HTML freeze slices, HTML tags, CSS class names, or kennisplatform markup as the researcher surface.

Owner evidence 2026-09-02: bronpassage rendered freeze HTML as `<pre>` of raw bytes (`</h3><div class="brxe-faadvp brxe-text"><p>…`). Owner photo the same day after PR #74: bronpassage for the doelgroep sentence still shows `</h3><div class="brxe-faadvp brxe-text"><p>De richtlijn is bedoeld voor …`. Owner asked “Is dat hoe het definitief eruit gaat zien?” Recorded answer: **NO**. That MUST NOT remain.

- This bronpassage prose rule is **per-object / whole freeze**, not a one-off on one card. Same law for every object and every section.
- Researcher bronpassage MUST be the readable sentence, never tags. MUST NOT show raw HTML freeze slices, HTML tags, CSS class names, or kennisplatform markup as the researcher surface on any object.
- Protocol v2.11 freeze bytes and locators stay exact. MUST NOT reserialize, pretty-print, or re-save the freeze. Locators remain on freeze bytes (`provenance.source_fragments`; HTML `web_line_range`). This delta MUST NOT invent a locator scheme.
- The researcher surface is visible prose derived from that locator, not the raw tag soup.
- The left-column knowledge object and the right-column bronpassage MUST present the same readable sentence (the confirmable meaning unit), not a markup dump of the locator slice.
- Open-origineel remains required before type confirm (Protocol v2.13 unchanged). Type confirmation without that flow remains unacceptable.
- The two-column card (object left, bronpassage right; stack on narrow) remains required.
- Non-binding implementer hunch (MUST be verified in the later implementation, not in this protocol change): `open_source_passage` / `passage_from_html_freeze` returns a raw HTML line slice; the card dumps it in `<pre>`. Strip tags only for display; locators stay on freeze bytes. This hunch is not a protocol requirement of those function names.

## 7. Site chrome MUST NOT be knowledge objects or Koppen

Extract MUST NOT emit kennisplatform chrome as knowledge objects and MUST NOT land that chrome in Koppen. Koppen MUST be real guideline TOC / section titles of the richtlijn body, not site nav.

Owner evidence 2026-09-02: extract emitted kennisplatform chrome as objects/headings (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated). Owner photo the same day after PR #74: a review card titled **Tools**, unclassified, snippet the single word Tools, right column raw HTML of the kennisplatform nav (`<li class="menu-item … bricks-menu-item"><a href="https://kennisplatform.venvn.nl/tools/">Tools</a></li>`). Owner: “Je krijgt soms nogsteeds 1 woord”. Those MUST NOT remain.

- One-word site chrome MUST NOT be an object. One-word chrome remains a fail under Protocol v2.16 tiny-objects **and** this chrome rule. Tools, Home, Richtlijnen, Meedenken and the rest of kennisplatform nav MUST NOT be knowledge objects.
- Chrome includes site navigation, platform chrome, duplicated nav labels, and kennisplatform shell headings that are not titles of the richtlijn body. The listed labels are evidence, not an exhaustive closed set.
- Chrome MUST NOT become `heading`. Chrome MUST NOT become `unclassified`. Chrome MUST NOT become any other stored object type.
- Recommendation-strength UI (**Sterkte van de aanbeveling**, the DOEN/OVERWEEG/NIET DOEN picker) MUST NOT appear except on type `recommendation`. A nav word MUST NOT get a recommendation-strength control. Stamps exist only on type `recommendation` (Protocol v2.16 unchanged). Showing that picker on unclassified **Tools** is forbidden.
- **Koppen** remains the v2.15 fast lane under a researcher name: real table-of-contents / section titles from the freeze (structure). Batch-confirm as structure, never as advice. Headings MUST NOT be served as handelingsadvies.
- Extract MUST still propose `heading` for real source headings / TOC / structural crumbs of the richtlijn body so they do not all land as `unclassified` (Protocol v2.15), except DOEN/OVERWEEG/NIET DOEN (Protocol v2.16) and chrome (this delta).
- Where this sentence and Protocol v2.15 “Extract MUST propose `heading` for real source headings / TOC / structural crumbs” conflict for site chrome, this delta governs.
- MUST NOT add a new object type for chrome, page, or nav. Chrome is not stored.

## 8. Compact relation checkboxes

Protocol v2.16 already forbade stretching status / checkbox / text into disconnected columns across the viewport. That bar MUST also bind relation checkboxes on the object card.

Owner photo 2026-09-02 after PR #74: “Dit kennisobject is onderliggend aan:” then a checkbox far left and the label **Inleiding** far right, huge empty gap. Owner: vinkje and Inleiding still lie very far apart. That MUST NOT remain.

- The relation label MUST sit immediately next to its checkbox.
- MUST NOT stretch checkbox and target title to opposite edges of the viewport.
- A checkbox MAY sit on the same compact line as its target title. It MUST NOT float in a far-left column with empty white space to the title.
- This is the same compact-row law as Protocol v2.16 §6, applied to relation checkboxes (`applies_if`, `except_if`, `defines`, `explains`, `supported_by`, `supersedes`, `parent` / `child`, including “onderliggend aan”).
- MUST NOT invent a relation-graph editor (Protocol v2.13 / 2026-08-29 lock unchanged).

## 9. Whole freeze, every object, every section

These rules (no slogans, no one-word chrome, compact relation checkboxes, bronpassage prose not HTML, recommendation-strength UI only on `recommendation`) apply to the **whole freeze / every object / every section**. Not a one-off on one card.

Owner: “Ik zie inleiding, doel, doelgroep en aanleiding vaker voorkomen; ik ga ervanuit dat dit voor meerdere delen geldt.” Confirmed.

- **Inleiding**, **Doel**, **Doelgroep** and **Aanleiding** are examples of sections the law covers, not a closed list.
- The rest of the richtlijn body is in scope on the same terms. Operators MUST NOT treat a later section as exempt because the photo was of Tools, Inleiding, or doelgroep.
- Same law for Koppen and Inhoud. Same law for every object version extracted from this freeze.

## 10. Unclassified bar unchanged; unpublished Continentie re-extract

2641 unclassified on one richtlijn remains a fail of the review surface. The Protocol v2.15 / v2.16 bar is unchanged: a page of thousands of identical `unclassified` titles, tiny objects, or chrome-as-objects MUST NOT be accepted as workload.

Freeze source bytes and SHA-256 stay. Existing published objects are not silently rewritten (there is no published projection). Continentie is unpublished: a new extract of the same freeze bytes is REQUIRED so the review page can meet this bar (no chrome objects; no tiny objects; Koppen = richtlijn body TOC; bronpassage readable prose on the same freeze locators). Source hash of the freeze stays. Unpublished object identities MAY be replaced by that new extract. MUST NOT hide stored fragments without a new extract.

- MUST NOT lie in the UI by hiding stored fragments without that new extract. Hiding is lying; a new extract is the lawful fix.
- Published objects, if any later exist, MUST NOT be silently rewritten. Identity of published hashed objects stays until a new source version / snapshot under existing v2.7 / v2.12 / v2.13 rules.
- This delta MUST NOT rewrite Protocol v2.13 split rules except as already bounded by Protocol v2.16 tiny objects. Token-budget chunking still MUST NOT define object identity. Fusion of condition into recommendation remains the forbidden default.

## 11. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged. G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication.

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

## 12. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the Review page has researcher copy without slogans, empty Onderwerp on a fresh ingest, bronpassage readable prose on every object, an extract that does not emit chrome (including one-word Tools) as objects, recommendation-strength UI only on `recommendation`, and relation checkboxes with the label adjacent to the checkbox.

Where this delta and Protocol v2.16 conflict on which implementation is next, this delta governs. The v2.16 one-door / stacks / compact-rows / stamps / tiny-objects wave is already in code on `main`. The next implementation after this protocol merges MUST be the Implementation engineer on the existing kernel/console for exactly this wave:

1. researcher copy without slogans (lead copy says what to do: Beoordeel Koppen as structure, Inhoud as knowledge objects; MUST NOT say “wat een EPD MAG zeggen”; the entire sentence “Dit wordt wat een EPD MAG zeggen.” MAG weg; MUST NOT claim a single subscriber class);
2. empty Onderwerp / family on a fresh new ingest;
3. bronpassage right column as readable prose derived from the v2.11 locator on **every object** (MUST NOT dump raw HTML tag soup; freeze bytes stay exact; recorded answer to “Is dat hoe het definitief eruit gaat zien?” is NO);
4. extract MUST NOT emit kennisplatform chrome as knowledge objects or Koppen, including one-word Tools/Home/Richtlijnen/Meedenken;
5. recommendation-strength UI (**Sterkte van de aanbeveling**) MUST NOT appear except on type `recommendation`;
6. relation checkbox and its label MUST be adjacent (MUST NOT stretch across the viewport);
7. re-extract unpublished Continentie on the same freeze SHA-256 so the page can pass this bar on the whole freeze; unpublished object identities MAY be replaced; MUST NOT hide stored fragments without that extract;

THEN William click-through of the running console (not screenshots). THEN Azure ZIP of that `main` from a V&VN-trusted device. THEN G2. Do not start Azure in this change. Azure ZIP is after William accepts the live Review page. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes and v2.16 one-door/stacks/rows/stamps/tiny-objects remain required law, except the bounded supersessions in this file. The v2.10 console follow-up is already in code and MUST NOT be reopened by this delta. The 2026-08-29 two-column review card is already in code and is not the next implementation after this delta. The v2.15 ingest/lanes wave is already in code and is not the next implementation after this delta. The v2.16 door/stacks/stamps wave is already in code and is not the next implementation after this delta.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: Azure deploy, G2 PASS, Protocol v2.14, LLM, Vercel/Neon, new object types, GRADE English labels, relation-graph editor, huisstyle-bar-only tweaks without the bar in sections 3–9, `publish()` PASS, Blob, managed identity, app settings, expanding empty-Onderwerp to class default, rewriting freeze bytes.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 13. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (slogan copy, via-negativa help, raw-HTML bronpassage, site chrome as objects, stamp UI on non-recommendation, and stretched relation checkboxes bias assessment). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff.

Any later implementation of researcher copy without slogans, empty Onderwerp on a fresh ingest, bronpassage readable prose, chrome suppression, stamp UI only on `recommendation`, compact relation checkboxes, or a new extract of unpublished Continentie remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 14. Gates and approval effect

Approval of v2.17 establishes that UI copy MUST be researcher language and MUST NOT be slogans, MUST NOT say “wat een EPD MAG zeggen”, MUST NOT keep the entire sentence “Dit wordt wat een EPD MAG zeggen.”, and MUST NOT claim a single subscriber class; that Review lead copy MUST say what to do on this screen (Beoordeel Koppen as structure, Inhoud as knowledge objects) without marketing; that via-negativa MUST NOT appear on researcher rooms including collapsed help “Over deze console”; that Onderwerp / family MUST be empty on a fresh new ingest and MUST NOT be prefilled `continentie`; that bronpassage MUST show the same readable sentence as the knowledge object without HTML tags, CSS class names, or kennisplatform markup, on every object / the whole freeze (recorded answer to “Is dat hoe het definitief eruit gaat zien?” is NO), while v2.11 freeze bytes and locators stay exact (MUST NOT reserialize or re-save the freeze); that Open-origineel remains required before type confirm; that extract MUST NOT emit kennisplatform chrome as knowledge objects or Koppen, including one-word Tools/Home/Richtlijnen/Meedenken (Koppen = real guideline TOC / section titles of the richtlijn body, not site nav); that recommendation-strength UI MUST NOT appear except on type `recommendation`; that relation checkbox and its label MUST be adjacent (MUST NOT stretch across the viewport); that these rules apply to the whole freeze / every object / every section (Inleiding, Doel, Doelgroep, Aanleiding are examples, not a closed list); that 2641 unclassified on one richtlijn remains a fail of the review surface (v2.15 / v2.16 bar unchanged); and that unpublished Continentie MAY be re-extracted after this law on the same source SHA-256, unpublished object identities MAY be replaced, and MUST NOT hide stored fragments without a new extract. Serving / G2 unchanged: only confirmed `recommendation` MAY `supported` / handelingsadvies; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged; G2 remains the publication blocker; `publish()` remains G2-BLOCKED; capture is not publication. It does not:

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
- emit kennisplatform chrome (Home, Richtlijnen, Meedenken, Kennisinstituut V&VN, Tools, Veelgestelde vragen, duplicated nav) as knowledge objects or Koppen;
- fuse condition into recommendation, or reopen that Protocol v2.13 forbid;
- lie in the UI by hiding stored fragments without a new extract;
- silently rewrite published objects (there is no published projection);
- rewrite Protocol v2.13 split rules beyond forbidding tiny objects that cannot stand as one meaning unit;
- reopen Protocol v2.11 freeze/locator except researcher-visible prose derived from those locators;
- reserialize or re-save freeze bytes, or bind locators to reserialized HTML;
- dump raw HTML tag soup, CSS class names or kennisplatform markup as the researcher bronpassage;
- reopen Protocol v2.12 types/projection, or Protocol v2.13 atomic objects/relations/four-eyes;
- reopen Protocol v2.15 ingest date, ingest version, or type-based lanes except the heading-proposal rules superseded by v2.16 stamps and by this chrome rule;
- reopen Protocol v2.16 one-door, two-stack, compact-row, stamp or tiny-object rules except the slogan, help, Onderwerp, bronpassage-display, chrome-extract, stamp-UI-on-non-recommendation, stretched-relation-checkbox and next-implementation readings superseded here;
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
- implement Blob, managed identity, or huisstyle-bar-only tweaks without the bar in sections 3–9;
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
