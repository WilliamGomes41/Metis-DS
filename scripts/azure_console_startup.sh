#!/bin/bash
set -euo pipefail
# Internal operations console host for Azure App Service. Not a public website.
# Vendored dependencies live in .python_packages (wave C ZIP). Runtime data
# stays under CONSOLE_DATA_ROOT / /home/data — never in this wwwroot tree.
#
# Supported topology (Post-#120 remediation 5): one Gunicorn worker /
# one instance / sequential writes. Accidental multi-writer scale is
# out of bound (CONFIGURE). EXTEND for multiple writers is later.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [ -d "${ROOT}/.python_packages" ]; then
  export PYTHONPATH="${ROOT}/.python_packages:${PYTHONPATH}"
fi
export CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"

# Reject an unsupported writer topology first. Authority configuration is a
# separate production precondition and must not mask topology violations.
if [ -n "${WEB_CONCURRENCY:-}" ] && [ "${WEB_CONCURRENCY}" != "1" ]; then
  echo "topology_bound: WEB_CONCURRENCY=${WEB_CONCURRENCY} is out of bound (supported: 1 worker)" >&2
  exit 1
fi
if [ -n "${CONSOLE_GUNICORN_WORKERS:-}" ] && [ "${CONSOLE_GUNICORN_WORKERS}" != "1" ]; then
  echo "topology_bound: CONSOLE_GUNICORN_WORKERS=${CONSOLE_GUNICORN_WORKERS} is out of bound (supported: 1 worker)" >&2
  exit 1
fi
if [ -n "${CONSOLE_INSTANCE_COUNT:-}" ] && [ "${CONSOLE_INSTANCE_COUNT}" != "1" ]; then
  echo "topology_bound: CONSOLE_INSTANCE_COUNT=${CONSOLE_INSTANCE_COUNT} is out of bound (supported: 1 instance)" >&2
  exit 1
fi
python -c "from src.topology_bound_v1 import assert_supported_topology; assert_supported_topology()"

# Production authority is explicit and fail-closed. /home/data is work state;
# PostgreSQL owns published object/release metadata and Azure Blob owns the exact
# immutable source bytes. App startup must never silently degrade either one.
if [ "${METIS_CANONICAL_STORE:-}" != "postgres" ]; then
  echo "canonical_store_required_in_azure: METIS_CANONICAL_STORE must be postgres" >&2
  exit 1
fi
if [ "${CONSOLE_IMMUTABLE_SOURCE_STORE:-}" != "azure" ]; then
  echo "azure_blob_source_store_required_in_azure: CONSOLE_IMMUTABLE_SOURCE_STORE must be azure" >&2
  exit 1
fi

exec python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.console_asgi:app --bind "0.0.0.0:${PORT:-8000}"
