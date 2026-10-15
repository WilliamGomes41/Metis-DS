# Publish-gate refusal audit event

Change class: B
Promise: Every publish-gate refusal MOET emit one bounded `publication_refused` audit event (actor digest, document, revision digest, reason codes); the gate verdict, its reasons, the returned result and all durable state MAG NIET change.
Proof: tests/test_publish_refusal_audit_v1.py (fails on 8db82cb: module missing; 8 green after) with before/after verdict tests on the file and durable gate proving identical verdicts and envelope state, an allowed publication emitting no event, and a logging failure leaving the verdict unchanged; existing publication suites unchanged.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Forge acked this item with limits (own module, one call line at the refusal point, no gate restructuring).

## Change

- New `src/publish_refusal_audit_v1.py`: `record_publish_refusal(console, *, actor_id, snapshot_id, verdict, revision=None)`.
  It MOET only read the final verdict. Allowed verdicts MOETEN NOOIT produce an event.
  Reason codes are bounded to `[a-z][a-z0-9_]{0,95}` (else `unrecognized_reason`), at most 128.
  The actor is logged as SHA-256 only; the revision as SHA-256 only. Any exception is swallowed.
- One call line plus one import line at each existing refusal point, directly after the
  final verdict and before the existing `if not considered.get("publish_allowed")`:
  - `src/operations_console_v1.py` `_publish_locked`: import line 127, call line 4767.
  - `src/durable_publication_console_v1.py` `_publish_locked`: import line 26, call line 272.
- The gate functions (`consider_publish`, `_publish_locked`) are NOT restructured.

## Open questions

OPENVRAAG-GATE-1: MOET the actor be logged as an account id instead of a SHA-256 digest? The existing diagnostics policy forbids user identifiers in logs.
OPENVRAAG-GATE-2: MOET the event also be written to a durable audit store? This PR is log-only (no durable write).

## Uitbreiding (Forge-ack): HMAC-actor en duurzame audit
- Logs MOETEN de actor alleen als keyed HMAC-SHA256 (`actor_hmac`) bevatten; sleutel uit app setting `METIS_AUDIT_HMAC_KEY`, die NOOIT gelogd wordt. Zonder sleutel MOET `actor_hmac` null zijn.
- De weigering MOET ook in de duurzame auditstore staan via `review_ledger.append_event` (event_type `publication_refused`, actor in klare tekst); signatuur en semantiek van `append_event` MOGEN NIET wijzigen.
- Een fout in de auditwrite MAG NOOIT het verdict wijzigen (test: `test_verdict_identical_when_durable_audit_write_raises`).
- OPENVRAAG-GATE-HMAC: `METIS_AUDIT_HMAC_KEY` MOET nog als app setting/Key Vault-referentie op de omgevingen gezet worden; tot dan logt de app geen actor.
