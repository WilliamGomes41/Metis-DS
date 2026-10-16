#!/usr/bin/env bash
# Runs inside the isolated `runner` container. Reads requests from the control
# volume (read-only here), executes only whitelisted security_sandbox.py
# subcommands and writes results ONLY to its artifact dir. The control container
# copies them into the control volume; the verdict never comes from here (#653 T5).
set -u
CTL=/sandbox-control/jobs
ART=/workspaces/metis/output/runtime/sandbox-artifacts
DIAG=/workspaces/metis/output/runtime/sandbox-runner-diag/startup.log
{ date -u +%FT%TZ; echo "sandbox-runner: uid=$(id -u) gid=$(id -g) cwd=$(pwd)"
  ls -ld /workspaces/metis /workspaces/metis/output/runtime/* /sandbox-control 2>&1; } | tee "$DIAG" 2>/dev/null || true
date +%s > "$ART/heartbeat" || { echo "sandbox-runner: FATAL cannot write $ART/heartbeat" | tee -a "$DIAG" >&2; exit 1; }
# Heartbeat keeps running during long jobs; control drops `ready` when it goes stale.
( while true; do date +%s > "$ART/heartbeat.tmp" && mv "$ART/heartbeat.tmp" "$ART/heartbeat"; sleep 3; done ) &
echo "sandbox-runner: ready"
while true; do
  for req in "$CTL"/*.request; do
    [ -e "$req" ] || continue
    id=$(basename "$req" .request)
    [ -e "$ART/$id.rc" ] && continue
    cmd=$(cat "$req")
    case "$cmd" in
      check|scan|test|"test --local"|probe|rt) ;;
      *) echo "rejected: $cmd" > "$ART/$id.log"; echo 2 > "$ART/$id.rc"; continue ;;
    esac
    if [ "$cmd" = probe ]; then
      bash /workspaces/metis/scripts/sandbox_probe.sh > "$ART/$id.log" 2>&1
    else
      # rt included: security_sandbox.py runs assert_isolated_network() in this job before pytest.
      # shellcheck disable=SC2086
      python scripts/security_sandbox.py $cmd > "$ART/$id.log" 2>&1
    fi
    echo $? > "$ART/$id.rc"
  done
  sleep 1
done
