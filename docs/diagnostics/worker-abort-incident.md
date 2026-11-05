# Aborted Review saves and slow reads: collect evidence

Issue #974. [Change contract](../change-contracts/974-worker-abort-incident.md).
These commands read existing Azure logs and database state. They do not restart
workers, change diagnostics settings, or repeat/repair a review decision.

## 1. Logs (Azure Cloud Shell, Bash)

Use a reviewed checkout of PR #975, not the old deployed checkout: these new
scripts are not yet in the current production image. Choose the intended
subscription explicitly. The example window is UTC (14:28–15:05 in Amsterdam)
and surrounds the five unclosed POSTs and the later handled refusal.

```bash
export METIS_SUBSCRIPTION_ID="8c829c96-1784-4947-8a2b-92027c51fec9"
export METIS_RESOURCE_GROUP="AI_Dataservice"
export METIS_WEBAPP="vvn-metis-console"
export METIS_LOG_WORKSPACE="metis-log-analytics"
# Set METIS_LOG_WORKSPACE_GROUP only if the workspace is in another group.
az account set --subscription "$METIS_SUBSCRIPTION_ID"
bash scripts/collect_worker_abort_evidence.sh 2026-11-04T13:28:00Z 2026-11-04T14:05:00Z ~/metis-incident-974
```

The collector validates calendar dates, window order, subscription and the
resolved output path, including symlinks. It creates a new directory outside
the checkout with mode 700 and files under umask 077. It executes all six
sections of [the KQL file](worker-abort-incident.kql); a failed section is recorded
and makes the collector exit nonzero while other sections still run.

| File | Evidence |
|---|---|
| `aborted_review_saves.json` | Starts lacking a finish in the selected window; last recorded phase and heartbeat count |
| `worker_lifecycle.json` | Worker exit/start lines and available stack frames |
| `worker_pids.json` | First/last diagnostic records per pid and instance |
| `platform_events.json` | Available container/restart/memory signals |
| `slow_reads.json` | Read durations, counters, total DB bytes and measured phase tree |
| `review_save_finished.json` | Completed saves and refusals, including `review_disposition_conflict` |

### Interpretation

- Missing finishes or heartbeats are clues, not proof of a timeout, blocked
  eventloop or rollback. Check ingestion, window boundaries and log coverage.
- A matching `WORKER TIMEOUT` confirms a watchdog intervention. The startup
  script normally inherits Gunicorn's default timeout, but runtime overrides
  must be checked before asserting the effective value. A stack can locate the
  blocking path; it need not be a C call because the async correction exception
  handler also invokes synchronous work directly.
- `SIGKILL ... Perhaps out of memory?` confirms a hard kill, not OOM by itself.
  Corroborate with platform/memory evidence. A regular interval does not exclude OOM.
- A new pid may be a replacement; correlate the instance and exit lines before
  concluding. KQL `LastPhase` is the phase on the latest recorded event, not an
  arbitrary sample of heartbeats.
- `db_json_bytes` is a request total. The phase tree locates elapsed work but does
  not assign those bytes to a particular query.
- A missing table produces a query error. An empty or failed section is missing
  evidence, not proof of absence. Do not enable diagnostics as part of this
  read-only command. `az webapp log download` is an alternative if existing logs
  are downloadable; keep that archive private.

## 2. Candidate save evidence (App Service container SSH)

The Docling container runs from **`/app`**, not `/home/site/wwwroot`. The new
script is not deployed yet; transfer the reviewed script to `/tmp` without
changing the running app. One way is to generate a paste block from the reviewed
Cloud Shell checkout:

```bash
python3 - <<'PY'
from pathlib import Path
print("cat > /tmp/check_review_save_outcome.py <<'METIS_DIAGNOSTIC_974'")
print(Path('scripts/check_review_save_outcome.py').read_text(), end='')
print('METIS_DIAGNOSTIC_974')
PY
```

Paste that generated block into the container SSH terminal, then run the app's
Python with its existing packages/credentials and imports from `/app`:

```bash
METIS_DIAGNOSTIC_APP_ROOT=/app python /tmp/check_review_save_outcome.py \
  --doc-ref d_0123456789abcdef --start 2026-11-04T13:34:46Z --seconds 60
```

Use a DocRef from the captured body/heartbeat evidence if present; a POST start
may not contain it. Do not guess a document solely from the selected page.

The connection is READ ONLY, each statement has a 10 s timeout, and the process
has a 60 s alarm. At most 1000 events are returned; `events_truncated` marks
incomplete output and `review_events_in_window` is null when truncated. Only
event types, event timestamps and hashed object references are printed.

**`save_outcome` remains `not_determined`**, whether the window has zero or many
events. Another command can write in the same window, and an event timestamp is
not its commit timestamp. An exact command/interaction, object version, binding
and stored decision must be checked before assigning a commit/rollback outcome
to one unclosed HTTP request. This script alone does not establish that outcome.

## 3. Recording and proof limits

Keep raw output private. Record only reviewed technical summaries, with the
source and limitations; never source text, raw model output, credentials or
personal data. Preserve the production counters: the 945 reader calls contain
944 comparisons, 943 reuses and **two** builds, not 945 fresh reconstructions.
Historical local probe results and their limits are in
[diagnosis-summary.json](../../evidence/worker-abort-974/diagnosis-summary.json).
The automated tests cover collection/validation and PostgreSQL observations;
they do not validate KQL against a live workspace or prove a production fix.
