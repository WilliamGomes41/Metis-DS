# V&VN Data Services Protocol v2.11 — HTML Freeze File and Source Locator

**Status:** Approved for project use  
**Protocol delta version:** 2.11.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.10.0  
**Highest change class:** C3 (source/review/publish / retrieve safety)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.11 records the owner-approved lock of 2026-08-28 after sparring source locators. Do NOT ban HTML entirely. The kennisplatform freeze is often HTML; Continentie first envelope would stall if HTML were banned.

Official first-wave HTML MUST be an uploaded freeze file (exact bytes). Live URL-HTML MUST be rejected at ingest: the kennisplatform page is an app shell; line locators would bind to the wrong bytes. HTML line-range locators are acceptable for first wave on uploaded freeze bytes. They are not an excuse to scrape a live URL.

This delta does not reopen rooms, users, hierarchy, brand, console nav, or G2. It does not implement console or product UI.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0 and this delta jointly form normative baseline v2.11.0. All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules, all Protocol v2.8 primary-user and two-axis hierarchy rules, all Protocol v2.9 researcher-task UX and V&VN digital-brand rules, and all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules remain in force, except the ingest sentence superseded in section 3. This protocol-only change does not implement UI or product code. Do not rewrite `src/operations_console_*.py` or `src/product_api_*.py` in this protocol change.

This delta is a **scoped supersession** of Protocol v2.7 only as it said ingest MUST accept a URL for official files without distinguishing HTML vs PDF. Where this delta and that sentence conflict for HTML, this delta governs. File-upload HTML/PDF and immediate byte freeze of an uploaded file remain mandatory. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

This delta also sets the next concrete implementation after merge. Protocol v2.10 §8 set the next implementation as a console follow-up (Documentenhierarchie, waiting-task badges, Accounts). That console follow-up remains required. Where this delta and Protocol v2.10 §8 conflict on which implementation is next, this delta governs.

## 2. Unchanged v2.6, v2.7, v2.8, v2.9 and v2.10 rules

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. The v2.9 UX rewrite now exists in code. Every rule in Protocol v2.6.0 remains mandatory, including:

- four rooms that are not four buttons for one person: ingest (mailbox), review (mandatory return loop; the uploader MAY also be a reviewer and MUST NOT be the only required reviewer), publish (a separate authorized act), analytics last;
- identity (researcher, reviewer, publisher); no shared login for review or publish; internal identity, not public signup;
- chat is not a room in this console;
- a care-app frontend, a chatbot as a product surface, an EPD/ECD UI and a public website MUST NOT live in this repository;
- engineers MUST NOT submit sources through the ingest room.

Every rule in Protocol v2.7.0 remains mandatory, except the undifferentiated URL-ingest sentence superseded in section 3, including:

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

## 3. HTML freeze file versus live URL-HTML

Do NOT ban HTML entirely.

Official first-wave HTML MUST be an uploaded freeze file (exact bytes).

- Live URL-HTML MUST be rejected at ingest. The kennisplatform page is an app shell; line locators would bind to the wrong bytes.
- PDF upload remains in.
- URL ingest of a PDF MAY remain (bytes are the PDF).
- URL ingest of HTML MUST NOT.
- File-upload HTML/PDF and immediate byte freeze of an uploaded file remain mandatory.
- A URL of HTML MUST NOT be treated as an official first-wave file, even if a fetcher could snapshot bytes. Capture of live URL-HTML is not a freeze of the official file.

The official file remains the kennisplatform freeze, not a living Word document, as in Protocol v2.7. kennisplatform `story.html` boom players remain out of the first wave.

HTML line-range locators are acceptable for first wave on uploaded freeze bytes. They are not an excuse to scrape a live URL.

Capture remains not publication. The G2 locator still required to publish. A captured freeze is not a published object.

## 4. Source locators on knowledge objects

Knowledge objects MUST carry enough source context to return to the exact place in that hashed original.

The schema already has `provenance.source_fragments` (page, bbox, `source_locator`). That contract remains mandatory.

- PDF extract uses `page_bbox`.
- HTML extract uses `web_line_range` against those freeze bytes. A `web_line_range` locator is stable only if the freeze is never reserialized.
- HTML line-range locators are acceptable for first wave on uploaded freeze bytes.
- Reserializing, pretty-printing, or re-saving the freeze bytes MUST NOT be used as ingest. A locator bound to reserialized HTML is not a locator into the hashed original.

A source locator MUST be present and non-empty on each knowledge object that is eligible to retrieve as `supported`. An empty `source_locator`, a missing `source_locator`, or a fragment that cannot return to the exact place in the hashed freeze MUST NOT be treated as sufficient provenance.

## 5. Product API fail-closed without a source locator

The Product API MUST NOT return `supported` if the object's source locator is missing/empty. Fail-closed. Abstain instead (catalog sentence, no LLM).

- A `supported` result still MUST carry V and VN labels, as in Protocol v2.7.
- Unpublished branch objects MUST still abstain even if the trunk is published.
- DS MUST NOT generate prose. No LLM in the MVP.
- abstain MUST remain a closed sentence catalog maintained in the console and reviewed like a tiny guideline.
- Missing or empty source locator is a retrieve-safety abstain, not a licence to invent a locator or to scrape a live URL at query time.

This fail-closed retrieve rule does not convert G2 to PASS. Publication remains BLOCKED without an immutable locator, as in existing G2 rules.

## 6. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement ingest rejection or API fail-closed. This delta does not implement the new UI.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor.

## 7. Build order

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the kernel rejects live URL-HTML and fail-closes `supported` without a source locator.

The next implementation after this delta MUST be the Implementation engineer on the existing kernel:

- reject live URL-HTML at ingest;
- fail-closed Product API `supported` without a source locator;

on the existing kernel (ingest, family × class tree, review return-loop, local G0 identity, `sources/private/` as the G0 stand-in, Product API retrieve-and-abstain). File-upload HTML/PDF and immediate byte freeze of an uploaded file remain mandatory. URL ingest of a PDF MAY remain. HTML line-range locators remain acceptable on uploaded freeze bytes that are never reserialized.

This protocol-only change does not implement ingest rejection or API fail-closed. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py` or `src/product_api_*.py` in this protocol change.

That follow-up MUST NOT invent Azure, Vercel or Neon as in-scope. MUST NOT scrape a live URL as a substitute for an uploaded freeze. MUST NOT ban HTML entirely. MUST NOT add chat as a room. MUST NOT design for nurses. The Documentenhierarchie / waiting-task badge / Accounts console follow-up from Protocol v2.10 remains required and is not skipped; it is not the next implementation after this delta. Analytics remains later. The publish room remains fail-closed without an immutable locator (G2).

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 8. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is source/review/publish and retrieve safety. Treat the highest class as **C3** (source/review/publish / retrieve safety).

This delta is owner-approved. Named C3 reviewers are not yet staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not reopen GD-03.

Any later implementation of live URL-HTML ingest rejection, freeze-byte preservation, or Product API fail-closed `supported` without a source locator remains separately classified, including at least C3.

## 9. Gates and approval effect

Approval of v2.11 establishes uploaded HTML freeze files, rejection of live URL-HTML at ingest, mandatory source locators on knowledge objects, and fail-closed Product API abstain when a source locator is missing or empty. It does not:

- implement ingest rejection, freeze storage, Product API fail-closed behaviour, any room rewrite, or any other product code;
- ban HTML entirely;
- authorize scraping a live URL, reserializing freeze bytes, or binding line locators to an app shell;
- treat capture as publication, or convert G2 to PASS;
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
- open the role set or allow operators to invent new role types;
- allow open registration or shared login;
- let AI, Grok Bot, Metis, the Implementation engineer or the Auditor be created as required reviewers;
- let the uploader be the only required reviewer;
- require clinical re-review for a family move;
- waive review when promoting class;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- pirate fonts or commit unlicensed font files;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
