#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
./scripts/run_hybrid_retrieval_v1.sh
PYTHONPATH=. pytest -q
