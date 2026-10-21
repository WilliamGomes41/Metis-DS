#!/usr/bin/env bash
# Compatibility entry point for managed environments configured by D6a prep.
# Install only; tests start their own disposable PostgreSQL in the agent phase.
set -euo pipefail
exec bash "$(dirname "$0")/setup_test_environment.sh" "$@"
