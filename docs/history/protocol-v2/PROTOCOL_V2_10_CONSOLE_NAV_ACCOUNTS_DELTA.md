# V&VN Data Services Protocol v2.10 — Console Nav, Waiting-Task Badges, and Accounts

**Status:** Approved for project use  
**Protocol delta version:** 2.10.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.9.0  
**Highest change class:** C5 (identity/access) spanning C3 (console rooms/nav)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.10 records the owner-approved evaluation of 2026-08-28 after the project owner used the v2.9 researcher console. The kernel model remains family × class. Three researcher-facing gaps remain: the console room heading "Familieboom" is specialist jargon; top navigation does not show real waiting work; account creation and role assignment have no researcher-facing room (bootstrap remains the CLI).

This delta adds UI vocabulary, waiting-task badges and an Accounts room. It does not reopen ingest types, class/family review rules, brand, or G2.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0 and this delta jointly form normative baseline v2.10.0. All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules, all Protocol v2.8 primary-user and two-axis hierarchy rules, and all Protocol v2.9 researcher-task UX and V&VN digital-brand rules remain in force, except the sequencing sentences superseded in section 8. This protocol-only change does not implement UI or product code. Do not rewrite `src/operations_console_*.py` in this protocol change.

This delta is a **scoped supersession** of Protocol v2.9 §10 only as it sets the next concrete implementation after the console UX rewrite is in progress. Where this delta and that sequencing sentence conflict, this delta governs. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. For all other requirements, the stricter fail-closed requirement applies.

## 2. Unchanged v2.6, v2.7, v2.8 and v2.9 rules

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

Every rule in Protocol v2.9.0 remains mandatory, including:

- The console MUST be a task-oriented researcher surface, not a dump of the kernel data model;
- via-negativa MUST NOT be the primary on-screen copy;
- UI vocabulary MUST be researcher language; MUST NOT use "envelope" as a UI term; MUST NOT ask a researcher to type or pick a "snapshot" id;
- Login MUST ask for gebruikersnaam AND wachtwoord; no shared login; no open registration; the password field MUST be `type=password`;
- the console MUST use the V&VN digital stylesheet.

## 3. Documentenhierarchie (UI vocabulary only)

The console room currently labelled "Familieboom" MUST be renamed **Documentenhierarchie**.

- Documentenhierarchie is ordinary Dutch for the researcher-facing tree of documents.
- The kernel model remains family × class. Family remains a hook, not a new file.
- This is UI vocabulary only. It MUST NOT invent a new file, a new object type, or a third hierarchy axis.
- "Familieboom" MUST NOT remain the lasting top-nav heading.
- Researchers MUST NOT be asked for snapshot ids. Snapshot remains an internal kernel identifier, as in Protocol v2.9.
- Researcher terms familie and klasse remain valid on-screen for the two axes. The room heading is Documentenhierarchie.

## 4. Waiting-task badges

Each top nav heading MUST show a visible waiting-task badge (a count, for example "1") when that room has work for the current user.

- The badge MUST be absent or zero-hidden when nothing waits for that user in that room.
- Counts MUST be real kernel work, not decoration. A painted number, a static "0", or a badge that does not match a kernel queue MUST NOT be used.
- Badges are per current user. A global or shared count MUST NOT substitute for that user's queue.
- **Review** = objects or documents in `needs_review` assigned to this reviewer, or waiting on named reviewers including this user.
- **Publish** = captured documents this publisher can consider. The Publish badge MUST NOT imply that publication passed G2. A countable queue of captured documents is not a publication authorization.
- **Ingest** = drafts or returns waiting on this researcher if such a queue exists, else 0.
- **Documentenhierarchie** MAY badge documents awaiting family/class action for this curator.
- **Accounts** has no waiting-task queue in the MVP; its badge MUST be absent or zero-hidden.
- Analytics, if present as a heading, follows the same rule and is 0 until real traffic creates a defined queue.
- A badge MUST NOT be used to claim that G2, G0 Azure DEV, G7 or G8 has passed.

## 5. Accounts room

The console MUST include an **Accounts** room. Accounts is identity administration. It is not chat. It is not a fifth clinical room replacing ingest, review or publish. The four clinical rooms remain ingest, review, publish, and analytics last.

A permitted actor MUST be able to:

- create a user (username, display name, password);
- assign roles;
- change role assignment.

The role set remains **CLOSED**: `researcher`, `reviewer`, `publisher` only.

- Operators MUST NOT invent new role types in the MVP.
- "Create a role" in owner talk means assign one of those three closed roles, not a free-form RBAC editor.
- The Accounts room MUST NOT be a role-type editor.
- No open registration.
- No shared login.
- Login still username AND password, as in Protocol v2.9.

AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT be creatable as required reviewers. Those identities MUST NOT be created as accounts that can serve as required reviewers, MUST NOT count as required reviewers, MUST NOT approve, and MUST NOT publish.

The uploader MUST NOT be the only required reviewer (unchanged from Protocol v2.6). That rule MUST remain enforced in accounts, not as a social rule.

Who may manage accounts: an actor with the **publisher** role (internal identity admin for the MVP). Other roles MUST NOT create users or change role assignment.

First bootstrap via the existing CLI `console-account` remains valid. The Accounts room does not replace that bootstrap; it is the operator surface after a publisher exists. This delta does not select an identity vendor, provision Azure AD, or close G8.

## 6. Unchanged class and family review rules

Promoting class still MUST require a new review (already Protocol v2.8). Family move still MUST NOT require clinical re-review. That move remains a curator act.

If later evidence shows that family moves change meaning, that is a new protocol change, not a silent extra review.

The console tree remains family × class. Each file MUST keep its own hash.

## 7. Unchanged fail-closed product boundary

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

## 8. Build order

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before researchers have Documentenhierarchie, real waiting-task badges and an Accounts room.

The next implementation after this delta MUST be a console follow-up on the v2.9 UX (open PR #25 if still open):

- rename the console room "Familieboom" to "Documentenhierarchie";
- waiting-task badges as in section 4;
- Accounts room as in section 5;

on the existing kernel (ingest, family × class tree, review return-loop, local G0 identity, `sources/private/` as the G0 stand-in). Task-oriented rooms, researcher vocabulary, visible move and promote actions, and the V&VN digital stylesheet remain required as in Protocol v2.9.

That follow-up MUST NOT invent Azure, Vercel or Neon as in-scope. MUST NOT rebuild the Product API first. MUST NOT add chat as a room. MUST NOT design for nurses. Analytics remains later. The publish room remains a small third room after the review-loop works, and remains fail-closed without an immutable locator (G2).

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next UI implementation.

This protocol-only change does not itself implement that follow-up. Do not change `src/operations_console_*.py` in this protocol change.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is identity/access plus the human door of the source/review/publish loop. Treat the highest class as **C5** (identity/access) spanning C3 (console rooms/nav).

This delta is owner-approved. Named C5 reviewers are not yet staffed. Retrospective independent technical and security/operations review remains due, using the same pattern as Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). Retrospective C3 review of Protocol v2.9 / PR #24 remains due.

Any later implementation of Documentenhierarchie, waiting-task badges, or the Accounts room remains separately classified, including at least C5 spanning C3.

## 10. Gates and approval effect

Approval of v2.10 establishes Documentenhierarchie as the lasting tree heading, waiting-task badge rules, and the Accounts room with a closed role set. It does not:

- implement the new UI, any room rewrite, any account store change, or any Product API behaviour change;
- claim that "Familieboom" is the lasting researcher heading;
- authorize a mockup, Azure, Vercel or Neon as the next implementation;
- skip durable immutable storage or convert G2 to PASS;
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
