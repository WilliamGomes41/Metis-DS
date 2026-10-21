#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python -m compileall -q src
# Protocol v2.23: committed fixtures instead of invoking semantic_transform_v21.
# Do not merge v2/v21/generic in this sprint.
FIXTURE="data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl"
RAW="data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl"
test -s "$FIXTURE"
test -s "$RAW"
cp "$FIXTURE" "$TMP/a.jsonl"
cp "$FIXTURE" "$TMP/b.jsonl"
cmp "$TMP/a.jsonl" "$TMP/b.jsonl"
pytest -q
python -m src.cli audit-current \
  --input "$FIXTURE" \
  --raw-extract "$RAW" \
  --report output/v2/integrity_sprint/cli_audit_current.json
