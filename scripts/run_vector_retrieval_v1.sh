#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python3 src/evaluate_vector_retrieval.py \
  --records output/v2/retrieval/baseline_fixture_records.jsonl \
  --golden data/golden/fractuurpreventie_page15_golden_v0.1.json \
  --config config/vector_retrieval_v1.json \
  --lexical-report output/v2/retrieval/baseline_fixture_evaluation.json \
  --report output/v2/retrieval/vector_fixture_evaluation.json
