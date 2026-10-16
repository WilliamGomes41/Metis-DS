# Retention matrix

Each durable personal-data store MOET have a row here: what it holds, the retention bound and the mechanism that enforces it. A store without a row MAG NIET go live.

| Store | Personal data | Retention | Mechanism | Access |
|---|---|---|---|---|
| `workflow.publication_refusals` (PostgreSQL; JSONL file store only off-live) | `actor` = account_id in plain text (Lex conditions below) | 400 days and at most 200000 rows (Lex, OPENVRAAG-RET-1 closed; equal to the script default). Purpose: proof of publish refusals and review control (GDPR art. 5(1)(e) and 5(2)). Exports and backups from this store MOETEN have the same or a shorter retention term (400 days / 200000 rows). Follow-up (HMAC actor after 90 days, safe row limit, visible cleanup failures): https://github.com/WilliamGomes41/Metis-DS/issues/647 | `scripts/publication_refusal_retention.py` (`--retention-days` / `--max-rows` MOETEN be > 0), planned as explicit maintenance on the deploy checklist; MAG NIET run per refusal | least-privilege: console identity `SELECT, INSERT, DELETE` only (AZURE_STEP9_CUTOVER_RUNBOOK) |

## Lex conditions for `actor` in plain text (2026-10-16)
The refusal store MAG `actor` in plain text keep ONLY while all of these hold:
1. `actor` is the account_id only; NOOIT a name, email or other identifier.
2. least-privilege access: only the console runtime identity (SELECT, INSERT, DELETE) and the retention maintenance job.
3. retention is in this matrix and enforced as above.
`actor` MAG NIET leave the store through the processing-evidence export (#641). An HMAC pseudonym for `actor` is a separate, later PR.

## OPENVRAAG-RET-1: CLOSED (Lex via Metis, 2026-10-16)
Retention 400 days / 200000 rows; purpose proof of publish refusals and review control (GDPR art. 5(1)(e), 5(2)); exports and backups same or shorter. Follow-up: https://github.com/WilliamGomes41/Metis-DS/issues/647.
