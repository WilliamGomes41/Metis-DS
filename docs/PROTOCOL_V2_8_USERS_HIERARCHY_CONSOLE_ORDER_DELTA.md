# V&VN Data Services Protocol v2.8 — Users, Source Hierarchy, and Console Build Order

**Status:** Approved for project use  
**Protocol delta version:** 2.8.0  
**Approval date:** 2026-08-28  
**Approved by:** Project owner  
**Extends:** Protocol v2.7.0  
**Highest change class:** C5 (identity/access / publication / entitlement) spanning C3 (source/review/publish loop)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.8 records the owner-approved evaluation of the 2026-08-28 design grilling. It adds primary-user, two-axis source-hierarchy and console-build-order rules to V&VN Data Services, and it clarifies that RAG on kennisplatform HTML is not the product.

Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0 and this delta jointly form normative baseline v2.8.0. All Protocol v2.6 console rules and all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules remain in force, except the sequencing statements superseded in section 6. This protocol-only change does not implement UI or product code. Do not claim the console exists in code. Do not implement the console in this protocol change.

This delta is a **scoped supersession** of Protocol v2.6 §7 and Protocol v2.7 §2 only as they set console-versus-Fase-2 implementation order and the next concrete task. Where this delta and those sequencing sentences conflict, this delta governs. Durable immutable storage is not skipped. For all other requirements, the stricter fail-closed requirement applies.

## 2. Unchanged v2.6 and v2.7 rules

The internal operations console remains authorized DS scope and remains unbuilt. Every rule in Protocol v2.6.0 remains mandatory, including:

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

## 3. Users

Primary DS users MUST be:

- guideline researchers, who use the console;
- B2B subscribers: an EPD, an institution, or their bot, who call the Product API.

Nurses are not primary users of DS. The console MUST NOT be designed for nurses. This restates and tightens Protocol v2.7: the console source tree is researcher UX only and MUST NOT be a nurse decision tree.

## 4. Source hierarchy — two axes

Source organization has two axes. Family is a hook, not a new file. Class/weight sits on each object.

### 4.1 Class / weight

Each object MUST carry a class. Heavier class MUST NOT be filled by lighter class. The minimum class order MUST be:

`richtlijn` > `handreiking` > `artikel` > `transcript` / `podcast`

A podcast MUST NOT replace a guideline in the API even in the same family.

A lower class MAY be `supported` only with its class label. A lower class MUST NOT fill a gap left by a missing higher class on the same question if a higher class exists in the published corpus.

### 4.2 Family / topic

Family (for example `continentie`) groups sources that are related but not equal: a guideline, a magazine article on products, a podcast on shame. Family is a hook, not a new file.

MVP: the ingest researcher MUST set family. Adding a branch tomorrow MUST NOT redraw the tree.

Moving a source between families MUST NOT require clinical re-review. That move is a curator act.

Promoting class (for example transcript to richtlijn) MUST require review.

If later evidence shows that family moves change meaning, that is a new protocol change, not a silent extra review.

### 4.3 Console tree and API

The console tree MUST be family × class. Each file MUST keep its own hash.

The Product API remains object-level: only what was asked. Unpublished branches MUST abstain.

## 5. Product clarification (v2.7)

RAG on kennisplatform HTML is not the product. DS is the owned live curated switch, not a scrape.

Train-ready structured objects plus a live published-check remain the B2B offer, as in Protocol v2.7: training MAY exist only as a second licence, and only if the client still calls DS at question time to check published status.

## 6. Build order

Do not build a mockup. Do not wait for Azure or a finished "DS" before researchers have a real console.

The next implementation after this delta MUST be a real console MVP, not a mockup:

- ingest HTML/PDF;
- family tree;
- select reviewers;
- review return-loop;

wired to the existing kernel (extract, objects, gates, local `sources/private/` as the G0 local store).

Continentie bron 2 MUST enter through that console. Bron 2 MUST NOT enter via a parallel engineer-only path as the researcher experience.

The Product API already exists; do not rebuild it first. Azure DEV remains BLOCKED under G0. Analytics remains later. The publish room remains a small third room after the review-loop works.

This does not skip durable immutable storage. The local store is the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules.

This protocol-only change does not itself implement that console. The console remains unbuilt. The next concrete task after this delta is the real console MVP on the existing kernel, with bron 2 as the first envelope.

## 7. Unchanged fail-closed rules

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

## 8. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The change class is source/review/publish plus publication, entitlement, source class/family and console implementation order. Treat the highest class as **C5** (identity/access / publication / entitlement) spanning C3 (source/review/publish loop).

This delta is owner-approved. Named C5 reviewers are not yet staffed. Retrospective independent technical and security/operations review remains due, using the same pattern as Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5).

Any later implementation of the console MVP, family/class ingest, class-weight retrieve behaviour or family moves remains separately classified, including at least C5 spanning C3.

## 9. Gates and approval effect

Approval of v2.8 establishes the primary-user, two-axis source-hierarchy and console-build-order rules. It does not:

- implement the console, any room, any account, or any Product API behaviour change;
- claim that the console exists in code;
- authorize a mockup as the next implementation;
- skip durable immutable storage or convert G2 to PASS;
- select an identity vendor, provision Azure AD, or convert G0 Azure DEV, G7 or G8 to PASS;
- introduce Vercel, Neon or an LLM vendor;
- publish a source or knowledge object;
- authorize an external consumer or onboard the first paying subscriber;
- add a care-app frontend, chatbot, EPD/ECD UI or public website;
- put chat in the console;
- design the console for nurses;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets or confidential review artefacts in Git;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- reopen or alter GD-03;
- staff named human reviewers.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest.
