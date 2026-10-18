# V&VN Data Services Protocol v2.9 — Console UX and Brand

**Status:** Approved for project use  
**Protocol delta version:** 2.9.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.8.0  
**Highest change class:** C3 (source/review/publish loop; the console is the human door of that loop)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.9 records the owner-approved evaluation of the 2026-08-28 console-MVP walkthrough. The project owner clicked through the internal operations console as a researcher. The kernel (ingest, family, review, publish, promote) is logically right. The researcher-facing UI is still a technical data-model dump: stacked HTML forms of equal weight, too much text, via-negativa copy, buried actions, and kernel words on screen.

This delta adds researcher-task UX and V&VN digital-brand rules to that human door. It does not reopen rooms, ingest types, users or hierarchy.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0 and this delta jointly form normative baseline v2.9.0. All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules, and all Protocol v2.8 primary-user and two-axis hierarchy rules remain in force, except the sequencing sentences superseded in section 10. This protocol-only change does not implement UI or product code. Do not rewrite `src/operations_console_*.py` in this protocol change. Do not claim the stacked data-model dump is the lasting researcher surface.

This delta is a **scoped supersession** of Protocol v2.8 §6 only as it sets the next concrete implementation after the console-MVP exists. Where this delta and that sequencing sentence conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. For all other requirements, the stricter fail-closed requirement applies.

## 2. Unchanged v2.6, v2.7 and v2.8 rules

The internal operations console remains authorized DS scope. The console-MVP ingest+review loop now exists in code on the existing kernel. Every rule in Protocol v2.6.0 remains mandatory, including:

- four rooms that are not four buttons for one person: ingest (mailbox), review (mandatory return loop; the uploader MAY also be a reviewer and MUST NOT be the only required reviewer), publish (a separate authorized act), analytics last;
- identity (researcher, reviewer, publisher); no shared login for review or publish; internal identity, not public signup;
- chat is not a room in this console;
- a care-app frontend, a chatbot as a product surface, an EPD/ECD UI and a public website MUST NOT live in this repository;
- engineers MUST NOT submit sources through the ingest room.

Every rule in Protocol v2.7.0 remains mandatory, including:

- first-wave official files MUST be the HTML page and the PDF only; kennisplatform `story.html` boom players MUST be out of the first wave;
- the official file MUST be the kennisplatform freeze, not a living Word document;
- ingest MUST accept a file upload or a URL; a URL MUST be snapshotted to exact bytes immediately at ingest;
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

## 3. Task-oriented researcher surface

The console MUST be a task-oriented researcher surface, not a dump of the kernel data model.

- The primary action on each room MUST be visually obvious.
- Visual hierarchy MUST distinguish sections and next steps.
- Stacked unlabeled HTML forms with equal weight MUST NOT be the console UX.
- The 2026-08-28 mailbox (stacked technical fields, kernel vocabulary, buried submit) MUST NOT remain the lasting researcher surface.

Kernel correctness is not UX completeness. A form that can submit an envelope is not, by itself, a researcher task.

## 4. Copy

On-screen copy MUST say:

- what the researcher can do here;
- what happens next;
- what is expected of them.

Via-negativa (what this is not, what does not happen, who it is not for) MUST NOT be the primary on-screen copy. Protocol constraints (not a nurse app, not chat, not the Product API, not publication) remain law off-screen; they MAY appear once in a short help, not as the heading of every room.

Too much protocol-prose on every room MUST NOT replace a short task heading and a visible next step.

## 5. Researcher vocabulary

UI vocabulary MUST be researcher language: document, titel, versie, familie, klasse, status, inleveren, review, publiceren.

- MUST NOT use "envelope" as a UI term. Envelope remains a conversation metaphor only (Protocol v2.6 mailbox talk). It MUST NOT appear as a label, heading, button, empty-state or field name.
- MUST NOT ask a researcher to type or pick a "snapshot" id. Snapshot remains an internal kernel identifier.
- Move-between-families and promote-class MUST operate on a visible document (title + version + family), not a blank snapshot field.

Internal logs, hashes, locators and object ids MAY remain in technical detail or help. They MUST NOT be the primary way a researcher names or selects work.

## 6. Login

Login MUST ask for gebruikersnaam AND wachtwoord.

- No shared login.
- No open registration.
- The password field MUST be `type=password`.
- Internal identity remains required (researcher, reviewer, publisher) as in Protocol v2.6. This delta does not select an identity vendor, provision Azure AD, or close G8.

## 7. Move and promote as actions

Move-between-families and promote-class MUST look like real clickable actions, not buried extra forms.

A curator MUST be able to move a visible document to another family without typing a kernel id. Promoting class MUST remain a review-requiring act as in Protocol v2.8, presented as an action on that document, not as a second unlabeled form at the bottom of the tree.

## 8. Brand — V&VN digital stylesheet

The console MUST use the V&VN digital stylesheet (official digital huisstyle: beeldmerk and digital colours; HK Grotesk and Raleway Bold). Photography rules in that stylesheet remain brand guidance for any photo used in the console. This delta does not add a photo library.

### 8.1 Primary digital colours

| Name | Hex | Use |
|---|---|---|
| Rood | `#E23100` | Logo and accent only |
| Paars | `#5D3297` | Primary digital colour |
| Zwart | `#000000` | Logo and accent only |
| Wit | `#FFFFFF` | Surfaces, text on saturated colour where contrast requires it |

Red and black are the colours of the logo. They MUST be used as accent colours. They MUST NOT be used for large surfaces, such as backgrounds.

### 8.2 Secondary digital colours

Saturated secondary colours are for header text on white. Light variants are for backgrounds. Choose only one secondary colour family per view. MUST NOT mix colour families (for example MUST NOT use a blue background with green type).

| Family | Saturated (headers on white) | Light (backgrounds) |
|---|---|---|
| Zalm | `#E28080` | `#FDEFEB` |
| Water | `#45AAC7` | `#EAF8F8` |
| Gras | `#6FA57D` | `#EDFAF0` |
| Bamboe | `#E2A659` | `#FCF8EA` |

### 8.3 Typography

- **HK Grotesk** is the primary typeface for body text (regular and bold; italic MAY be used for accents).
- **Raleway Bold** is the secondary typeface and MUST be used for headlines (kopteksten), primary buttons (primaire knoppen) and statements.

### 8.4 Licensed fonts and fail-closed fallback

Licensed font files are not in this repository. If an implementation ships HK Grotesk or Raleway Bold, those files MUST come from a V&VN-licensed path, documented in that implementation. The recommended path is `assets/brand/fonts/` (HK Grotesk Regular/Bold/Italic and Raleway Bold).

If a licensed font file is not present, the implementation MUST fail closed to this documented system stack and MUST NOT pirate fonts:

- body fallback: `ui-sans-serif, system-ui, sans-serif`;
- heading, primary-button and statement fallback: the same stack at `font-weight: 700`.

MUST NOT fetch unlicensed copies from a public CDN as a substitute. MUST NOT commit the official Canva/PDF stylesheet into git (`*.pdf` is already gitignored). MUST NOT put source binaries or secrets in git.

### 8.5 Logo

The logo is the v&vn beeldmerk (first `v` rood `#E23100`, `&` paars `#5D3297`, second `v` rood `#E23100`, `n` zwart `#000000`). Use it as a brand mark, not as decoration wallpaper.

## 9. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, or EPD UI. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement the new UI.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Vercel, Neon, or LLM vendor.

## 10. Build order

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before researchers have a usable task-oriented console.

The next implementation after this delta MUST be a console UX rewrite on the existing kernel (ingest, family tree, review return-loop, local G0 identity, `sources/private/` as the G0 stand-in):

- task-oriented rooms with a visually obvious primary action;
- researcher vocabulary and copy as in sections 4–5;
- visible move and promote actions as in section 7;
- V&VN digital stylesheet as in section 8;
- login as in section 6.

That rewrite MUST NOT invent Azure, Vercel or Neon as in-scope. MUST NOT rebuild the Product API first. MUST NOT add chat as a room. MUST NOT design for nurses. Analytics remains later. The publish room remains a small third room after the review-loop works, and remains fail-closed without an immutable locator (G2).

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next UI implementation.

This protocol-only change does not itself implement that UX rewrite. Do not change `src/operations_console_*.py` in this protocol change.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is the human door of the source/review/publish loop. Treat the highest class as **C3** (canonical/review; console as the human door of that loop).

This delta is owner-approved. Named C3 reviewers are not yet staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5).

Any later implementation of the console UX rewrite, brand assets, or licensed-font loading remains separately classified, including at least C3.

## 12. Gates and approval effect

Approval of v2.9 establishes the researcher-task UX and V&VN digital-brand rules. It does not:

- implement the new UI, any room rewrite, any account change, or any Product API behaviour change;
- claim that the stacked HTML dump is the lasting researcher surface;
- authorize a mockup, Azure, Vercel or Neon as the next implementation;
- skip durable immutable storage or convert G2 to PASS;
- select an identity vendor, provision Azure AD, or convert G0 Azure DEV, G7 or G8 to PASS;
- introduce Vercel, Neon or an LLM vendor;
- publish a source or knowledge object;
- authorize an external consumer or onboard the first paying subscriber;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- design the console for nurses;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- pirate fonts or commit unlicensed font files;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
