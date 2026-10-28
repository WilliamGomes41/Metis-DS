# Integrated Review evidence — #888

Change class: B
Promise: Assess the integrated Review repair against the predeclared budgets and existing read/domain rules.
Proof: Matched authenticated PostgreSQL/ASGI workload, phase evidence, source oracle and existing negative/concurrency tests.
Touches lifecycle invariants: no
Rewrite risk: none

## Measurement protocol

The baseline is `49e50be279925b7e87d4ffa551609b998cac5869` (WP1,
before WP2/WP3). The integrated production code is main
`36c80413ced37e5a4dc74a380c6b54e23235e007`. WP4 changes evidence only.
Each measurement records its actual HEAD, reconstruction-file hash, identical
harness hash, Python version, configuration, source hashes/size and
fragment/block/object/candidate/binding counts. An assertion rejects a module
loaded from a different checkout. Run the identical harness *inside* both
checkouts; pytest path discovery can otherwise import the other checkout.
The production source diff must be empty.

Start `scripts/test_postgres.sh` first and retain its DSN privately in
`METIS_TEST_POSTGRES_DSN`. No PostgreSQL skip counts as evidence. Use the same
Python environment, PostgreSQL server and isolated production-composition test
databases. Do not run other CPU/database-heavy checks during these measurements.
No actual deployment, Azure latency, model inference or live user is involved.
The original lifecycle projection is retained. Only model transport is replaced
by explicit literal selections through the real deterministic candidate creator.

```bash
REVIEW_PROOF_OUTPUT=/tmp/review-proof.json python -m pytest -q \
  -p tests.conftest evidence/review-integrated-888/benchmark.py
```

The matrix includes 20 closed paragraphs, 150 and 600 continuing paragraphs,
300 closed candidates with an occupied 20-member batch page, headings/table/
section transitions, and three genuinely persisted visible documents. It visits
overview, individual document task, inventory, batch and passage. Each has one
first-for-route observation plus seven warm samples, complete and incomplete.
The incomplete matrix deliberately adds a **synthetic retained finding** before
the GETs; genuine failed-provider/recovery cases are verified separately by the
existing formation tests. It must not be described as a failed real model run.

GETs must preserve full stored envelopes, object histories, bindings, review
events and command events. A non-assigned reviewer is denied passage access.
Two simultaneous passage GETs per formation state are an additional smoke test;
they are not sustained load or statistical concurrency evidence. Existing real
writer/concurrent capture and stale-command tests supply that separate proof.
These timed fixtures contain fresh object histories and zero review bindings.
Existing history and context tests supply functional coverage, not a latency
claim for heavily revised documents or many existing review bindings.

First-for-route samples do not establish process-cold or database-cold latency.
All requests perform the normal operation-local preparation, but module imports,
OS caches and PostgreSQL buffers may already be warm. Process-cold latency and
production load remain unmeasured. Seven warm observations support a local
median/range comparison, not a stable p95. No p95 is reported.

## Fixed budgets and interpretation

The WP1 contract fixes these provisional engineering budgets before optimization:

* Four times as many continuing fragments: at most six times median preparation
  work/time (separate source-scaling script and deterministic work-volume test).
* The large continuing workload's total route median: at least 30% reduction.
* Small/complex/multiple-document control routes: no more than 15% regression
  beyond measured run-to-run noise.

Retain all samples, including slow ones. Repeat small/complex/multiple controls
in reverse version order after the first complete comparison. Report both rounds
and their median differences; a first-round budget miss is not erased. Treat
unstable timings as inconclusive rather than changing the fixture or budget.

`report.py` rejects unmatched workloads/configurations/harnesses, missing samples,
different warning/batch outcomes, request errors and uncommitted production code.
It reports initial budget misses explicitly; `--assert-budget` exits nonzero on
them. A passing helper never closes the project by itself.

```bash
python evidence/review-integrated-888/report.py --before /tmp/before.json \
  --after /tmp/after.json --output /tmp/comparison.json --assert-budget
```

Supply `--before-repeat` and `--after-repeat` to also report the combined control
samples. The initial misses remain visible and `--assert-budget` still reports
those misses; generating a report without that flag is not a budget pass.
See [RESULT.md](RESULT.md) for the measured results and remaining evidence.

The optional `.json.gz` input is ordinary gzip-compressed JSON. It preserves the
complete safe numerical samples/phase trees while keeping generated evidence
small. Decompress with Python's `gzip` module or `gzip -dc`.

Phase columns are **inclusive** and overlap; do not sum source preparation,
block building and reconstruction. SQL execution and fetch are reported
separately, alongside JSON transfer and HTML size. The diagnostic remainder is
the existing conservative lower bound. A truncated phase tree makes that
remainder unknown, not zero.

## Review and completion boundaries

The integration diff from WP1 adds the reconstruction accumulator and full-source
passage reuse without replacing their owners or changing source/publication
contracts. The full old-output oracle remains; the rollback helper's explicit
legacy import switch retains its original assertions. New integrity, partial
window, immutable input, concurrent writer and stale-command checks were not
weakened. There is no new production state, schema, writer, job or cache.

The incomplete inventory still computes source-accountability twice; its current
review/closure decision is not reused as authorization or cached approval. A
safe further reduction has not been established. Historical probes in earlier
evidence directories remain intentionally reproducible and are not runtime code;
temporary exploration files stay outside the delivered patch.

Current deployment identity, representative production source, logged-in live
baseline and production latency remain open under GitHub #699/#680 (and #695 for
deployment identity). Their explicit production GO requirement still applies.
Neither this evidence, green tests nor a merge closes #888/#884 or those live
issues. Rollback is an evidence/code revert; no data migration or repair occurs.
