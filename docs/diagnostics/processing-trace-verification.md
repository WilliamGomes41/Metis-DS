# Slice 2 evidence and boundaries

Issue #616. Change class B, rewrite risk none. Existing envelope/attempt,
transaction, dispatcher, retry and activation owners remain in place.

## Local proof

The initial actual HTTP test failed because the POST response had no request ID.
The implemented observer now preserves its generated ID atomically with the
existing reservation. Repeated HTTP commands preserve the first accepted attempt.

A separate real dispatcher test reproduced an inherited ConsolePerformance
ContextVar in a worker after HTTP completion. Detaching request diagnostic and
performance contexts made that original test pass. Durable request correlation
is retained; background timings do not mutate the finished HTTP measurement.

Focused suite: 137 passed, 32 skipped, two dependency deprecation warnings. This
includes a real spawned worker terminated after an extraction/model-request
checkpoint, a fresh runtime reading the persisted attempt, explicit existing
expiry, and authorized retry with extraction forbidden. The retained extraction
hash is reused. A semantic partial-resume fixture targets only the open work and
preserves the completed candidate exactly. Telemetry failure does not change the
command result. No performance improvement or production root cause is claimed.

Native PostgreSQL is unavailable in this local executor: no server is installed;
package setup cannot switch to its service user under the executor's process
permissions. Local rollback controls fail before file writes. They are NOT
PostgreSQL rollback evidence. The new CI gate runs the same test module on real
PostgreSQL, including exceptions after SQL writes/before commit, concurrent
claims, child-process interruption and fresh-runtime readback. It rejects skipped
backend cases. Its outcome must be recorded before slice acceptance.

## Surface review

One new projection/observation module and one test module. Existing reservation,
claim, diagnostic writer and extraction record are extended; existing CSV ZIP,
incident CLI, middleware and CI are reused. No new service, state registry,
dispatcher, storage authority, automatic repair or infrastructure dependency.

The offline incident join has a relatively high static branch count: the
branches check independent missingness, selector validity, record identity,
truncation and deadline observations at an untyped evidence boundary. They do
not implement domain transitions. Keeping these checks together preserves
locality; no helper hierarchy was added to lower a metric. Exact metric/diff
values are recorded with the final revision rather than treated as a quality
score. Full repository context and per-feature behavior matter more than LOC.

Surface verdict: APPROVE WITH NOTES. Engineering readiness remains NOT ESTABLISHED
until native CI proof and required checks pass. This is a code review conclusion,
not authorization to merge or deploy.

## Delivery dependency

PR #613 was merged to main at 08f75f1. PR #615 was then merged to the older
fix/source-selection-diagnostics branch, so it is not present on main. The
slice-2 delivery will target main and include the unchanged, already-reviewed
slice-1 diff as its prerequisite, avoiding another PR whose changes remain only
on that older branch. No merge or deployment is performed by this implementation.
