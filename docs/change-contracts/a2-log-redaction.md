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

## Sherlock audit 02:10 (2026-10-16)
- **F1 (record.args):** RedactingFilter keeps `record.args` as a tuple (or mapping) of redacted values; it is NOOIT None, because formatters such as uvicorn's AccessFormatter read it positionally. When a secret spans the template and the args, the filter renders, redacts and sets `args = ()` (an empty tuple, NOOIT None). Proof: `test_uvicorn_access_formatter_works_and_redacts_after_filter` (real `uvicorn.logging.AccessFormatter`) and `test_redacting_filter_never_sets_args_to_none`; red 1751722 (2 failed).
- **F2:** accepted by Metis (correction, Sherlock 02:55: earlier text named Sherlock) as the documented limitation above (handlers added after application startup are NOT covered).

## Sherlock audit 02:55 (2026-10-16)
- F2 attribution corrected: accepted by Metis. Proof: `test_contract_attributes_f2_acceptance_to_metis`; red d75af8c.
- uvicorn.access (PER_ARG_LOGGERS) MOET keep its 5 positional args, each redacted on its own, also when a header-shaped secret would otherwise force the render-and-empty fallback. Proof: `test_uvicorn_access_redacts_each_arg_and_keeps_five_args` (3 cases, real AccessFormatter); red 0a4706c (2 failed).

## Sherlock P1/P2 (2026-10-16), red 6da399c + ac17676
- Escaped quote delimiters MAG NIET end a quoted secret; an unterminated quoted value is redacted to line end (fd02837).
- Every existing descendant of a library logger with an explicit level below WARNING MOET be clamped to WARNING; re-run at startup (2ddac50). A descendant created and lowered after startup is NOT covered (documented limitation, same as #638 F2).
- Standalone Digest parameter lists MOETEN be redacted completely (330f664).
- Capitalised scheme + any token MOET be redacted (`Bearer abc`, `Basic YTo=`); lowercase prose MAG only be redacted when the token carries credential characters (811a37e).
- A value under a sensitive mapping key MOET be replaced before formatting (1b5031b).
- Pre-existing handlers on `metis.console.performance` MOETEN get the RedactingFilter (fc94a8c).
- Email redaction MOET be Unicode-aware (c44f823).
Proof: tests/test_structured_logging_sherlock_p1p2_v1.py.

## Metis decisions (2026-10-16, 09:12)
- Any-case auth scheme + any token MOET be redacted; casing MAG NIET decide. Fail-closed: prose such as 'basic flow' is redacted too (red fc425ae, fix bc146ec).
- A line break inside a quoted value MAG NIET end it; an unterminated quoted value is redacted to the end of the text (red aa532cb, fix 03b16c2).
- Emails with a quoted local part MOETEN be redacted (red 6557e90, fix d95de59).
- Custom `extra` fields: values under sensitive keys MOETEN be replaced, other string fields redacted, before any handler formats them (red f08f855, fix 7197a79).

## Known limitation: over-redaction (accepted by Metis, 2026-10-16)
Any word that follows an auth scheme word (bearer, basic, digest, negotiate; any casing) is redacted, fail-closed. Ordinary prose is redacted too: 'use the basic flow' becomes 'use the [REDACTED]'. This MAG NIET be relaxed without a new Metis decision; a log reader MOET read '[REDACTED]' after a scheme word as possibly prose.
- Tuple-shaped header/credential pairs ((b'authorization', b'x'), ASGI scope headers) MOETEN be redacted (red 2475f3c, fix d1d9e40).
- Emails with a domain literal (user@[127.0.0.1], user@[IPv6:...]) MOETEN be redacted (red 15b224c, fix 40ddb68).
- Sensitive extra keys MOETEN be replaced for any value type (dict, list, object) (red 0e5f660, fix 9963ce3).
- Digest parameter lists with RFC 7616 `username*` MOETEN be redacted completely (red 3de3903, fix 4ef4314).
- Quoted email local parts with escaped quotes MOETEN be redacted (PII; red 599de42, fix 94f3b5a).

## Complete pass (Metis 12:21, 2026-10-16)
- bytes and bytearray reprs (b'x', bytearray(b'x')) MOETEN be redacted as values in assignments, headers and tuple pairs (red d88b3e5).
- Auth schemes MOETEN be redacted with any spacing, an '='/':' separator and quoted tokens; Digest/RFC 5987 parameters (k*=) with any spacing around '=' and ',' (red 7bd399a).
- Extra fields and mapping args MOETEN be redacted at any depth of dict/list/tuple/set (bound 32 levels, fail-closed beyond); sensitive keys (also prefixed, e.g. x_api_key, and bytes keys) and (key, value) header pairs are replaced for any value type (red cdda703).
- One combined red test for all forms: a0a9ea4.
- Mailboxes with a dotless domain (user@localhost) MOETEN be redacted (PII; red a858fa9, fix 5321c84). Over-redaction of other 'x@y' tokens is accepted fail-closed.
- A dangling escape at the end of an unterminated quoted secret MOET be consumed (red 1552aaa, fix a0e8300).
- Email local parts MOETEN cover the full dot-atom set (' / = ! # $ % & * + ? ^ ` { | } ~ -) (PII; red 6dd86a0, fix 665c066).

## Round 2026-10-16 15:00 (threads on 548070a)
Red commits 82f5b76, 2d0e6ab, c077a20, 7b117fc, 4fa2595, e995356; fix in one commit.
- Non-dict Mapping args (UserDict) MOETEN go through sensitive-key redaction (4294352255).
- When interpolation fails after redaction, the filter MOET fail closed: it renders the template, and MAG NIET render the original args (4294352269).
- Combining marks in SMTPUTF8 local parts MOETEN NIET split the address (4294352280).
- Header keys written as identifiers (x_functions_key, ocp_apim_subscription_key) MOETEN count as sensitive (4294629096).
- Nested mapping keys MOETEN be redacted, for example PII keys (4294629108).
- Positional container args MOETEN be deep-redacted. A container repr after a credential key MOET be redacted to line end (4294629122).
