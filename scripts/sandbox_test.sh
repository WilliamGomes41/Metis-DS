#!/usr/bin/env bash
# Run from the workspace (editor) container: drops a request for the control
# container and reads the verdict ONLY from the read-only control volume.
# Usage: scripts/sandbox_test.sh [check|probe|test|test --local|scan|rt]
#   (rt = pytest on output/runtime/sandbox-requests/rt/, copied by control)
set -eu
REQ="$(cd "$(dirname "$0")/.." && pwd)/output/runtime/sandbox-requests"
CTL=/sandbox-control
cmd="${*:-test}"
[ -e "$CTL/ready" ] || { echo "runner not ready ($CTL/ready missing or runner heartbeat stale)"; exit 3; }
id="$(date +%s)-$$"
printf '%s' "$cmd" > "$REQ/$id.tmp" && mv "$REQ/$id.tmp" "$REQ/$id.request"
for _ in $(seq 1 3600); do
  [ -e "$CTL/jobs/$id.exit" ] && break; sleep 1
done
[ -e "$CTL/jobs/$id.exit" ] || { echo "timeout waiting for runner"; exit 4; }
cat "$CTL/jobs/$id.log"
code="$(tr -d '[:space:]' < "$CTL/jobs/$id.exit")"
case "$code" in ''|*[!0-9]*) echo "invalid verdict; counted as failed"; exit 1 ;; esac
exit "$code"
