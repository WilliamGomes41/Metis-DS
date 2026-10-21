# Unified telemetry hub and the Inzicht room

Change class: B
Promise: Every operational signal of the console lands in one hub (`src/telemetry/`), correlated by request, trace, attempt and pseudonymous document; failures carry a safe exception fingerprint; Settings channels insight into one authenticated room (`/inzicht`) whose tabs Systeem, Kwaliteit & werkproces, Documenten and Controles reuse the existing owners and link to each other.
Proof: tests/test_insight_v1.py (four tabs behind login; quality API equals the existing measurement and store; documents API only shows authorized documents; Settings channels Inzicht, Beheer and Uitleg) and tests/test_telemetry_v1.py (write routes and exceptions captured with type/code/frames and no text; handled ConsoleError codes; traceparent adoption; doc_ref instead of document ids; store-lock wait/hold phases; logging bridge with request_id; aborted-request detection, error groups, commit regression and correlations; page/API require login; install idempotent with faulthandler). Existing request-diagnostics, logging-redaction and characterization suites stay green.
Touches lifecycle invariants: no
Rewrite risk: none

Taalregel: rules use MOET / MAG NIET / NOOIT only.

## Domain check

Telemetry is operational evidence, not durable domain state: the stateful overlay does not apply. The local JSONL store is disposable (rotation, 64 MB cap, 7 days) and MAG NOOIT be read by a domain decision. No authority, schema, lifecycle or publication path changes.

## What changed

- `src/telemetry/`: hub (event model, redaction, bounded store), errors (fingerprint), logging bridge (correlation filter, hub handler), analysis, playbook, routes and page, install (faulthandler, exception hooks, process lifecycle).
- `src/request_diagnostics_v1.py`: observes every route except polling/static/telemetry API; trace id (W3C traceparent or OTel span); `doc_ref`; exception evidence; handled codes; DB metrics; store phases; `diagnostic_record`/`diagnostic_since`/`diagnostic_clock`.
- `src/operations_console_v1.py::_store_write_lock`: wait and hold phases (timing via `diagnostic_clock`, no behavior change).
- `src/workflows/workflow_review_cutover_v1.py::_store_command`: `store_transaction` phase. The former `store_remirror` phase was removed by D5 (#785) when PG disk mirrors were retired.
- `src/console_performance_v1.py`: DB metrics attached to the request; `src/structured_logging_v1.py`: `trace_id` extra field.
- Characterization: route golden adds the four `/telemetry` routes; coverage baseline re-measured (operations_console_v1 range +3 lines; operations_console_app range −47 lines, already shifted on main by #735), coverage identical.

## Inzicht (harmonised Settings)

- `src/insight_v1.py`: tab bar, `/inzicht` page, `/inzicht/api/quality` (projection of `quality_metrics_app_v1.quality_view`) and `/inzicht/api/documents` (processing status, processing diagnostics, telemetry per `doc_ref`). `/telemetry` redirects to `/inzicht?tab=systeem`.
- `src/quality_metrics_app_v1.py`: `quality_view` is extracted unchanged from the page handler, so the table page and the charts read one measurement (same capture, scope check and immutable report store).
- Settings is grouped into Inzicht, Beheer and Uitleg; existing doors (Accounts, Technisch beheer, ChatGPT-koppeling, Over Metis) and all existing URLs remain. Technisch beheer points to Inzicht for diagnostics.
- Authorization is unchanged per source: telemetry for every signed-in account (no content); quality only for the user's own sources; documents with the Technisch-beheer rule.

## Privacy contract (unchanged and extended)

MAG NOOIT leave the hub: document ids (only `doc_ref`), user ids, query strings, SQL, source content, exception messages, locals. Strings are redacted with `structured_logging_v1.redact` and truncated to 240 characters.

## Limits

- A 500 response is produced outside the diagnostics middleware and carries no `X-Metis-Request-Id` header; the event carries the id.
- Product API (`serve-api`) is not yet connected.
