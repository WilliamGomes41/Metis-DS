# Aborted Review saves and slow reads: collect Azure evidence

Issue #974. Change contract: [974-worker-abort-incident](../change-contracts/974-worker-abort-incident.md).
These are diagnostic reads only. They create, change and restart nothing in Azure
or PostgreSQL, and they never repeat, repair or delete a review decision.

## 1. Log Analytics (Azure Cloud Shell, Bash)

Run from a clone of this repository. Check the production selection first.
The window is in UTC and should include about 2 minutes on either side of the
aborted saves.

```bash
export METIS_SUBSCRIPTION_ID="8c829c96-1784-4947-8a2b-92027c51fec9"
export METIS_RESOURCE_GROUP="AI_Dataservice"
export METIS_WEBAPP="vvn-metis-console"
export METIS_LOG_WORKSPACE="metis-log-analytics"
# Only if the workspace lives in another resource group:
# export METIS_LOG_WORKSPACE_GROUP="..."
az account set --subscription "$METIS_SUBSCRIPTION_ID"
bash scripts/collect_worker_abort_evidence.sh 2026-11-03T00:00:00Z 2026-11-05T00:00:00Z ~/metis-incident-974
```

The script runs every section of [worker-abort-incident.kql](worker-abort-incident.kql)
and writes one JSON file per section, plus `manifest.txt`, to a new directory with
mode 700 outside the repository. You can also paste a single section into the portal
(`metis-log-analytics` > Logs) after filling in `{START}`, `{END}` and `{SITE}`.

| File | Question it answers |
|---|---|
| `aborted_review_saves.json` | Which saves never finished: start, last line, number of heartbeats, last phase, pid, `doc_ref` |
| `worker_lifecycle.json` | Exit reason: `WORKER TIMEOUT` plus a faulthandler stack (SIGABRT) or `SIGKILL ... out of memory` |
| `worker_pids.json` | Which replacement worker started, and when |
| `platform_events.json` | Container restarts or memory signals reported by the platform |
| `slow_reads.json` | Counters, db metrics and the phase tree of Vorming/Review reads over 5 s |
| `review_save_finished.json` | Duration and error code of saves that did finish, such as `review_disposition_conflict` |

### Reading the exit reason

- **Event-loop timeout (gunicorn default 30 s):** the heartbeats stop shortly after
  `request_started`, followed by `WORKER TIMEOUT (pid:N)` and `Fatal Python error: Aborted`.
  The deepest Metis frame of the thread that was not idle shows what held the GIL.
- **Hard kill or out of memory:** the heartbeats continue until the worker disappears,
  followed by `was sent SIGKILL! Perhaps out of memory?` or a platform memory signal.
- **Neither visible:** check the diagnostic settings (Console/Platform logs to the
  workspace), ingestion delay and retention. This is missing evidence, not a cause.
  As a fallback, `az webapp log download` provides the raw container logs. Keep that
  zip private and never place it in the repository.

## 2. Save outcome per aborted request (App Service SSH)

Use the `DocRef` and `Started` values of each row in `aborted_review_saves.json`:

```bash
python /home/site/wwwroot/scripts/check_review_save_outcome.py \
  --doc-ref d_0123456789abcdef --start 2026-11-04T09:12:03Z --seconds 60
```

The check is read-only (`SET TRANSACTION READ ONLY`, a 10 s statement timeout and a
60 s overall limit). It prints only event types, timestamps and hashed object
references.

- **An event in the window that matches the reviewer's action:** the save was
  committed, but the user saw an error.
- **No event:** the transaction was rolled back and the decision is not stored.
- Other saves on the same document can also fall in the window, so compare
  timestamps before concluding.

## 3. Recording

Record only counts, error codes, pids, timestamps and SHAs in #974, the change
contract and Linear. Do not record stack text containing paths outside `src/`,
`doc_ref` lists, object references or raw logs.
