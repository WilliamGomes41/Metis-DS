# #629 F2/F3: bounded audit-failure diagnostic and PostgreSQL proof

Change class: B
Promise: Every failure of the refusal audit (log write, durable store write, store at capacity, revision or envelope read) MOET emit one bounded `publication_refusal_audit_failed` diagnostic (stage, error class name, outcome, snapshot id, request id; NOOIT exception text, actor or key), capped at 100 per process; it MAG NIET be swallowed by except-pass, and the gate verdict MAG NIET change.
Proof: tests/test_publish_refusal_audit_v1.py: 7 tests red at cff87ab (no diagnostic, silent except-pass), green at 4d2f3a2. F3: tests/test_publish_refusal_audit_postgres_v1.py runs on the CI postgres:16 service (METIS_TEST_POSTGRES_DSN): ledger chain unchanged, dedup, revision hashed, store failure keeps the verdict and emits the diagnostic.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Stacked on #629 F1 (separate store).

## Change

- src/publish_refusal_audit_v1.py: `_audit_failed` (bounded, WARNING level so default logging keeps it); every former `except Exception: pass` reports a stage. The only remaining containment is inside `_audit_failed` itself (logger failure has no further reporter).
- Call sites, publish gate, ledger and audit_events unchanged.

## Limits

- The #605 sandbox runner is an open PR and not usable here; F3 uses the existing CI postgres service. No local PostgreSQL in this sandbox, so the PG test is proven on CI only.
- OPENVRAAG-F2-1: the per-process cap resets on restart; a cross-process counter is out of scope.

## Metis decisions after Sherlock re-audit
- After the cap of 100, exactly ONE `publication_refusal_audit_failed_suppressed` event with `cap` and `suppressed_count` MOET be emitted; the counter keeps counting (`suppressed_failure_count()`); the cap MAG NIET go silent. Red 7dafa44, green 882a415.
- Restacked on #636 (PostgreSQL table, migration 018). #636 and #637 MOETEN merge together.
- The capacity diagnostic is replaced: the store no longer refuses at capacity. A corrupt record emits `stage: corrupt_record, outcome: skipped`, and the new record is still written.
- F3: tests/test_publish_refusal_audit_postgres_v1.py applies migration 018 and reads the table; it MOET show PASSED (not skipped) on the CI postgres:16 service.

## Sherlock re-audit (2026-10-16)
- CI proof: the step "Verify publication refusal store against native PostgreSQL (#637, PASSED proof)" runs `pytest -rA` on tests/test_publish_refusal_audit_postgres_v1.py with a junit report; it MOET fail on any skipped, failed or errored case, and the log MOET list every case as PASSED.
- #636 F3 merged in: the PostgreSQL test now proves the refusal path NOOIT deletes and that `apply_retention` (maintenance) bounds the rows. Migration 018 comes only from #636; this PR MAG NIET carry a second copy.
