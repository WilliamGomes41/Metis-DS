#!/usr/bin/env bash
# Runs inside the isolated `runner` container. Polls the shared job directory
# and executes only whitelisted security_sandbox.py subcommands.
set -u
JOBS=/workspaces/metis/output/runtime/sandbox-runner
DIAG=/workspaces/metis/output/runtime/sandbox-runner-diag/startup.log
{ date -u +%FT%TZ; echo "sandbox-runner: uid=$(id -u) gid=$(id -g) cwd=$(pwd)"
  ls -ld /workspaces/metis /workspaces/metis/output/runtime/* 2>&1; } | tee "$DIAG" 2>/dev/null || true
mkdir -p "$JOBS" || { echo "sandbox-runner: FATAL cannot create $JOBS" | tee -a "$DIAG" >&2; exit 1; }
echo "runner ready" > "$JOBS/ready" || { echo "sandbox-runner: FATAL cannot write $JOBS/ready" | tee -a "$DIAG" >&2; exit 1; }
echo "sandbox-runner: ready"
while true; do
  for req in "$JOBS"/*.request; do
    [ -e "$req" ] || continue
    id=$(basename "$req" .request)
    cmd=$(cat "$req"); rm -f "$req"
    case "$cmd" in
      check|scan|test|"test --local"|probe|rt) ;;
      *) echo "rejected: $cmd" > "$JOBS/$id.log"; echo 2 > "$JOBS/$id.exit"; continue ;;
    esac
    if [ "$cmd" = probe ]; then
      bash /workspaces/metis/scripts/sandbox_probe.sh > "$JOBS/$id.log" 2>&1
    else
      # rt included: security_sandbox.py runs assert_isolated_network() in this job before pytest.
      # shellcheck disable=SC2086
      python scripts/security_sandbox.py $cmd > "$JOBS/$id.log" 2>&1
    fi
    echo $? > "$JOBS/$id.exit"
  done
  sleep 1
done
