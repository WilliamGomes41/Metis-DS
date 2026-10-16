# #661 fix: redaction hardening follow-up (#638)

Change class: B
Promise: An unquoted credential value containing spaces (password=hunter two words) MOET be redacted up to the next key= assignment, a field delimiter or line end. The owned JSON handler MAG NIET emit secrets or PII in `logger` or in whitelisted extras (request_id, event, attempt_id, snapshot_id, phase, reason_code).
Proof: tests/test_structured_logging_followup_661_v1.py is red at f7aaded and 22085f4 and green after the fix. The #638 redaction tests stay green.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only. Source: #661 (threads 4295299102 and 4295299116 on #638, moved here by Metis's decision at 15:37).

## Change
- `_SECRET_PATTERNS`: the unquoted assignment value continues across spaces as long as the next word is not itself a `key=`/`key:` assignment.
- `JsonLogFormatter`: `logger` is redacted. A whitelisted extra that changes under redaction becomes `[REDACTED]`.

## Limits
- A secret word that looks like `x=...` ends the value (`password=a b=c`). This is accepted: what follows is treated as a new assignment.

## Scope extension (William, 18:21, 2026-10-16): three new #638 leaks
Red commits d9c0465, f8d0280 and e52806a (6 failed); fix in one commit.
- The reserved handler MOET only be trusted when its formatter is exactly JsonLogFormatter. A subclass that overrides format() MAG NIET count as owned, and that handler gets the RedactingFilter (4296203798).
- Composite keys (tuples, frozensets) in nested extra mappings MOETEN be deep-redacted (4296203813).
- SMTPUTF8: every UTF-8 non-ASCII character in a local part MOET count as atext (RFC 6531), for example \U0001F600@example.com (4296203827).
