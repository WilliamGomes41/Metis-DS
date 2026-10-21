#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RECORDS="${1:-$ROOT/output/v2/retrieval/real_current_retrieval_records.jsonl}"
REPORT="${2:-$ROOT/output/v2/retrieval/lexical_baseline_evaluation.json}"

cd "$ROOT"
python -m src.evaluation.evaluate_retrieval_baseline \
  --records "$RECORDS" \
  --golden "$ROOT/data/golden/fractuurpreventie_page15_golden_v0.1.json" \
  --config "$ROOT/config/retrieval_baseline_v1.json" \
  --report "$REPORT"
