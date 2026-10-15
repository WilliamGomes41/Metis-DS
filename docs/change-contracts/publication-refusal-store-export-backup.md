# Refusal store in the evidence export and the runtime backup

Change class: B
Promise: The per-document processing-evidence export MOET contain publication_refusals.csv with only that document's refusal records (NOOIT another document's; manifest 'not_recorded' when the store is unreadable); the runtime backup/restore MOET include the refusal store file byte-identical; the deploy package MAG NIET ship it.
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
- OPENVRAAG-EXP-1: export schema version stays processing-evidence-export-v14 (additive dataset); Metis decides whether it MOET become v15.
- MCP export path (metis_mcp_queries_v1) does not pass refusals; its manifest says not_recorded.
