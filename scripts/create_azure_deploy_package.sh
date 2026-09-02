#!/usr/bin/env bash
# Create a fully deployable Azure ZIP with vendored Python dependencies.
# git-archive-only is not enough (Protocol v2.22 wave C).
# MUST NOT include runtime data. MUST NOT overwrite /home/data.
set -euo pipefail

output_path="${1:?usage: bash scripts/create_azure_deploy_package.sh <output-path>}"

case "${output_path}" in
  /home/data|/*/home/data/*)
    echo "must_not_write_home_data" >&2
    exit 2
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
if [ -n "${PYTHON:-}" ]; then
  PY="${PYTHON}"
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  PY=python3
fi
exec "${PY}" -c 'import sys; from pathlib import Path; from src.azure_deploy_package import write_deploy_zip; write_deploy_zip(Path(sys.argv[1]))' "${output_path}"
