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
