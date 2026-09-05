# V&VN Data Services Protocol v2.27 — Unpublished delete: Documentenhiërarchie only + type-to-confirm

**Status:** Approved for project use  
**Protocol delta version:** 2.27.0  
**Approval date:** 2026-09-05  
**Approved by:** Project owner  
**Extends:** Protocol v2.26.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (unpublished document delete MUST be available from exactly one console place: Documentenhiërarchie; type-to-confirm exact document title; SUPERSEDES v2.20 document-card / Review-chooser alternative surfaces; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.27 records the owner-approved lock of 2026-09-05 (William Gomes). Metis is document owner. The Implementation engineer (Forge) writes code later after a separate GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

Owner lock (normative intent):

1. **Single place.** Unpublished document delete MUST be available from **exactly one** console place: **Documentenhiërarchie**. MUST NOT offer Verwijder unpublished document (or equivalent delete control) from Inleveren, Review, Publiceren, Accounts, or any other room. MUST NOT invent a separate Delete room/kamer (owner will add other rooms later; delete stays on Documentenhiërarchie).
2. **Type-to-confirm.** Before delete executes, the operator MUST type the **exact document title** into a confirmation field (type-to-confirm). The console MUST show the title clearly so the operator can copy/read it — this is a safety measure against accidental/fast delete, not a puzzle. Without an exact title match, delete MUST NOT run.
3. **Unchanged from Protocol v2.20 / related law.** Only unpublished captured snapshots MAY be deleted by an authorized console operator. MUST confirm before execute (now includes type-to-confirm title). MUST write an audit-ledger row. MUST NOT delete a published projection. MUST NOT treat SSH/wipe of `/home/data` as the product path. Four-eyes NOT required for unpublished capture delete. G2 remains BLOCKED; `publish()` G2-BLOCKED. `HANDOFF.md` MUST NOT be recreated. `PROTOCOL.md` is law for every guideline, not Continentie-only.
4. **Bounded supersession of v2.20 surface.** This SUPERSEDES any reading of Protocol v2.20 that delete MUST appear on the document card / Review-chooser as alternative surfaces. Replace with: Documentenhiërarchie only + type-to-confirm exact title.
5. **First Forge code wave** (after separate Metis GO — NOT this PR). Next code MUST be Forge on the existing console for exactly: (1) remove delete controls from every surface except Documentenhiërarchie; (2) add type-to-confirm field requiring exact document title (title shown); (3) keep existing unpublished-only / audit-ledger / no published delete / confirmation; (4) tests (tests-before-code). MUST NOT open G2/`publish()`, Azure ZIP, nurse UI, selective class-change work, or recreate `HANDOFF.md`.
6. No Forge implementation in this PR. No Azure. G2 stays BLOCKED. `publish()` stays G2-BLOCKED.
7. `HANDOFF.md` MUST NOT be recreated.
8. v2.26 Klasse wijzigen first wave is already on `main` (PR #97). v2.25 boom path UNCHANGED. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

Live baseline on `main` before this delta is Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0, v2.26.0 and this delta jointly form normative baseline v2.27.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It SUPERSEDES any reading of Protocol v2.20 that delete MUST appear on the document card / Review-chooser as alternative surfaces. Replace with: unpublished document delete MUST be available from exactly one console place — **Documentenhiërarchie** — and MUST type-to-confirm the exact document title (title shown; without exact match delete MUST NOT run). It SUPERSEDES the Protocol v2.26 reading that the next **code** is still the Klasse wijzigen first wave: that Forge wave is already on `main` (PR #97). Where this delta and Protocol v2.26 conflict on which implementation is next, this delta governs. Selective invalidation + published-candidate remain later law under Protocol v2.26, after this delete-surface wave — they are NOT this first Forge code wave. It does NOT supersede: freeze/locator (v2.11), closed serving types for the **richtlijn** path (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), the rest of unpublished-delete law (v2.20: unpublished-only; confirm; audit-ledger; no published delete; no SSH/wipe of `/home/data`; four-eyes not required; `PROTOCOL.md` every-guideline law), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family), Klasse wijzigen / controlled reclassification architecture (v2.26: invalidate only what the class change substantively affects; source unchanged; same-model vs cross-model; published never rewritten; **Klasse wijzigen** label), fail-closed G2. Clarify v2.20: unpublished captured snapshots MAY still be deleted by an authorized console operator; the **place** is now Documentenhiërarchie only; confirmation now includes type-to-confirm exact title.

Where this delta and those «delete MUST appear on the document card / Review-chooser as alternative surfaces» / «next code is still the v2.26 Klasse wijzigen first wave» readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types on the richtlijn path.

The v2.25 closed boom-path typeset remains UNCHANGED:

`path`, `node`, `outcome`

Operators MUST NOT invent other boom types. MUST NOT require boom types on the richtlijn path. MUST NOT invent boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`. Closed Klasse set remains:

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`

Operators MUST NOT invent other Klasse values.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession and except the v2.7 `story.html`-boom-out-of-MVP-as-a-knowledge-class reading superseded by Protocol v2.25), all Protocol v2.8 primary-user and two-axis hierarchy rules (except any reading that a class change is a silent total wipe of all review state as the only story, superseded by Protocol v2.26, and except any reading that reviewing boom objects as researchers would violate the nurse-tree rule), all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17, and except the researcher-facing action name **Promoveren** superseded by Protocol v2.26 **Klasse wijzigen**), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules (except the console-label **Promoveren** superseded by Protocol v2.26; «Klasse promoveren MUST review» remains as the review requirement), all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17; boom freeze extends the same spirit in Protocol v2.25), all Protocol v2.12 type/review/projection rules for the **richtlijn** path, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules (except the document-card / Review-chooser alternative-surface reading superseded here), all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules, all Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split rules, all Protocol v2.25 MVP-beslisboom / Klasse-selects-review-path / `path`/`node`/`outcome` / boom-freeze / boom-MUST-NOT-outrank-richtlijn rules, and all Protocol v2.26 Klasse wijzigen / controlled-reclassification / source-unchanged / same-model vs cross-model / published-never-rewritten rules remain in force, except the readings superseded in sections 3–8. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.26 files except index/conflict pointers. MUST NOT implement Documentenhiërarchie-only delete, type-to-confirm, or remove existing delete controls in this PR. Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished-delete except the surface / type-to-confirm lock here (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, the v2.26 Klasse wijzigen architecture, or fail-closed G2 except as already required.

This delta also sets the next concrete **code** implementation after this protocol. Protocol v2.26 §1 and §10 set the next code as the Klasse wijzigen first wave. That wave is already on `main` (PR #97). Where this delta and Protocol v2.26 conflict on which implementation is next, this delta governs. The next **code** MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the unpublished-delete Documentenhiërarchie + type-to-confirm wave in section 8. MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first code wave. MUST NOT open G2/`publish()`. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step. ROADMAP MUST mark this Documentenhiërarchie + type-to-confirm wave as next code. Selective invalidation + published-candidate remain later under Protocol v2.26, after this delete-surface wave.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

Index/conflict pointer: Protocol v2.28.0 SUPERSEDES the v2.27 reading that the next code after this file is still the only next Forge wave. Where this file and Protocol v2.28 conflict on which implementation is next: the v2.27 delete wave may already be in flight under separate Metis GO; Protocol v2.28's next Forge wave is Blocks A+B (structural heading / parent-list navigation + confirmed-type Sterkte gate) after its own GO. ROADMAP MUST state both. v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm exact title remains law. HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6 through v2.26 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.26.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain. v2.16 stamps on `recommendation` remain for the richtlijn path. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family) remains UNCHANGED. v2.26 Klasse wijzigen / controlled reclassification remains UNCHANGED (a document class change MUST invalidate only what that class change substantively affects; source freeze bytes / SHA-256 / title / version / provenance MUST NOT change; same-model vs cross-model; published never rewritten; researcher-facing label **Klasse wijzigen**). Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. v2.20 unpublished-delete remains on main, not a fifth wave — except the document-card / Review-chooser alternative-surface reading superseded here. `HANDOFF.md` MUST NOT be recreated.

v2.8 / v2.10 «Klasse promoveren MUST review» remains as the review requirement: a class change MUST require review. Moving a source between families MUST NOT require clinical re-review. Heavier class MUST NOT be filled by lighter class.

## 3. Exactly one console place — Documentenhiërarchie

Unpublished document delete MUST be available from **exactly one** console place: **Documentenhiërarchie**.

MUST NOT offer Verwijder unpublished document (or equivalent delete control) from Inleveren, Review, Publiceren, Accounts, or any other room.

MUST NOT invent a separate Delete room/kamer. Owner will add other rooms later; delete stays on Documentenhiërarchie.

The document card / Review-chooser as alternative delete surfaces is SUPERSEDED. A delete control MAY remain on a document row **inside Documentenhiërarchie**. That is still the one place. MUST NOT re-introduce the same control on Inleveren, Review, Publiceren, Accounts, a document card outside Documentenhiërarchie, or the Review chooser.

After delete, that snapshot MUST NOT appear on Inleveren, Review or Documentenhierarchie lists. Stored objects and the envelope for that `snapshot_id` are gone. Freeze bytes of that unpublished source MAY be removed with it. MUST NOT touch other snapshots. MUST NOT touch `/home/data` globally.

## 4. Type-to-confirm exact document title

Before delete executes, the operator MUST type the **exact document title** into a confirmation field (type-to-confirm).

The console MUST show the title clearly so the operator can copy/read it. This is a safety measure against accidental/fast delete, not a puzzle. MUST NOT hide the title, scramble it, or require a snapshot id as the typed value.

Without an exact title match, delete MUST NOT run. Exact match means the typed string MUST equal the document title as shown. A missing field, a partial title, extra characters, or a different title MUST NOT execute delete.

MUST confirm before execute. That confirmation now includes type-to-confirm title. A generic «OK» / «Bevestig» without the exact title MUST NOT suffice.

The label MUST remain researcher Dutch (for example **Verwijder unpublished document**). MUST NOT use "envelope" as a UI term. MUST NOT ask a researcher to type or pick a snapshot id as the primary act.

## 5. Unchanged unpublished-delete law (Protocol v2.20)

Only unpublished captured snapshots MAY be deleted by an authorized console operator. That operator is the same class as ingest: a named researcher or reviewer account, not a secret engineer path.

This is owner-authorized cleanup of unpublished capture, not publication, not G2, and not hiding fragments of a freeze that remains in Review.

- Capture remains not publication.
- `publish()` stays G2-BLOCKED. This delta does not implement `publish()` PASS.
- MUST NOT delete a published projection or anything that has been published.
- MUST write an audit-ledger row: who, when, `snapshot_id`, source SHA-256, title.
- MUST NOT treat SSH/wipe of `/home/data` as the product path. The console action is the path.
- Four-eyes is NOT required for unpublished capture delete.
- The uploader MAY delete unpublished they captured.
- A second named reviewer is not required for delete. Delete is not type-confirm of an object type.
- Type-to-confirm of the document title is not four-eyes and is not type-confirm.
- AI, Grok Bot, Metis, the Implementation engineer and the Auditor MUST NOT count as the authorized console operator for this delete, MUST NOT approve, and MUST NOT publish.
- Engineers MUST NOT submit sources through the ingest room and MUST NOT use a secret engineer path to delete unpublished capture.
- `PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol.
- Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. This delta MUST NOT strip them.
- The next freeze MUST NOT have to be Continentie.
- MUST NOT use this to hide selected objects inside a freeze that stays in Review. Protocol v2.16 hide-fragments-without-extract remains.
- This delete is the whole unpublished snapshot only.

## 6. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, EPD UI, or interactive nurse tree player. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. Boom serving is not opened here. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Four-eyes is not required to delete unpublished capture. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol. Do not claim GD-03.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. MUST NOT add numpy/sklearn or touch Azure deploy packaging.

## 7. PROTOCOL.md is the law for every guideline

`PROTOCOL.md` is the law of V&VN Data Services for every guideline, not a Continentie-only protocol.

- Continentie appears in Protocol v2.16–v2.19 as live evidence of fails (stamp words as Koppen; 2008 Inhoud cards), not as the product identity.
- Those historical evidence sentences MUST remain. This delta MUST NOT strip them.
- The next freeze MUST NOT have to be Continentie.
- Naming Continentie in a historical evidence sentence does not make Continentie the only lawful first-wave source.
- Family / Onderwerp remains a hook the ingest researcher sets. A fresh new ingest MUST still start with empty Onderwerp (Protocol v2.17 unchanged).

This supersedes any reading that `PROTOCOL.md`, the console, or the next freeze is Continentie-only. That lock is unchanged from Protocol v2.20.

## 8. Build order — first Forge code wave

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement Documentenhiërarchie-only delete, type-to-confirm, or remove existing delete controls in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.26 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`. MUST NOT merge to main unless repo rules auto-require — this PR is for Metis/William review.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (Forge unpublished-delete Documentenhiërarchie + type-to-confirm) after this protocol merges and Metis GO’s that wave.

Where this delta and Protocol v2.26 conflict on which implementation is next, this delta governs. The Klasse wijzigen first wave is already on `main` (PR #97). After this protocol merges:

1. Next code MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** this first wave, after a separate Metis GO — NOT this PR:
   1. Remove delete controls from every surface except Documentenhiërarchie
   2. Add type-to-confirm field requiring exact document title (title shown)
   3. Keep existing unpublished-only / audit-ledger / no published delete / confirmation
   4. Tests (tests-before-code)
2. MUST NOT implement selective invalidation, published-candidate fork, full `previous_review` schema, or further Klasse wijzigen work in that first code wave. PROTOCOL v2.26 states those as law for later waves. ROADMAP MUST mark this Documentenhiërarchie + type-to-confirm wave as next code. Selective invalidation + published-candidate remain later under Protocol v2.26, after this delete-surface wave.
3. MUST NOT open G2/`publish()`. G2 still BLOCKED; `publish()` still G2-BLOCKED.
4. MUST NOT Azure ZIP, nurse UI, selective class-change work, or recreate `HANDOFF.md`.
5. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 richtlijn-path type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete (except the document-card / Review-chooser alternative-surface reading superseded here), v2.21 wave definitions, v2.22 ZIP-then-B live path, v2.23 first DELETE cut, v2.24 thin-console / one-shared-kernel, v2.25 boom path and v2.26 Klasse wijzigen / controlled reclassification remain required law, except the bounded supersessions in this file.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing Documentenhiërarchie-only delete, type-to-confirm, or removal of existing delete controls; implementing ingest UI, extract, Storyline parser, or API scraper; inventing a separate Delete room/kamer; offering Verwijder unpublished document from Inleveren, Review, Publiceren, Accounts, or any other room; implementing Klasse wijzigen selective invalidation, published-candidate fork, or full `previous_review` schema; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; huisstyle-bar-only tweaks without the bar in sections 3–8; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; auto-promoting ordinary text or a `node` to `outcome`; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening atomic objects/relations/four-eyes (v2.13); reopening the v2.25 boom path; reopening stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except the surface / type-to-confirm lock here; rewriting v2.16–v2.26 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; live-URL ingest as the sole official boom file; treating live kennisplatform REST as the sole source of truth; silently substituting boom outcomes for unpublished or missing richtlijn recommendations; activating Product API boom serving unless separately GO’d; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`; mutating a live published release back to unpublished; re-labelling objects across review models as a direct class change; selective class-change work.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (unpublished document delete MUST be available from exactly one console place: Documentenhiërarchie; type-to-confirm exact document title; SUPERSEDES v2.20 document-card / Review-chooser alternative surfaces; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.26 / PR #96, Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of the unpublished-delete Documentenhiërarchie + type-to-confirm wave remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 10. Gates and approval effect

Approval of v2.27 establishes that the owner locked unpublished document delete to **exactly one** console place on 2026-09-05 (William Gomes): **Documentenhiërarchie**; that MUST NOT offer Verwijder unpublished document (or equivalent delete control) from Inleveren, Review, Publiceren, Accounts, or any other room; that MUST NOT invent a separate Delete room/kamer; that before delete executes the operator MUST type the exact document title into a confirmation field (type-to-confirm); that the console MUST show the title clearly so the operator can copy/read it; that this is a safety measure against accidental/fast delete, not a puzzle; that without an exact title match delete MUST NOT run; that only unpublished captured snapshots MAY be deleted by an authorized console operator; that MUST confirm before execute (now includes type-to-confirm title); that MUST write an audit-ledger row; that MUST NOT delete a published projection; that MUST NOT treat SSH/wipe of `/home/data` as the product path; that four-eyes is NOT required for unpublished capture delete; that G2 remains BLOCKED; that `publish()` stays G2-BLOCKED; that `HANDOFF.md` MUST NOT be recreated; that `PROTOCOL.md` is law for every guideline, not Continentie-only; that this SUPERSEDES any reading of Protocol v2.20 that delete MUST appear on the document card / Review-chooser as alternative surfaces; that the replacement is Documentenhiërarchie only + type-to-confirm exact title; that this PR is protocol-only; that next code MUST be Forge on the existing console for exactly the four first-wave items after a separate Metis GO; that MUST NOT open G2/`publish()`, Azure ZIP, nurse UI, selective class-change work, or recreate `HANDOFF.md`; that the Klasse wijzigen first wave is already on `main` (PR #97); that where this delta and Protocol v2.26 conflict on which implementation is next, this delta governs; that selective invalidation + published-candidate remain later law under Protocol v2.26, after this delete-surface wave; that v2.25 boom path is UNCHANGED; that v2.26 Klasse wijzigen architecture is UNCHANGED; that four layers are UNCHANGED; that this protocol MUST NOT claim G2 PASS; that MUST NOT implement Documentenhiërarchie-only delete or type-to-confirm in this PR; that MUST NOT rewrite v2.16–v2.26 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded Documentenhiërarchie-only + type-to-confirm lock: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; four-eyes is not required to delete unpublished capture; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement Documentenhiërarchie-only delete, type-to-confirm, or removal of existing delete controls in this PR;
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
- require four-eyes or a second named reviewer to delete unpublished capture;
- add a researcher “zwaar/licht” or “snel/langzaam” control;
- let the machine decide that something is “light enough to serve”;
- auto-confirm types;
- auto-promote ordinary text or a `node` to `outcome`;
- add page, paragraph, stamp, strength, GRADE, chrome, light/heavy, Storyline player, or `scorelist` as a fourth closed boom type;
- invent a separate Delete room/kamer;
- offer Verwijder unpublished document from Inleveren, Review, Publiceren, Accounts, or any other room;
- keep the document card / Review-chooser as alternative delete surfaces;
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
- treat `PROTOCOL.md` as Continentie-only law;
- rewrite Protocol v2.16–v2.26 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
- reopen the Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split;
- reopen the Protocol v2.25 boom path;
- reopen the Protocol v2.26 Klasse wijzigen architecture except the next-implementation reading superseded here;
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
- implement selective class-change work in this PR or in the first Forge delete-surface wave.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
