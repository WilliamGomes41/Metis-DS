#!/usr/bin/env bash
# Run from the workspace (editor) container: hands a job to the isolated runner
# and streams its result. Usage: scripts/sandbox_test.sh [check|probe|test|test --local|scan]
set -eu
JOBS="$(cd "$(dirname "$0")/.." && pwd)/output/runtime/sandbox-runner"
cmd="${*:-test}"
[ -e "$JOBS/ready" ] || { echo "runner not ready ($JOBS/ready missing)"; exit 3; }
id="$(date +%s)-$$"
printf '%s' "$cmd" > "$JOBS/$id.tmp" && mv "$JOBS/$id.tmp" "$JOBS/$id.request"
for _ in $(seq 1 3600); do
  [ -e "$JOBS/$id.exit" ] && break; sleep 1
done
[ -e "$JOBS/$id.exit" ] || { echo "timeout waiting for runner"; exit 4; }
cat "$JOBS/$id.log"; exit "$(cat "$JOBS/$id.exit")"
