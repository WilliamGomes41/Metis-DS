#!/bin/bash
set -euo pipefail
# Internal operations console host for Azure App Service. Not a public website.
# Vendored dependencies live in .python_packages (wave C ZIP). Runtime data
# stays under CONSOLE_DATA_ROOT / /home/data — never in this wwwroot tree.
#
# Supported topology: one worker by default, or two workers on exactly one
# instance with Azure Blob as source authority. PostgreSQL is always the workflow
# and canonical authority (D6b). Writes stay sequential through the
# process-shared store lock.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [ -d "${ROOT}/.python_packages" ]; then
  export PYTHONPATH="${ROOT}/.python_packages:${PYTHONPATH}"
fi
export CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"

# Resolve one authoritative worker count and reject conflicting declarations,
# unsupported counts, missing durable stores, or more than one instance.
WORKERS="$(python -c "from src.topology_bound_v1 import assert_supported_topology; print(assert_supported_topology()['workers'])")"

# Production authority is explicit and fail-closed. PostgreSQL owns all workflow
# and published state; the application refuses to start without it. Azure Blob
# owns the exact immutable source bytes. Startup must never silently degrade.
if [ "${CONSOLE_IMMUTABLE_SOURCE_STORE:-}" != "azure" ]; then
  echo "azure_blob_source_store_required_in_azure: CONSOLE_IMMUTABLE_SOURCE_STORE must be azure" >&2
  exit 1
fi

exec python -m gunicorn -w "${WORKERS}" -k uvicorn.workers.UvicornWorker src.console_asgi:app --bind "0.0.0.0:${PORT:-8000}"
