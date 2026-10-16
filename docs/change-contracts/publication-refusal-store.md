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

## Sherlock audit 02:10 (2026-10-16): F1, F2, F3
- **F1 (018 idempotent on a database that already ran it):** the UNIQUE is the named constraint `publication_refusals_dedup_key_uniq`, added in a DO block guarded by `pg_constraint` (conname + conrelid). This PR MAG NIET rely on 018 never having reached a persistent database. Proof: `tests/test_migration_018_postgres_v1.py` (018 twice; on top of the pre-UNIQUE 018 from `tests/fixtures/018_publication_refusal_audit_pre_unique.sql`). Red d180002.
- **F1-5 CLOSED (Metis, 2026-10-16):** 018 does NO UPDATE on audit rows. With duplicate dedup_keys from the pre-UNIQUE 018, 018 MOET fail with `publication_refusals_duplicate_dedup_keys count=N keys=…` and change nothing; a human decides (runbook, Migratie 018). Proof: `test_018_fails_on_duplicates_with_count_and_keys_and_updates_nothing`, `test_018_applies_on_top_of_the_pre_unique_018_without_duplicates`, `test_018_contains_no_update`; red 5f025bb.
- Metis confirmed the fixed 10-minute UTC buckets for the PostgreSQL dedup.
- **F2 (runbook):** docs/TEST_AND_RELEASE_RUNBOOK.md: 018 MOET be applied before the code, only with William's GO; proof `test_runbook_orders_018_before_code_with_williams_go_and_lists_retention` (red locally before the runbook text).
- **F3 (retention bounds):** `scripts/publication_refusal_retention.py` refuses `--max-rows <= 0` and `--retention-days <= 0` (exit 2, nothing deleted); `apply_retention` raises ValueError. Proof: `test_retention_script_refuses_non_positive_max_rows`, `test_apply_retention_refuses_non_positive_max_rows`. Red d180002.
- Retention scheduling is a deploy-checklist item only (runbook); it is NOT built.

## Sherlock audit 02:55 (2026-10-16)
- The 018 duplicate error lists at most 20 dedup_keys (`count=N more=M keys=…`); count is exact. Proof: `test_018_duplicate_error_lists_a_capped_number_of_keys`, `test_018_caps_the_key_list_in_sql`; red f52b58a.
- METIS_TEST_POSTGRES_DSN MOET only point at a disposable database (the fixtures DROP SCHEMA workflow); documented in the test docstring and the runbook. Proof: `test_disposable_database_rule_is_documented`; red e787851.
