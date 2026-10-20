# Processing deadline shadow forecast — PR 4

Issue: #770
Depends on: #768
Change class: B
Rewrite risk: none
Promise: Selected authorized documents show a bounded chronological evaluation
of the existing coarse duration estimator and an experimental comparison to the
stored attempt deadline, without executing any intervention.
Proof: `tests/test_processing_forecast_v1.py` and installed-app local/PostgreSQL
regression `tests/test_processing_forecast_http_v1.py`.
Touches lifecycle invariants: no

## Existing path, owner and smallest change

This is a stateless calculation, not a new lifecycle or durable authority.
`source_selection_ui_v1.selection_get` already loads envelopes once within the
existing read scope, filters actor-visible documents, authorizes the selected
document and calls `source_selection_v1.projection`. Only an explicitly selected
document receives this additional calculation, using those same visible envelopes.
The original ETA and processing/status/review/retry/admission behavior are unchanged.
The new adapter calls the existing `source_selection_v1.estimate` numeric model;
it does not create a second model, producer, store, schema migration or platform.

The kernel remains sole owner of attempts, deadlines, dispatch, durable state,
idempotency, recovery, transactions and audit. No forecast modifies an envelope,
expires an attempt, authorizes a retry or establishes formation completeness.
Existing account and named-reviewer checks remain in force. No additional store
reads are performed. No source/model prose, source identifiers, claim tokens or
configuration values are included in the derived report.

## Measurement and chronological contract

The estimated quantity is **technical ingest-attempt duration from reservation,
including waiting**, normalized by received source bytes. It is not full document
completion, an execution-only estimate, a failure probability or a fleet metric.
Only the current running ingest is supported; resumes/retries of other kinds HOLD.

The adapter requires positive finite bytes, a known route/class, timezone-aware
coherent timestamps, unambiguous attempt identity, matching stored source
hash/version and nonempty **attempt-recorded** configuration. It never substitutes
the envelope's later configuration. Comparable peers have the same route/class
and exact stored configuration with a byte-size ratio between 0.5 and 2.
Equal configuration is not proof of equal dependency health or document complexity.

Each estimate is made as of its target's reservation time. Only outcomes finished
at or before that time can train it. Earlier work still unfinished then is censored,
even when its later outcome is now known. Any comparable censored or non-successful
prior attempt prevents a confident success-only range. Future terminal labels are
masked at the observation time. Input storage order cannot supply future evidence.

The existing range requires at least three peers. A shadow range additionally
requires at least three chronologically scoreable historical cases, a future valid
stored deadline and elapsed time below the historical upper range. These are
research defaults, not calibrated safety thresholds. Missing/inconsistent history,
duplicate identities and limits produce HOLD. Known failures and censoring are
counted; missing historical records remain unquantifiable (`coverage=not_established`).

The exact existing estimator is reused: the lower bound is the smaller of the
minimum normalized duration and half the median, and the upper bound the larger
of the maximum and twice the median. This broad empirical range is not a confidence
interval and has no asserted probability or production calibration.

## Evaluation and operational meaning

Walk-forward evaluation reports scored and abstained technically succeeded cases,
durations below/above the range, the number with a usable deadline, false upper-range
pressure signals and missed observed deadline crossings. Denominators are explicit.
Unsuccessful work is not a completed-duration label; it forces abstention where
comparable and cannot prove incident recall. There is no training/test random split.
Evaluation covers retained comparable history, not an independent incident corpus.

Pressure means the range's upper edge reaches the reservation-to-expiry budget.
This is a potential time-limit consequence, not a predicted crash. A range inside
the deadline is explicitly not evidence of safety. Remaining time to the stored
deadline is measured separately and may become negative without mutating state.
Known deadlines inside 5m/15m/1h/6h/24h are only horizon metadata; predictive
accuracy at **every** horizon remains `not_established`.

The UI offers inspection of the existing status/dispatcher/dependencies through
the existing diagnosis link. No new action or generic push alert is added.
Detection is on selected-page reads (existing active-page polling is about 5s,
not a delivery guarantee). Human decision, safe intervention and recovery times
are unknown. Therefore actionable lead time is not established even when a
synthetic case identifies pressure at reservation, 80 seconds before expiry.

## Cost, limits and decision gates

Only documents with the current route and a comparable size (0.5–2×) are
examined, and only ingest attempts that started within the last 30 days. The
adapter stops at 256 such candidate documents, 64 attempts per document or 128
analyzable ingest records, with an explicit HOLD reason. Attempts of other routes,
sizes or configurations and older attempts are counted separately; they neither
train nor hold the range. An invalid or failed attempt still holds the forecast
when it could have been comparable (same route, size and lookback). It never silently samples
a complete-looking cohort. These are computational limits, not retention changes.
The report counts documents/attempts over their limits; at an early record-limit
stop it reports a lower bound of unexamined records rather than a fabricated total.
Evaluation is at most quadratic in 128 records, only for the selected document.
No telemetry retention, 64MB store limit or 50,000-event scan limit is expanded.

| Extension | Decision | Acceptance / remaining evidence |
| --- | --- | --- |
| Bounded strict adapter, chronological evaluation and selected shadow display | GO for review | Synthetic chronology, bias, isolation, limits, unchanged state and estimator regression checks. |
| Operational alerts or claims of earlier real incident detection | HOLD | Real chronological incident/control corpus; comparison with existing diagnostics; missed incidents/false alarms, usable intervention lead and bounded alert burden. |
| Production enablement and overhead acceptance | HOLD | Pinned CI including real app and storage regressions; representative load/latency/memory measurements. |
| Calibrated 5m/15m/1h/6h/24h forecasts | HOLD | Out-of-sample evidence per risk and horizon, adequate history and stable cohort. |
| Fleet queue/worker/memory/storage/connection exhaustion | HOLD | No complete fleet time series or authoritative operational bounds established here. |
| Wider retention or new telemetry collection | HOLD | Incident-frequency/cost/privacy case and loss accounting first. |
| Autonomous admission, capacity or recovery intervention | NO-GO in this PR | Separate authorization, proven effectiveness, hard execution bounds and rollback/fallback. |

Unpredictable/insufficiently observed risks remain: new failure mechanisms without
precursors, abrupt outages, uncaptured concurrency and dependency contention,
changes inside a matching configuration, complex documents unlike byte-size peers,
missing history/telemetry and all failure/capacity/repair outcomes beyond the
technically succeeded duration label. No ML or synthetic accuracy claim closes these gaps.

Synthetic tests prove temporal behavior only. Required checks, actual outcomes and
remaining environment limitations are recorded in the PR; a draft is not rollout approval.

### Local development evidence

The synthetic pressure case has six earlier 100-second ingests and an 80-second
stored budget: the reused range is 50–200 seconds and pressure is visible at
reservation, while the stored state remains running. A 400-second budget is a
normal control. A held-out 250-second duration after three 100-second ingests is
above its earlier 50–200 range and crosses its 220-second deadline: the evaluator
counts one missed boundary. A separate 10-second held-out case falls below the
range; three 150-second-budget controls yield three false upper-range signals.
These are intentionally constructed functional examples, not accuracy estimates.

An in-memory mutation removing the finish-before-reservation condition is caught
by the test where a prior outcome is known now but was unknown at reservation.
The unchanged legacy estimator regression also passes through direct execution
of that test function; it does not substitute for the installed-app suite.

On this development machine, 20 warmed calculations at the bound (256 visible
envelopes, 128 accepted records, 124 scoreable cases) measured median wall/CPU
22.5ms, maximum wall 43.9ms, temporary traced peak 70,137 bytes and 1,111 JSON bytes
for the derived report. This measures the added calculation, excluding existing
page/store reads and rendering. It is not a production overhead guarantee.

## Review correction R1

Before R1 every visible document counted towards the limits and the invalid-history
check, and failures never aged out. One unrelated legacy attempt without stored
configuration, more than 128 processed documents or one comparable failure at any
time therefore held every forecast. R1 filters by route, size and configuration
first and applies a 30-day lookback; regression tests cover all three cases and
failed before the change. The installed HTTP test no longer patches a
non-existent console method; durable writes still go through the patched
`_commit_prepared_store`.
