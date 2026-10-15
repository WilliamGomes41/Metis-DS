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
