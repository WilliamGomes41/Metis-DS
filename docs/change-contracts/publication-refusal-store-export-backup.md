# Refusal store in the evidence export and the runtime backup

Change class: B
Promise: The per-document processing-evidence export MOET contain publication_refusals.csv with only that document's refusal records (NOOIT another document's; manifest availability 'unreadable' when the store is unreadable, 'recorded_with_skipped_records' when corrupt records were skipped, 'not_recorded' only when no refusal store is configured; a read error MAG NOOIT be swallowed: it MOET be reported as an export issue and a warning event publication_refusal_export_issue); the runtime backup/restore MOET include the refusal store file byte-identical; the deploy package MAG NIET ship it.
Proof: tests/test_publication_refusal_store_export_backup.py: 3 tests red at 16110a6, green after; existing export, inventory and chain-recovery suites unchanged (51 passed locally).
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Stacked on #636 (store exists there). The store is TIJDELIJK (file) until William's GO on a PostgreSQL table.

## Change
- src/processing_evidence_export_v1.py: dataset publication_refusals, optional `refusals=` input.
- src/operations_console_app.py: export route passes the store records (`_refusal_records`).
- src/runtime_data_inventory_v1.py: category publication_refusals (inventory, backup, restore).
- src/azure_deploy_package.py: runtime-data marker for the store file.
Not touched: operations_console_v1.py, publish gate.

## Limits
- OPENVRAAG-EXP-1: CLOSED (Metis 2026-10-16): export schema MOET be processing-evidence-export-v15 (actor/actor_id removed).
- MCP export path (metis_mcp_queries_v1) does not pass refusals; its manifest says not_recorded.

## After restack on #636 (PostgreSQL table)
- Live export reads `workflow.publication_refusals` for that document only (max 500 newest); local topology reads the file. Red 3af3d56, green fe904dc.
- Runtime backup includes the file store and its rotated generation `.jsonl.1`. In the PostgreSQL topology the table is covered by the database backup, not by this runtime archive (OPENVRAAG-EXP-2: Metis confirms that the PostgreSQL backup scope includes workflow.publication_refusals).

## Sherlock FAIL #641 (2026-10-16)
- Swallowed except in `_refusal_records` removed: corrupt records → `corrupt_record:<Class>`, unreadable store → `store_unreadable:<Type>` (red c1407df, fix 0ba9288).
- Manifest text matches the availability states above (red d5fdf96, fix 94ed33f).
- OPENVRAAG-641-LEX (actor PII): open, see PR body. No code change until Lex decides.

## Lex advice / Metis GO (2026-10-16)
- `actor` / `actor_id` MAG NIET be in the publication_refusals, processing_attempts or processing_recovery exports; no plain account_id MAG appear anywhere in the export (red 0957352, 952afa2).
- The refusal store keeps `actor` in plain text ONLY under Lex's conditions: account_id only, least-privilege access, retention in docs/RETENTION_MATRIX.md (red 300b180).
- The HMAC pseudonym is NOT built here; separate PR.

- OPENVRAAG-RET-1: CLOSED (Lex via Metis, 2026-10-16): 400 days / 200000 rows, purpose GDPR art. 5(1)(e)/5(2), exports and backups same or shorter; follow-up #647.

- Concurrent/stale (opslag gate after #636 merged into main): refusal-store files MOETEN be hashed and archived from ONE byte snapshot under the store lock (red b6efdd7, closes 4288477439).
