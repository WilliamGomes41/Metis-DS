# V&VN Data Services Protocol v2.30 — Object contract, hard admission gate, reason codes, and normative reviewer passage-flow

**Status:** Approved for project use  
**Protocol delta version:** 2.30.0  
**Approval date:** 2026-09-05  
**Approved by:** Project owner  
**Extends:** Protocol v2.29.0  
**Highest change class:** C3 spanning extract/review-surface / retrieve-safety (a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; missing required field → `gate_result=blocked`; soft scores / volume / “ship then fix” MUST NOT open the hard gate; blocked candidates MUST NOT enter the ordinary review queue; There MUST be NO tradeoff — UI polish MUST NOT excuse bad candidates; current knowledge-object quality is ~5/10 (fail, not a shippable bar); primary reviewer UI MUST use ordinary language only and MUST NOT start from a mandatory Relatie bevestigen / always-visible TOC+full parent list; Open volledige richtlijn / broncontext MUST show real surrounding source context with the exact span marked; SUPERSEDES subjective admission, dumping every assertive sentence into ordinary review, primary Relatie bevestigen as a mandatory chain, always-visible TOC+full parent lists, open-original same-card enlarge, and type UI without proposal+evidence; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR)  
**Normative language:** MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are normative requirements

## 1. Purpose

Protocol v2.30 records the owner-approved lock of 2026-09-05 (William Gomes; Metis CoS GO). Metis is document owner. The Implementation engineer (Forge) writes code later after **separate** Metis GOs for four named phases. Do not redesign the four layers (source/evidence → canonical knowledge → governance → product). Layers remain: frozen source → source passage → knowledge object → human review → published projection. A knowledge object MUST NOT replace the brondocument. G2 and `publish()` remain BLOCKED in this PR.

This is **one focused protocol cut** with **two separate acceptance blocks**. The two blocks MUST be independently testable. A pass of Block A MUST NOT be treated as a pass of Block B. A pass of Block B MUST NOT be treated as a pass of Block A.

Owner lock (normative intent):

### Block A — Hard admission gate, object contract, reason codes

A knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with **literal localizable source text**. Missing required field → `gate_result=blocked`. Soft scores (`relevant` / `complete` / `understandable`) MAY rank only; they MUST NOT open the hard gate. The model MUST NOT fill gaps with “impliciet” prose. Owner reconfirmed GO 2026-09-05: current knowledge-object quality is ~5/10 — a fail of extract quality, not a shippable bar. There MUST be NO tradeoff. UI polish MUST NOT excuse bad candidates. Soft scores / volume / “ship then fix” MUST NOT open the hard gate. Blocked candidates MUST NOT enter the ordinary review queue.

Admission MUST require: full carrying sentence AND `subject_span` AND `predicate_span` AND valid locator AND `type_contract` complete AND `type_evidence` present AND no unresolved core reference AND no incomplete comparison AND context scan done AND found constraints processed.

Hard blocks MUST emit deterministic `reason_codes[]`. Soft scores MUST NOT override a hard block.

### Block B — Reviewer passage-flow, documentpositie, real open-source context

Document position UX SUPERSEDES any primary UI that always shows a TOC list + full parent list + a separate Relatie bevestigen. Internal parent ids MAY remain. The primary UI MUST use ordinary language only (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**). Full hierarchy ONLY after **Andere kop**; body headings only; TOC excluded; search; navigate vs select MUST be distinct. Visibility rule: if the reviewer need not act → do not show; if shown → one clear action in ordinary language. No ouder/kind/parent/confirmed relation on the primary surface.

**Open volledige richtlijn** / **broncontext** MUST show surrounding page/paragraph context from the freeze with the exact span marked — MUST NOT merely enlarge the same truncated card sentence. That surrounding context is **real open-source context**: the previous paragraph, the candidate paragraph, the next paragraph, and current + ancestor headings from the hashed original.

Review UI order + ONE save is normative. v2.28 Sterkte-on-confirmed-type remains.

### Four Forge phases (after separate Metis GOs — NOT this PR)

ROADMAP MUST state four Forge phases after separate Metis GOs:

1. fields + contracts + hard gate + reason codes + dJG regression + minimal adjacent `context_before` / `context_after` (richtlijn inhoudelijke candidates only; boom stays v2.25)
2. context / refs / abbrev / comparisons / expand-merge (deep context window; full `context_scan_done`)
3. review UI + open-bron real context + collapsed document position
4. passage register + coverage + gold + metrics (passage register MUST NOT be a Phase-1 admission prerequisite)

This PR is protocol-only. MUST NOT implement any Forge phase in this PR. MUST NOT recreate `HANDOFF.md`. MUST NOT open G2/`publish()`.

v2.29 temporary production-only deploy remains law (UNCHANGED). v2.28 Sterkte-on-confirmed-type remains law (UNCHANGED). v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm remains law (UNCHANGED). v2.26 Klasse wijzigen first wave is already on `main`. v2.25 boom path UNCHANGED — Phase-1 hard admission contracts apply to richtlijn inhoudelijke candidates; boom `path` / `node` / `outcome` follow Protocol v2.25 until a separate boom-gate GO. Four layers UNCHANGED. Console remains not a nurse tree player. Metis / Forge / Auditor MUST NOT count as GD-03 reviewers.

Live baseline on `main` before this delta is Protocol v2.29.0 plus Protocol v2.28.0 plus Protocol v2.27.0 plus Protocol v2.26.0 plus Protocol v2.25.0 plus Protocol v2.24.0 plus Protocol v2.23.0 plus Protocol v2.22.0 plus Protocol v2.21.0 plus Protocol v2.20.0 plus Protocol v2.19.0 plus Protocol v2.18.0 plus Protocol v2.17.0 plus Protocol v2.16.0 plus Protocol v2.15.0 plus Protocol v2.13.0 plus Protocol v2.12.0 plus Protocol v2.11.0. Protocol v2.2.0, v2.3.0, v2.4.0, v2.5.0, v2.6.0, v2.7.0, v2.8.0, v2.9.0, v2.10.0, v2.11.0, v2.12.0, v2.13.0, v2.15.0, v2.16.0, v2.17.0, v2.18.0, v2.19.0, v2.20.0, v2.21.0, v2.22.0, v2.23.0, v2.24.0, v2.25.0, v2.26.0, v2.27.0, v2.28.0, v2.29.0 and this delta jointly form normative baseline v2.30.0. Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds; captured → classified → reviewed → approved → published → superseded → withdrawn → archived) is LOCKED as the later lifecycle/time delta and MUST NOT be written now. This file is not Protocol v2.14.

This is a **bounded supersession**. It SUPERSEDES any reading that admission MAY be subjective; that every assertive sentence MAY be dumped into the ordinary review queue; that UI polish MAY excuse bad candidates; that volume or “ship then fix” MAY open the hard gate; that a blocked candidate MAY enter the ordinary review queue; that the primary reviewer surface MUST show Relatie bevestigen as a mandatory chain; that the primary UI MUST always show a TOC list + full parent list; that **Open volledige richtlijn** / open-original MAY merely enlarge the same truncated card sentence; or that type UI MAY start from only “nog niet bevestigd” without a Metis proposal + evidence. Replace with: a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; missing required field → `gate_result=blocked`; soft scores MAY rank only and MUST NOT open the hard gate; soft scores / volume / “ship then fix” MUST NOT open the hard gate; blocked candidates MUST NOT enter the ordinary review queue; There MUST be NO tradeoff — UI polish MUST NOT excuse bad candidates; current knowledge-object quality is ~5/10 (fail, not a shippable bar); the model MUST NOT fill gaps with “impliciet” prose; primary UI MUST use ordinary language only (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**); full hierarchy ONLY after **Andere kop**; body headings only; TOC excluded; **Open volledige richtlijn** / broncontext MUST show surrounding page/paragraph context with the exact span marked; type UI MUST show the Metis proposal + **Dit klopt** / **Type wijzigen**. It does NOT supersede: freeze/locator (v2.11), four-eyes high-risk (v2.13), v2.28 Sterkte-on-confirmed-type, v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm, v2.25 boom path, v2.26 Klasse wijzigen, v2.29 temporary production-only deploy, or fail-closed G2.

Where this delta and those «subjective admission» / «dump every assertive sentence» / «primary Relatie bevestigen mandatory chain» / «always-visible TOC+full parent lists» / «open-original same-card enlarge» / «type UI without proposal+evidence» readings conflict, this delta governs. Historical Continentie evidence sentences in Protocol v2.16–v2.19 MUST remain. Those sentences are live evidence of fails, not the product identity. Durable immutable storage is not skipped. The G2 locator remains the publication blocker. Capture remains not publication. For all other requirements, the stricter fail-closed requirement applies.

The v2.12 closed serving typeset for the **richtlijn** path remains UNCHANGED:

`heading`, `definition`, `explanation`, `condition`, `exception`, `recommendation`

plus `unclassified` as default, not a sixth advice type. Operators MUST NOT invent serving types on the richtlijn path. Admission/review **type contracts** in this delta (Aanbeveling, Definitie, Voorwaarde, Uitzondering, Feitelijke constatering, Toelichting) are the required-field contracts for proposing a **richtlijn-path** candidate. They do NOT apply to boom `path` / `node` / `outcome` (Protocol v2.25 UNCHANGED until a separate boom-gate GO). Feitelijke constatering is an admission/review contract for a factual claim; it MUST NOT invent a seventh closed serving type; when confirmed it MUST map to existing closed serving type `explanation`; it MUST NOT be served as recommendation / handelingsadvies; it MUST NOT enter the ordinary queue as Aanbeveling.

The v2.25 closed boom-path typeset remains UNCHANGED:

`path`, `node`, `outcome`

Operators MUST NOT invent other boom types. MUST NOT require boom types on the richtlijn path. Closed Klasse set remains:

`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`

Operators MUST NOT invent other Klasse values.

Four layers remain: frozen source → source passage → knowledge object → human review → published projection, which is the same four-layer stack as source/evidence → canonical knowledge → governance → product. This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. A knowledge object MUST NOT replace the brondocument. `HANDOFF.md` MUST NOT be recreated.

All Protocol v2.6 room rules, all Protocol v2.7 first-wave source, retrieve-and-abstain and distribution rules (except the v2.11 HTML-URL supersession and except the v2.7 `story.html`-boom-out-of-MVP-as-a-knowledge-class reading superseded by Protocol v2.25), all Protocol v2.8 primary-user and two-axis hierarchy rules (except any reading that a class change is a silent total wipe of all review state as the only story, superseded by Protocol v2.26, and except any reading that reviewing boom objects as researchers would violate the nurse-tree rule), all Protocol v2.9 researcher-task UX and V&VN digital-brand rules (except the short-help via-negativa reading superseded by Protocol v2.17, and except the researcher-facing action name **Promoveren** superseded by Protocol v2.26 **Klasse wijzigen**), all Protocol v2.10 Documentenhierarchie, waiting-task badge and Accounts-room rules (except the console-label **Promoveren** superseded by Protocol v2.26; «Klasse promoveren MUST review» remains as the review requirement), all Protocol v2.11 freeze/locator rules (except researcher-visible bronpassage prose in Protocol v2.17; boom freeze extends the same spirit in Protocol v2.25; this delta SUPERSEDES any reading that open-original MAY merely enlarge the same truncated card sentence), all Protocol v2.12 type/review/projection rules for the **richtlijn** path, all Protocol v2.13 atomic-object, classification, closed-relation and high-risk four-eyes rules (except any reading that admission MAY be subjective, that the model MAY fill missing required fields with “impliciet” prose, or that every assertive sentence MAY enter the ordinary review queue; four-eyes high-risk remains UNCHANGED), all Protocol v2.15 ingest-date, ingest-version and type-based review-lane rules, all Protocol v2.16 one-door, two-stack, compact-row, stamp and tiny-object rules (except the stamp-UI-on-proposed-type reading superseded by Protocol v2.28, and except any reading that type UI MAY start from only “nog niet bevestigd” without a Metis proposal + evidence, superseded here), all Protocol v2.17 slogan, HELP_ONCE via-negativa, empty-Onderwerp, bronpassage-prose, chrome-extract, stamp-UI-on-recommendation and compact-relation-checkbox rules (except the stamp-UI-MAY-appear-on-proposed-type reading superseded by Protocol v2.28, and except any reading that primary Relatie bevestigen is a mandatory chain or that open-original MAY merely enlarge the card sentence, superseded here), all Protocol v2.18 once-only card sentence, grammatical-continuation-split and identical-`clean_text` rules, all Protocol v2.19 review-duty / queue-presentation rules (except any reading that every assertive sentence MUST enter the ordinary review queue, superseded here; the duty remains to assess normative/application-critical knowledge, not to objectify every sentence), all Protocol v2.20 every-guideline-law / unpublished-snapshot-delete rules (except the document-card / Review-chooser alternative-surface reading superseded by Protocol v2.27), all Protocol v2.21 wave-definition / G2-evidence / recoverability rules, all Protocol v2.22 ZIP-then-B live-path rules (except as already superseded by Protocol v2.23), all Protocol v2.23 first-DELETE-cut / keep-list / two-product / CLI-review-queue / PR-#82-closed rules, all Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split rules, all Protocol v2.25 MVP-beslisboom / Klasse-selects-review-path / `path`/`node`/`outcome` / boom-freeze / boom-MUST-NOT-outrank-richtlijn rules, all Protocol v2.26 Klasse wijzigen / controlled-reclassification / source-unchanged / same-model vs cross-model / published-never-rewritten rules, all Protocol v2.27 unpublished-delete Documentenhiërarchie-only + type-to-confirm rules, all Protocol v2.28 structural heading / parent-list navigation + confirmed-type Sterkte gate rules (except the primary always-visible TOC+full parent list + Relatie bevestigen reading superseded here; v2.28 Sterkte-on-confirmed-type remains; body-heading hierarchy after **Andere kop** still uses v2.28 structural validity), and all Protocol v2.29 temporary production-only deploy rules remain in force, except the readings superseded in sections 3–12. This protocol-only change does not implement console Python, extract, kernel, Product API, Azure, G2 PASS or `publish()`. Do not rewrite `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py` in this protocol change. MUST NOT rewrite v2.16–v2.29 files except index/conflict pointers. MUST NOT implement Forge phases 1–4 in this PR. Do not reopen freeze/locator (v2.11), four-eyes high-risk (v2.13), v2.28 Sterkte gate, v2.27 delete, v2.25 boom, v2.26 Klasse wijzigen, v2.29 temp prod deploy, or fail-closed G2 except as already required.

This delta also sets the next concrete **code** implementation after this protocol. The next **code** after this protocol's own Metis GO MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** Forge phase 1 in section 12, then phase 2, then phase 3, then phase 4 — each after its own separate Metis GO. MUST NOT implement those phases in this protocol PR. MUST NOT open G2/`publish()`. Until those Forge GOs, no Cloud Shell ZIP required for this delta alone. Protocol v2.14 is still not written and is still not the next step.

G2 remains BLOCKED. `publish()` remains G2-BLOCKED. This protocol does not claim G2 PASS. MUST NOT claim G2 PASS. MUST NOT claim GD-03 or publication.

This is not a GD-03 knowledge-publish. G2 remains the publication blocker. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers, MUST NOT approve, and MUST NOT publish.

## 2. Unchanged v2.6 through v2.29 rules

The four layers remain frozen source → source passage → knowledge object → human review → published projection (source/evidence → canonical knowledge → governance → product). This delta MUST NOT invent a fifth layer and MUST NOT collapse those four. A knowledge object MUST NOT replace the brondocument.

The internal operations console remains authorized DS scope (Protocol v2.6). The authorized inspection surface is the operations console. Every rule in Protocol v2.6.0 through Protocol v2.29.0 remains mandatory as already written, except the readings superseded here.

v2.11 freeze/locator remains law. v2.12 closed serving types for the **richtlijn** path remain UNCHANGED. v2.13 atomic objects, closed relations and four-eyes remain (unconfirmed relations still MUST NOT bind; four-eyes high-risk UNCHANGED). v2.16 stamps on `recommendation` remain for the richtlijn path; v2.28 confirmed/stored-type Sterkte gate remains. v2.8 «console MUST NOT be a nurse decision tree» remains true for console UX. v2.25 boom path remains UNCHANGED. v2.26 Klasse wijzigen / controlled reclassification remains UNCHANGED. v2.27 unpublished-delete Documentenhiërarchie only + type-to-confirm remains UNCHANGED. v2.28 structural heading / parent-list navigation remains for the **Andere kop** hierarchy (body headings; TOC marked separately; structurally valid parent). v2.29 temporary production-only deploy remains UNCHANGED. Waves A–D / deploy split remain. Fail-closed G2 remains. `publish()` stays G2-BLOCKED. `HANDOFF.md` MUST NOT be recreated.

v2.8 / v2.10 «Klasse promoveren MUST review» remains as the review requirement: a class change MUST require review. Moving a source between families MUST NOT require clinical re-review. Heavier class MUST NOT be filled by lighter class.

## 3. Block A — Kernel: propose only on a complete type contract

A knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text taken from the freeze.

Missing any required field for the proposed type → `gate_result=blocked`. Soft scores (`relevant` / `complete` / `understandable`) MAY rank blocked or allowed candidates for later inspection. Soft scores MUST NOT open the hard gate. A high soft score MUST NOT change `blocked` to `allowed`. Volume (more candidates, a fuller queue, “enough objects”) MUST NOT open the hard gate. “Ship then fix” MUST NOT open the hard gate. UI polish MUST NOT excuse bad candidates. There MUST be NO tradeoff between reviewer-surface polish and candidate quality. Owner reconfirmed GO 2026-09-05: current knowledge-object quality is ~5/10 — a fail, not a shippable bar. That score MUST NOT be treated as acceptance. Blocked candidates MUST NOT enter the ordinary review queue.

The model MUST NOT fill gaps with “impliciet” prose. If the freeze does not contain the required literal text, the field is missing. Invented, inferred, or “impliciet in de context” filler is `source_fidelity_failure` and MUST block.

`source_text_exact` is immutable. Normalized / paraphrased text MAY exist only after human confirm. Paraphrase MUST NOT strengthen meaning. Strengthening a hedge, widening a population, dropping a condition, or turning a comparison into advice is `source_fidelity_failure` / paraphrase-strengthening and MUST block publication of that paraphrase.

## 4. Block A — Required candidate fields before human review

Before a candidate MAY enter human review, the candidate record MUST carry all of the following fields:

- `candidate_id`
- `document_id`
- `document_version`
- `source_hash`
- `section_path`
- `source_locator_start`
- `source_locator_end`
- `source_text_exact`
- `candidate_text`
- `subject_span`
- `predicate_span`
- `proposed_type`
- `type_evidence_spans`
- `context_before`
- `context_after`
- `conditions_detected`
- `exceptions_detected`
- `comparison_markers`
- `comparison_targets`
- `references_detected`
- `references_resolved`
- `abbreviations_detected`
- `abbreviations_resolved`
- `related_candidates`
- `gate_result` (`allowed` | `blocked`)
- `reason_codes[]`

Empty arrays are allowed where the scan found nothing (for example `conditions_detected=[]` after a completed scan). A missing field (the field is absent, or a required span is empty when the type contract requires it) is not an empty-array success. `gate_result` MUST be exactly `allowed` or `blocked`. `reason_codes[]` MUST be present; it MAY be empty only when `gate_result=allowed` and no warning codes apply.

Admission MUST require all of the following at once **on the completed pipeline** (after Forge phases 1–2 exist):

1. a full carrying sentence
2. `subject_span`
3. `predicate_span`
4. a valid locator (`source_locator_start` / `source_locator_end` against the hashed freeze; Protocol v2.11)
5. `type_contract` complete for `proposed_type` (richtlijn-path contracts in this section; boom excluded — see below)
6. `type_evidence` present (`type_evidence_spans` pointing at literal freeze text)
7. no unresolved core reference
8. no incomplete comparison
9. context scan done (full Phase-2 window)
10. found constraints processed (detected conditions / exceptions / comparisons / references / abbreviations either resolved, linked, or turned into a hard `reason_code`)

Failure of any one **active** item → `gate_result=blocked`.

**Phase-1 admission set (normative now, so a conforming Phase-1 MUST be able to emit `allowed`):** items 1–6 PLUS a **minimal** `context_before` / `context_after` taken from the adjacent sentence or paragraph, sufficient for the hard gate and the dJG regression. Phase 1 MUST also emit the catalog hard `reason_codes` those checks produce. Phase 1 MUST NOT treat `context_scan_not_done` as a universal hard block on every candidate. Phase 1 MUST NOT empty the ordinary review queue with `context_scan_not_done` merely because the Phase-2 deep context window does not yet exist. The full context scan (candidate paragraph + previous paragraph + next paragraph + current + ancestor headings; conditions/exceptions linking; expand/merge) is Phase 2. Passage-register assignment is Phase 4 and MUST NOT be a Phase-1 admission prerequisite. Until Phase 4 exists, a missing passage-register status MUST NOT by itself set `gate_result=blocked`.

This Phase-1 hard-gate scope applies to **richtlijn inhoudelijke candidates** only (`richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast`). Boom types `path` / `node` / `outcome` remain under Protocol v2.25 closed contracts UNCHANGED. This delta MUST NOT force boom candidates through the six richtlijn contracts and MUST NOT invent incomplete boom contracts. A boom candidate MUST NOT receive `type_contract_incomplete` merely because it is `path`, `node`, or `outcome`. Boom candidates follow Protocol v2.25 until a **separate boom-gate GO**.

## 5. Block A — Type contracts

Closed admission/review type contracts for the **richtlijn path** (Dutch name + English closed token). Operators MUST NOT invent other admission contracts in this delta. Operators MUST NOT invent boom admission contracts in this delta. Boom `path` / `node` / `outcome` stay Protocol v2.25 until a separate boom-gate GO.

### Aanbeveling (`recommendation`)

MUST include all of:

- `actor_of_scope`
- `recommended_action`
- `action_object_or_goal`
- `recommendation_evidence_span`

MAY include: audience, setting, condition, exception, strength.

Missing `recommendation_evidence_span` → `recommendation_evidence_missing` → blocked. A comparison, prevalence, or “wordt vaker gebruikt” sentence is not recommendation evidence. Soft “this sounds like advice” MUST NOT open the gate.

v2.28 Sterkte-on-confirmed-type remains: Sterkte visible and active ONLY when stored/confirmed type is Aanbeveling (`recommendation`) OR an actionable boom `outcome`. A machine proposal MUST NOT activate Sterkte.

### Definitie (`definition`)

MUST include: `defined_term` + `definiens_span` from literal freeze text. Out: action advice; “X is geïndiceerd”. Serving: MUST NOT receive advice-weight (Protocol v2.13 UNCHANGED).

### Voorwaarde (`condition`)

MUST include: `condition_span` + `condition_target` (the claim / recommendation / population the condition bounds). Missing target → `condition_target_missing` → blocked. Serving: MAY bound advice only via confirmed `applies_if`. MUST NOT receive advice-weight.

### Uitzondering (`exception`)

MUST include: `exception_span` + `exception_target`. Missing target → `exception_target_missing` → blocked. A lone exception without a target MUST NOT enter the ordinary queue as an independent claim (`no_independent_claim` and/or `exception_target_missing`). Serving: MAY bound advice only via confirmed `except_if`. ALWAYS high-risk (four-eyes UNCHANGED).

### Feitelijke constatering (`factual_finding`)

MUST include: `factual_claim_span` from literal freeze text. This is an admission/review **contract**, not a serving type. MUST NOT invent a seventh closed serving type. MUST NOT be proposed, queued, confirmed, or served as Aanbeveling / `recommendation` / handelingsadvies. A factual comparison without a comparison target is still blocked (`comparison_target_missing`) even under this contract.

**Canonical mapping (explicit):** when a Feitelijke constatering is confirmed, the stored/confirmed serving type MUST be the existing closed type `explanation`. Confirm → `explanation`. MUST NOT serve that object as recommendation / handelingsadvies (Protocol v2.13: `explanation` MUST NOT receive advice-weight). Type-confirmation MUST NOT write `confirmed_object_type=factual_finding`. If the passage cannot be confirmed as `explanation` under the Toelichting contract (no `support_span` / no `supported_object`), it MUST remain blocked from serving (`supported_object_missing` and/or `no_independent_claim`) until it maps. Prefer confirm → `explanation` when the support link exists.

### Toelichting (`explanation`)

MUST include: `support_span` + `supported_object`. Missing supported object → `supported_object_missing` → blocked. Toelichting is not independently publishable by default. MUST NOT enter the ordinary queue as an independent claim when no supported object is linked (`no_independent_claim` and/or `supported_object_missing`). Serving: MUST NOT receive advice-weight.

## 6. Block A — Deterministic reason_codes

Hard blocks MUST include at least the following deterministic `reason_codes` (owner plan catalog). Implementation MUST emit the named code; synonyms MUST NOT replace these tokens.

| `reason_code` | MUST block when |
|---|---|
| `incomplete_sentence` | no full carrying sentence |
| `subject_missing` | `subject_span` empty or not literal freeze text |
| `predicate_missing` | `predicate_span` empty or not literal freeze text |
| `unresolved_reference` | a core reference is detected and not resolved |
| `comparison_target_missing` | a comparison marker is present and the comparison target is missing |
| `abbreviation_unresolved` | an abbreviation is detected and not resolved |
| `table_of_contents_entry` | the passage is a TOC / inhoudsopgave entry, not a body claim |
| `editorial_transition_only` | the passage is only an editorial transition (no independent claim) |
| `recommendation_evidence_missing` | proposed Aanbeveling lacks `recommendation_evidence_span` |
| `condition_target_missing` | a condition is detected / proposed and has no target |
| `exception_target_missing` | an exception is detected / proposed and has no target |
| `supported_object_missing` | Toelichting has no supported object |
| `no_independent_claim` | the passage cannot stand as one independently confirmable meaning |
| `duplicates` | identical confirmable meaning already emitted from this freeze |
| `source_fidelity_failure` | text is invented, “impliciet” filled, or a paraphrase strengthens meaning |

Additional deterministic codes that the admission list requires. Implementation MUST emit these when the matching admission check fails:

| `reason_code` | MUST block when |
|---|---|
| `locator_invalid` | locator missing, empty, or not bound to the hashed freeze |
| `type_contract_incomplete` | a required field of the proposed type contract is missing |
| `type_evidence_missing` | `type_evidence_spans` empty or not literal freeze text |
| `context_scan_not_done` | required **Phase-2** full context scan was not performed **after Phase 2 exists**. Phase 1 MUST NOT emit this code for every candidate merely because the Phase-2 scanner is not yet implemented. Phase 1 uses minimal adjacent `context_before` / `context_after` instead. |
| `context_necessary_unresolved` | necessary context was found and was neither included nor linked |
| `context_unnecessary_unrecorded` | the machine claims context is unnecessary without recording checked signals |

A blocked candidate MUST NOT enter the ordinary review queue. `gate_result=blocked` MUST NOT be presented as an ordinary-queue item, as an allowed Aanbeveling, or as any allowed inhoudelijk object. Blocked candidates MAY be inspectable in a blocked/audit lane. Soft scores MUST NOT move them into the ordinary queue. Volume MUST NOT move them into the ordinary queue. “Ship then fix” MUST NOT move them into the ordinary queue. UI polish MUST NOT excuse a blocked candidate.

## 7. Block A — Context scan, atomicity, passage register

Context scan MUST cover: the candidate paragraph + previous paragraph + next paragraph + current heading + ancestor headings. Necessary context → include OR link OR block. The machine MUST NOT claim that context is unnecessary without recording the checked signals (`context_unnecessary_unrecorded` if it does).

Atomicity: one independently confirmable meaning **including** required conditions and exceptions — NOT always one word and NOT always one sentence. MUST NOT split into broken fragments (`incomplete_sentence` / `no_independent_claim` / `fragment` under `source_fidelity_failure`). MUST NOT fuse a condition into a recommendation as the only representation (Protocol v2.13 fusion forbid UNCHANGED). A recommendation that grammatically carries its exception MAY stay one object when splitting would break the single grammatical claim; the exception MUST still be detected and either linked or kept as a processed constraint.

Passage register statuses (closed):

- `selected_as_candidate`
- `used_as_context`
- `linked_as_support`
- `excluded_with_reason`
- `not_yet_assessed`

MUST NOT silently drop passages. Coverage reporting MUST be per section. There is no duty to objectify every sentence. There **is** a duty to assess normative / application-critical knowledge. Dumping every assertive sentence into the ordinary review queue is SUPERSEDED.

## 8. Block A — Mandatory regressions (including dJG)

Mandatory regression **dJG** (literal freeze sentence):

> De dJG wordt in Nederland vaker gebruikt.

This sentence MUST NOT enter the ordinary queue as Aanbeveling. `reason_codes` MUST include `recommendation_evidence_missing`, `comparison_target_missing`, and `abbreviation_unresolved` (when the abbreviation remains unresolved). Soft “sounds like a recommendation” MUST NOT open the gate.

Also regress, as independently named cases:

1. **one-word** — a single word / stamp / nav token MUST NOT become an inhoudelijk object (`incomplete_sentence` and/or `no_independent_claim` and/or `subject_missing` / `predicate_missing` as applicable).
2. **unresolved ref** — a core reference left unresolved → `unresolved_reference` → blocked.
3. **incomplete comparison** — a comparison marker without a target → `comparison_target_missing` → blocked.
4. **false recommendation** — a factual / comparative / prevalence sentence proposed as Aanbeveling → `recommendation_evidence_missing` (and any other matching codes) → blocked from the ordinary queue as Aanbeveling.
5. **full “adviseert” recommendation** — a carrying sentence with actor, recommended action, action object/goal, and literal recommendation evidence MAY be proposed as Aanbeveling when the type contract is complete (example shape from open V&VN guideline prose: a werkgroep/richtlijn **adviseert** a named actor to perform a named action on a named object, with the advice sentence itself as `recommendation_evidence_span`).
6. **lone exception** — an exception without a target MUST NOT enter as an independent ordinary-queue object (`exception_target_missing` and/or `no_independent_claim`).
7. **recommendation+exception** — a recommendation that requires its exception MUST include or link that exception; dropping the exception is `source_fidelity_failure` and/or an unprocessed constraint.

Real open-source context is normative for these regressions: the reviewer (and the later Open-bron surface) MUST be able to see the surrounding freeze paragraph, not only the isolated sentence. The dJG sentence in isolation is insufficient context; the scan MUST still record prev/next paragraph and headings.

## 9. Block B — Documentpositie UX (ordinary language)

Document position UX SUPERSEDES any primary UI that always shows a TOC list + full parent list + a separate **Relatie bevestigen**.

Internal parent ids MAY remain in the kernel. The primary UI MUST use ordinary language only:

- **Gevonden onder**
- **Dit klopt**
- **Andere kop kiezen**

Full hierarchy ONLY after **Andere kop**. That hierarchy MUST use body headings only (Protocol v2.28: TOC / inhoudsopgave excluded from the choice list; structurally valid parent; no naive global numeric sort of TOC+body). Search MUST be available on that expanded chooser. Navigate vs select MUST be distinct: browsing the tree MUST NOT silently select a parent.

Visibility rule: if the reviewer need not act → do not show; if shown → one clear action in ordinary language. No ouder / kind / parent / confirmed relation on the primary surface.

v2.28 structural validity remains for the expanded chooser: heading `5.4.1` MUST NOT get heading `2` as parent merely because it was extracted nearby.

## 10. Block B — Open broncontext is real surrounding source, not card enlarge

**Open volledige richtlijn** / **broncontext** MUST show surrounding page/paragraph context from the freeze with the exact candidate span marked.

MUST NOT merely enlarge the same truncated card sentence. A zoom of `candidate_text` / the compact-row snippet is not broncontext.

Real open-source context MUST include at least:

- the candidate paragraph
- the previous paragraph (when it exists)
- the next paragraph (when it exists)
- the current heading and ancestor headings

The exact `source_text_exact` span MUST be visually marked inside that surrounding context. Locators remain Protocol v2.11. Freeze bytes MUST NOT be reserialized.

Normative shape (open V&VN-style freeze, not a mock card):

```
[ancestor] Signalering
[heading]  Aanbevelingen
[prev]     Bij een cliënt ≥ 60 jaar zonder recente fractuur …
[MARKED]   De werkgroep adviseert de risicofactoren scorelijst te gebruiken …
[next]     Overleg bij een vastgesteld verhoogd fractuurrisico met de cliënt …
```

The marked span is the candidate. The surrounding lines are freeze context. Replacing those surrounding lines with a larger rendering of the same marked sentence is forbidden.

## 11. Block B — Review UI order + ONE save

Review UI order is normative. ONE save. Button: **Review opslaan en volgende**.

1. **(A)** selected passage + why selected
2. **(B)** broncontext (real surrounding source; section 10)
3. **(C)** suitability question with options: **Ja** / **mist context** / **samenvoegen** / **alleen onderbouwing** / **geen kenniseenheid**
4. **(D)** documentpositie (section 9)
5. **(E)** type: show the Metis proposal + **Dit klopt** / **Type wijzigen** — MUST NOT start from only “nog niet bevestigd”
6. **(F)** eindoordeel: **Goedkeuren** / **Goedkeuren na correctie** / **Afwijzen** / **Later beoordelen**

v2.28 Sterkte-on-confirmed-type remains: Sterkte appears only after stored/confirmed Aanbeveling (or actionable boom `outcome`), live before submit.

## 12. Validation pipeline, publication gate, metrics, gold, Forge phases

Validation pipeline order is normative for the **completed** law (after the matching Forge phases exist):

1. Freeze / locator integrity (Protocol v2.11; `source_hash`; valid locator)
2. Passage register status assignment (section 7; MUST NOT silently drop) — **Phase 4**; MUST NOT be a Phase-1 admission prerequisite
3. Hard admission gate (sections 3–6; required fields + richtlijn type contract + evidence + Phase-1 minimal adjacent context)
4. Full context scan (section 7) — **Phase 2** deep window (conditions/exceptions linking, expand/merge, refs/abbrev/comparisons). Phase 1 uses only minimal adjacent `context_before` / `context_after`.
5. `reason_codes[]` + `gate_result`
6. Human review of `allowed` candidates only, in the section 11 order
7. Publication gate — still G2-BLOCKED; `publish()` stays G2-BLOCKED

**Phase-1 runnable pipeline** (so Phase 1 can admit `allowed` candidates): step 1 → step 3 with the Phase-1 admission set (required fields, richtlijn type contracts, hard blocks, reason codes, dJG regression, minimal adjacent context) → step 5 → step 6 for those `allowed` candidates. MUST NOT insert step 2 before the Phase-1 gate. MUST NOT require step 4 as a Phase-1 hard block. A conforming Phase-1 implementation MUST NOT return `context_scan_not_done` for every candidate.

Soft scores MAY run in parallel for ranking. They MUST NOT sit before the hard gate as an opener. They MUST NOT replace `reason_codes`. Soft scores / volume / “ship then fix” MUST NOT open the hard gate. Human review in this pipeline is of `allowed` candidates only. Blocked candidates MUST NOT enter the ordinary review queue.

Metrics MUST be required by protocol (implementation MAY be later Forge phase 4):

- precision
- type accuracy
- context completeness
- coverage vs gold
- review burden

A gold standard is required before claiming extract quality. MUST NOT claim extract quality from soft scores, from a single guideline, or without gold.

ROADMAP MUST state four Forge phases after separate Metis GOs. This PR is protocol-only. MUST NOT implement those phases here.

1. fields + contracts + hard gate + reason codes + dJG regression + minimal adjacent `context_before` / `context_after` (richtlijn inhoudelijke candidates only; boom stays v2.25)
2. context / refs / abbrev / comparisons / expand-merge (deep context window; full `context_scan_done`)
3. review UI + open-bron real context + collapsed document position
4. passage register + coverage + gold + metrics (passage register MUST NOT be a Phase-1 admission prerequisite)

## 13. Unchanged fail-closed product boundary

The console MUST NOT be a nurse-facing care app, chatbot, public website, EPD UI, or interactive nurse tree player. Chat is not a room. Publication remains fail-closed without G2. This delta does not implement console, extract, review queues, API, Azure or `publish()`. This delta does not implement the new UI.

Serving / G2 unchanged. Only confirmed `recommendation` MAY return `supported` / handelingsadvies on the richtlijn path. Boom serving is not opened here. The machine MUST NOT decide that something is light enough to serve. Four-eyes unchanged for type-confirm and high-risk. Protocol v2.14 unchanged (not written, not next). Azure unchanged in this protocol PR (not this change). G2 remains the publication blocker. This delta does not implement `publish()` PASS, Azure ZIP, app settings, identity, or Blob. Capture is not publication. Do not claim G2 PASS in this protocol. Do not claim GD-03.

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

## 14. Build order — four Forge phases after separate Metis GOs (NOT this PR)

This PR is protocol-only. PROTOCOL → tests → code later. Do not change `src/operations_console_*.py`, `src/extract_*.py` or `src/product_api_*.py`. MUST NOT implement Forge phases 1–4 in this PR. MUST NOT start Azure in this protocol PR. MUST NOT rewrite v2.16–v2.29 files except index/conflict pointers. MUST NOT recreate `HANDOFF.md`. MUST NOT merge to main unless repo rules auto-require — this PR is for Metis/William review.

Do not build a mockup. Do not wait for Azure, Vercel, Neon or a finished "DS" before the next code (Forge phase 1) after this protocol merges and Metis GO’s that phase.

After this protocol merges:

1. Next code after this protocol's own Metis GO MUST be Forge (Implementation engineer) on the existing kernel/console for **exactly** phase 1 (fields + richtlijn contracts + hard gate + reason codes + dJG regression + minimal adjacent context; boom stays v2.25; MUST NOT empty the ordinary queue with `context_scan_not_done`; passage register is not a Phase-1 admission prerequisite), with tests-before-code — NOT this PR.
2. Phase 2 (context / refs / abbrev / comparisons / expand-merge; deep context window) MUST wait for its own Metis GO.
3. Phase 3 (review UI + open-bron real context + collapsed document position) MUST wait for its own Metis GO.
4. Phase 4 (passage register + coverage + gold + metrics) MUST wait for its own Metis GO. Passage register MUST NOT be a Phase-1 admission prerequisite.
5. MUST NOT open G2/`publish()`. G2 still BLOCKED; `publish()` still G2-BLOCKED.
6. MUST NOT Azure ZIP, nurse UI, or recreate `HANDOFF.md`.
7. Until those Forge GOs, no Cloud Shell ZIP required for this delta alone. MUST NOT treat this protocol PR as Azure ZIP. MUST NOT Cloud Shell this protocol PR.

No G2 PASS. No Blob grant. Do not start Azure in this protocol PR. Azure/G2 MUST stay out of this delta (no locator implementation, no Blob, no claiming G2 PASS). This delta does not implement `publish()` PASS.

v2.11 freeze/locator, v2.12 richtlijn-path type/projection, v2.13 atomic objects/relations/four-eyes (except the subjective-admission / impliciet-gap-fill readings superseded here; four-eyes high-risk UNCHANGED), v2.15 ingest date/version/type-lanes, v2.16 one-door/stacks/rows/stamps/tiny-objects (except type UI without proposal+evidence), v2.17 researcher-surface (except primary Relatie bevestigen mandatory chain and open-original same-card enlarge), v2.18 once-only card / trailing-clause / identical-`clean_text`, v2.19 review duty / queue presentation (except dump-every-assertive-sentence), v2.20 every-guideline law / unpublished-snapshot delete (except the document-card / Review-chooser alternative-surface reading superseded by v2.27), v2.21 wave definitions, v2.22 ZIP-then-B live path, v2.23 first DELETE cut, v2.24 thin-console / one-shared-kernel, v2.25 boom path, v2.26 Klasse wijzigen / controlled reclassification, v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm, v2.28 structural heading / confirmed-type Sterkte (Sterkte gate UNCHANGED; primary always-visible TOC+full parent + Relatie bevestigen superseded here), and v2.29 temporary production-only deploy remain required law, except the bounded supersessions in this file.

Protocol v2.14 (lifecycle names and `valid_from` / `valid_until` serving bounds) is LOCKED as a later protocol, not this file, and is still not the next step. This delta MUST NOT write Protocol v2.14. Lock v2.14 only when the first official source has a date that must bound serving. G2 still blocks publish, so that wait is for a real dated source, not for more UX deltas. Ingest source date on the freeze is not `valid_from` / `valid_until`.

Out of scope for this PR and this delta: implementing Forge phases 1–4; implementing fields, contracts, hard gate, reason codes, or dJG regression in `src/`; implementing context/refs/abbrev/comparisons/expand-merge; implementing review UI, open-bron real context, or collapsed document position; implementing passage register, coverage, gold, or metrics; filling missing required fields with “impliciet” prose; opening the hard gate with soft scores / volume / “ship then fix”; letting blocked candidates enter the ordinary review queue; treating UI polish as an excuse for bad candidates; treating ~5/10 knowledge-object quality as a shippable bar; dumping every assertive sentence into the ordinary review queue; keeping Relatie bevestigen as a mandatory primary chain; always-visible TOC+full parent lists on the primary surface; enlarging the same truncated card sentence as Open volledige richtlijn; starting type UI from only “nog niet bevestigd”; silently dropping passages; claiming extract quality without gold; implementing Klasse wijzigen selective invalidation, published-candidate fork, or full `previous_review` schema; implementing console/extract/Azure; merging product code; G2 PASS; Protocol v2.14; LLM; nurse UI / nurse-facing interactive tree player; SSH wipe; hiding fragments without extract; treating Metis / Implementation engineer / Auditor as GD-03 reviewers; Vercel/Neon; inventing richtlijn-path serving types; inventing a fourth boom type `scorelist`; GRADE English labels; relation-graph editor; `publish()` PASS; Blob; managed identity; app settings; rewriting freeze bytes; auto-confirming types; auto-promoting ordinary text or a `node` to `outcome`; a researcher “zwaar/licht” or “snel/langzaam” switch; reopening freeze/locator (v2.11); reopening richtlijn-path serving typeset (v2.12); reopening four-eyes high-risk (v2.13); reopening the v2.25 boom path; reopening the v2.28 Sterkte gate; reopening v2.27 delete; reopening v2.26 Klasse wijzigen; reopening v2.29 temp prod deploy; rewriting v2.16–v2.29 files except index/conflict pointers; creating or activating a test App Service; claiming G2 PASS; claiming GD-03 or publication; taking this protocol PR as the Cloud Shell ZIP; opening G2/`publish()`; adding numpy/sklearn; touching Azure deploy packaging; recreating `HANDOFF.md`; mutating a live published release back to unpublished; re-labelling objects across review models as a direct class change.

This does not skip durable immutable storage. The local store remains the console stand-in until G0 Azure DEV. Publication remains BLOCKED without an immutable locator, as in existing G2 rules. The G2 locator remains the publication blocker; it is not the next implementation. Capture remains not publication. G2 locator still required to publish.

## 15. Change class and review

This is a protocol version change, not a silent C0 documentation edit. The highest class is **C3 spanning extract/review-surface / retrieve-safety** (a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; missing required field → `gate_result=blocked`; soft scores / volume / “ship then fix” MUST NOT open the hard gate; blocked candidates MUST NOT enter the ordinary review queue; There MUST be NO tradeoff — UI polish MUST NOT excuse bad candidates; current knowledge-object quality is ~5/10 (fail, not a shippable bar); primary reviewer UI MUST use ordinary language only and MUST NOT start from a mandatory Relatie bevestigen / always-visible TOC+full parent list; Open volledige richtlijn / broncontext MUST show real surrounding source context with the exact span marked; SUPERSEDES subjective admission, dumping every assertive sentence into ordinary review, primary Relatie bevestigen as a mandatory chain, always-visible TOC+full parent lists, open-original same-card enlarge, and type UI without proposal+evidence; G2 remains BLOCKED; `publish()` stays G2-BLOCKED; no Forge code in this PR). This is not a C5 reopen of four-eyes or publish. Treat the highest class as **C3 spanning extract/review-surface / retrieve-safety**. This delta does not reopen GD-03. This is not a GD-03 knowledge-publish.

This delta is owner-approved. Named C3 reviewers are not yet staffed. Named reviewers are not staffed. Retrospective independent clinical and technical review remains due, using the same pattern as Protocol v2.29 / PR #103, Protocol v2.28 / PR #100, Protocol v2.27 / PR #98, Protocol v2.26 / PR #96, Protocol v2.25 / PR #94, Protocol v2.24 / PR #91, Protocol v2.23 / PR #88, Protocol v2.22 / PR #86, Protocol v2.21 / PR #84, Protocol v2.20 / PR #80, Protocol v2.19 / PR #78, Protocol v2.18 / PR #76, Protocol v2.17 / PR #74, Protocol v2.16 / PR #72, Protocol v2.15 / PR #70, Protocol v2.13 / PR #32, Protocol v2.12 / PR #29, Protocol v2.11 / PR #27, Protocol v2.10 / PR #26, Protocol v2.9 / PR #24, Protocol v2.8 / PR #21, Protocol v2.7 / PR #19, Protocol v2.6 / PR #18, Protocol v2.5 / PR #16 (and HANDOFF.md for PR #4 and PR #5). This delta does not invent a separate named C5 staff. Metis, the Implementation engineer and the Auditor MUST NOT count as GD-03 reviewers.

Any later Forge implementation of phases 1–4 remains separately classified, including at least C3 spanning extract/review-surface / retrieve-safety. Block A and Block B MUST remain independently testable. The four Forge phases MUST remain separately GO’d.

## 16. Gates and approval effect

Approval of v2.30 establishes that the owner locked two independently testable acceptance blocks on 2026-09-05 (William Gomes; Metis CoS GO; owner reconfirmed GO the same day): **Block A** — a knowledge object MAY be proposed ONLY when all required fields for the proposed type are filled with literal localizable source text; missing required field → `gate_result=blocked`; soft scores (`relevant` / `complete` / `understandable`) MAY rank only and MUST NOT open the hard gate; soft scores / volume / “ship then fix” MUST NOT open the hard gate; blocked candidates MUST NOT enter the ordinary review queue; There MUST be NO tradeoff — UI polish MUST NOT excuse bad candidates; current knowledge-object quality is ~5/10 (fail, not a shippable bar); the model MUST NOT fill gaps with “impliciet” prose; admission MUST require full carrying sentence AND `subject_span` AND `predicate_span` AND valid locator AND type_contract complete AND type_evidence present AND no unresolved core reference AND no incomplete comparison AND context scan done AND found constraints processed; required candidate fields before human review are the section 4 list including `gate_result` (`allowed`|`blocked`) and `reason_codes[]`; hard blocks MUST include at least `incomplete_sentence`, `subject_missing`, `predicate_missing`, `unresolved_reference`, `comparison_target_missing`, `abbreviation_unresolved`, `table_of_contents_entry`, `editorial_transition_only`, `recommendation_evidence_missing`, `condition_target_missing`, `exception_target_missing`, `supported_object_missing`, `no_independent_claim`, `duplicates`, `source_fidelity_failure`; type contracts are Aanbeveling (`actor_of_scope` + `recommended_action` + `action_object_or_goal` + `recommendation_evidence_span` + optional audience/setting/condition/exception/strength), Definitie, Voorwaarde, Uitzondering, Feitelijke constatering, Toelichting (must link supported object; not independently publishable by default); context scan covers candidate paragraph + prev/next paragraph + current+ancestor headings; necessary context → include OR link OR block; MUST NOT claim context unnecessary without recording checked signals; atomicity is one independently confirmable meaning including required conditions/exceptions — NOT always one word/one sentence; MUST NOT split into broken fragments; `source_text_exact` is immutable; normalized text only after human confirm; MUST NOT strengthen meaning; passage register statuses are `selected_as_candidate` | `used_as_context` | `linked_as_support` | `excluded_with_reason` | `not_yet_assessed`; MUST NOT silently drop passages; coverage reporting per section; no duty to objectify every sentence; duty to assess normative/application-critical knowledge; mandatory dJG regression “De dJG wordt in Nederland vaker gebruikt.” MUST NOT enter the ordinary queue as Aanbeveling; `reason_codes` MUST include `recommendation_evidence_missing`, `comparison_target_missing`, `abbreviation_unresolved` (when unresolved); also regress one-word, unresolved ref, incomplete comparison, false recommendation, full “adviseert” recommendation, lone exception, recommendation+exception; **Block B** — documentpositie SUPERSEDES primary UI that always shows TOC list + full parent list + separate Relatie bevestigen; internal parent ids MAY remain; primary UI MUST use ordinary language only (**Gevonden onder** / **Dit klopt** / **Andere kop kiezen**); full hierarchy ONLY after **Andere kop**; body headings only; TOC excluded; search; navigate vs select distinct; visibility rule: if reviewer need not act → do not show; if shown → one clear action in ordinary language; no ouder/kind/parent/confirmed relation on the primary surface; **Open volledige richtlijn** / broncontext MUST show surrounding page/paragraph context with the exact span marked — MUST NOT merely enlarge the same truncated card sentence; review UI order + ONE save: (A) selected passage + why selected (B) broncontext (C) suitability Ja / mist context / samenvoegen / alleen onderbouwing / geen kenniseenheid (D) documentpositie (E) type: show Metis proposal + Dit klopt / Type wijzigen — MUST NOT start from only “nog niet bevestigd” (F) eindoordeel Goedkeuren / Goedkeuren na correctie / Afwijzen / Later beoordelen; button **Review opslaan en volgende**; v2.28 Sterkte-on-confirmed-type remains; that validation pipeline order and publication gate are as in section 12; that metrics (precision, type accuracy, context completeness, coverage vs gold, review burden) MUST be required by protocol and implementation MAY be later phases; that a gold standard is required before claiming extract quality; that ROADMAP MUST state four Forge phases after separate Metis GOs; that this PR is protocol-only; that G2 remains BLOCKED; that `publish()` stays G2-BLOCKED; that `HANDOFF.md` MUST NOT be recreated; that `PROTOCOL.md` is law for every guideline, not Continentie-only; that MUST NOT implement Forge phases in this PR; that v2.25 boom path is UNCHANGED; that v2.26 Klasse wijzigen architecture is UNCHANGED; that v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm is UNCHANGED; that v2.28 Sterkte gate is UNCHANGED; that v2.29 temporary production-only deploy is UNCHANGED; that four layers are UNCHANGED; that this protocol MUST NOT claim G2 PASS; that MUST NOT rewrite v2.16–v2.29 files except index/conflict pointers; and that serving / G2 / four-eyes / Protocol v2.14 / Azure unchanged except the bounded Block A admission lock and Block B reviewer-surface lock: only confirmed `recommendation` MAY `supported` / handelingsadvies on the richtlijn path; boom serving is not opened here; the machine MUST NOT decide that something is light enough to serve; four-eyes unchanged for type-confirm and high-risk; G2 remains the publication blocker; capture is not publication; Protocol v2.14 is not this file and is not next; Azure is not this protocol PR. It does not:

- implement console Python, extract, kernel, Product API, Azure, or `publish()`;
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
- auto-promote ordinary text or a `node` to `outcome`;
- fill missing required fields with “impliciet” prose;
- open the hard gate with soft scores;
- open the hard gate with volume or “ship then fix”;
- let blocked candidates enter the ordinary review queue;
- treat UI polish as an excuse for bad candidates (There MUST be NO tradeoff);
- treat current knowledge-object quality of ~5/10 as a shippable bar;
- dump every assertive sentence into the ordinary review queue;
- keep Relatie bevestigen as a mandatory primary chain;
- always show TOC + full parent lists on the primary surface;
- enlarge the same truncated card sentence as Open volledige richtlijn;
- start type UI from only “nog niet bevestigd”;
- silently drop passages;
- claim extract quality without gold;
- let “De dJG wordt in Nederland vaker gebruikt.” enter the ordinary queue as Aanbeveling;
- invent Klasse values outside `richtlijn` | `handreiking` | `artikel` | `transcript` | `podcast` | `beslisboom`;
- invent a seventh closed serving type on the richtlijn path;
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
- rewrite Protocol v2.16–v2.29 files except index/conflict pointers;
- reopen Protocol v2.21 wave A / wave B / wave C / wave D definitions;
- undo the Protocol v2.23 first DELETE cut or keep list;
- reopen the Protocol v2.24 thin-console / one-shared-kernel / deploy-package-split;
- reopen the Protocol v2.25 boom path;
- reopen the Protocol v2.26 Klasse wijzigen architecture;
- reopen the Protocol v2.27 unpublished-delete Documentenhiërarchie + type-to-confirm lock;
- reopen the Protocol v2.28 Sterkte-on-confirmed-type gate;
- reopen the Protocol v2.29 temporary production-only deploy;
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
- silently add a new quality metric as a protocol gate that opens publish;
- authorize a mockup, Azure ZIP as this PR, Cloud Shell of this protocol PR, Vercel or Neon as the next implementation;
- treat Protocol v2.14 as this file or as the next step;
- mutate a live published release back to unpublished;
- re-label objects across review models as a direct class change;
- treat a pass of Block A as a pass of Block B, or a pass of Block B as a pass of Block A.

The immutable checksum and authoritative merge commit MUST be recorded after merge in the protocol approval manifest. Until that merge, `commit_sha` in the approval manifest MUST remain a clearly incomplete field. Metis records the merge commit checksum after merge.
