#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python "$ROOT/src/evaluate_hybrid_retrieval.py" \
  --records "$ROOT/output/v2/retrieval/baseline_fixture_records.jsonl" \
  --golden "$ROOT/data/golden/fractuurpreventie_page15_golden_v0.1.json" \
  --hybrid-config "$ROOT/config/hybrid_retrieval_v1.json" \
  --lexical-config "$ROOT/config/retrieval_baseline_v1.json" \
  --vector-config "$ROOT/config/vector_retrieval_v1.json" \
  --lexical-report "$ROOT/output/v2/retrieval/baseline_fixture_evaluation.json" \
  --vector-report "$ROOT/output/v2/retrieval/vector_fixture_evaluation.json" \
  --report "$ROOT/output/v2/retrieval/hybrid_fixture_evaluation.json"
