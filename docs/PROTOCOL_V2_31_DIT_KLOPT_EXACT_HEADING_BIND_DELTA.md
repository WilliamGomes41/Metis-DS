# V&VN Data Services Protocol v2.31 — Dit klopt exact heading bind

**Status:** Approved for project use  
**Protocol delta version:** 2.31.0  
**Approval date:** 2026-09-06  
**Approved by:** Project owner  
**Extends:** Protocol v2.30.0  
**Highest change class:** C3 review-surface / documentpositie bind safety (**Dit klopt** auto-bind from the shown **Gevonden onder** path MUST prefer exact visible heading title match after normalization; MUST NOT use substring / containment / first-hit-win; zero or ambiguous exact matches MUST fail closed to **Andere kop kiezen**; SUPERSEDES any reading that Dit klopt MAY bind via partial title containment; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.31 records the owner-approved lock of 2026-09-06 (William Gomes; Metis CoS). Metis is document owner. The Implementation engineer (Forge) writes code later after a **separate** Metis GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). Layers remain: frozen source → source passage → knowledge object → human review → published projection. A knowledge object MUST NOT replace the brondocument. G2 and `publish()` remain BLOCKED in this PR. This file is not Protocol v2.14. This delta MUST NOT write Protocol v2.14. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

Owner lock (normative intent): when the reviewer confirms documentpositie with **Dit klopt** (auto-bind from the shown **Gevonden onder** path to a heading parent), the bind MUST be an **exact** visible heading title match after normalization. Partial / substring / containment matches MUST NOT bind a parent. First-hit win among substring candidates is forbidden. Fail closed.

This is a **bounded supersession**. It SUPERSEDES any reading that **Dit klopt** MAY bind via partial title containment (`last in text`, `text in last`, startswith-as-bind, fuzzy, or first-hit among substring candidates). Replace with: exact visible heading title match after normalization; zero exact matches or two-or-more exact matches without a unique outline-number + body-heading identification MUST leave the parent unbound and require **Andere kop kiezen**; MUST NOT invent a parent. It does NOT supersede: Protocol v2.30 Block B ordinary language (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**); Protocol v2.28 structural validity / body-only chooser / TOC exclusion; Phase 1–4 admission / register; freeze/locator (v2.11); four-eyes high-risk (v2.13); v2.28 Sterkte-on-confirmed-type; v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm; v2.25 boom path; v2.26 Klasse wijzigen; v2.29 temporary production-only deploy; or fail-closed G2.

Where this delta and those «Dit klopt MAY bind via partial title containment» readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

Live baseline on `main` before this delta is Protocol v2.30.0 plus Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0, v2.26.0, v2.27.0, v2.28.0, v2.29.0, v2.30.0 and this delta jointly form normative baseline v2.31.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This PR is protocol-only. MUST NOT implement Forge code in this PR. MUST NOT recreate `HANDOFF.md`. MUST NOT open G2/`publish()`.

v2.30 Block B ordinary language (Gevonden onder / Dit klopt / Andere kop) remains law (UNCHANGED). v2.28 structural validity / body-only chooser / TOC exclusion remains law (UNCHANGED). Phase 1–4 admission/register remain law (UNCHANGED). v2.29 temporary production-only deploy remains law (UNCHANGED). v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remains law (UNCHANGED). v2.26 Klasse wijzigen first wave is already on `main`. v2.25 boom path UNCHANGED. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

## 2. Unchanged v2.6 through v2.30 rules

The four layers remain frozen source → source passage → knowledge object → human review → published projection (source/evidence → canonical knowledge → governance → product). This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. A knowledge object MUST NOT replace the brondocument.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.30.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain (unconfirmed relations still MUST NOT bind; four-eyes high-risk UNCHANGED). v2.16 stamps on `recommendation` remain for the richtlijn path; v2.28 confirmed/stored-type Sterkte gate remains. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path remains UNCHANGED. v2.26 Klasse wijzigen / controlled reclassification remains UNCHANGED. v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm remains UNCHANGED. v2.28 structural heading / parent-list navigation remains for the **Andere kop** hierarchy (body headings; TOC marked separately; structurally valid parent). v2.28 structural validity / body-only chooser / TOC exclusion UNCHANGED. v2.29 temporary production-only deploy remains UNCHANGED. v2.30 Block A hard admission gate / object contract / reason codes UNCHANGED. v2.30 Block B ordinary language (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**), full hierarchy ONLY after **Andere kop**, body headings only, TOC excluded, search, navigate vs select distinct, **Open volledige richtlijn** real surrounding context, review UI order + ONE save, and type UI (Metis proposal + Dit klopt / Type wijzigen) remain UNCHANGED. Phase 1–4 admission/register UNCHANGED. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. `HANDOFF.md` MUST NOT be recreated.

This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/review_cockpit_v1.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.30 files except index/conflict pointers. MUST NOT implement the exact-bind Forge fix in this PR. Do not reopen freeze/locator (v2.11), four-eyes high-risk (v2.13), v2.28 Sterkte gate, v2.27 delete, v2.25 boom, v2.26 Klasse wijzigen, v2.29 temp prod deploy, v2.30 Phase 1–4 admission/register, or fail-closed G2 except as already required.

## 3. Normative lock — Dit klopt exact heading bind

When the reviewer confirms documentpositie with **Dit klopt** (auto-bind from the shown **Gevonden onder** path to a heading parent):

1. Binding MUST prefer **exact** visible heading title match after normalization (trim; collapse internal whitespace). Outline prefix such as `5.2` MAY be stripped for comparison ONLY when both sides are compared with the same rule; MUST NOT use substring/`in` matching.
2. MUST NOT use partial / substring / containment matches (`last in text`, `text in last`, startswith-as-bind, fuzzy).
3. MUST NOT first-hit win among substring candidates.
4. If zero exact matches after normalization: MUST NOT silently bind a parent. Leave parent unbound / require **Andere kop kiezen** (fail closed). MUST NOT invent a parent.
5. If two or more exact matches: MUST NOT guess. Fail closed the same way (**Andere kop kiezen**) unless a single candidate is uniquely identified by matching outline number from the path AND body-heading role (Protocol v2.28 body-only chooser).
6. When exactly one exact match exists: bind that heading. If multiple exact titles but one unique outline match from the path’s last segment: that body heading MAY bind.
7. SUPERSEDES any reading that Dit klopt MAY bind via partial title containment.
8. v2.28 structural validity / body-only chooser / TOC exclusion UNCHANGED. v2.30 Block B ordinary language (Gevonden onder / Dit klopt / Andere kop) UNCHANGED. Phase 1–4 admission/register UNCHANGED. G2/`publish()` remain BLOCKED. MUST NOT recreate HANDOFF.md.

Normalization for this bind is **title identity**, not semantic similarity. After trim and internal-whitespace collapse, the last segment of the shown **Gevonden onder** path MUST equal the visible heading title (with the optional symmetric outline-prefix strip). A shorter heading that is a prefix or infix of a longer heading is not an exact match. A longer heading that merely contains the path’s last segment is not an exact match.

The candidate set for this bind remains the Protocol v2.28 body-only chooser: body headings only; TOC / inhoudsopgave excluded. A TOC crumb MUST NOT become the Dit klopt parent merely because its title text matches. Structural parent validity (Protocol v2.28) remains: an exact title match that is not a structurally valid parent MUST NOT bind.

Internal parent ids MAY remain in the kernel. The primary UI MUST still use ordinary language only (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**). This delta does not rename those controls and does not restore Relatie bevestigen or an always-visible TOC + full parent list.

## 4. Acceptance / regressions (protocol-level)

These regressions are protocol-level acceptance. They MUST be encoded as tests-before-code in the later Forge exact-bind PR. They are law now. They are not implemented in this PR.

- `Preventie` vs `Preventie van vallen`: **Dit klopt** MUST NOT bind the prefix when the exact longer title exists; MUST NOT bind the longer title when the path’s last segment exacts only the short title and a short heading exists.
  - Path last segment `Preventie van vallen` + body headings `Preventie` and `Preventie van vallen` → MUST bind `Preventie van vallen`. MUST NOT bind `Preventie`.
  - Path last segment `Preventie` + body heading `Preventie` exists → MUST bind `Preventie`. MUST NOT bind `Preventie van vallen` merely because the short title is contained in the longer title.
- Shared stems (`Screening` / `Screening en diagnostiek`): substring MUST NOT decide.
  - Path last segment `Screening en diagnostiek` MUST NOT bind `Screening`.
  - Path last segment `Screening` MUST NOT bind `Screening en diagnostiek`.
- First-hit win among substring candidates is a fail. Walking the parent-choice list and returning the first row where `last in text` or `text in last` is forbidden, even if that first row is a plausible prefix.
- Zero exact matches after normalization → parent unbound; reviewer MUST use **Andere kop kiezen**. MUST NOT invent a parent. MUST NOT pick the “closest” or “longest common prefix” heading.
- Two or more exact title matches → fail closed to **Andere kop kiezen**, unless one candidate is uniquely identified by matching outline number from the path AND body-heading role (Protocol v2.28 body-only chooser). Example: path last segment `5.2 Preventie` with two body headings titled `Preventie` and one of them outline `5.2` MAY bind that `5.2` body heading. Two body headings both titled `Preventie` with no unique outline match MUST NOT guess.

## 5. Next code after this protocol

This delta also sets the next concrete **code** implementation after this protocol. The next **code** after this protocol's own Metis GO MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the exact-bind fix on `resolve_found_under_parent` (tests-before-code). MUST NOT implement that Forge code in this protocol PR. MUST NOT open G2/`publish()`. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step.

That later Forge wave MUST:

1. write failing tests first for the section 4 regressions (including `Preventie` / `Preventie van vallen` and `Screening` / `Screening en diagnostiek`);
2. then change `resolve_found_under_parent` (and only the bind helper surface required to satisfy this lock) so **Dit klopt** uses exact visible heading title match after normalization;
3. fail closed to unbound / **Andere kop kiezen** on zero or ambiguous exact matches;
4. keep v2.28 body-only chooser / TOC exclusion / structural validity;
5. keep v2.30 Block B ordinary language and Phase 1–4 admission/register.

MUST NOT implement that wave in this PR. MUST NOT treat a protocol-only merge as the Forge fix.

## 6. Out of scope

Out of scope for this PR and this delta: implementing the exact-bind Forge fix on `resolve_found_under_parent`; implementing Forge phases 1–4; implementing review UI, open-bron real context, or collapsed document position; implementing passage register, coverage, gold, or metrics; binding a parent via `last in text`, `text in last`, startswith-as-bind, fuzzy, or first-hit among substring candidates; silently binding a prefix heading when the exact longer title exists; silently binding a longer title when the path’s last segment exacts only the short title; inventing a parent when zero exact matches exist; guessing among two or more exact title matches without a unique outline + body-heading identification; restoring Relatie bevestigen as a mandatory primary chain; always-visible TOC+full parent lists on the primary surface; changing v2.30 Block B ordinary language; changing v2.28 structural validity / body-only chooser / TOC exclusion; changing Phase 1–4 admission/register; filling missing required fields with “impliciet” prose; opening the hard gate with soft scores / volume / “ship then fix”; letting blocked candidates enter the ordinary review queue; implementing Klasse wijzigen selective invalidation, published-candidate fork, or full `previous_review` schema; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path serving types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening four-eyes high-risk (v2.13); reopening the v2.25 boom path; reopening the v2.28 Sterkte gate; reopening v2.27 delete; reopening v2.26 Klasse wijzigen; reopening v2.29 temp prod deploy; reopening v2.30 Phase 1–4; rewriting v2.16–v2.30 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 7. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 review-surface / documentpositie bind safety** (**Dit klopt** auto-bind from the shown **Gevonden onder** path MUST prefer exact visible heading title match after normalization; MUST NOT use substring / containment / first-hit-win; zero or ambiguous exact matches MUST fail closed to **Andere kop kiezen**; SUPERSEDES any reading that Dit klopt MAY bind via partial title containment; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 review-surface / documentpositie bind safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.30 / PR #105, Protocol v2.29 / PR #103, Protocol v2.28 / PR #100, Protocol v2.27 / PR #98, Protocol v2.26 / PR #96, Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of the exact-bind fix remains separately classified, including at least C3 review-surface / documentpositie bind safety.

## 8. Gates and approval effect

Approval of v2.31 establishes that the owner locked exact heading bind on 2026-09-06 (William Gomes; Metis CoS): when the reviewer confirms documentpositie with **Dit klopt**, binding MUST prefer exact visible heading title match after normalization (trim; collapse internal whitespace); outline prefix such as `5.2` MAY be stripped for comparison ONLY when both sides are compared with the same rule; MUST NOT use substring/`in` matching; MUST NOT use partial / substring / containment matches (`last in text`, `text in last`, startswith-as-bind, fuzzy); MUST NOT first-hit win among substring candidates; zero exact matches MUST NOT silently bind a parent — leave parent unbound / require **Andere kop kiezen** (fail closed); MUST NOT invent a parent; two or more exact matches MUST NOT guess — fail closed the same way unless a single candidate is uniquely identified by matching outline number from the path AND body-heading role (Protocol v2.28 body-only chooser); when exactly one exact match exists, bind that heading; if multiple exact titles but one unique outline match from the path’s last segment, that body heading MAY bind; SUPERSEDES any reading that Dit klopt MAY bind via partial title containment; v2.28 structural validity / body-only chooser / TOC exclusion UNCHANGED; v2.30 Block B ordinary language (Gevonden onder / Dit klopt / Andere kop) UNCHANGED; Phase 1–4 admission/register UNCHANGED; G2/`publish()` remain BLOCKED; MUST NOT recreate HANDOFF.md; protocol-level regressions include `Preventie` vs `Preventie van vallen` and shared stems `Screening` / `Screening en diagnostiek`; next code after this protocol's own Metis GO is Forge exact-bind fix on `resolve_found_under_parent` (tests-before-code); MUST NOT implement Forge code in this PR; that G2 remains BLOCKED; that `publish()` stays G2-BLOCKED; that `HANDOFF.md` MUST NOT be recreated; that `PROTOCOL.md` is law for every guideline, not Continentie-only; that v2.25 boom path is UNCHANGED; that v2.26 Klasse wijzigen architecture is UNCHANGED; that v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm is UNCHANGED; that v2.28 Sterkte gate is UNCHANGED; that v2.29 temporary production-only deploy is UNCHANGED; that v2.30 Phase 1–4 are UNCHANGED; that four layers are UNCHANGED; that this protocol MUST NOT claim G2 PASS; that MUST NOT rewrite v2.16–v2.30 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded exact-bind lock: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement the exact-bind Forge fix on `resolve_found_under_parent` in this PR;
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
- bind a parent via partial title containment;
- first-hit win among substring candidates;
- silently bind `Preventie` when the path exacts `Preventie van vallen`;
- silently bind `Preventie van vallen` when the path exacts only `Preventie` and a short heading exists;
- let substring decide `Screening` / `Screening en diagnostiek`;
- invent a parent when zero exact matches exist;
- guess among two or more exact title matches without unique outline + body-heading identification;
- restore Relatie bevestigen as a mandatory primary chain;
- always show TOC + full parent lists on the primary surface;
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
