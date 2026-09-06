# V&VN Data Services Protocol v2.32 — Documenten UI room name

**Status:** Approved for project use  
**Protocol delta version:** 2.32.0  
**Approval date:** 2026-09-06  
**Approved by:** Project owner  
**Extends:** Protocol v2.31.0  
**Highest change class:** C3 review-surface / UI vocabulary (researcher-facing console room heading / nav label / page title for `/tree` MUST be **Documenten**; MUST NOT use **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom** as the live console room heading or primary nav label; kernel model remains family × class UNCHANGED; this is UI vocabulary only — same pattern as Protocol v2.26 renaming Promoveren → Klasse wijzigen; Protocol v2.27 unpublished-delete remains ONE place only: that same console room, now labelled Documenten, plus type-to-confirm exact title; SUPERSEDES only the UI name in v2.10 / later «heading MUST be Documentenhierarchie» readings; do NOT reopen delete surface to Review/Inleveren; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.32 records the owner-approved lock of 2026-09-06 (William Gomes; Metis CoS). Metis is document owner. The Implementation engineer (Forge) writes code later after a **separate** Metis GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). Layers remain: frozen source → source passage → knowledge object → human review → published projection. A knowledge object MUST NOT replace the brondocument. G2 and `publish()` remain BLOCKED in this PR. This file is not Protocol v2.14. This delta MUST NOT write Protocol v2.14. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

Owner lock (normative intent): the researcher-facing console room heading / nav label / page title for `/tree` MUST be **Documenten** (ordinary Dutch, singular room name). **Documentenhiërarchie**, **Documentenhierarchie**, and **Familieboom** MUST NOT be the live console room heading or primary nav label.

This is a **bounded supersession**. It SUPERSEDES only the UI name in Protocol v2.10 and later readings that the live heading MUST be Documentenhierarchie / Documentenhiërarchie. Replace with: **Documenten**. It does NOT supersede: the kernel model family × class; Protocol v2.27 unpublished-delete remaining ONE place only (that same `/tree` room + type-to-confirm exact title); the prohibition on offering delete from Inleveren, Review, Publiceren, Accounts, or any other room; Protocol v2.31 **Dit klopt** exact heading bind; Protocol v2.30 Block B ordinary language; Protocol v2.28 structural validity / body-only chooser / TOC exclusion; Phase 1–4 admission / register; freeze/locator (v2.11); four-eyes high-risk (v2.13); v2.28 Sterkte-on-confirmed-type; v2.25 boom path; v2.26 Klasse wijzigen; v2.29 temporary production-only deploy; or fail-closed G2.

Where this delta and those «heading MUST be Documentenhierarchie» / «heading MUST be Documentenhiërarchie» readings conflict, this delta governs for live UI vocabulary. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

Live baseline on `main` before this delta is Protocol v2.31.0 plus Protocol v2.30.0 plus Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0, v2.26.0, v2.27.0, v2.28.0, v2.29.0, v2.30.0, v2.31.0 and this delta jointly form normative baseline v2.32.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This PR is protocol-only. MUST NOT implement Forge code in this PR. MUST NOT recreate `HANDOFF.md`. MUST NOT open G2/`publish()`. MUST NOT implement landing-page sketch B in this PR. MUST NOT rename the live console heading in product code in this PR.

v2.31 **Dit klopt** exact heading bind remains law (UNCHANGED). v2.30 Block B ordinary language (Gevonden onder / Dit klopt / Andere kop) remains law (UNCHANGED). v2.28 structural validity / body-only chooser / TOC exclusion remains law (UNCHANGED). Phase 1–4 admission/register remain law (UNCHANGED). v2.29 temporary production-only deploy remains law (UNCHANGED). v2.27 unpublished-delete remains ONE place only: that same console room (now labelled **Documenten**) + type-to-confirm exact title (UNCHANGED except the UI name). v2.26 Klasse wijzigen first wave is already on `main`. v2.25 boom path UNCHANGED. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

## 2. Unchanged v2.6 through v2.31 rules

The four layers remain frozen source → source passage → knowledge object → human review → published projection (source/evidence → canonical knowledge → governance → product). This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. A knowledge object MUST NOT replace the brondocument.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.31.0 remains mandatory as already written, except the UI-name readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain (unconfirmed relations still MUST NOT bind; four-eyes high-risk UNCHANGED). v2.16 stamps on `recommendation` remain for the richtlijn path; v2.28 confirmed/stored-type Sterkte gate remains. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path remains UNCHANGED. v2.26 Klasse wijzigen / controlled reclassification remains UNCHANGED. v2.27 unpublished-delete remains ONE place only + type-to-confirm UNCHANGED except the live room label is now **Documenten**. v2.28 structural heading / parent-list navigation remains for the **Andere kop** hierarchy (body headings; TOC marked separately; structurally valid parent). v2.28 structural validity / body-only chooser / TOC exclusion UNCHANGED. v2.29 temporary production-only deploy remains UNCHANGED. v2.30 Block A hard admission gate / object contract / reason codes UNCHANGED. v2.30 Block B ordinary language (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**), full hierarchy ONLY after **Andere kop**, body headings only, TOC excluded, search, navigate vs select distinct, **Open volledige richtlijn** real surrounding context, review UI order + ONE save, and type UI (Metis proposal + Dit klopt / Type wijzigen) remain UNCHANGED. Phase 1–4 admission/register UNCHANGED. v2.31 **Dit klopt** exact heading bind UNCHANGED. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. `HANDOFF.md` MUST NOT be recreated.

This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/review_cockpit_v1.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.31 files except index/conflict pointers. MUST NOT implement the console rename or landing-page sketch B in this PR. Do not reopen freeze/locator (v2.11), four-eyes high-risk (v2.13), v2.28 Sterkte gate, v2.27 delete surface (except the UI name locked here), v2.25 boom, v2.26 Klasse wijzigen, v2.29 temp prod deploy, v2.30 Phase 1–4 admission/register, v2.31 exact-bind, or fail-closed G2 except as already required.

## 3. Normative lock — Documenten UI room name

Researcher-facing console room heading / nav label / page title for `/tree`:

1. MUST be **Documenten** (ordinary Dutch, singular room name).
2. MUST NOT use **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom** as the live console room heading or primary nav label.
3. The kernel model remains family × class (UNCHANGED). Family remains a hook, not a new file. This is UI vocabulary only — same pattern as Protocol v2.26 renaming Promoveren → Klasse wijzigen. MUST NOT invent a new file, a new object type, or a third hierarchy axis.
4. Protocol v2.27 unpublished-delete remains ONE place only: that same console room (now labelled **Documenten**) + type-to-confirm exact title. MUST NOT offer Verwijder unpublished document (or equivalent delete control) from Inleveren, Review, Publiceren, Accounts, or any other room. MUST NOT invent a separate Delete room/kamer. MUST NOT reopen delete surface to Review/Inleveren.
5. Spelling: prefer **Documenten** everywhere for live UI law. Historical delta filenames (for example `PROTOCOL_V2_27_UNPUBLISHED_DELETE_DOCUMENTENHIERARCHIE_TYPE_CONFIRM_DELTA.md`) MAY keep their path; do not rename historical delta files. Historical delta text MAY keep Documentenhierarchie / Documentenhiërarchie as the then-current lock.
6. SUPERSEDES only the UI name in v2.10 / later «heading MUST be Documentenhierarchie» readings. Does not reopen v2.10 waiting-task badges, Accounts room, or closed role set.

Prefer **Documenten** in live `PROTOCOL.md` and `ROADMAP.md` UI-law sentences. Historical Eigenaarslock text and historical `PROTOCOL_V2_*` files MAY retain the older heading as a record of what those deltas locked.

## 4. Acceptance / regressions (protocol-level)

These regressions are protocol-level acceptance. They MUST be encoded as tests-before-code in the later Forge console-rename PR. They are law now. They are not implemented in this PR.

- Live `/tree` room heading / primary nav label / page title MUST render **Documenten**.
- MUST NOT render **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom** as that live heading or primary nav label.
- Unpublished delete MUST remain available from that same `/tree` room only (now labelled **Documenten**) + type-to-confirm exact title. MUST NOT reappear on Inleveren, Review, Publiceren, Accounts, or a new Delete room.
- Kernel family × class MUST remain. Class change and family move rules remain Protocol v2.26 / v2.8.
- Waiting-task badges and Accounts remain Protocol v2.10 except the room label superseded here.

## 5. Next code after this protocol

This delta does **not** implement product code. Landing-page sketch B (centered sparse home, primary **Bron inleveren**) is OUT of this protocol PR.

The next **code** after a **separate** Metis GO MUST be Forge (Implementation engineer) on the existing console for **exactly** landing-page sketch B + the console rename to **Documenten** (tests-before-code). MUST NOT implement that Forge code in this protocol PR. MUST NOT treat a protocol-only merge as the Forge rename. MUST NOT open G2/`publish()`. Until that separate Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step.

That later Forge wave MUST:

1. write failing tests first for the section 4 regressions (live heading **Documenten**; forbidden live labels; delete remains on that same room only);
2. then rename the researcher-facing `/tree` heading / nav label / page title to **Documenten**;
3. keep v2.27 unpublished-delete on that same room + type-to-confirm;
4. keep family × class;
5. implement landing-page sketch B only under that same separate Metis GO — not in this protocol PR.

MUST NOT implement that wave in this PR.

## 6. Out of scope

Out of scope for this PR and this delta: implementing the console rename in product code; implementing landing-page sketch B (centered sparse home, primary Bron inleveren); implementing Forge phases 1–4; implementing review UI, open-bron real context, or collapsed document position; implementing passage register, coverage, gold, or metrics; reopening unpublished-delete to Review/Inleveren/Publiceren/Accounts; inventing a separate Delete room; renaming historical `PROTOCOL_V2_*` filenames; changing the kernel family × class model; inventing a new file, a new object type, or a third hierarchy axis; changing v2.31 exact heading bind; changing v2.30 Block B ordinary language; changing v2.28 structural validity / body-only chooser / TOC exclusion; changing Phase 1–4 admission/register; implementing Klasse wijzigen selective invalidation, published-candidate fork, or full `previous_review` schema; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path serving types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening four-eyes high-risk (v2.13); reopening the v2.25 boom path; reopening the v2.28 Sterkte gate; reopening v2.27 delete surface except the UI name; reopening v2.26 Klasse wijzigen; reopening v2.29 temp prod deploy; reopening v2.30 Phase 1–4; reopening v2.31 exact-bind; rewriting v2.16–v2.31 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 7. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 review-surface / UI vocabulary** (researcher-facing console room heading / nav label / page title for `/tree` MUST be **Documenten**; MUST NOT use **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom** as the live console room heading or primary nav label; kernel model remains family × class UNCHANGED; this is UI vocabulary only — same pattern as Protocol v2.26 renaming Promoveren → Klasse wijzigen; Protocol v2.27 unpublished-delete remains ONE place only: that same console room, now labelled Documenten, plus type-to-confirm exact title; SUPERSEDES only the UI name in v2.10 / later «heading MUST be Documentenhierarchie» readings; do NOT reopen delete surface to Review/Inleveren; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 review-surface / UI vocabulary**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.31 / PR #110, Protocol v2.30 / PR #105, Protocol v2.29 / PR #103, Protocol v2.28 / PR #100, Protocol v2.27 / PR #98, Protocol v2.26 / PR #96, Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of landing-page sketch B + the console rename remains separately classified, including at least C3 review-surface / UI vocabulary.

## 8. Gates and approval effect

Approval of v2.32 establishes that the owner locked the Documenten UI room name on 2026-09-06 (William Gomes; Metis CoS): the researcher-facing console room heading / nav label / page title for `/tree` MUST be **Documenten** (ordinary Dutch, singular room name); MUST NOT use **Documentenhiërarchie**, **Documentenhierarchie**, or **Familieboom** as the live console room heading or primary nav label; the kernel model remains family × class UNCHANGED; this is UI vocabulary only — same pattern as Protocol v2.26 renaming Promoveren → Klasse wijzigen; Protocol v2.27 unpublished-delete remains ONE place only: that same console room, now labelled Documenten, plus type-to-confirm exact title; SUPERSEDES only the UI name in v2.10 / later «heading MUST be Documentenhierarchie» readings; do NOT reopen delete surface to Review/Inleveren; historical delta filenames MAY keep their path; landing-page sketch B is OUT of this protocol PR and MAY be the next Forge implementation after a separate Metis GO; G2/`publish()` remain BLOCKED; MUST NOT recreate HANDOFF.md; next code after a separate Metis GO is Forge landing sketch B + console rename (tests-before-code); MUST NOT implement Forge code in this PR; that G2 remains BLOCKED; that `publish()` stays G2-BLOCKED; that `HANDOFF.md` MUST NOT be recreated; that `PROTOCOL.md` is law for every guideline, not Continentie-only; that v2.25 boom path is UNCHANGED; that v2.26 Klasse wijzigen architecture is UNCHANGED; that v2.27 unpublished-delete remains one place + type-to-confirm UNCHANGED except the UI name; that v2.28 Sterkte gate is UNCHANGED; that v2.29 temporary production-only deploy is UNCHANGED; that v2.30 Phase 1–4 are UNCHANGED; that v2.31 exact heading bind is UNCHANGED; that four layers are UNCHANGED; that this protocol MUST NOT claim G2 PASS; that MUST NOT rewrite v2.16–v2.31 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded UI-name lock: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement the console rename in this PR;
- implement landing-page sketch B in this PR;
- implement Forge phases 1–4 in this PR;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- claim GD-03 or publication;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- take this protocol PR as the Cloud Shell ZIP;
- open G2/`publish()`;
- activate Product API boom serving unless separately GO’d;
- recreate `HANDOFF.md`;
- skip durable immutable storage;
- staff named reviewers;
- treat Metis, the Implementation engineer or the Auditor as GD-03 reviewers;
- write Protocol v2.14, or treat ingest date as `valid_from` / `valid_until`;
- reopen four-eyes or publish as C5;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- auto-confirm types;
- reopen unpublished-delete to Review/Inleveren;
- invent a separate Delete room;
- rename historical `PROTOCOL_V2_*` filenames;
- change the kernel family × class model;
- invent a new file, a new object type, or a third hierarchy axis;
- change v2.31 exact heading bind;
- change v2.30 Block B ordinary language;
- change v2.28 structural validity / body-only chooser / TOC exclusion;
- change Phase 1–4 admission/register;
- invent Klasse values outside `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`;
- invent a seventh closed serving type on the richtlijn path;
- invent boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`;
- require boom types on the richtlijn path;
- add numpy/sklearn or touch Azure deploy packaging;
- treat capture as publication;
- reopen or alter GD-03;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- add a care-app frontend, chatbot, EPD/ECD-UI or public website;
- put chat in the console;
- design the console for nurses;
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
