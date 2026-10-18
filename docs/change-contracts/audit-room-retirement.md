# Retire the Audit room; semantic safety tests become a standalone check

Change class: B
Promise: The Audit room (`/audit`, create, detail, archive, restore, purge) is removed and no runtime path creates audit records any more. The frozen semantic safety tests run as a standalone check at `/inzicht/veiligheidstests`: the result is shown directly, nothing is persisted, and one content-free telemetry event records the counts. Old Audit addresses redirect to Inzicht › Controles or to the safety tests; `/audit/review-signals` stays as it is.
Proof: tests/test_semantic_safety_app_v1.py (run shows the result and persists no audit record, envelope or publication state; fails closed without a valid packaged commit; researcher-only; retired addresses redirect, old detail URLs are gone and review signals stay reachable). Retention and recovery suites stay green unchanged in meaning: tests/test_audit_retention_v1.py, tests/test_workflow_audit_retention_v1.py (now drives `AuditRetentionService` directly instead of the retired HTTP pages), tests/test_lifecycle_withdrawal_recovery_v1.py, tests/test_workflow_chain_recovery_v1.py.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: rules use MOET / MAG NIET / NOOIT only.

## Decision

William, 2026-10-17: audit records hoeven niet bewaard te worden. The room had two live types (an experiment stub and a document-quality snapshot that duplicates Inzicht › Documenten) and two disabled types. Its only substantive use was persisting semantic safety results, which a researcher reads once.

## Domain check

The change removes a writer; it adds no durable state. Audit records were never read by review, publication, serving or recovery decisions. Class-change history lives in the envelope (`prior_processing_history`), not in audit records. Review signals and publication-refusal audit events are different concepts and stay.

## Staged removal

- Step A (this change): UI, routes and runtime writers go. `AuditRegistry` (file store) moves into `audit_retention_v1` next to the retention service it serves; `PostgresAuditRegistry`, the PostgreSQL tables, the Azure audit archive, backup/restore coupling (`workflow_chain_recovery_v1`, `publication_chain_recovery_v1`) and migrations stay unchanged and inert. Restore of existing backups MOET keep working.
- Step B (separate change, explicit GO from William required): delete audit data and tables, the Azure archive and the recovery coupling, with backward-compatible restore of older backups. That step is destructive and MAG NIET run autonomously.

## What changed

- New `src/semantic_safety_app_v1.py`: GET `/inzicht/veiligheidstests`, POST `/inzicht/veiligheidstests/run`, explicit 303 redirects for `/audit`, `/audit/new`, `/audit/archive`, `/audit/semantic-safety` (no catch-all, so `/audit/review-signals` keeps its own route).
- Removed `src/audit_room_v1.py` and the unwired `src/audit_experiment_v1.py`.
- `src/console_asgi.py`: no audit room, no Azure audit archive store construction, no route-backend binding; installs the safety tests instead.
- `src/workflows/workflow_remaining_cutover_v1.py`: `bind_remaining_route_backends` removed; regexes come from `audit_retention_v1`.
- Links: Inzicht › Controles, Technisch beheer and the review-signals page point to the new check and to Controles.
