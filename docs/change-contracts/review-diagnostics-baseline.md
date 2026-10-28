# Review diagnostics baseline — #885

Change class: B
Promise: Review preparation and read costs are visible in bounded request diagnostics.
Proof: A red scaling probe and phase-tree, privacy and authenticated route checks.
Touches lifecycle invariants: no
Rewrite risk: none

## Existing boundary and scope

The authenticated `/review` route uses the existing workboard or document read.
`read_review_document` captures the envelope, objects and bindings using the
existing transaction; source preparation and revision hashing follow that read.
`prepare` derives temporary source views and `source_accountability` and
`review_work_projection` continue to decide existing domain projections.
The additions measure these calls; they do not change their inputs, outputs,
authorization, storage, source semantics, exceptions, or transaction boundaries.
Only request-local diagnostics may change. A diagnostic failure must not change
the response or durable state.

## Repeatable scaling workload

Run `PYTHONPATH=. python scripts/benchmark_review_source_scaling.py --sizes 150 600 --repeats 3 --assert-budget`.
The command exits red on the unoptimized path if the median for four times as
many continuing fragments exceeds six times the baseline. This is a proposed
regression budget, not a proof of linear complexity or a production SLO.
The script emits all samples, Python version, commit and fixture shape. The
default workload also includes 300 and 1200 fragments. The fixture constructs
synthetic HTML, holds source text and fragment size fixed, verifies a continued
sequence forms one block, and compares it to independently closed paragraphs.
It exercises source preparation, not PostgreSQL, HTTP, concurrency or production.
Do not copy source text or request identifiers into telemetry.

The baseline on 0707d89, Python 3.12.14, three repeats, measured medians
0.527 s (150) and 7.778 s (600), approximately 14.8x for 4x input. The test
exited red. Earlier measurements were also synthetic; production causation and
representativeness of this shape remain unknown.

## Integration workload and budgets

Before WP2/WP3, measure the existing real authenticated ASGI routes against
disposable PostgreSQL with the same runtime, code version, fixture data, actor
role and source contract on both sides: overview, document task and individual
passage; complete and incomplete formation; one large document and multiple
visible documents; closed sentences and continued fragments; candidate, binding,
source mapping and context counts recorded. The existing 300-candidate benchmark
has an empty batch and is not representative of an occupied batch.

Proposed performance gates for the later integrated acceptance, to be fixed before
the change and interpreted with repeated measurements: the 4x continued-input
median must be at most 6x the smaller case, with work/allocations profiled; matched
large-case total route median should fall by at least 30%; matched control route
median must not regress more than 15% beyond measured run-to-run noise. Use at
least five repeated runs per scenario for medians; report all values. These are
provisional engineering budgets, not an agreed production SLO. For p95 use a
separately justified sample size and report sample count; never derive it from
three requests. The actual production document, runtime and current deployment
remain unobserved. Existing #699/#680 govern authorized production measurement.

Log total request, source preparation/build, capture/revision, work projection,
source accountability, replay/status, database and unaccounted remainder.
Nested inclusive timings overlap; compare tree children and exclusive durations
rather than summing all phase totals. A failed or unavailable PostgreSQL setup is
not a passing integration test.

`unattributed_lower_bound_ms` subtracts the sum of root phase times from the
request elapsed time and clamps at zero. Root phases may overlap, so it is only
a conservative lower bound, not an exact remainder. It is omitted if the phase
tree is truncated. Missing coverage is not proof of CPU or database work.

A separate local authenticated ASGI benchmark used the existing 300-candidate
fixture against disposable PostgreSQL 16.2, Python 3.12.14 and the working tree
based on 0707d89 with diagnostic changes. Three samples per task are recorded in
`evidence/review-diagnostics-885/document-task-baseline.json`. The test passed.
It uses short, closed paragraphs and an empty batch fixture; it does not cover
incomplete formation, multiple visible documents, a real production source, or
statistically support a p95. It ran while other tests were active, so the results
are exploratory and are not a controlled regression threshold.

## CI follow-up and lessons for later pushes

The first PR run, 40614363772 on e108727, failed `change-contract` because
the PR description omitted all five required contract fields. The fields were
present in this document and issue #885, but CI reads the pull request event's
body instead. The local repository and release preflights did not test that body.
The same validator reproduced the five errors locally; adding the five fields
to the PR description made the same command pass.

The CI preflight and suite depend on the contract gate. They were skipped;
aggregate jobs then failed on absent suite XML files. Those missing artifacts do
not prove that the skipped tests failed. The separate Docling acceptance workflow
passed, as did architecture boundaries, Bend, workflow topology and source
processing. A prior interrupted local parallel run reported an unidentified
failure; a later complete run passed. Its original failure cannot be diagnosed
from the available output.

For the next push:

* Validate the exact proposed PR body with `python scripts/validate_change_contract.py
  --text-file <path-to-pr-body>` before creating or updating the PR. Include the
  five explicit fields, not only a link to the issue or contract file.
* Compare preflight commands with the actual CI job list: a passing repository
  preflight or local pytest does not include the change-contract event check.
* Diagnose the earliest failed gate and downstream dependency states before
  interpreting absent artifacts as separate test failures. Inspect both Python
  matrix jobs and real acceptance independently.
* Capture full parallel test logs with test names, including on interruption;
  retain the first error before rerunning so a later green result does not erase
  evidence of a potential intermittent failure.
* When retrying an event-driven workflow, verify the run uses the corrected PR
  body and exact commit. An old pull-request event payload can retain old metadata;
  a new synchronized PR event is required for a definitive check of updated text.

This records the observed incident and its limits; it does not establish that a
new push, the complete CI matrix, or current production Review is successful.
