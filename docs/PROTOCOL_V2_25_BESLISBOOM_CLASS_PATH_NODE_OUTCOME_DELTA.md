# V&VN Data Services Protocol v2.25 — MVP beslisboom class, path / node / outcome

**Status:** Approved for project use  
**Protocol delta version:** 2.25.0  
**Approval date:** 2026-09-04  
**Approved by:** Project owner  
**Extends:** Protocol v2.24.0  
**Highest change class:** C3 spanning review-surface / retrieve-safety (MVP beslisboom document class with closed boom types `path` / `node` / `outcome`; closed Klasse set includes `beslisboom`; Klasse choice selects review path; boom freeze+locator; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family; console remains not a nurse tree player; no Forge code; no G2 PASS; `publish()` stays G2-BLOCKED)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.25 records the owner-approved lock of 2026-09-04 (William Gomes). Owner compared four kennisplatform Storyline booms and locked **one stable family**: MVP **beslisboom** document class with its own object model **pad / node / uitkomst** (English closed types: `path`, `node`, `outcome`), selected by Inleveren **Klasse** (not a separate second chooser labeled “path”). Metis is document owner. The Implementation engineer (Forge) writes code later after a separate GO. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product).

Owner review 2026-09-04 of Storyline + beslisboom API outcomes for:

- Valrisico (tree 4): multifactor modules + scorelist; many empty outcomes; Adviseer/Overweeg language
- Fractuurpreventie (tree 2): screening + themes + scorelist; some empty outcomes
- Mantelzorg (tree 3): 4-step; Bespreek-heavy; no empty
- Eenzaamheid (tree 1): 3-step; Verwijs / geen actie; no empty

Shared: Storyline player, same `/wp-json/beslisboom/v1/*` APIs, legenda→branches→evaluatie→samenvatting, path-fused conditions, multi-bullet outcomes, cross-guideline body refs (Continentie, Depressie, Medicatietrouw, …).

Owner locks (normative intent):

1. Owner photo-lock 2026-09-04 on Inleveren **Klasse** UI: the existing closed dropdown shows `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`. `beslisboom` MUST also appear in that same Klasse list. What the researcher chooses there determines the review path. This SUPERSEDES any reading that Inleveren needs a separate path control distinct from Klasse. Operators MUST NOT add a second chooser labeled “path”. Closed Klasse set MUST include `beslisboom` alongside `richtlijn`, `handreiking`, `artikel`, `transcript`, `podcast`. Operators MUST NOT invent other Klasse values. Choosing Klasse = `beslisboom` MUST select the boom review path (`path` / `node` / `outcome`). Choosing Klasse = `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` MUST select the existing non-boom (richtlijn-style) review path / stacks for that document. MUST NOT invent boom types on those classes. Family × class remains. A family MAY hold documents of different classes; each document keeps its own freeze, objects and the review path selected by its Klasse.
2. Beslisboom MUST be in the MVP because it is the hangable working method (researchers/care staff do not have time to read every full guideline).
3. Console remains researcher surface — MUST NOT become a nurse-facing interactive tree player (v2.8 nurse rule stays for console UX).
4. Boom review needs functions beyond current guideline stacks: path/node/outcome as review units; not only loose condition/recommendation fusion from a flat extract.
5. No Forge implementation in this PR. No Azure. G2 stays BLOCKED. `publish()` stays G2-BLOCKED.
6. `HANDOFF.md` MUST NOT be recreated.
7. Do NOT rewrite historical Continentie evidence sentences in older deltas except index/conflict pointers as usual.

Live baseline on `main` before this delta is Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0 and this delta jointly form normative baseline v2.25.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It SUPERSEDES the Protocol v2.7 reading that kennisplatform `story.html` boom players MUST stay entirely out of the MVP / first console **as a knowledge class**. Replace with: the beslisboom class is in the MVP for researcher ingest+review; the Storyline **player package** is not the Product API surface and MUST NOT be the nurse console. It SUPERSEDES any reading that the only MVP document classes are guideline HTML/PDF without a boom path. It SUPERSEDES any reading that Inleveren needs a separate path control distinct from Klasse. Replace with: choosing Klasse selects the review path. It does NOT supersede: freeze/locator (v2.11), closed serving types for the **richtlijn** path (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), fail-closed G2. Clarify v2.8 «console MUST NOT be a nurse decision tree»: still true for console UX; reviewing beslisboom objects as researchers is allowed.

Where this delta and those v2.7 / “guideline-HTML-only MVP” / “separate Inleveren path control distinct from Klasse” readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent types on the richtlijn path. Adding a richtlijn-path type is a new protocol change. MUST NOT require boom types (`path`, `node`, `outcome`) on the richtlijn path. MUST NOT add new object types for page, paragraph, stamp, strength, GRADE, chrome, “light/heavy” review, Storyline player, or scorelist-as-a-fourth-boom-type.

This delta **adds** a closed boom-path typeset for the **beslisboom** path only (section 4). That is this protocol change. Operators MUST NOT invent other boom types.

Four layers remain: source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession and except the v2.7 `story.html`-boom-out-of-MVP-as-a-knowledge-class reading superseded here), all Protocol v2.8 primary-user and two-axis hierarchy rules (except any reading that reviewing boom objects as researchers would violate the nurse-tree rule), all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules, all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17; boom freeze extends the same spirit in section 7), all Protocol v2.12 type/review/projection rules for the **richtlijn** path, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules, all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules (except the slow-lane-unclassified-as-equal-one-object-duty reading superseded by Protocol v2.19), all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the Inhoud-as-thousands-of-equal-one-object-cards reading superseded by Protocol v2.19, and except the Continentie-as-product-identity and leftover-unpublished-must-stay readings superseded by Protocol v2.20), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules, all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules, all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules, all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules, and all Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split rules remain in force, except the readings superseded in sections 3–9. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.24 files except index/conflict pointers. MUST NOT implement ingest UI, extract, Storyline parser, or API scraper in this PR. Do not reopen freeze/locator (v2.11), richtlijn-path serving types (v2.12), atomic objects/relations/four-eyes (v2.13), stamps on recommendation (v2.16), researcher surface (v2.17), extract dedup (v2.18), duty queue (v2.19), unpublished delete (v2.20), waves A–D / deploy split (v2.21–v2.24), or fail-closed G2 except as already required.

This delta also sets the next concrete **code** implementation after this protocol. Protocol v2.24 §3 and §11 set the next code as the console vs retrieval requirements split. That split is already on `main`. Where this delta and Protocol v2.24 conflict on which implementation is next, this delta governs. The next **code** MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the beslisboom path wave: Klasse includes beslisboom; Klasse choice selects review path; boom object model `path`/`node`/`outcome`; review stacks/functions for those types; freeze+locator for boom content; tests. MUST NOT activate Product API boom serving in that first code wave unless separately GO’d. MUST NOT open G2/`publish()`. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

Index/conflict pointer: Protocol v2.26.0 SUPERSEDES the reading that the current `promote_class` reset is the only lawful story for a document class change, the researcher-facing action name **Promoveren**, any reading that a class change MAY rewrite freeze bytes / SHA-256 / title / version / provenance, any reading that objects MAY be re-labelled across review models as a direct class change, any reading that a class change MAY mutate a live published release back to unpublished, and the v2.25 reading that the next code is still the beslisboom path wave. Where this file and Protocol v2.26 conflict on those readings, or on which implementation is next, Protocol v2.26 governs: Klasse wijzigen; a document class change MUST invalidate only what that class change substantively affects; target architecture = selective invalidation; temporary safe full re-review allowed in the first implementation wave; source unchanged; cross-model MUST block direct change and REQUIRE re-extract from the same freeze; published never rewritten; next code is Forge on the existing console for exactly the Klasse wijzigen first wave after a separate Metis GO. v2.25 boom path (`path` / `node` / `outcome`; Klasse includes `beslisboom`; Klasse choice selects review path; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family), HANDOFF.md MUST NOT be recreated, G2 remains BLOCKED, and `publish()` stays G2-BLOCKED remain.

## 2. Unchanged v2.6 through v2.24 rules

The four layers remain source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.24.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law and is extended in spirit to boom content (section 7), not rewritten. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain. v2.16 stamps on `recommendation` remain for the richtlijn path. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. v2.20 unpublished-delete remains on main, not a fifth wave. `HANDOFF.md` MUST NOT be recreated.

## 3. Inleveren Klasse selects review path and boom-in-MVP

This SUPERSEDES any reading that Inleveren needs a separate path control distinct from Klasse. At Inleveren the researcher MUST choose **Klasse** from the closed set. What you choose there determines the review path. Operators MUST NOT add a second chooser labeled “path”.

The closed Klasse set MUST include `beslisboom` alongside the existing classes:

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`

Operators MUST NOT invent other Klasse values.

- Family × class remains. A family MAY hold documents of different classes; each document keeps its own freeze, objects and the review path selected by its Klasse. Paths MAY differ for the same family.
- Choosing Klasse = `beslisboom` MUST select the boom review path (`path` / `node` / `outcome`). MUST NOT treat a flat extract fused into richtlijn types as the only representation of a beslisboom document.
- Choosing Klasse = `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` MUST select the existing non-boom (richtlijn-style) review path / stacks for that document. MUST NOT invent boom types (`path`, `node`, `outcome`) on those classes. Those classes MUST keep the existing closed richtlijn-style set and MUST NOT require boom types.

Beslisboom MUST be in the MVP. It is the hangable working method: researchers and care staff do not have time to read every full guideline.

This SUPERSEDES the Protocol v2.7 reading that kennisplatform `story.html` boom players MUST stay entirely out of the MVP / first console **as a knowledge class**. The Storyline **player package** (`story.html` and the live player shell) is not the Product API surface and MUST NOT be the nurse console. Live URL-HTML `story.html` alone remains insufficient without a freeze of reviewable node/outcome content (section 7; align with v2.11 spirit).

This SUPERSEDES any reading that the only MVP document classes are guideline HTML/PDF without a boom path.

v2.8 «console MUST NOT be a nurse decision tree» is still true for console UX. Reviewing beslisboom objects as researchers is allowed. The console MUST NOT become a nurse-facing interactive tree player.

## 4. Closed object model (beslisboom path only)

Add closed types for the beslisboom path. Operators MUST NOT invent others:

- `path` — ordered reviewable branch/route through the boom (structure; batch-confirmable as structure like headings, NEVER as advice).
- `node` — decision point / question / branch choice (maps to screening or multifactor questions; often behaves like `condition` for serving but is boom-native for review).
- `outcome` — terminal advice text for a path/node combination.

Documented scorelist choice: a **scorelist item** MAY be modeled as a `node` with a documented scorelist flag or kind. This delta MUST NOT add a fourth closed boom type (`scorelist`). Prefer `node` + metadata over a fourth type unless a later protocol adds a distinct type name because tests need it.

Richtlijn path keeps the existing closed set: `heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation` (+ `unclassified` default). MUST NOT require boom types on the richtlijn path. MUST NOT invent boom types on the richtlijn path. MUST NOT invent richtlijn types on the boom path as a substitute for `path` / `node` / `outcome`.

`unclassified` remains the default until a human confirms a type from the closed set of **that path**. Machine classification is a proposal, never published truth.

## 5. Relations

Reuse the closed relation set where possible (`applies_if`, `except_if`, `parent` / `child`, `explains`, `supported_by`, `defines`, `supersedes`). Operators MUST NOT invent relation types. Unconfirmed relations MUST NOT bind.

Normative boom wiring:

- `path` uses `parent` / `child` or ordered membership of `node`s.
- `outcome` MUST bind to the `node` / `path` conditions via `applies_if` (or equivalent confirmed relation). MUST NOT silently fuse condition into outcome as the only representation. Fusion of condition into advice remains the default FORBIDDEN pattern (Protocol v2.13), including on the boom path.
- Cross-guideline references in outcome bodies (Continentie, Depressie, Medicatietrouw, …) SHOULD become `supported_by` / `explains` targets when those objects exist. MUST NOT remain body-only forever as the sole link.

## 6. Review functions (law for later Forge — do not implement)

MUST support on the beslisboom path:

- Confirm `path` as structure (batch OK). A `path` is structure, NEVER advice. Batch-confirm of paths MUST NOT serve them as handelingsadvies.
- Confirm `node` (slow if it gates advice). A node that gates an `outcome` is researcher-required slow review, like `condition` on the richtlijn path.
- Confirm `outcome` as advice. Strength stamps DOEN / OVERWEEG / NIET DOEN apply when the outcome is actionable advice equivalent to `recommendation`; closed values remain `doen` | `overweeg` | `niet_doen`. «geen actie nodig» maps to `niet_doen` or an explicit no-action outcome that MUST NOT be served as positive advice.
- Split multi-bullet outcomes into atomic outcomes OR reject until split (same atomic-meaning bar as Protocol v2.13 / v2.16). One knowledge object MUST be one confirmable meaning unit.
- Empty/placeholder outcomes (empty API bodies, `UitkomstX_Y_titel` placeholders) MUST NOT pass review; MUST be incomplete/reject.
- High-risk (dosage e.g. vitamine D 800IE, medication change, delier) keeps four-eyes. Four-eyes unchanged: second named reviewer on the exact object tuple when confirmed type, `risk_level` or a listed high-risk field requires it.
- Bronpassage + open-original remain required against the boom freeze bytes. From every boom knowledge object the reviewer MUST be able to open the exact source passage. Type-confirm without that flow is not acceptable. This delta MUST NOT invent a locator scheme; locators remain Protocol v2.11 spirit against hashed boom freeze bytes.

MUST NOT auto-confirm types. MUST NOT auto-promote ordinary text or a `node` to `outcome`. MUST NOT a researcher “zwaar/licht” or “snel/langzaam” switch. The machine MUST NOT decide that something is light enough to serve.

## 7. Freeze / source integrity

Beslisboom ingest MUST produce a hashed freeze of the canonical boom knowledge used for review (node text + outcome text at minimum).

- MUST NOT treat live kennisplatform REST (`/wp-json/beslisboom/v1/outcomes`) as the sole source of truth for published knowledge.
- Live URL-HTML Storyline `story.html` alone remains insufficient without a freeze of reviewable node/outcome content (align with v2.11 spirit). Live URL-HTML MUST still be rejected at ingest as the sole official file.
- Exact packaging format for boom freeze (ZIP of player vs structured JSON export) MAY be left to the implementation PR, but this protocol MUST require byte-freeze + locators + SHA-256.
- Reserializing, pretty-printing, or re-saving the freeze bytes MUST NOT be used as ingest. A locator bound to reserialized boom content is not a locator into the hashed original.
- Capture remains not publication. The G2 locator still required to publish.

## 8. Class axis

Fit `beslisboom` into family × class without letting boom advice outrank a confirmed `richtlijn` recommendation of the same family.

- `beslisboom` is a document class on the family × class axis. Family remains a hook the ingest researcher sets. Klasse choice selects the review path for that document. Paths MAY differ for the same family.
- Beslisboom is a lighter/derived class than `richtlijn`. Heavier class MUST NOT be filled by lighter class (Protocol v2.8).
- Promoting or substituting boom `outcome`s for unpublished or missing guideline `recommendation`s MUST NOT happen silently.
- A confirmed `richtlijn` `recommendation` of the same family MUST outrank a `beslisboom` `outcome`. A boom MUST NOT fill a gap left by a missing or unpublished higher class as if it were that richtlijn.
- The existing minimum class order `richtlijn` > `handreiking` > `artikel` > `transcript` / `podcast` remains. This delta does not invent a new five-level ranking. It records `richtlijn` > `beslisboom` (same family): boom is derived working method, not a substitute guideline.
- Promoting class MUST require review. Moving a source between families MUST NOT require clinical re-review.

Product API boom serving is not activated by this delta and MUST NOT be activated in the first Forge code wave unless separately GO’d. When boom serving is later GO’d, fail-closed still applies: unpublished boom objects MUST abstain; missing locator MUST abstain; a boom `outcome` MUST NOT outrank a confirmed `richtlijn` `recommendation` of the same family.

## 9. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, EPD UI, or interactive nurse tree player. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement ingest UI, Storyline parser, or API scraper.

Serving / G2 unchanged for the richtlijn path. Only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. Boom serving is not opened here. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol. Do not claim GD-03.

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

G1 technical protection remains ON. The authoritative remote remains public under Protocol v2.5 during the declared MVP period. G0 Azure DEV remains BLOCKED. No Azure/Vercel/Neon in this delta. No Vercel, Neon, or LLM vendor. No locator implementation, no Blob, no claiming G2 PASS. No huisstyle-bar-only tweaks without the bar in sections 3–8. MUST NOT add numpy/sklearn or touch Azure deploy packaging.

## 10. Build order

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement ingest UI, extract, Storyline parser, or API scraper in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.24 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`. MUST NOT merge to main unless repo rules auto-require — this PR is for Metis/William review.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (Forge beslisboom path) after this protocol merges and Metis GO’s that wave.

Where this delta and Protocol v2.24 conflict on which implementation is next, this delta governs. After this protocol merges:

1. Next code MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** the beslisboom path wave: Klasse includes beslisboom; Klasse choice selects review path; boom object model `path`/`node`/`outcome`; review stacks/functions for those types; freeze+locator for boom content; tests.
2. MUST NOT activate Product API boom serving in that first code wave unless separately GO’d.
3. MUST NOT open G2/`publish()`. G2 still BLOCKED; `publish()` still G2-BLOCKED.
4. Until that Forge GO, no Cloud Shell ZIP required for this delta alone. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 richtlijn-path type/projection, v2.13 atomic objects/relations/four-eyes, v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects, v2.17 researcher-surface, v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation, v2.20 every-guideline law / unpublished-snapshot delete, v2.21 wave definitions, v2.22 ZIP-then-B live path, v2.23 first DELETE cut and v2.24 thin-console / one-shared-kernel remain required law, except the bounded supersessions in this file.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing ingest UI, extract, Storyline parser, or API scraper; adding a second Inleveren chooser labeled “path” distinct from Klasse; inventing Klasse values outside the closed set; inventing boom types on `richtlijn` / `handreiking` / `artikel` / `transcript` / `podcast`; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; huisstyle-bar-only tweaks without the bar in sections 3–8; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; auto-promoting ordinary text or a `node` to `outcome`; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11) except boom freeze in the same spirit; reopening richtlijn-path serving typeset (v2.12); reopening atomic objects/relations/four-eyes (v2.13) except boom wiring that reuses the closed set; reopening stamps, chrome, slogans, bronpassage-prose, empty Onderwerp, relation-checkbox adjacency, review-duty / queue presentation, unpublished-snapshot delete except as already required; rewriting v2.16–v2.24 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; live-URL ingest as the sole official boom file; treating live kennisplatform REST as the sole source of truth; silently substituting boom outcomes for unpublished or missing richtlijn recommendations; activating Product API boom serving in the first Forge wave unless separately GO’d; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 11. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning review-surface / retrieve-safety** (MVP beslisboom document class with closed boom types `path` / `node` / `outcome`; closed Klasse set includes `beslisboom`; Klasse choice selects review path; boom freeze+locator; boom MUST NOT outrank a confirmed `richtlijn` recommendation of the same family; console remains not a nurse tree player; no Forge code; no G2 PASS; `publish()` stays G2-BLOCKED). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of the beslisboom path wave, or a later GO of Product API boom serving, remains separately classified, including at least C3 spanning review-surface / retrieve-safety.

## 12. Gates and approval effect

Approval of v2.25 establishes that the owner locked MVP **beslisboom** document class with its own object model **pad / node / uitkomst** (English closed types: `path`, `node`, `outcome`), separate from the richtlijn review path, after comparing four kennisplatform Storyline booms (Valrisico tree 4, Fractuurpreventie tree 2, Mantelzorg tree 3, Eenzaamheid tree 1): one stable family; that at Inleveren the researcher MUST choose **Klasse** from the closed set and that Klasse choice selects the review path; that this SUPERSEDES any reading that Inleveren needs a separate path control distinct from Klasse; that Closed Klasse set MUST include `beslisboom` alongside `richtlijn`, `handreiking`, `artikel`, `transcript`, `podcast`; that Operators MUST NOT invent other Klasse values; that Choosing Klasse = `beslisboom` MUST select the boom review path (`path` / `node` / `outcome`); that Choosing Klasse = `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` MUST select the existing non-boom (richtlijn-style) review path / stacks for that document and MUST NOT invent boom types on those classes; that Paths MAY differ for the same family; that Beslisboom MUST be in the MVP because it is the hangable working method; that Console remains researcher surface and MUST NOT become a nurse-facing interactive tree player; that v2.8 «console MUST NOT be a nurse decision tree» is still true for console UX and reviewing beslisboom objects as researchers is allowed; that boom review needs path/node/outcome as review units, not only loose condition/recommendation fusion from a flat extract; that this SUPERSEDES the Protocol v2.7 reading that kennisplatform `story.html` boom players MUST stay entirely out of the MVP / first console **as a knowledge class**; that the Storyline **player package** is not the Product API surface and MUST NOT be the nurse console; that this SUPERSEDES any reading that the only MVP document classes are guideline HTML/PDF without a boom path; that closed boom types are `path`, `node`, `outcome` and Operators MUST NOT invent others; that a scorelist item MAY be modeled as a `node` with a documented scorelist flag or kind and this delta MUST NOT add a fourth closed boom type; that the richtlijn path keeps `heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation` (+ `unclassified` default) and MUST NOT require boom types; that `outcome` MUST bind to `node` / `path` via `applies_if` (or equivalent confirmed relation) and MUST NOT silently fuse condition into outcome as the only representation; that Cross-guideline references in outcome bodies SHOULD become `supported_by` / `explains` targets when those objects exist and MUST NOT remain body-only forever as the sole link; that MUST confirm `path` as structure (batch OK, NEVER as advice); that MUST confirm `node` (slow if it gates advice); that MUST confirm `outcome` as advice and strength stamps DOEN/OVERWEEG/NIET DOEN apply when the outcome is actionable advice equivalent to recommendation; that «geen actie nodig» maps to `niet_doen` or an explicit no-action outcome that MUST NOT be served as positive advice; that multi-bullet outcomes MUST be split into atomic outcomes OR rejected until split; that empty/placeholder outcomes MUST NOT pass review; that high-risk keeps four-eyes; that Bronpassage + open-original remain required against the boom freeze bytes; that Beslisboom ingest MUST produce a hashed freeze of the canonical boom knowledge used for review (node text + outcome text at minimum); that MUST NOT treat live kennisplatform REST (`/wp-json/beslisboom/v1/outcomes`) as the sole source of truth for published knowledge; that live URL-HTML Storyline `story.html` alone remains insufficient without a freeze; that this protocol MUST require byte-freeze + locators + SHA-256; that exact packaging format MAY be left to the implementation PR; that `beslisboom` is a lighter/derived class than `richtlijn`; that Heavier class MUST NOT be filled by lighter class; that Promoting or substituting boom outcomes for unpublished or missing guideline recommendations MUST NOT happen silently; that a confirmed `richtlijn` recommendation of the same family MUST outrank a `beslisboom` outcome; that next code MUST be Forge on the existing kernel/console for exactly the beslisboom path wave; that MUST NOT activate Product API boom serving in that first code wave unless separately GO’d; that MUST NOT open G2/`publish()`; that Until that Forge GO, no Cloud Shell ZIP required for this delta alone; that `HANDOFF.md` MUST NOT be recreated; that this protocol MUST NOT claim G2 PASS; that G2 remains BLOCKED; that `publish()` remains G2-BLOCKED; that MUST NOT implement ingest UI, extract, Storyline parser, or API scraper in this PR; that MUST NOT rewrite v2.16–v2.24 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded boom-in-MVP and boom-path typeset: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
- implement ingest UI, Storyline parser, or API scraper in this PR;
- convert G2 to PASS;
- claim G2 PASS in this protocol;
- claim GD-03 or publication;
- implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob;
- take this protocol PR as the Cloud Shell ZIP;
- open G2/`publish()`;
- activate Product API boom serving in the first Forge wave unless separately GO’d;
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
- rewrite Protocol v2.16–v2.24 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
- reopen the Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split except the next-implementation reading superseded here;
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
- treat Protocol v2.14 as this file or as the next step.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
