# Frozen KO4 save method, version 1

Prepared only. No acceptance result exists until the root supplies both an
immutable final KO4 head and an explicit quiet GO. Baseline is the actual
KO2/KO3 integration `837b115f213bcfd0e9f4a71a1010231d2040365e`.

The original `evidence/974-p4b` script measures warmed repair specification
and rendering. It does not measure a committed correction, runs only AB and
overwrites receipts. This method preserves its large synthetic source shape
while measuring the actual approval and correction POSTs that change state.

Two required gates: approval-save wall p95 and correction-save wall p95 must
each be at most 1.10 times baseline. Every individual save must be at most
30 seconds, the unmodified installed Gunicorn default used by the startup
script. Server latency and SQL/JSON/connection/response counters are
attribution only, not additional acceptance thresholds.

Five alternating pairs start with baseline: AB, BA, AB, BA, AB. Five is odd,
so the declared balance is 3 AB / 2 BA. Four samples per operation and
execution give 20 samples per operation/side and 80 measured saves total.
Nearest-rank p95 is observation 19 of 20; every observation remains in the
report and the independent timeout rule covers the maximum as well.

The source has 923 paragraphs, one heading, 924 raw fragments and 92
materialized candidates. Synthetic model proposals supply source/version-bound
support links. During untimed setup, real authenticated compact-form
approvals confirm those typed links; real type-confirmation commands then
create open successor versions retaining them. Thus each measured approval
starts with actual confirmed supporting evidence and cannot depend on an
implicit N/A. Four other candidates undergo a real literal-source correction
that changes text, creates a new version and leaves it open for review.

Each execution uses two fresh production Gunicorn workers: four approval
GET/POST pairs in one, four correction GET/POST pairs in the other. Startup,
login and authentic form GETs are outside the measured POST response. No
receipt navigation is included. PostgreSQL and all approval/correction
writers are the actual production composition. Only model fixture inputs and
local configuration use existing test infrastructure. Default GC remains
enabled; no forced collection, threshold change or timeout override occurs.

All business proof reads and diagnostic-log parsing follow both complete
timed paths. The proof checks four exact valid approval bindings and three-yes
decision events; four changed-text, new open corrections; unchanged unrelated
objects, source bytes and public canonical tables; and persistence through a
real production-composition restart. Deliberate login sessions are expected
authentication writes. This is local PG17 evidence, not Azure production.

Reproduce in this workspace:

1. Copy the four scripts, `protocol.json` and `source.sha256` to
   `/tmp/ko4-perf/`; verify `sha256sum -c source.sha256`.
2. Pin clean detached `/tmp/ko4-perf/base` and `/tmp/ko4-perf/head` worktrees
   to the exact baseline and final head. Both must have no tracked or
   untracked changes when an execution starts.
3. Use `/workspace/.venvs/metis-ds/bin/python`, ordinary local PostgreSQL on
   port 55432 and the repository PG helper. Provide a verified localhost TLS
   certificate/key at `/tmp/ko4-perf/server.crt` and `server.key`; private
   keys are never committed. Clear `GUNICORN_CMD_ARGS` rather than overriding
   the production default. Current certificate expires 8 November 2026.
4. After all other local PG/browser/test work ends, set `KO4_HEAD_SHA` to
   the full immutable head and `KO4_QUIET_GO=1`, then run `runner.py`.
   It verifies pinned heads, clean source and frozen hashes before every
   execution. It refuses an existing output directory. No retries occur.
5. Run the committed `summarize.py OUTPUT_DIRECTORY`. It validates every
   execution, worker, post-save proof, planned/actual order and source hash
   before producing `summary.json` and all 80 raw rows in `saves.csv`.

Output is `/workspace/ko4-perf-evidence/v1-counterbalanced-HEAD8`. Failures
stop the runner and remain in the raw log/failed-observation files and
execution order. Never overwrite, discard or relabel a run. A later test-only
head requires an explicit production-equivalence receipt; it is not the
original measured SHA.

One baseline-only setup smoke passed at the pinned baseline in 69.82 seconds,
with no skips, under concurrent development work. It is **not acceptance**;
none of those values is reused. The acceptance estimate is about 12–15 minutes
for ten full fixture/worker executions. No acceptance run has started.
