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
exec python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.console_asgi:app --bind "0.0.0.0:${PORT:-8000}"
