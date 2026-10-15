# #629 F1: publication refusals in a separate append-only store

> **Live store: PostgreSQL table `workflow.publication_refusals` (migration 018, needs William's GO to apply).** The file store is TIJDELIJK, local/test only, and MAG NIET go live: with WEBSITE_SITE_NAME set and no PostgreSQL workflow store it raises RefusalStoreUnavailable. File records carry `store_status: temporary_file_store_pending_postgres_table`.

Change class: B
Promise: A publication_refused record MAG NIET enter the review ledger hash chain; it MOET be written only to the separate append-only refusal store, deduplicated per (document, reason codes, actor) within 10 minutes and bounded by retention, NOOIT by a permanent refusal (table: 400 days / 200000 rows; file: rotation at 4 MiB, one generation; 128 reason codes per record); dedup reads at most 256 KiB, never the full file; a corrupt record is skipped, reported and NOOIT blocks later writes. Existing ledger event hashes MOETEN NOOIT change; the gate verdict MAG NIET change.
Proof: tests/test_publish_refusal_audit_v1.py: 5 tests red at the red commit (REFUSAL_IN_LEDGER_CHAIN; ledger contains publication_refused; no store records), green after the fix. The chain test compares (event_type, event_hash, previous_event_hash) of every ledger event before and after a refusal and runs verify_ledger, in file and durable topology.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Decision: Metis (#629 F1), Sherlock retro-audit.

## Change

- src/publication_refusal_store_v1.py (new): `<ledger dir>/publication_refusal_audit.jsonl`, process + flock lock, fsync, outcomes recorded / deduplicated / capacity_reached. Revision stored only as SHA-256 (fixes the unbounded m2. revision token).
- src/publish_refusal_audit_v1.py: `_append_durable` writes to that store instead of `review_ledger.append_event`.
- Call sites in operations_console_v1.py and durable_publication_console_v1.py are unchanged (one-line calls from #629). Publication gate untouched.

## Limits

- OPENVRAAG-F1-1: in the PostgreSQL topology the store is a file next to the local ledger mirror, not a database table. A table needs a new migration (017) and William's GO to apply; Metis decides.
- OPENVRAAG-F1-2: the store is not yet part of the evidence export or backup.
- Failure handling (except-pass) is replaced in the follow-up PR (#629 F2).
- Legacy: #629 was never deployed, so no production ledger contains publication_refused; no backfill.

## Metis decisions after Sherlock re-audit (red d877899, green 7f0dd5c)
- PostgreSQL table + migration `db/migrations/018_publication_refusal_audit.sql` (added to MIGRATION_NAMES and REQUIRED_TABLES: schema verification MOET fail until 018 is applied).
- Retention instead of capacity refusal; tail-only dedup; corrupt records skipped and reported; file store never live.
- #636 and #637 are restacked and MOETEN merge together (Argos merge queue).
- OPENVRAAG-F1-1 is closed by the table. OPENVRAAG-F1-3: RETENTION_DAYS (400) and MAX_ROWS (200000) are proposals; Metis confirms.
