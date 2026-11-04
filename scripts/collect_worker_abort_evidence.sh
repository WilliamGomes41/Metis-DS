#!/usr/bin/env bash
# Issue #974: read-only collection of Azure evidence for aborted Review saves and
# slow Vorming/Review reads. Runs every section of
# docs/diagnostics/worker-abort-incident.kql against Log Analytics and writes one
# JSON file per section to a NEW private directory outside the repository.
#
# Read-only: only `az account show`, `az monitor log-analytics workspace show` and
# `az monitor log-analytics query`. Creates, changes and restarts nothing in Azure.
#
# Usage (Azure Cloud Shell, Bash, from a clone of this repository):
#   export METIS_SUBSCRIPTION_ID="8c829c96-1784-4947-8a2b-92027c51fec9"
#   export METIS_RESOURCE_GROUP="AI_Dataservice"
#   export METIS_WEBAPP="vvn-metis-console"
#   export METIS_LOG_WORKSPACE="metis-log-analytics"
#   export METIS_LOG_WORKSPACE_GROUP="AI_Dataservice"   # optional, default METIS_RESOURCE_GROUP
#   bash scripts/collect_worker_abort_evidence.sh 2026-11-03T00:00:00Z 2026-11-05T00:00:00Z ~/metis-incident-974
set -euo pipefail

usage() {
  echo "usage: $0 <start-utc-iso8601> <end-utc-iso8601> <new-output-dir>" >&2
  exit 2
}
[ "$#" -eq 3 ] || usage
START="$1"; END="$2"; OUT="$3"
iso='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z$'
[[ "$START" =~ $iso && "$END" =~ $iso ]] || { echo "start/end must be UTC ISO-8601 like 2026-11-03T08:00:00Z" >&2; exit 2; }

for name in METIS_SUBSCRIPTION_ID METIS_RESOURCE_GROUP METIS_WEBAPP METIS_LOG_WORKSPACE; do
  [ -n "${!name:-}" ] || { echo "missing environment variable: $name" >&2; exit 2; }
done
[[ "$METIS_WEBAPP" =~ ^[A-Za-z0-9-]+$ ]] || { echo "METIS_WEBAPP has unexpected characters" >&2; exit 2; }
WORKSPACE_GROUP="${METIS_LOG_WORKSPACE_GROUP:-$METIS_RESOURCE_GROUP}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KQL="$ROOT/docs/diagnostics/worker-abort-incident.kql"
[ -f "$KQL" ] || { echo "query file not found: $KQL" >&2; exit 2; }

# Evidence never lands in the repository and is never overwritten.
case "$(cd "$(dirname "$OUT")" 2>/dev/null && pwd)/" in
  "$ROOT"/*) echo "output directory must be outside the repository" >&2; exit 2;;
esac
[ ! -e "$OUT" ] || { echo "output directory already exists: $OUT" >&2; exit 2; }

# Explicit production selection; stop on any mismatch.
active="$(az account show --query id -o tsv)"
if [ "$active" != "$METIS_SUBSCRIPTION_ID" ]; then
  echo "active subscription $active differs from METIS_SUBSCRIPTION_ID; run: az account set --subscription \"$METIS_SUBSCRIPTION_ID\"" >&2
  exit 1
fi
workspace_id="$(az monitor log-analytics workspace show \
  --subscription "$METIS_SUBSCRIPTION_ID" --resource-group "$WORKSPACE_GROUP" \
  --workspace-name "$METIS_LOG_WORKSPACE" --query customerId -o tsv)"
[ -n "$workspace_id" ] || { echo "workspace not found" >&2; exit 1; }

mkdir -p "$OUT"
chmod 700 "$OUT"
sections="$(grep -oE '^// ==== [a-z_]+ ====$' "$KQL" | sed -E 's#^// ==== ([a-z_]+) ====$#\1#')"
status=0
{
  echo "issue: 974"
  echo "window: $START .. $END"
  echo "site: $METIS_WEBAPP"
  echo "workspace: $METIS_LOG_WORKSPACE ($WORKSPACE_GROUP)"
  echo "collected_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "query_file_sha256: $(sha256sum "$KQL" | cut -d' ' -f1)"
} > "$OUT/manifest.txt"

for section in $sections; do
  query="$(awk -v s="// ==== $section ====" '
      $0 == s {on=1; next}
      on && /^\/\/ ==== [a-z_]+ ====$/ {exit}
      on {print}' "$KQL" \
    | sed -e "s/{START}/$START/g" -e "s/{END}/$END/g" -e "s/{SITE}/$METIS_WEBAPP/g")"
  if az monitor log-analytics query --workspace "$workspace_id" \
       --analytics-query "$query" --timespan "$START/$END" -o json > "$OUT/$section.json" 2> "$OUT/$section.err"; then
    rows="$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))))' "$OUT/$section.json")"
    echo "$section: $rows rows" | tee -a "$OUT/manifest.txt"
    rm -f "$OUT/$section.err"
  else
    echo "$section: query failed (see $section.err)" | tee -a "$OUT/manifest.txt"
    status=1
  fi
done

cat <<EOF

Evidence written to $OUT (private; do not commit, contains pseudonymous doc_ref values).
Read next:
  aborted_review_saves.json  -> Started/LastSeen/Heartbeats/LastPhase/Pid per aborted save
  worker_lifecycle.json      -> WORKER TIMEOUT + faulthandler stack, or SIGKILL/out of memory
  worker_pids.json           -> replacement worker after each aborted save
Then check whether each save was committed (App Service SSH):
  python /home/site/wwwroot/scripts/check_review_save_outcome.py --doc-ref <DocRef> --start <Started> --seconds 60
A zero-row section is missing evidence, not proof: check diagnostic settings and ingestion.
EOF
exit "$status"
