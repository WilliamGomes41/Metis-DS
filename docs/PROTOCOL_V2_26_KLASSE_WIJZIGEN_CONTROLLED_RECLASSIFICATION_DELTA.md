# V&VN Data Services Protocol v2.26 — Klasse wijzigen / controlled reclassification

**Status:** Approved for project use  
**Protocol delta version:** 2.26.0  
**Approval date:** 2026-09-05  
**Approved by:** Project owner  
**Extends:** Protocol v2.25.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (controlled Klasse wijzigen / reclassification; a document class change MUST invalidate only what that class change substantively affects; current `promote_class` silent total wipe SUPERSEDED for the target architecture; temporary safe full re-review allowed in the first implementation wave; source freeze bytes / SHA-256 / title / version / provenance MUST NOT change; same-model vs cross-model matrix; published never rewritten; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.26 records the owner-approved lock of 2026-09-05 (William Gomes). Combined architecture + first code wave. Metis is document owner. The Implementation engineer (Forge) writes code later after a separate GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

Owner lock (normative intent):

1. **Core rule.** A document class change MUST invalidate only what that class change substantively affects. MUST NOT be a silent total wipe of all review state as the only story. The current `promote_class` reset (wipe `review_passes`; set every object `needs_review`; clear `validated_by` / `validation_date` / `review_snapshot_hash` as the only story) is SUPERSEDED for the target architecture. A temporary safe full re-review is allowed in the first implementation wave (section 10).
2. **Source unchanged.** Class change MUST NOT alter freeze bytes, SHA-256, title, version, or provenance of the source. Class is how Metis interprets the document, not what the source is.
3. **Object-/review-model distinction.** richtlijn-path Klassen (same review model / object typeset): `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` — closed types `heading` / `definition` / `explanation` / `condition` / `exception` / `recommendation` (+ `unclassified`). beslisboom-path Klasse: `beslisboom` — closed types `path` / `node` / `outcome` (Protocol v2.25). Cross-model = any transition where from-Klasse and to-Klasse select different review paths (boom vs non-boom).
4. **Transition matrix** (section 6). Same-model: keep objects, locators, fragment bounds, content hashes, class-independent relations; re-open only class-dependent confirmations. Target architecture = selective invalidation. Cross-model: MUST NOT direct class change / re-label objects across models. MUST block direct change and REQUIRE re-extract from the same freeze → new object graph → full review. Prior object set MUST remain as audit history of prior processing.
5. **Review history.** MUST NOT conceptually wipe `validated_by` / `validation_date` / `review_snapshot_hash` alone. Prefer invalidate with reason (e.g. `document_class_changed`) and keep prior review reconstructible. Exact schema MAY be left to an implementation PR but this protocol MUST require auditability of prior review + invalidation reason/time.
6. **Published never rewritten.** If a document/projection is already published, class change MUST NOT mutate the live published release back to unpublished. MUST create a new draft candidate version; published v1 remains until v2 is published through the existing fail-closed publish/G2 path. G2 remains BLOCKED; this delta does not open `publish()`.
7. **UX.** Rename console action **Promoveren** → **Klasse wijzigen**. Before confirm, MUST show consequence: source unchanged; same-model vs cross-model; objects kept vs re-extract required; how many reviews reopen (when known) / that full re-review applies in the first wave.
8. **First Forge code wave** (after separate Metis GO — NOT this PR). Protocol-only PR now. Next code MUST be Forge on the existing console for exactly the six items in section 10. MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO’d — but this PROTOCOL MUST state them as law for later waves. ROADMAP MUST mark selective + published-candidate as next after the narrow wave.
9. No Forge implementation in this PR. No Azure. G2 stays BLOCKED. `publish()` stays G2-BLOCKED.
10. `HANDOFF.md` MUST NOT be recreated.
11. v2.25 boom path UNCHANGED. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

Live baseline on `main` before this delta is Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0 and this delta jointly form normative baseline v2.26.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It SUPERSEDES the reading that the current `promote_class` reset — a silent total wipe of all review state — is the only lawful story for a document class change. Replace with: a class change MUST invalidate only what that class change substantively affects (target architecture = selective invalidation); a temporary safe full re-review is allowed in the first implementation wave. It SUPERSEDES the console action name **Promoveren** as the researcher-facing label. Replace with: **Klasse wijzigen**. It SUPERSEDES any reading that a class change MAY rewrite freeze bytes, SHA-256, title, version or provenance of the source. It SUPERSEDES any reading that objects MAY be re-labelled across review models (richtlijn-path typeset ↔ boom-path typeset) as a direct class change. It SUPERSEDES any reading that a class change MAY mutate a live published release back to unpublished. It SUPERSEDES the Protocol v2.25 reading that the next **code** is still the beslisboom path wave: that Forge wave is already on `main` (PR #95). Where this delta and Protocol v2.25 conflict on which implementation is next, this delta governs. It does NOT supersede: freeze/locator (v2.11), closed serving types for the **richtlijn** path (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family), fail-closed G2. Clarify v2.8 / v2.10 «Klasse promoveren MUST review»: review is still required; the action name is now **Klasse wijzigen**; the wipe-everything reset is not the target architecture. Family move still MUST NOT require clinical re-review.

Where this delta and those `promote_class`-total-wipe / «Promoveren»-as-the-only-label / «class change rewrites the source» / «re-label objects across models» / «unpublish a live published release» / «next code is still the v2.25 beslisboom path wave» readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types on the richtlijn path.

The v2.25 closed boom-path typeset remains UNCHANGED:

`path`, `node`, `outcome`

Operators MUST NOT invent other boom types. MUST NOT require boom types on the richtlijn path. MUST NOT invent boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`. Closed Klasse set remains:

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`

Operators MUST NOT invent other Klasse values.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession and except the v2.7 `story.html`-boom-out-of-MVP-as-a-knowledge-class reading superseded by Protocol v2.25), all Protocol v2.8 primary-user and two-axis hierarchy rules (except any reading that a class change is a silent total wipe of all review state as the only story, superseded here, and except any reading that reviewing boom objects as researchers would violate the nurse-tree rule), all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17, and except the researcher-facing action name **Promoveren** superseded here by **Klasse wijzigen**), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules (except the console-label **Promoveren** superseded here; «Klasse promoveren MUST review» remains as the review requirement), all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17; boom freeze extends the same spirit in Protocol v2.25), all Protocol v2.12 type/review/projection rules for the **richtlijn** path, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules, all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules, all Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split rules, and all Protocol v2.25 MVP-beslisboom / Klasse-selects-review-path / `path`/`node`/`outcome` / boom-freeze / boom-MUST-NOT-outrank-richtlijn rules remain in force, except the readings superseded in sections 3–10. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.25 files except index/conflict pointers. MUST NOT implement Klasse wijzigen, the transition matrix, selective invalidation, published-candidate fork, or `previous_review` schema in this PR. Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, or fail-closed G2 except as already required.

This delta also sets the next concrete **code** implementation after this protocol. Protocol v2.25 §1 and §10 set the next code as the beslisboom path wave. That wave is already on `main` (PR #95). Where this delta and Protocol v2.25 conflict on which implementation is next, this delta governs. The next **code** MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the Klasse wijzigen first wave in section 10. MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO’d. MUST NOT open G2/`publish()`. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step. ROADMAP MUST mark selective invalidation + published-candidate as next after the narrow wave.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

Index/conflict pointer: Protocol v2.27.0 SUPERSEDES the v2.26 reading that the next code is still the Klasse wijzigen first wave. That Forge wave is already on `main` (PR #97). Where this file and Protocol v2.27 conflict on which implementation is next, Protocol v2.27 governs: next code is Forge on the existing console for unpublished-delete Documentenhiërarchie only + type-to-confirm exact title. Selective invalidation + published-candidate remain later law under this file, after that delete-surface wave. v2.26 Klasse wijzigen architecture (invalidate only what the class change substantively affects; source unchanged; same-model vs cross-model; published never rewritten; **Klasse wijzigen** label), HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6 through v2.25 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.25.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain. v2.16 stamps on `recommendation` remain for the richtlijn path. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family) remains UNCHANGED. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. v2.20 unpublished-delete remains on main, not a fifth wave. `HANDOFF.md` MUST NOT be recreated.

v2.8 / v2.10 «Klasse promoveren MUST review» remains as the review requirement: a class change MUST require review. Moving a source between families MUST NOT require clinical re-review. Heavier class MUST NOT be filled by lighter class.

## 3. Core rule — invalidate only what the class change substantively affects

A document class change MUST invalidate only what that class change substantively affects.

MUST NOT be a silent total wipe of all review state as the only story.

The current `promote_class` reset is SUPERSEDED for the target architecture. That reset today: writes the new Klasse; sets `clinical_rereview_required`; empties `review_passes`; for every object clears `validated_by` / `validation_date` / `review_snapshot_hash` and sets `validation_status` = `needs_review` and `publication_status` = `unpublished`; invalidates bindings. That wipe-everything path MUST NOT remain the only lawful story.

Target architecture = **selective invalidation**: re-open only class-dependent confirmations. A temporary safe **full** re-review is allowed in the first implementation wave (section 10). Selective invalidation is later code under this same protocol, after a separate GO.

## 4. Source unchanged

Class change MUST NOT alter freeze bytes, SHA-256, title, version, or provenance of the source.

Class is how Metis interprets the document, not what the source is.

Reserializing, pretty-printing, or re-saving the freeze bytes MUST NOT be used as a class change. A locator bound to the hashed original remains bound to those same bytes. Capture remains not publication.

## 5. Object-/review-model distinction

Two review models. Klasse choice already selects the review path (Protocol v2.25). This delta records what a later class change across those paths MUST and MUST NOT do.

**richtlijn-path Klassen** (same review model / same object typeset):

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast`

Closed types: `heading` / `definition` / `explanation` / `condition` / `exception` / `recommendation` (+ `unclassified`).

**beslisboom-path Klasse**:

`beslisboom`

Closed types: `path` / `node` / `outcome` (Protocol v2.25).

**Cross-model** = any transition where from-Klasse and to-Klasse select different review paths (boom vs non-boom). That includes:

- any non-boom ↔ `beslisboom`
- `beslisboom` → other non-boom
- `richtlijn` → `beslisboom`
- `beslisboom` → `richtlijn`

Operators MUST NOT invent a third review model. Operators MUST NOT invent Klasse values outside the closed set. Operators MUST NOT invent boom types on the richtlijn path. Operators MUST NOT invent richtlijn types on the boom path as a substitute for `path` / `node` / `outcome`.

## 6. Transition matrix

Normative intent:

| From → to | Consequence |
| transcript → artikel | light reclassification / same model |
| artikel → handreiking | substantive re-review (same model) |
| handreiking → richtlijn | substantive re-review (same model) |
| richtlijn → artikel | substantive re-review (same model) |
| richtlijn → beslisboom | re-extract + full review (cross-model) |
| beslisboom → richtlijn | re-extract + full review (cross-model) |
| any non-boom ↔ beslisboom | cross-model |
| beslisboom → other non-boom | cross-model |

**Same-model** (both Klassen select the richtlijn-path typeset): keep objects, locators, fragment bounds, content hashes, class-independent relations. Re-open only class-dependent confirmations (e.g. is this a recommendation; strength; conditions/exceptions linkage; four-eyes; serveability under the stricter class). Target architecture = selective invalidation. `transcript` → `artikel` is light reclassification / same model. `artikel` → `handreiking`, `handreiking` → `richtlijn` and `richtlijn` → `artikel` are substantive re-review (same model): more class-dependent confirmations reopen because serveability, strength and four-eyes under the stricter or lighter class change.

**Cross-model:** MUST NOT direct class change / re-label objects across models. MUST block direct change and REQUIRE re-extract from the same freeze → new object graph → full review. Prior object set MUST remain as audit history of prior processing. MUST NOT silently convert a `recommendation` into an `outcome`, or a `node` into a `condition`, by renaming the Klasse.

Same-model MUST NOT become a silent excuse to skip review. Cross-model MUST NOT become a silent re-label. Family move still MUST NOT require clinical re-review.

In the first implementation wave (section 10), same-model MAY keep the existing safe **full** re-review. That is a temporary safe subset of this protocol, not a rewrite of the target architecture.

## 7. Review history

MUST NOT conceptually wipe `validated_by` / `validation_date` / `review_snapshot_hash` alone.

Prefer invalidate with reason (e.g. `document_class_changed`) and keep prior review reconstructible.

Exact schema MAY be left to an implementation PR but this protocol MUST require auditability of prior review + invalidation reason/time.

A later `previous_review` (or equivalent) schema is law for later waves. MUST NOT implement the full `previous_review` schema in the first Forge code wave unless separately GO’d. The first wave MUST still record the class change as an audit-event (who, when, from-Klasse, to-Klasse, snapshot, source SHA-256).

## 8. Published never rewritten

If a document/projection is already published, class change MUST NOT mutate the live published release back to unpublished.

MUST create a new draft candidate version; published v1 remains until v2 is published through the existing fail-closed publish/G2 path.

G2 remains BLOCKED. This delta does not open `publish()`. `publish()` remains G2-BLOCKED.

MUST NOT implement the published-candidate fork in the first Forge code wave unless separately GO’d. The protocol states the fork as law for later waves. Until that later wave, a class change on a published document MUST still fail closed rather than rewrite the live published release: MUST NOT unpublish v1 in place.

## 9. UX — Klasse wijzigen

Rename the console action **Promoveren** → **Klasse wijzigen**.

Before confirm, MUST show consequence:

- source unchanged (freeze bytes, SHA-256, title, version, provenance);
- same-model vs cross-model;
- objects kept vs re-extract required;
- how many reviews reopen (when known) / that full re-review applies in the first wave.

MUST NOT hide that a cross-model change blocks direct change and requires re-extract. MUST NOT hide that same-model in the first wave applies full re-review. MUST NOT present Klasse wijzigen as a silent relabel.

«Klasse promoveren MUST review» remains: Klasse wijzigen MUST require review. The researcher-facing label is **Klasse wijzigen**.

## 10. Build order — first Forge code wave and deferred waves

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement Klasse wijzigen, the transition matrix, selective invalidation, published-candidate fork, or `previous_review` schema in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.25 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`. MUST NOT merge to main unless repo rules auto-require — this PR is for Metis/William review.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (Forge Klasse wijzigen first wave) after this protocol merges and Metis GO’s that wave.

Where this delta and Protocol v2.25 conflict on which implementation is next, this delta governs. After this protocol merges:

1. Next code MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** this first wave, after a separate Metis GO — NOT this PR:
   1. Rename **Promoveren** → **Klasse wijzigen**
   2. Enforce the matrix: cross-model (especially to/from `beslisboom`) → block direct change + require re-extract on the same freeze
   3. Same-model → for now keep the existing safe **full** re-review (temporary; selective invalidation is later code under this same protocol)
   4. Show consequence before confirm
   5. Record class change as an audit-event
   6. Source / SHA unchanged
2. MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO’d. PROTOCOL states them as law for later waves. ROADMAP MUST mark selective invalidation + published-candidate as next after the narrow wave.
3. MUST NOT open G2/`publish()`. G2 still BLOCKED; `publish()` still G2-BLOCKED.
4. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 richtlijn-path type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete, v2.21 wave definitions, v2.22 ZIP-then-B live path, v2.23 first DELETE cut, v2.24 thin-console / one-shared-kernel and v2.25 boom path remain required law, except the bounded supersessions in this file.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. MUST NOT add numpy/sklearn or touch Azure deploy packaging.

The console MUST NOT be a nurse-facing care app, chatbot, public website, EPD UI, or interactive nurse tree player. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement ingest UI, Storyline parser, or API scraper.

Serving / G2 unchanged for the richtlijn path. Only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. Boom serving is not opened here. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol. Do not claim GD-03.

Out of scope for this PR and this delta: implementing Klasse wijzigen, the transition matrix, selective invalidation, published-candidate fork, or full `previous_review` schema; implementing ingest UI, extract, Storyline parser, or API scraper; adding a second Inleveren chooser labeled “path” distinct from Klasse; inventing Klasse values outside the closed set; inventing boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; huisstyle-bar-only tweaks without the bar in sections 3–10; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; auto-promoting ordinary text or a `node` to `outcome`; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening atomic objects/relations/four-eyes (v2.13); reopening the v2.25 boom path except the next-implementation reading superseded here; reopening stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except as already required; rewriting v2.16–v2.25 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; live-URL ingest as the sole official boom file; treating live kennisplatform REST as the sole source of truth; silently substituting boom outcomes for unpublished or missing richtlijn recommendations; activating Product API boom serving unless separately GO’d; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`; mutating a live published release back to unpublished; re-labelling objects across review models as a direct class change.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (controlled Klasse wijzigen / reclassification; a document class change MUST invalidate only what that class change substantively affects; current `promote_class` silent total wipe SUPERSEDED for the target architecture; temporary safe full re-review allowed in the first implementation wave; source freeze bytes / SHA-256 / title / version / provenance MUST NOT change; same-model vs cross-model matrix; published never rewritten; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of the Klasse wijzigen first wave, or a later GO of selective invalidation / published-candidate / `previous_review`, remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 12. Gates and approval effect

Approval of v2.26 establishes that the owner locked controlled **Klasse wijzigen** / reclassification on 2026-09-05 (William Gomes): combined architecture + first code wave; that a document class change MUST invalidate only what that class change substantively affects; that MUST NOT be a silent total wipe of all review state as the only story; that the current `promote_class` reset is SUPERSEDED for the target architecture; that a temporary safe full re-review is allowed in the first implementation wave; that class change MUST NOT alter freeze bytes, SHA-256, title, version, or provenance of the source; that class is how Metis interprets the document, not what the source is; that richtlijn-path Klassen (`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast`) share the same review model / object typeset; that beslisboom-path Klasse is `beslisboom` with closed types `path` / `node` / `outcome` (Protocol v2.25 UNCHANGED); that cross-model is any transition where from-Klasse and to-Klasse select different review paths (boom vs non-boom); that the transition matrix is normative intent (`transcript` → `artikel` light reclassification / same model; `artikel` → `handreiking` substantive re-review same model; `handreiking` → `richtlijn` substantive re-review same model; `richtlijn` → `artikel` substantive re-review same model; `richtlijn` → `beslisboom` re-extract + full review cross-model; `beslisboom` → `richtlijn` re-extract + full review cross-model; any non-boom ↔ `beslisboom` cross-model; `beslisboom` → other non-boom cross-model); that same-model MUST keep objects, locators, fragment bounds, content hashes, class-independent relations and re-open only class-dependent confirmations; that target architecture = selective invalidation; that cross-model MUST NOT direct class change / re-label objects across models; that cross-model MUST block direct change and REQUIRE re-extract from the same freeze → new object graph → full review; that the prior object set MUST remain as audit history of prior processing; that MUST NOT conceptually wipe `validated_by` / `validation_date` / `review_snapshot_hash` alone; that prefer invalidate with reason (e.g. `document_class_changed`) and keep prior review reconstructible; that exact schema MAY be left to an implementation PR but this protocol MUST require auditability of prior review + invalidation reason/time; that if a document/projection is already published, class change MUST NOT mutate the live published release back to unpublished; that MUST create a new draft candidate version; that published v1 remains until v2 is published through the existing fail-closed publish/G2 path; that G2 remains BLOCKED; that this delta does not open `publish()`; that the console action MUST be renamed **Promoveren** → **Klasse wijzigen**; that before confirm MUST show consequence (source unchanged; same-model vs cross-model; objects kept vs re-extract required; how many reviews reopen when known / that full re-review applies in the first wave); that this PR is protocol-only; that next code MUST be Forge on the existing console for exactly the six first-wave items after a separate Metis GO; that MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave unless separately GO’d; that PROTOCOL states those as law for later waves; that ROADMAP MUST mark selective + published-candidate as next after the narrow wave; that source/SHA unchanged; that v2.25 boom path is UNCHANGED; that four layers are UNCHANGED; that `HANDOFF.md` MUST NOT be recreated; that this protocol MUST NOT claim G2 PASS; that G2 remains BLOCKED; that `publish()` remains G2-BLOCKED; that MUST NOT implement Klasse wijzigen in this PR; that MUST NOT rewrite v2.16–v2.25 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded Klasse-wijzigen / controlled-reclassification lock: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement Klasse wijzigen, the transition matrix, selective invalidation, published-candidate fork, or full `previous_review` schema in this PR;
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
- auto-promote ordinary text or a `node` to `outcome`;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, Storyline player, or `scorelist` as a fourth closed boom type;
- add a second Inleveren chooser labeled “path” distinct from Klasse;
- invent Klasse values outside `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`;
- invent boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`;
- require boom types on the richtlijn path;
- silently fuse condition into outcome as the only representation;
- treat live kennisplatform REST as the sole source of truth for published knowledge;
- treat live URL-HTML `story.html` alone as sufficient without a freeze;
- silently substitute boom outcomes for unpublished or missing richtlijn recommendations;
- let boom advice outrank a confirmed `richtlijn` recommendation of the same family;
- design the console as a nurse-facing interactive tree player;
- lie in the UI by hiding stored fragments without a new extract;
- treat SSH or a wipe of `/home/data` as the product path;
- strip historical Continentie evidence sentences from Protocol v2.16–v2.19;
- rewrite Protocol v2.16–v2.25 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
- reopen the Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split;
- reopen the Protocol v2.25 boom path except the next-implementation reading superseded here;
- authorize live URL-HTML as the sole official boom file, LLM in the core API, nurse-facing console, chat, hospital protocols, patient data, Vercel/Neon, or treating Azure as the knowledge model;
- start Azure, Vercel, Neon or an LLM vendor in this protocol PR;
- add numpy/sklearn or touch Azure deploy packaging;
- treat capture as publication;
- reopen or alter GD-03;
- close GD-01, GD-02, GD-04, GD-05, GD-06 or GD-07;
- add a care-app frontend, chatbot, EPD/ECD-UI or public website;
- put chat in the console;
- design the console for nurses;
- open the role set or allow operators to invent new role types, object types or relation types;
- allow open registration or shared login;
- store hospital protocols, adoption lists or patient data;
- authorize source binaries, secrets, confidential review artefacts or the official stylesheet PDF in Git;
- silently add a new quality metric as a protocol gate;
- authorize a mockup, Azure ZIP as this PR, Cloud Shell of this protocol PR, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step;
- mutate a live published release back to unpublished;
- re-label objects across review models as a direct class change;
- keep the current `promote_class` silent total wipe as the only lawful story for the target architecture.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
