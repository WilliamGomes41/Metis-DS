# V&VN Data Services Protocol v2.28 — Structural heading / parent-list navigation + confirmed-type Sterkte gate

**Status:** Approved for project use  
**Protocol delta version:** 2.28.0  
**Approval date:** 2026-09-05  
**Approved by:** Project owner  
**Extends:** Protocol v2.27.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (parent-choice / heading navigation MUST use a deduplicated, hierarchically ordered document-body structure, not naive global numeric sort of TOC+body; Sterkte visible and active ONLY on stored/confirmed `recommendation` or actionable boom `outcome`, not on a machine-proposed type; SUPERSEDES the v2.16/v2.17 reading that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.28 records the owner-approved lock of 2026-09-05 (William Gomes). Metis is document owner. The Implementation engineer (Forge) writes code later after a separate GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

This is **one focused protocol cut** with **two separate acceptance blocks**. The two blocks MUST be independently testable. A pass of Block A MUST NOT be treated as a pass of Block B. A pass of Block B MUST NOT be treated as a pass of Block A.

Owner lock (normative intent):

### Block A — Structural heading / parent-list navigation

Current extract order is useful for provenance but unsuitable as researcher navigation. MUST NOT use naive global numeric sort of all headings (TOC + body merge risk).

MUST:

1. Recognize and mark table-of-contents (inhoudsopgave) items separately from body headings.
2. Parent-choice / heading navigation list MUST primarily use headings from the **document body**.
3. Derive hierarchy from outline numbers where reliable: `5` → `5.4` → `5.4.1` → `5.4.2`.
4. Near-duplicates MAY be removed from the **choice list only**; all source anchors MUST remain in freeze/audit trail.
5. Source/extract order remains fallback for headings without a reliable outline number.
6. MAY show page number or source locator to distinguish same-named headings.
7. **Structural parent validity:** a parent MUST be structurally valid. e.g. heading `5.4.1` MUST NOT get heading `2` as parent merely because it was extracted nearby. Invalid parent proposals MUST NOT bind / MUST NOT be offered as default structure.

Product rule: parent list shows a deduplicated, hierarchically ordered document structure from the main text. Source order kept for provenance and as fallback.

### Block B — Strength stamp gating (confirmed type only)

Stricter than current main (`recommendation_strength_ui_applies` on proposed type).

MUST:

1. A machine proposal `recommendation` MUST NOT activate/show Sterkte.
2. Sterkte visible and active ONLY when **stored/confirmed** type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`.
3. On type change in the browser, Sterkte MUST appear/disappear **before submit** (live UI).
4. If type changes away from recommendation/actionable outcome: Sterkte disappears immediately; any previously chosen strength MUST NOT be actively saved on that object; old value MAY remain in audit history only.
5. Machine MAY still propose a strength value, but it MUST stay hidden/inactive until the user confirms the relevant type.

This SUPERSEDES any reading of Protocol v2.16/v2.17 that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm. v2.16/v2.17 stamp-on-recommendation law remains; the gate becomes confirmed/stored type.

### First Forge code wave (after separate Metis GO — NOT this PR)

Next code after this protocol (and after/alongside the already-GO'd v2.27 delete wave) MUST be Forge for exactly Blocks A+B with separate acceptance tests. MUST NOT open G2/`publish()`, Azure ZIP, nurse UI, recreate `HANDOFF.md`. MUST NOT implement v2.27 delete in this protocol PR.

Where this delta and Protocol v2.27 conflict on which implementation is next: v2.27 delete wave may already be in flight under separate Metis GO; this delta's next Forge wave is A+B after its own GO. ROADMAP MUST state both.

No Forge implementation in this PR. No Azure. G2 stays BLOCKED. `publish()` stays G2-BLOCKED.

`HANDOFF.md` MUST NOT be recreated.

v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remains law (surface lock UNCHANGED). v2.26 Klasse wijzigen first wave is already on `main` (PR #97). v2.25 boom path UNCHANGED. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

Live baseline on `main` before this delta is Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0, v2.26.0, v2.27.0 and this delta jointly form normative baseline v2.28.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It SUPERSEDES any reading of Protocol v2.16/v2.17 that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm. Replace with: Sterkte visible and active ONLY when stored/confirmed type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`; a machine proposal `recommendation` MUST NOT activate/show Sterkte. v2.16/v2.17 stamp-on-recommendation law remains; the gate becomes confirmed/stored type. It SUPERSEDES any reading that parent-choice / heading navigation MAY use naive global numeric sort of all headings (TOC + body merged), or that a nearby-extracted heading MAY bind as default parent without being structurally valid. Replace with: recognize and mark inhoudsopgave items separately from body headings; parent-choice / heading navigation list MUST primarily use headings from the document body; derive hierarchy from outline numbers where reliable (`5` → `5.4` → `5.4.1` → `5.4.2`); near-duplicates MAY be removed from the choice list only (all source anchors MUST remain in freeze/audit trail); source/extract order remains fallback for headings without a reliable outline number; a parent MUST be structurally valid; invalid parent proposals MUST NOT bind / MUST NOT be offered as default structure. Where this delta and Protocol v2.27 conflict on which implementation is next: v2.27 delete wave may already be in flight under separate Metis GO; this delta's next Forge wave is A+B after its own GO. ROADMAP MUST state both. It does NOT supersede: freeze/locator (v2.11), closed serving types for the **richtlijn** path (v2.12), atomic objects/relations/four-eyes (v2.13), the rest of stamps-on-recommendation law (v2.16: DOEN/OVERWEEG/NIET DOEN are stamps on `recommendation`, not objects, not Koppen rows, not a new type), researcher surface except the proposed-type stamp-UI reading superseded here (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished-delete Documentenhiërarchie + type-to-confirm (v2.27; surface lock UNCHANGED), the rest of unpublished-delete law (v2.20), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family; actionable outcomes still take DOEN/OVERWEEG/NIET DOEN), Klasse wijzigen / controlled reclassification architecture (v2.26), fail-closed G2.

Where this delta and those «stamp UI MAY appear on proposed type without human type confirm» / «naive global numeric sort of all headings» / «nearby-extract parent MAY bind as default» readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types on the richtlijn path.

The v2.25 closed boom-path typeset remains UNCHANGED:

`path`, `node`, `outcome`

Operators MUST NOT invent other boom types. MUST NOT require boom types on the richtlijn path. MUST NOT invent boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`. Closed Klasse set remains:

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`

Operators MUST NOT invent other Klasse values.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession and except the v2.7 `story.html`-boom-out-of-MVP-as-a-knowledge-class reading superseded by Protocol v2.25), all Protocol v2.8 primary-user and two-axis hierarchy rules (except any reading that a class change is a silent total wipe of all review state as the only story, superseded by Protocol v2.26, and except any reading that reviewing boom objects as researchers would violate the nurse-tree rule), all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17, and except the researcher-facing action name **Promoveren** superseded by Protocol v2.26 **Klasse wijzigen**), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules (except the console-label **Promoveren** superseded by Protocol v2.26; «Klasse promoveren MUST review» remains as the review requirement), all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17; boom freeze extends the same spirit in Protocol v2.25), all Protocol v2.12 type/review/projection rules for the **richtlijn** path, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules (except any reading that a nearby-extracted heading MAY bind as default parent without being structurally valid, superseded here), all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19, and except any reading that TOC crumbs and body headings are interchangeable in the parent-choice / heading navigation list, superseded here; extract MAY still propose `heading` for real source headings / TOC / structural crumbs), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20, and except the stamp-UI-on-proposed-type reading superseded here), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules (except the stamp-UI-MAY-appear-on-proposed-type reading superseded here), all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules (except the document-card / Review-chooser alternative-surface reading superseded by Protocol v2.27), all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules, all Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split rules, all Protocol v2.25 MVP-beslisboom / Klasse-selects-review-path / `path`/`node`/`outcome` / boom-freeze / boom-MUST-NOT-outrank-richtlijn rules, all Protocol v2.26 Klasse wijzigen / controlled-reclassification / source-unchanged / same-model vs cross-model / published-never-rewritten rules, and all Protocol v2.27 unpublished-delete Documentenhiërarchie-only + type-to-confirm rules remain in force, except the readings superseded in sections 3–8. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.27 files except index/conflict pointers. MUST NOT implement structural heading navigation, parent-list hierarchy, confirmed-type Sterkte gate, or v2.27 delete in this PR. Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes except the invalid-default-parent reading superseded here (v2.13), stamps on recommendation except the proposed-type gate superseded here (v2.16), researcher surface except the proposed-type stamp-UI reading superseded here (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished-delete Documentenhiërarchie + type-to-confirm (v2.27), waves A–D / deploy split (v2.21–v2.24), the v2.25 boom path, the v2.26 Klasse wijzigen architecture, or fail-closed G2 except as already required.

This delta also sets the next concrete **code** implementation after this protocol. Protocol v2.27 §1 and §8 set the next code as the unpublished-delete Documentenhiërarchie + type-to-confirm wave. That wave may already be in flight under separate Metis GO. Where this delta and Protocol v2.27 conflict on which implementation is next: v2.27 delete wave may already be in flight under separate Metis GO; this delta's next Forge wave is A+B after its own GO. ROADMAP MUST state both. The next **code** after this protocol's own Metis GO MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** Blocks A+B in section 8, with separate acceptance tests. MUST NOT implement v2.27 delete in this protocol PR. MUST NOT open G2/`publish()`. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

## 2. Unchanged v2.6 through v2.27 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.27.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain (unconfirmed relations still MUST NOT bind; this delta adds that an invalid parent MUST NOT be offered as default structure). v2.16 stamps on `recommendation` remain for the richtlijn path; the **gate** becomes stored/confirmed type. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family; actionable outcomes still take DOEN/OVERWEEG/NIET DOEN and MUST carry a strength when the type is stored/confirmed `outcome`) remains UNCHANGED. v2.26 Klasse wijzigen / controlled reclassification remains UNCHANGED. v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm remains UNCHANGED. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. `HANDOFF.md` MUST NOT be recreated.

v2.8 / v2.10 «Klasse promoveren MUST review» remains as the review requirement: a class change MUST require review. Moving a source between families MUST NOT require clinical re-review. Heavier class MUST NOT be filled by lighter class.

## 3. Block A — Recognize TOC separately; parent list is body structure

MUST recognize and mark table-of-contents (inhoudsopgave) items separately from body headings.

Parent-choice / heading navigation list MUST primarily use headings from the **document body**.

MUST NOT use naive global numeric sort of all headings. Merging TOC crumbs with body headings and then sorting by number globally is forbidden: that merge risk is why TOC items MUST be marked separately. A TOC line `5.4.1 …` is not interchangeable with the body heading `5.4.1 …` as a parent-choice row.

Current extract / source order remains useful for **provenance** and as the **fallback** for headings without a reliable outline number. Extract order MUST NOT be the primary researcher navigation of the parent-choice list when a reliable outline number exists.

Product rule: the parent list shows a deduplicated, hierarchically ordered document structure from the main text. Source order is kept for provenance and as fallback.

## 4. Block A — Outline hierarchy, dedup of the choice list, locators

Where outline numbers are reliable, hierarchy MUST be derived from those numbers: `5` → `5.4` → `5.4.1` → `5.4.2`.

A heading whose outline number is a prefix of another is the structural ancestor. `5.4` is parent of `5.4.1` and of `5.4.2`. `5` is parent of `5.4`. `2` is not parent of `5.4.1`.

Near-duplicates MAY be removed from the **choice list only**. All source anchors MUST remain in the freeze/audit trail. Dedup of the researcher-facing parent-choice list is not deletion of freeze objects, not hide-fragments-without-extract, and not unpublished-document delete.

Source/extract order remains fallback for headings without a reliable outline number. MUST NOT invent an outline number. MUST NOT force a numeric sort on unnumbered headings.

MAY show page number or source locator to distinguish same-named headings (for example two body headings both titled Inleiding in different sections). Distinct real headings in different sections MAY remain (`1.1 Inleiding` vs `2. Inleiding`); Protocol v2.18 identical-`clean_text` law is UNCHANGED.

## 5. Block A — Structural parent validity

A parent MUST be structurally valid.

Heading `5.4.1` MUST NOT get heading `2` as parent merely because it was extracted nearby.

Invalid parent proposals MUST NOT bind. Invalid parent proposals MUST NOT be offered as default structure.

A nearby-extract proposal that is not a structural ancestor MUST NOT auto-check, MUST NOT pre-select, and MUST NOT be the default parent. Unconfirmed relations still MUST NOT bind (Protocol v2.13). This delta adds: an invalid parent MUST NOT be offered as the default structure even as a proposal the researcher is expected to accept.

The researcher MAY still confirm a valid parent from the body-heading choice list. That confirmation remains a human act on the exact object version.

## 6. Block B — Sterkte only on stored/confirmed type (live UI)

A machine proposal `recommendation` MUST NOT activate/show Sterkte.

Sterkte is visible and active ONLY when **stored/confirmed** type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`.

On type change in the browser, Sterkte MUST appear/disappear **before submit** (live UI). A page reload or a completed POST MUST NOT be required for Sterkte to appear or disappear after the researcher changes type in the type select.

If type changes away from recommendation / actionable outcome: Sterkte disappears immediately; any previously chosen strength MUST NOT be actively saved on that object; old value MAY remain in audit history only. The object MUST NOT keep an active strength field that would display or serve as if the type were still recommendation/outcome.

Machine MAY still propose a strength value, but it MUST stay hidden/inactive until the user confirms the relevant type. A proposed strength on a proposed `recommendation` MUST NOT show the picker. A proposed strength on a proposed `outcome` MUST NOT show the picker.

This SUPERSEDES any reading of Protocol v2.16/v2.17 that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm. v2.16/v2.17 stamp-on-recommendation law remains: DOEN/OVERWEEG/NIET DOEN are stamps on `recommendation` (`doen` | `overweeg` | `niet_doen`), not objects, not Koppen rows, not a new type; the researcher help sentence remains; extract MUST NOT heading-propose those words. The **gate** becomes confirmed/stored type. v2.25 actionable-outcome strength law remains; the same confirmed/stored-type gate applies.

A nav word MUST NOT get a stamp picker (Protocol v2.17 UNCHANGED). Showing Sterkte on unclassified **Tools**, on a proposed-only `recommendation`, or on any type that is not stored/confirmed `recommendation` or stored/confirmed actionable `outcome`, is forbidden.

Serving remains fail-closed: only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. A stamp without a confirmed advice sentence MUST NOT be `supported`. Boom serving is not opened here.

## 7. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, EPD UI, or interactive nurse tree player. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. Boom serving is not opened here. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol. Do not claim GD-03.

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

## 8. Build order — first Forge code wave (Blocks A+B; v2.27 delete may already be in flight)

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement structural heading navigation, parent-list hierarchy, confirmed-type Sterkte gate, or v2.27 delete in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.27 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`. MUST NOT merge to main unless repo rules auto-require — this PR is for Metis/William review.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (Forge Blocks A+B) after this protocol merges and Metis GO’s that wave.

Where this delta and Protocol v2.27 conflict on which implementation is next: v2.27 delete wave may already be in flight under separate Metis GO; this delta's next Forge wave is A+B after its own GO. ROADMAP MUST state both.

After this protocol merges:

1. Next code after this protocol's own Metis GO MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** Blocks A+B, with **separate acceptance tests** (Block A independently testable; Block B independently testable) — NOT this PR:
   1. Block A: mark TOC (inhoudsopgave) separately from body headings; parent-choice / heading navigation list primarily from document-body headings; outline-number hierarchy where reliable (`5` → `5.4` → `5.4.1` → `5.4.2`); near-duplicates MAY leave the choice list only; source/extract order as fallback; MAY show page/locator for same-named headings; structurally valid parent only; invalid parent proposals MUST NOT bind / MUST NOT be offered as default
   2. Block B: Sterkte hidden/inactive on machine-proposed `recommendation`; Sterkte visible/active ONLY on stored/confirmed `recommendation` or actionable boom `outcome`; live UI before submit; type change away clears active strength (audit history MAY keep the old value); machine-proposed strength stays hidden until type confirm
   3. Tests (tests-before-code), two independent acceptance blocks
2. MUST NOT implement v2.27 delete in this protocol PR. The v2.27 delete wave may already be in flight under separate Metis GO. MUST NOT fold v2.27 delete into the A+B Forge wave unless that delete wave is separately already GO'd and the owner asks to combine live PRs. This protocol PR MUST NOT contain that delete implementation.
3. MUST NOT implement selective invalidation, published-candidate fork, or full `previous_review` schema in that first A+B code wave. Selective invalidation + published-candidate remain later under Protocol v2.26.
4. MUST NOT open G2/`publish()`. G2 still BLOCKED; `publish()` still G2-BLOCKED.
5. MUST NOT Azure ZIP, nurse UI, or recreate `HANDOFF.md`.
6. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 richtlijn-path type/projection, v2.13 atomic objects/relations/four-eyes (except the invalid-default-parent reading superseded here), v2.15 ingest date/version/type-lanes (except TOC/body interchangeable-in-parent-list), v2.16 one-door/stacks/rows/stamps/tiny-objects (except proposed-type stamp gate), v2.17 researcher-surface (except proposed-type stamp-UI), v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete (except the document-card / Review-chooser alternative-surface reading superseded by v2.27), v2.21 wave definitions, v2.22 ZIP-then-B live path, v2.23 first DELETE cut, v2.24 thin-console / one-shared-kernel, v2.25 boom path, v2.26 Klasse wijzigen / controlled reclassification and v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remain required law, except the bounded supersessions in this file.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing structural heading navigation, parent-list hierarchy, or confirmed-type Sterkte gate; implementing v2.27 Documentenhiërarchie-only delete or type-to-confirm; implementing ingest UI, extract, Storyline parser, or API scraper; naive global numeric sort of all headings as the parent list; treating TOC crumbs and body headings as interchangeable parent-choice rows; binding an invalid nearby-extracted parent as default structure; deleting freeze anchors when deduplicating the choice list; showing Sterkte on a machine-proposed `recommendation` or proposed-only type; requiring a submit/reload before Sterkte appears or disappears after a browser type change; actively saving a previously chosen strength after type changes away from recommendation/actionable outcome; implementing Klasse wijzigen selective invalidation, published-candidate fork, or full `previous_review` schema; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; huisstyle-bar-only tweaks without the bar in sections 3–8; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; auto-promoting ordinary text or a `node` to `outcome`; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening atomic objects/relations/four-eyes except the invalid-default-parent lock here (v2.13); reopening the v2.25 boom path; reopening stamps except the confirmed-type gate; reopening chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete / Documentenhiërarchie type-to-confirm; rewriting v2.16–v2.27 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; live-URL ingest as the sole official boom file; treating live kennisplatform REST as the sole source of truth; silently substituting boom outcomes for unpublished or missing richtlijn recommendations; activating Product API boom serving unless separately GO’d; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`; mutating a live published release back to unpublished; re-labelling objects across review models as a direct class change; implementing v2.27 delete in this protocol PR.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 9. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (parent-choice / heading navigation MUST use a deduplicated, hierarchically ordered document-body structure, not naive global numeric sort of TOC+body; Sterkte visible and active ONLY on stored/confirmed `recommendation` or actionable boom `outcome`, not on a machine-proposed type; SUPERSEDES the v2.16/v2.17 reading that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.27 / PR #98, Protocol v2.26 / PR #96, Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of Blocks A+B remains separately classified, including at least C3 spanning review-surface / retrieve-safety. Block A and Block B MUST remain independently testable in that Forge wave.

## 10. Gates and approval effect

Approval of v2.28 establishes that the owner locked two independently testable acceptance blocks on 2026-09-05 (William Gomes): **Block A** — current extract order is useful for provenance but unsuitable as researcher navigation; MUST NOT use naive global numeric sort of all headings (TOC + body merge risk); MUST recognize and mark table-of-contents (inhoudsopgave) items separately from body headings; parent-choice / heading navigation list MUST primarily use headings from the document body; MUST derive hierarchy from outline numbers where reliable (`5` → `5.4` → `5.4.1` → `5.4.2`); near-duplicates MAY be removed from the choice list only; all source anchors MUST remain in freeze/audit trail; source/extract order remains fallback for headings without a reliable outline number; MAY show page number or source locator to distinguish same-named headings; a parent MUST be structurally valid; heading `5.4.1` MUST NOT get heading `2` as parent merely because it was extracted nearby; invalid parent proposals MUST NOT bind / MUST NOT be offered as default structure; the parent list shows a deduplicated, hierarchically ordered document structure from the main text; source order kept for provenance and as fallback; **Block B** — a machine proposal `recommendation` MUST NOT activate/show Sterkte; Sterkte visible and active ONLY when stored/confirmed type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`; on type change in the browser, Sterkte MUST appear/disappear before submit (live UI); if type changes away from recommendation/actionable outcome, Sterkte disappears immediately and any previously chosen strength MUST NOT be actively saved on that object (old value MAY remain in audit history only); machine MAY still propose a strength value but it MUST stay hidden/inactive until the user confirms the relevant type; this SUPERSEDES any reading of Protocol v2.16/v2.17 that stamp UI MAY appear based solely on `proposed_object_type` without human type confirm; v2.16/v2.17 stamp-on-recommendation law remains; the gate becomes confirmed/stored type; that G2 remains BLOCKED; that `publish()` stays G2-BLOCKED; that `HANDOFF.md` MUST NOT be recreated; that `PROTOCOL.md` is law for every guideline, not Continentie-only; that this PR is protocol-only; that next code after this protocol's own Metis GO MUST be Forge on the existing console for exactly Blocks A+B with separate acceptance tests; that MUST NOT implement v2.27 delete in this protocol PR; that where this delta and Protocol v2.27 conflict on which implementation is next, v2.27 delete wave may already be in flight under separate Metis GO and this delta's next Forge wave is A+B after its own GO; that ROADMAP MUST state both; that MUST NOT open G2/`publish()`, Azure ZIP, nurse UI, or recreate `HANDOFF.md`; that v2.25 boom path is UNCHANGED; that v2.26 Klasse wijzigen architecture is UNCHANGED; that v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm is UNCHANGED; that four layers are UNCHANGED; that this protocol MUST NOT claim G2 PASS; that MUST NOT implement structural heading navigation, parent-list hierarchy, or confirmed-type Sterkte gate in this PR; that MUST NOT rewrite v2.16–v2.27 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded Block A navigation lock and Block B confirmed-type Sterkte gate: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement structural heading navigation, parent-list hierarchy, or confirmed-type Sterkte gate in this PR;
- implement v2.27 Documentenhiërarchie-only delete or type-to-confirm in this PR;
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
- use naive global numeric sort of all headings as the parent-choice list;
- treat TOC crumbs and body headings as interchangeable parent-choice rows;
- bind an invalid nearby-extracted parent as default structure;
- delete freeze anchors when deduplicating the choice list;
- show Sterkte on a machine-proposed `recommendation` or on any type that is not stored/confirmed `recommendation` or stored/confirmed actionable `outcome`;
- require submit/reload before Sterkte appears or disappears after a browser type change;
- actively save a previously chosen strength after type changes away from recommendation/actionable outcome;
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
- rewrite Protocol v2.16–v2.27 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
- reopen the Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split;
- reopen the Protocol v2.25 boom path;
- reopen the Protocol v2.26 Klasse wijzigen architecture;
- reopen the Protocol v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm lock except the next-implementation reading stated here (both waves);
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
- treat a pass of Block A as a pass of Block B, or a pass of Block B as a pass of Block A.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
