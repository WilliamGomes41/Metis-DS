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

## Sherlock re-audit (2026-10-16): F1 and F2
- **F1 (exc_info):** RedactingFilter reduces exc_info to `[ExceptionType: redacted message]` inside the redacted message and clears exc_info, exc_text and stack_info: a traceback MAG NIET reach a handler we do not own. JsonLogFormatter keeps type only. Proof: `test_exception_message_secret_is_redacted_in_foreign_handler`, `test_json_formatter_exception_secret_never_rendered`.
- **F2 (non-propagating loggers):** handlers on uvicorn, uvicorn.error, uvicorn.access, gunicorn, gunicorn.error and gunicorn.access MOETEN get the RedactingFilter (NON_PROPAGATING_LOGGERS). Proof: `test_non_propagating_logger_handlers_emit_only_redacted_text` (5 cases). Red c608e91 (6 failed).
- **638-1 CLOSED (Metis, 2026-10-16):** `build_app()` registers `install_startup_reinstall(app)`: the idempotent install re-runs at application startup, AFTER the server's own log setup, so uvicorn/gunicorn handlers configured after build MOETEN redact. Proof: `test_server_handlers_added_after_build_are_redacted_after_startup` (3 cases, also asserts one filter and one root JSON handler after a repeat install) and `test_build_app_registers_the_startup_reinstall`; red 1fa6f2c (4 failed).
- **Known limitation:** a handler added after application startup is NOT covered.
