#!/bin/bash
set -euo pipefail
# Internal operations console host for Azure App Service. Not a public website.
exec python -m gunicorn -w 1 -k uvicorn.workers.UvicornWorker src.console_asgi:app --bind "0.0.0.0:${PORT:-8000}"
