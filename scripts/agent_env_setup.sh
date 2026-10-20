#!/usr/bin/env bash
# One-time setup for cloud coding agents (Codex setup script, Cursor cloud
# agent "install"). Installs PostgreSQL 16 binaries and the Python test
# dependencies, then proves a disposable test server can start.
# The server is NOT left running: tests start it via scripts/test_postgres.sh
# (tests/conftest.py does that automatically), so it also works when a
# process from the setup phase does not survive into the agent phase.
set -euo pipefail
cd "$(dirname "$0")/.."

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || { echo "agent_env_setup: need root or sudo to install PostgreSQL" >&2; exit 1; }
  SUDO="sudo"
fi

if ! scripts/test_postgres.sh >/dev/null 2>&1 && ! ls /usr/lib/postgresql/*/bin/initdb >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  $SUDO apt-get update -q
  if apt-cache show postgresql-16 >/dev/null 2>&1; then
    $SUDO apt-get install -y -q postgresql-16 postgresql-client-16
  else
    $SUDO apt-get install -y -q postgresql postgresql-client
  fi
fi

# System Python on Ubuntu 24.04 is "externally managed"; agent sandboxes are disposable.
export PIP_BREAK_SYSTEM_PACKAGES=1
python3 -m pip install -q -r requirements-dev.lock
python3 -m pip install -q --no-deps --no-build-isolation -e .

# Prove the test server can start here, then stop it again.
scripts/test_postgres.sh >/dev/null
scripts/test_postgres.sh stop
echo "agent_env_setup: PostgreSQL test server and Python test dependencies ready"
