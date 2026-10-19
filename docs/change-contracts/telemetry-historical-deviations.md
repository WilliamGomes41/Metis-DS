# Historical telemetry deviations

Issue: #765
Depends on: #764
Change class: B
Rewrite risk: none
Promise: Signed-in Inzicht users can inspect sustained deviations in existing
request observations, with a historical reference, uncertainty and abstention.
Proof: `tests/test_telemetry_history_v1.py`, existing telemetry/quality regressions,
production JavaScript rendering executed in Node, chronological synthetic replay.
Touches lifecycle invariants: no

## Program design and authority

Existing producers -> logging bridge -> TelemetryHub/JsonlSink -> recent_events ->
summarize -> authenticated summary API -> Inzicht Systeem. `summarize` already
reconstructs requests; one pure helper consumes those same objects. The API passes
PR 1 measurement quality into that helper. No extra scan, producer, persistence,
platform, dependency, domain authority, admission decision or notification exists.
Only derived JSON and the read-only page change. Export and request detail remain
unchanged, as do lifecycle, audit, idempotency, transactions and authorization.
There is no new instrumentation in the request/worker execution path.

## Statistical contract (research defaults)

- Always compare the latest 15 minutes with the preceding hour, even when the
  page selects a longer window. The existing reader starts one hour before the
  earlier of the visible-window start and the historical-reference start, so
  both receive a reconstruction margin. Retention and the 50,000-event cap stay.
- Fifteen adjacent five-minute bins end at evaluation time (sliding windows,
  half-open boundaries). The first twelve form the reference, the final three
  form the evaluation. A request is assigned by its recorded finish timestamp;
  future finishes cannot participate. All bins need at least five usable
  completed requests, independently for each route + method + commit cohort.
- Unknown commit, missing start, non-finite/negative duration or inconsistent
  timestamps exclude observations and prevent conclusions for that cohort.
  In-flight/unfinished requests are outside this response-time population;
  completed-work bias remains a limitation, not evidence of health.
- Measurements are bin medians of response time, p90-minus-median spread, and
  per-request exclusive phase time divided by elapsed time. A phase needs valid,
  untruncated evidence in every request of every bin; absent phases are not zero.
- Reference center is the median of twelve bin values. Required change is the
  maximum of 4 x 1.4826 x reference MAD, 25% of reference center, and a floor of
  25 ms (median latency), 20 ms (spread), or 0.10 (phase fraction). All three
  subsequent bins must strictly exceed center + required change. These values
  are transparent defaults, not calibrated significance levels or probabilities.
- Route, method and commit filters select cohorts. Request/search, error, status
  and state filters abstain to avoid outcome-selected baselines. Different
  commits never borrow each other's reference.
- Missing quality or any quality status other than `no_known_loss` abstains,
  including memory-only reads. Even `no_known_loss` does not establish coverage;
  every result retains that uncertainty. Known loss cannot become zero risk.
- At most 30 cohorts (highest observed volume, deterministic tie-break) and 20
  findings are returned. Omitted cohorts/findings, unsupported cohorts/phases and
  excluded requests are counted and shown. A result with no findings describes
  only evaluated metrics and explicitly does not prove health.

Findings identify scope, reference/evaluation intervals, sample counts, values,
MAD, minimum effect and persistence. They describe possible narrowing of margins,
not a proven failure mechanism. The safe action is inspecting request details,
document mix, configuration and dependencies. Time to an operational limit and
usable intervention lead time remain null; no operational threshold or response
time budget is established by these data. No action is executed.

## Decisions and boundaries

| Extension | Decision | Basis / next acceptance condition |
| --- | --- | --- |
| Read-only robust historical comparisons | GO for review | Bounded reuse of existing data; deterministic evidence and abstention. |
| Production alerting or predictive accuracy claims | HOLD | Historical incident labels, chronological production backtests, false-positive budget and intervention timing needed. |
| Capacity/time-to-limit forecasts | HOLD | Reliable queue/worker/resource limits and measurements are not present in this slice. |
| Seasonal baselines or cross-deployment comparisons | HOLD | Need sufficient comparable history and deployment/configuration context. |
| Compound/unknown failure-pattern claims | HOLD | Correlated observations are not established precursors; need incident evidence and validation. |
| ML, new storage, retention expansion | NO-GO in PR 2 | No demonstrated improvement over this smaller baseline. |
| Automatic mitigation | NO-GO in PR 2 | Separate authorization, efficacy proof, limits and recovery path required. |

Still insufficiently observable/predictable: document/configuration mix within a
cohort, uninstrumented background/external paths, rare/low-volume routes, short
spikes deliberately suppressed by persistence, slow drift absorbed into the moving
reference, long-running work without a finish, sudden crashes, seasonal shifts,
missing instances/producers and uncounted historic/export losses. None gains a
forecast horizon of 5m/15m/1h/6h/24h from this PR. Detection delay is not lead time.

## Verification and release limits

Synthetic positive cases cover sustained latency, spread and phase shifts;
controls cover stable load/noise, a spike, recovery, route mix and a new commit.
Replay supplies only chronological prefixes and checks equality when future
events are present. A stable one-hour reference followed by 100 -> 180 ms latency
is first detected at the third five-minute checkpoint (15 minutes after change).
Existing diagnostics produce no warning for that representative fixture; this is
an additional detected deviation, not proof of earlier warning before an incident.
The fixture has multiple measured phases rather than an always-dominant phase.

Known-loss/empty/gapped/unknown-commit/outcome-filter/truncated-phase cases verify
abstention. Handler tests verify auth-before-read and quality wiring; a separate
HTTP test traverses actual hub files, reader, ASGI API and serialization for CI.
Node executes the production renderer with positive, abstained, empty and unsafe
text values. No production records or failure injection in production are used.

Local verification and performance results are recorded below after execution.
A draft PR is not merge or rollout approval. Reverting code removes this derived
view; no data migration, data repair or domain-state rollback is needed.

### Local execution evidence

On the isolated workspace based on the exact #764 head tree
`a4143cfe045c6cbbf39a65a87c6f9ded1151627f`:

- Eleven focused tests passed, including chronological replay, three positive
  metric scenarios, stable/noisy/spike/recovery/mix/deploy controls, measured
  exclusions/limits, real hub files/quality, auth-before-read and the production Node renderer.
- Eight non-HTTP PR 1 quality regressions and the existing pure analysis
  regression passed. HTTP/ASGI execution timed out even for a minimal unchanged
  endpoint in this environment. The HTTP test is committed for CI; direct
  handler/reader checks are not presented as HTTP proof.
- Local pytest and the architecture pytest suite could not start: pytest is not
  installed. Compileall, architecture-boundary and repository checks passed;
  final focused release-control results are recorded in the PR.
- Three summary runs over 1,500 events / 750 reconstructed requests: baseline
  254.17/63.02/59.31 ms, with comparison 91.97/79.26/77.01 ms; median difference
  16.24 ms. Cold start/order effects make this indicative, not a production SLO.
- The helper alone over 45,000 events / 22,500 reconstructed requests / 30 cohorts
  took 357.52/467.20/371.24/551.40/870.05 ms in five runs; traced temporary peak
  allocation 2,079,172 bytes, excluding event loading and reconstruction.
  An attempted full-summary benchmark at this size was stopped after several
  minutes of inherited summary work without a result; no full-size endpoint
  performance claim is made. Concurrent users and polling multiply cost.

The helper measurements do not establish a production overhead budget. Production
rollout stays HOLD pending CI, representative endpoint/overhead measurements and
an operator-approved cost/false-positive budget. No deployment is performed.

### Synthetic detection ledger

| Fixture | New sustained comparison | Existing diagnostic comparison |
| --- | --- | --- |
| Median latency 100 -> 180 ms | Detected at 15m checkpoint | No warning in this chronological fixture. |
| Spread p90-minus-p50 0 -> 150 ms, median unchanged | Detected | Not used for a relative lead-time claim. |
| db phase share 20% -> 55% | Detected | Existing dominance advice may also appear; no earlier-detection claim. |
| Small slow drift 100 -> 110/115/120 ms | Missed: below minimum effect | Remains outside this detector's sensitivity. |
| Stable/noisy/spike/recovery/route-mix/new-commit controls (6) | No sustained findings | Controls, not incident labels. |

Within this deliberately small synthetic set: 3/4 deterioration fixtures detected,
1/4 missed and 0/6 control fixtures flagged. Abstentions are counted separately
and never treated as true negatives. These ratios are fixture outcomes, not
estimates of production recall, precision or false-alarm frequency. No historical
production incident corpus or actual actionable warning lead has been validated.

Bounded self-review covered the new helper, the existing reader/summary call path,
filters/auth, the actual renderer and all changed-file tests. It caught a test
clock mismatch: file mtimes must match fixed replay time to exercise the real
reader rather than its old-file optimization. Both filesystem and HTTP fixtures
now set that time explicitly; the executable filesystem regression covers it.
Remaining evidence gaps (HTTP execution, full pytest, operational calibration)
stay HOLD and are not relabeled as passed checks.


### Review corrections R1 and R2

R1: the original reader began exactly at the historical-reference boundary for
`window=15m`. A request crossing that boundary lost its start, and the detector's
missing-start guard correctly refused the entire cohort. The same data was
therefore detected under `1h` but not `15m`. The reader now applies its existing
one-hour reconstruction margin before the earlier of the visible window and the
75-minute historical window. `HISTORY_SECONDS` is shared with the detector.

The regression traverses actual hub files, `recent_events`, the registered summary
handler and JSON serialization. Two requests start before the reference (one by
one second, the other by thirty minutes) and finish inside it. `15m`, `1h` and
`6h` must return identical historical evidence: 122 reference and 30 evaluation
samples, one supported cohort, no excluded observations. A genuinely absent start
inside the reference still prevents comparison; known-loss quality still abstains.
No start is inferred from duration and no quality/persistence guard is weakened.
The regression failed on the prior revision and passed after the reader repair.

This is one scan over a longer interval, not a second scan or retention change.
For `15m` it reads at most one extra hour of available history; for `1h` it reads
15 extra minutes; longer supported windows keep their original read interval.
Reads still retain at most 50,000 events and report window/lookback omissions.
Starts older than the bounded margin can still be unavailable; that remains
insufficient evidence, not health. Additional scan cost has not been established
under production load; the rollout HOLD and cost-budget requirement remain.

R2: the added slow-traffic batch in the route-mix control reused 30 request IDs
from its reference batch. Request reconstruction merged those observations and
left one cohort unsupported, so the old empty-findings assertion could pass
without checking both routes. The fixture now gives the added batch a distinct
request-ID prefix and asserts all 375 finishes have distinct IDs, both cohorts
are supported, neither is excluded, and no sustained finding is emitted.
The strengthened test failed first (375 finishes versus 345 unique IDs), then
passed with distinct identities. Abstention no longer satisfies this control.

After these corrections, twelve focused non-HTTP tests pass locally. The two
red/green regressions, the original boundary replay, eight PR 1 non-HTTP quality
regressions and the existing pure analysis regression are the repair evidence.
The pre-repair performance figures above describe the helper/old scan; the helper
algorithm is unchanged, and no claim is made about the longer reader interval.
HTTP/full pytest proof for this revision remains required in CI.
