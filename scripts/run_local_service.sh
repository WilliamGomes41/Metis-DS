#!/usr/bin/env bash
set -euo pipefail
MODE="${VVN_SERVICE_MODE:-real}"
HOST="${VVN_SERVICE_HOST:-127.0.0.1}"
PORT="${VVN_SERVICE_PORT:-8000}"
exec python -m uvicorn src.service_app:app --host "$HOST" --port "$PORT"
