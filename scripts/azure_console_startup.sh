#!/bin/bash
set -euo pipefail
# Internal operations console host for Azure App Service. Not a public website.
# Vendored dependencies live in .python_packages (wave C ZIP). Runtime data
# stays under CONSOLE_DATA_ROOT / /home/data — never in this wwwroot tree.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -d "${ROOT}/.python_packages" ]; then
  export PYTHONPATH="${ROOT}/.python_packages${PYTHONPATH:+:${PYTHONPATH}}"
fi
export CONSOLE_DATA_ROOT="${CONSOLE_DATA_ROOT:-/home/data/metis-console}"
exec python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.console_asgi:app --bind "0.0.0.0:${PORT:-8000}"
