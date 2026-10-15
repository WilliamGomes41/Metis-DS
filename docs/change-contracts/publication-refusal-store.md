# #629 F1: publication refusals in a separate append-only store

Change class: B
Promise: A publication_refused record MAG NIET enter the review ledger hash chain; it MOET be written only to the separate append-only refusal store, deduplicated per (document, reason codes, actor) within 10 minutes and bounded (5000 records, 128 reason codes per record, no eviction). Existing ledger event hashes MOETEN NOOIT change; the gate verdict MAG NIET change.
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
