#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m compileall -q src
pytest -q
python -m src.cli audit-current --report output/v2/integrity_sprint/cli_audit_current.json
