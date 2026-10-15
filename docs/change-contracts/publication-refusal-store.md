# #629 F1: publication refusals in a separate append-only store

> **Live store: PostgreSQL table `workflow.publication_refusals` (migration 018, needs William's GO to apply).** The file store is TIJDELIJK, local/test only, and MAG NIET go live: the gate is the topology (assert_supported_topology PASS, one worker, one instance, no METIS_* store in postgres mode), NOOIT WEBSITE_SITE_NAME; any other topology without the PostgreSQL workflow store raises RefusalStoreUnavailable. File records carry `store_status: temporary_file_store_pending_postgres_table`.

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

## Sherlock re-audit (2026-10-16): F2 and F3
- **F2 (topology gate):** `file_store_allowed()` uses `assert_supported_topology` plus postgres-mode detection (METIS_CANONICAL/WORKFLOW/WORKFLOW_DOCUMENT/WORKFLOW_REVIEW/WORKFLOW_REMAINING_STORE=postgres). WEBSITE_SITE_NAME MAG NIET decide. Proof: `test_file_store_blocked_by_topology_without_website_site_name` (4 cases, WEBSITE_SITE_NAME unset) and `test_file_store_allowed_in_single_worker_file_topology`.
- **F3 (refusal path):** `PostgresRefusalStore.append` is ONE transactional `INSERT … SELECT … WHERE NOT EXISTS … RETURNING`: no advisory lock, no DELETE, no OFFSET. Retention is the explicit maintenance command `scripts/publication_refusal_retention.py` → `apply_retention()` (age bound, then row bound via `max(refusal_id) - max_rows`, no OFFSET); it MAG NIET run per refusal. Proof: `test_postgres_refusal_path_is_a_single_insert_without_lock_or_delete`, `test_postgres_refusal_dedup_returns_deduplicated_when_insert_skips`, `test_retention_is_an_explicit_maintenance_command_without_offset`, `test_retention_script_runs_apply_retention`; red c2456eb (7 failed).
- F1-4 CLOSED (Metis, 2026-10-16): a duplicate row is NOT acceptable. 018 makes `dedup_key` UNIQUE; the refusal path is `INSERT … ON CONFLICT (dedup_key) DO NOTHING RETURNING` (no lock). `dedup_key` = SHA-256 of (document, reason codes, actor, fixed 10-minute UTC bucket): the table dedups per bucket, NOOIT a sliding window (the file store keeps its sliding 10-minute window). Proof: `test_migration_018_has_unique_dedup_key`, `test_postgres_refusal_insert_uses_on_conflict_do_nothing_without_lock`, `test_dedup_key_is_stable_within_a_window_and_changes_across_windows` (red fe62a20, 3 failed) and the PostgreSQL concurrency test in #637.
- Migration 018 changed only for F1-4 (UNIQUE dedup_key; the separate dedup index is dropped as redundant). 018 lives only in this PR.
