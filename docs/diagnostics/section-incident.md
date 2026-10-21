# Opening a section: collect evidence outside the broken page

Issue #614; extends draft PR #613. This is a diagnostic read, not a recovery command.
The probe works independently of Metis startup/document pages. It observes one
navigation in an existing session, without submitting any domain action.

## Run

Use Node with Playwright and a working Chromium installation. The repository
already uses Playwright for browser checks; it is not added to the Azure runtime.
`METIS_PLAYWRIGHT_MODULE` and `METIS_BROWSER_EXECUTABLE` optionally select an existing
module/browser installation. Keep authenticated storage-state files private and
outside Git. The probe consumes an existing session; it does not automate login.

```sh
export METIS_PROBE_URL='https://YOUR_HOST/source-selection'
export METIS_PROBE_STORAGE_STATE='/private/existing-session.json'
node scripts/probe_section.cjs /private/probe.json
python scripts/export_section_incident.py --browser /private/probe.json --output /private/incident
```

Supported fixed paths: `/login`, `/ingest`, `/tree`, `/source-selection`, `/review`,
`/publish`. Document query parameters may be supplied in the environment URL but
are never exported. A reviewer reassigned to a trajectory page produces an
unmatched target, not a false success. The current review assertion covers the
Review entry/workboard, not every document-specific review task.

`METIS_PROBE_TIMEOUT_MS` defaults to 30000, bounded 100..300000. A timeout is
observation failure, not a cancellation or retry instruction. Browser startup or
invalid configuration fails with exit 2 and a generic message; that is a local
probe failure and supplies no evidence about Metis availability.

The assertions are explicitly **section visibility**: the expected heading or
entry control must be visible after the response loads. They do not prove all
controls functional, a document correct, a task complete or publication allowed.
The probe blocks cross-origin traffic, non-GET/HEAD requests, websockets and
subsequent top-level reloads. This restriction can prevent a page from behaving
like an unrestricted browser; blocked-request counts are therefore exported.
Use an already authenticated session. A Microsoft redirect is not followed.

## Join existing evidence

Use `section-incident.kql` in the existing log destination. Save the projected
JSON event objects as an array or JSONL (single-column `d` rows and lines starting
with `metis_diagnostic ` are also accepted). No Azure resource is created or changed.
If no events appear, check resource/time window/ingestion and deployed build;
absence in an export does not establish absence at the application.

```sh
python scripts/export_section_incident.py \
  --browser /private/probe.json \
  --application /private/application.jsonl \
  --platform /private/platform.json \
  --output /private/incident-with-evidence
```

Platform evidence is an optional **operator-supplied** JSON array. After inspecting
existing Azure startup/process/gateway logs, record only observed categories:
`startup_failed`, `process_unavailable`, `process_restarted`, `gateway_response`,
`platform_available`; `timestamp` must carry a timezone; `status` is optional.
Example shape: `[{"event":"gateway_response","timestamp":"2026-10-14T04:00:00Z","status":502}]`.
Use the browser start/end window, including any later application completion.
These records retain their own times and are never causally joined on time alone.
Raw platform logs, URLs, cookies, exception messages and document content are
not copied into the incident. Keep originals under existing operational access
controls; file SHA256 values identify supplied evidence, not its authenticity.

## Read the result

`incident.json` and `summary.txt` separate browser boundaries, application
boundaries, platform observations, contradictions, missing evidence and the next
check. No root-cause confidence percentage is invented. Correlation strength:

- `response_request_id`: browser-observed server token matches app records.
- `client_attempt_untrusted`: no response token, exactly one app request shares
  the caller-controlled token. This is correlation, never authenticated identity.
- `ambiguous`: token reused across app requests; no request is selected.
- `none`: no matching evidence. Never guess using route or elapsed time.

A 502 followed by server completion retains both observations. It does not prove
which gateway failed, that the browser received a later response or that retry
is safe. Inclusive phase durations overlap and must not be added as exclusive time.
ASGI send completion means the server accepted that send; not browser receipt.

Inputs are independently observed, not one atomic domain snapshot. Each input is
limited to 8 MiB; exported application events to 1000 and platform events to 100.
Truncation and absent fields are explicit. Output directories/files are new and
never overwritten. The script rejects arbitrary log wrappers: normalize locally
rather than placing raw portal dumps or private material in the repository.

## Verification and limits

Run `tests/test_section_incident.py`, `tests/test_request_diagnostics.py` and
`node tests/browser_section_probe.cjs` (with Playwright/browser configured).
Browser tests simulate HTTP failure boundaries on a local server; they do not
prove an Azure gateway root cause. The authenticated integration test additionally
uses the actual Metis section route and the existing fixture session.

After deploying through the existing reviewed release process, still verify live
Azure receipt, startup/gateway evidence and one representative authenticated
journey. This slice does not instrument background attempts or establish an
end-to-end publication proof. Reassess the critical-path blocker after it lands.
