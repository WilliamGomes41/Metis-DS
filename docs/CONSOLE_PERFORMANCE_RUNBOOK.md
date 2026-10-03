# Measure console navigation after deployment

The diagnostic script performs only read transactions and `SELECT` queries,
does not bootstrap a second app, and stops after 60 seconds. It uses the same
vendored Python package directory and configured database credentials as the app.
Do not install packages or activate the Azure monitoring agent for this check.

In App Service SSH, paste the entire block below. Enter the existing Metis account
ID locally when prompted; no account ID or task/document payload is printed.

```bash
read -r -p 'Metis account-ID: ' METIS_MEASURE_ACCOUNT
python /home/site/wwwroot/scripts/measure_console_navigation.py --account-id "$METIS_MEASURE_ACCOUNT"
unset METIS_MEASURE_ACCOUNT
```

Compare measurements 2–3, which reuse the process-local Azure token. The output
contains duration and attempted connection/statement counts. The script adds
two session-control statements per connection to enforce read-only execution and
a 10-second SQL timeout; subtract these when comparing application query counts.
This standalone measurement has `immutable_source_store=None` and intentionally
skips startup/reconciliation. It proves the count path, not the entire configured
HTTP request. The diagnostic script itself creates no source-readback authority.

Open the same Technical, Exports, Ingest, Review and Publish pages used before.
Record browser time to first byte and the matching `console_performance` log
entries. Logs include route template, status, request-to-response-header elapsed
time, badge duration and attempted database connections/statement calls. They do
not measure the complete body of a streaming response. Full publication/detail
checks may still perform necessary work; inspect timings rather than assuming
every route is now equally fast. An application/version difference or competing
load can affect comparisons.

Acceptance: same authorized counts, no duplicate policy work-item calculation,
bounded input reads independent of passage count, successful tests and reduced
count duration AND page waiting time. A local benchmark is not proof of Azure
latency or elimination of unrelated delays. Repository rollback requires only
restoring the previous application version.

Synthetic development benchmark (pytest dependencies required):

```bash
python scripts/benchmark_console_navigation.py --documents 2 --objects 100 --evidence-items 64
```

This benchmark contains only synthetic payloads and counting fake stores. It
compares the old duplicate construction pattern with batched navigation and
excludes actual SQL/network and full readiness cost. Do not quote its speedup as
an Azure performance result. Repeat the actual SSH and browser checks above.
