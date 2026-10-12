#!/usr/bin/env bash
# Runs inside the isolated `runner` container. Polls the shared job directory
# and executes only whitelisted security_sandbox.py subcommands.
set -u
JOBS=/workspaces/metis/output/runtime/sandbox-runner
mkdir -p "$JOBS"
echo "runner ready" > "$JOBS/ready"
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
    elif [ "$cmd" = rt ]; then
      # Red-team tests dropped by the workspace into the job dir (repo stays read-only).
      # Same env allowlist as security_sandbox.py (no inherited runner env).
      RT="$JOBS/rt" python -c 'import os,subprocess,sys; sys.path.insert(0,"scripts"); import security_sandbox as s; rt=os.environ["RT"]; env=s.sandbox_environment(postgres=True); env["PYTEST_ADDOPTS"]="-p no:cacheprovider"; sys.exit(subprocess.call([sys.executable,"-m","pytest","-q","--rootdir",rt,rt],env=env))' > "$JOBS/$id.log" 2>&1
    else
      # shellcheck disable=SC2086
      python scripts/security_sandbox.py $cmd > "$JOBS/$id.log" 2>&1
    fi
    echo $? > "$JOBS/$id.exit"
  done
  sleep 1
done
