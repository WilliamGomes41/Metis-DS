# Telemetry measurement quality

Issue: #761
Change class: B
Rewrite risk: none
Promise: A signed-in user can see why the available telemetry is incomplete in
the existing Inzicht summary and request detail, including unavailable detail.
Proof: `tests/test_telemetry_quality_v1.py`, existing telemetry, request-diagnostics
and Inzicht regression suites.
Touches lifecycle invariants: no

## Existing mechanism and change

The existing path is producers -> logging bridge -> TelemetryHub/JsonlSink ->
recent_events -> authenticated telemetry API -> Inzicht Systeem.

The hub remains the owner of disposable operational observations. Request
diagnostics and processing producers remain unchanged. Only operation-local read
counts, process-lifetime buffer/failure counts, and derived projections change.
No domain data, durable state, audit, authorization or lifecycle rule changes.
Retention, storage limits, analysis limits and transient-event exclusions stay.

`recent_events` keeps its `(events, truncated)` return contract. Its optional
`quality` output reports exact omissions in the requested window separately from
omissions in the reconstruction lookback. Losing lookback alone does not set the
legacy window-only `truncated` flag, but does mark reconstruction as partial.

Summary and request-detail responses add `telemetry.quality`. An unknown, valid
request ID still returns 404 and now carries the same quality information.
An empty request population has `kpis.error_rate = null`: zero observations do
not establish a zero failure rate. The existing JavaScript percentage formatter
already supports null. Dynamic text continues to use textContent.

## Count semantics and limitations

- `process` identifies this worker's pid/runtime and counts since hub creation.
  Ring evictions count displaced buffer entries, including entries also retained
  on disk. They are a missing-history reason only when reading the process ring.
  Existing `dropped` remains compatible; `record_failures` explicitly includes
  storage/setup failures and is not an exact lost-event total.
- `read` belongs to one scan of available instance files. JSON parse failures,
  non-object/missing-time records and file/list/decode failures are separate.
  Repeated reads do not accumulate read errors as newly lost production events.
  Unreadable records may not be attributable to the requested time window.
- `analysis` counts readable events seen and used, with window/lookback omissions
  and the oldest/newest used timestamps, including reconstruction lookback.
  These bounds do not establish uninterrupted coverage.
- `coverage` remains `not_established`, even when no known loss was encountered.
  Unobserved producers, previous processes, deleted files, Azure export losses,
  sampling and field truncation cannot be reconstructed by these counters.
- A record failure, malformed line or other read problem never logs recursively
  through the hub. Reads remain best effort; the change does not retry production
  work or turn an observation into a domain decision.

## Acceptance and verification

The decisive regressions compare the same bounded analysis with/without omitted
events, test memory versus retained disk copies, repeat a corrupt-file scan, and
exercise authorization plus summary/existing/missing request detail via HTTP.
An unreadable file must leave other files readable. UI checks cover the quality
message and the empty-population rendering, including request-detail omissions.

Deployment and production predictive accuracy are outside this slice. No new
dependency or platform is introduced. Revert code to remove the additions; no
domain migration, data restore or lifecycle rollback is necessary.

## Review corrections R1 and R2

R1: enumerate files using `os.scandir`, which propagates directory access errors
to the existing best-effort read/write boundaries. A real POSIX permission test
checks denial, per-scan error counts, and recovery after access is restored.
An empty readable directory remains distinct from a directory that cannot be read.

R2: the API state `aborted` and its counters keep their existing semantics, but
presentation says that completion is missing. Advice, state badges, groups and
insights use a warning and explain that telemetry loss or processing interruption
are both possible; no crash is inferred. The operator checks measurement coverage
first. Existing exception/error severity is unchanged. A corrupt-finish regression
checks this distinction and that a later recorded finish removes the warning.

## Review corrections R3 and R4

R3: a file that another worker prunes between listing and reading is retention,
not a read failure. It is skipped without a `read_errors` count, so a normal
multi-worker prune does not mark the scan `partial`.

R4: `prune()` treats a failed directory listing as a skipped housekeeping round.
Writing continues on the disk store; only reads report listing failures. Both
corrections have a regression test that failed before the change.
