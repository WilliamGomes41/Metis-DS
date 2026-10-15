# #627 fix: log redaction and library logger levels

Change class: B
Promise: The JSON log formatter MAG NIET emit email addresses, Authorization/Proxy-Authorization values (Basic, Bearer, Digest, Negotiate, opaque), API-key headers (X-Api-Key, api-key, Ocp-Apim-Subscription-Key, x-functions-key), Cookie/Set-Cookie values, or quoted credential assignments (password="x", {"password":"x"}); third-party loggers (azure, urllib3, httpx, httpcore, openai, msal, psycopg, asyncio) MOETEN stay at WARNING after install_structured_logging.
Proof: tests/test_structured_logging_redaction_v1.py: 16 tests red at b0e6354, green at 233b8b9 (19 passed); tests/test_a2_attempt_records.py stays green.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: B18. Rules use MOET / MAG NIET / NOOIT only; open items are marked OPENVRAAG. Source: Sherlock retro-audit #627; Codex P1 (quoted assignments).

## Change

- src/structured_logging_v1.py and src/console_performance_v1.py (handler formatter only): header-key pattern (value to closing quote or line end), quoted/unquoted assignment pattern, auth-scheme pattern, email pattern; LIBRARY_LOGGERS raised to WARNING (an explicitly higher level is kept).

Not touched: operations_console_v1.py, publish gate, metis_diagnostic logger.

## Limits

- Redaction is pattern-based and fail-closed for unquoted header values (whole rest of the line).
- OPENVRAAG-627-1 CLOSED: pre-existing root handlers get a RedactingFilter (they MAG NIET emit unredacted text) and metis.console.performance uses JsonLogFormatter. Red 2565fe8 (2 failed), green 86ae800.
