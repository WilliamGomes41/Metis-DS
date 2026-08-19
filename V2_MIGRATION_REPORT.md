# Protocol v2 migration - technical status

Date: 2026-08-19
Scope: migration of steps 1-4.5 before canonical storage/publication.

## Implemented

- Closed knowledge-object enum: document, section, definition, condition, score_rule, decision, action, recommendation, exception, out_of_scope, supersession.
- Existing 20 expert-review object IDs preserved.
- Added one technical `document` object.
- Migrated legacy `table` -> `section` and `background` -> `definition` without changing the reviewed text or IDs.
- Added deterministic semantic spec v2.0 with explicit predicates and risk fields.
- Added source hierarchy manifest and conflict rule.
- Canonical source binary absence is explicit (`binary_unavailable`) and blocks publication.
- Added separate validation and publication statuses (`approved` is not `published`).
- Added risk classification and mandatory four-eyes marker for age boundaries, operators, score fields, units and escalation rules.
- Added second-review queue and second-review application workflow with reviewer separation and snapshot checking.
- Added decision graph schema support (nodes/edges/exclusivity) for Storyline decision trees.
- Added separate AI proposal schema. AI proposals cannot validate as canonical knowledge objects.
- Added first-review snapshot comparison compatible with the already-sent expert workbook.
- Corrected the canonical alcohol rule to `>= 3` / `gte 3` while preserving fail-closed mismatch behavior against the older expert snapshot.
- Added heavy protocol-v2 pre-publication gate.
- Added persistent pytest regression suite and one-command check script.

## Verification

- Semantic v2 objects: 21 total (20 existing expert objects + 1 document object).
- High-risk/four-eyes objects: 12.
- Schema validation: PASS.
- Integrity checks: PASS.
- Regression tests: 12/12 PASS.
- Deterministic rerun: byte-identical JSONL output tested.
- Real expert-workbook compatibility simulation: 19 approvals can map; the known old `> 3` review snapshot is deliberately blocked against current `>= 3` content.

## Current release state

`BLOCKED` by design.

Reasons:
1. Canonical PDF binary has not yet been locally hash-verified; source checksum is therefore absent.
2. Twenty clinical objects are awaiting first review.
3. One technical document object is awaiting technical review.
4. High-risk objects will require a second independent reviewer after first approval.

No canonical object is `published`, and embeddings/retrieval remain disabled.
