# Processing and recovery margins — PR 3

Issue: #767
Depends on: #766
Change class: B
Rewrite risk: none
Promise: Authorized document users can inspect measured processing/recovery
margins in the existing trace JSON and document diagnosis without changing work.
Proof: `tests/test_processing_margins_v1.py`, installed-app local/PostgreSQL proof
in `tests/test_processing_margins_http_v1.py`, existing trace/Inzicht regressions.
Touches lifecycle invariants: no

## Program design and ownership

This is a stateless read projection. Durable processing attempts, dispatch,
checkpoint metadata, retry/cooldown/admission policy, recovery and audit remain
owned by the existing kernel. No new lifecycle, transaction, producer, queue,
store, infrastructure or domain decision is introduced.

Existing path: processing_retry.reserve -> source_processing_dispatch.claim ->
existing diagnostic writer/finish -> processing_trace.project_attempt -> bounded
processing_trace JSON. The additive `processing_margins` field consumes those
same whitelisted rows, using the trace's observation time. The existing guarded
`/inzicht/document/verwerkingsspoor` export includes it; document diagnosis renders
it only after existing processing access checks. No second envelope/telemetry
scan is added. Existing processing_status still owns allowed follow-up actions.

The JSON guard calls source_selection.authorize with a current account. The
HTML route uses processing_status authorization; publisher-only users keep their
existing publication view and receive no processing margins. The renderer escapes
all dynamic text. Source/model prose, raw command/revision/configuration values,
claim tokens and credentials are not added to the projection. Offline clean_trace
ignores supplied derived fields; they are not authenticated kernel evidence.

## Measurement contract

All numbers refer to retained attempts of one document, never fleet occupancy.
Times use timezone-aware stored timestamps and the fixed observation time.
Missing values are null, not zero. Future or contradictory attempt timing prevents
confident timing/reference calculations. An invalid checkpoint cannot become a
healthy heartbeat. Missing/partial checkpoint evidence is explicit.

| Measurement | Basis | Limitation |
| --- | --- | --- |
| Pending wait so far | observation minus reservation, stored running/pending | Lower-bound elapsed wait, not estimated queue length or future admission. |
| Reservation-to-claim wait | recorded claim minus reservation | Missing/inconsistent claim remains unknown. |
| Claimed execution | recorded finish or observation minus claim | Completed-work bias; no worker occupancy or liveness proof. |
| Deadline margin | stored expiry minus observation, running only | May be negative; does not expire stored state or guarantee intervention time. |
| Time available at claim | expiry minus claim | No prediction that all this time was usable. |
| Last retained checkpoint age | latest valid checkpoint to observation/recorded end | Silence is not failure; omitted history is shown. |
| Retry gap | current reservation minus explicitly linked predecessor finish | No inferred order, retry rights, total recovery duration or causal assertion. |

Ambiguous/missing attempt identities and retry predecessors are not guessed.
Retained attempt/retry counts are not the kernel's retry budget: progress-aware
caps and recovery grants remain in processing_retry/status. No count subtracts
from a maximum to invent remaining retries.

An experimental comparison requires at least three earlier technically succeeded,
claimed attempts with the same nonempty source hash, configuration hash, execution
version and attempt kind. Only finishes at or before the current claim count;
storage order cannot introduce future outcomes. Known omitted attempt history or
missing/contradictory supporting evidence prevents the comparison. This is an
observed median, not a confidence interval, SLO, model forecast or complete history.
Different resume/retry/ingest work is not pooled. Remaining-work differences inside
one kind remain uncertain.

If available time at claim is shorter than that median, the view explains that
the attempt may reach its stored deadline and shows the values/sample count.
Elapsed stored deadlines are also visible while stored state remains unchanged.
The advice is to inspect the existing status, dispatcher and dependencies, then
use only an already authorized follow-up path. No retry, claim, cancellation,
expiry, repair or admission adjustment is performed by this analysis.

## Evidence and acceptance

| Claim | Falsifying scenario/check | Scope |
| --- | --- | --- |
| Evidence before a stored boundary | Synthetic active attempt has 30s available at claim versus a 50s median from 3 earlier attempts; comparison appears at claim while status still says in progress. | Functional temporal proof, no incident prediction accuracy or safe action lead. |
| Ordinary work remains ordinary | Sufficient claim budget produces no margin signal with a usable reference. | One synthetic control; no production false-alarm rate. |
| Context cannot borrow a reference | Change configuration, execution version or attempt kind; supply too few/partial peers. | Comparison abstains. |
| No look-ahead | Add completions after claim, including after observation; permute storage order. | Same current-attempt result; isolated mutation admitting later completions is detected by the test. |
| No authority drift | Read input is unchanged; expired stored running attempt stays running; current role guards and forbidden command/write methods. | Pure projection and registered handler locally; installed HTTP/local and native-store proof in CI. |
| Privacy/compatibility | Inject private fields and supplied derived evidence; use legacy metadata/empty history. | Whitelist/redaction and existing offline export remain authoritative. |

No historical production incidents or controlled production fault injection were
used. Synthetic data proves calculation and warning capability only. The view
creates no independent telemetry health claim: `coverage` stays `not_established`.
A warning is not claimed operationally actionable until decision/intervention and
recovery times have been measured and shown shorter than its warning lead.

## Decisions and remaining blind spots

| Extension | Decision | Acceptance boundary |
| --- | --- | --- |
| Bounded document timing/retry evidence | GO for review | Same authority, authorization, projection and omissions. |
| Experimental claim-margin comparison | GO for review only | Explicit evidence and uncertainty; CI and cost evidence still required for rollout. |
| Production alerting / accuracy claims | HOLD | Incident corpus, chronological backtests, false-positive budget and intervention timing needed. |
| Global queue/worker saturation, memory/DB limits | HOLD | Current snapshots/logs do not establish complete fleet inflow/outflow or capacity. |
| Multi-horizon forecasts / failure-chain causality | HOLD | More comparable longitudinal evidence required; this PR offers no 5m–24h forecast. |
| New producer/store or retention expansion | NO-GO in this slice | No need for a second data authority. |
| Autonomous prevention or new recovery rights | NO-GO | Separate authorization and proof required. |

Still insufficiently observable: unclaimed jobs never reserved in the kernel,
missing old attempts/checkpoints, vanished instances/logs, external-provider state,
worker liveness between checkpoints, progress within a processing phase,
remaining work within a resume, cross-document contention and semantic completion.
A retry gap includes human/admission/cooldown delay; it is not active repair time.
Technical success does not establish formation, review or publication completion.

## Verification / rollback

The retained bounds remain 64 attempts and 128 checkpoints per attempt; omissions
are shown. The helper performs bounded in-memory arithmetic over an existing
projection. It reads no source content, opens no connections and exports no new
logs. Revert code to remove the addition; no data migration or restore is needed.

Locally pytest and Azure app dependencies are absent, and the installed ASGI stack
differs from the lock. Direct handler tests isolate unrelated dispatcher startup;
they execute the existing current-account source guard, not a mocked permission
check. They are not described as complete HTTP/session/native-storage proof.
The separate installed-app test covers those paths in the pinned CI environment.
The PR stays draft/HOLD for merge and rollout until required CI and representative
performance/privacy/operational checks pass. No merge, deployment or automatic
intervention is performed.


### Executed local evidence

- Twelve new focused tests pass: measurements, early claim-margin capability,
  ordinary-budget/context controls, chronological/order invariance, legacy and
  contradictory data, truncation, explicit retry links, privacy, actual existing
  guard/handler wiring and escaped/open advice rendering.
- An isolated in-memory mutation admitting completions after claim causes the
  chronological test to fail by assertion (one failure, no import/setup error).
  The unmodified code then passes. No mutation remains in the repository.
- The 32-check local selection (12 new + 12 PR 2 + 8 PR 1) initially passed 31
  checks; the inherited Node renderer check timed out during concurrent cost
  measurements. The unchanged renderer check passed on an isolated retry.
  This is a setup/load observation, not a changed timeout or claimed single-run
  full-suite pass. The existing processing CLI export regression also passed by
  direct execution of its test function.
- Repository preflight, compileall and architecture-boundary checks pass.
  Pytest/architecture pytest cannot start locally because pytest is absent.
  Installed HTTP/app test collection is also blocked by missing Azure packages;
  neither that test nor PostgreSQL proof is claimed locally.
- Bounded self-review covered the helper, whitelist/legacy/export compatibility,
  both caller paths, actual source guard, HTML escaping and the tests. It corrected
  an order-dependent reference variable during implementation and verified the
  exclusion of differing attempt kinds. These fixes are covered by the final
  order/context tests. Final review found no additional demonstrated code blocker;
  mandatory HTTP/native/CI/performance evidence remains unestablished.

The maximum-size synthetic fixture contains 64 attempts and 8,192 checkpoints.
Five baseline projector measurements were 47.599/32.579/28.355/29.313/31.693 ms;
with margins they were 141.370/10508.566/2931.684/69.917/46.263 ms. The two large
outliers remain part of the evidence, not discarded as healthy performance.
A follow-up using alternating runs without the mocked observation clock measured
baseline wall/CPU pairs 44.689/44.678, 35.911/35.914, 25.664/25.668 ms and enabled
pairs 146.247/146.253, 31.947/31.952, 28.358/28.238 ms. The environment/benchmark
variance prevents a production overhead claim. Helper traced temporary peak was
54,272 bytes; the additional JSON was 31,790 bytes. These figures exclude real
HTTP/auth/database/native-store latency and do not prove fleet or polling cost.

GO is limited to review of this bounded implementation. Merge/rollout stays HOLD
for pinned CI, required HTTP/native proof, representative performance and an
operator-approved cost/false-positive/intervention-time budget. No production
accuracy, safe warning lead, new configuration activation or mitigation is claimed.
