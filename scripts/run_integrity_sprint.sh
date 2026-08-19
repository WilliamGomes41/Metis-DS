#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python -m compileall -q src
python -m src.semantic_transform_v21 data/semantic_page15_spec.v2.1.json \
  --source-manifest data/source_manifest.v2.json \
  --schema schemas/knowledge_object.schema.v1.1.json \
  --root . --out "$TMP/a.jsonl" --report "$TMP/a-report.json" >/dev/null
python -m src.semantic_transform_v21 data/semantic_page15_spec.v2.1.json \
  --source-manifest data/source_manifest.v2.json \
  --schema schemas/knowledge_object.schema.v1.1.json \
  --root . --out "$TMP/b.jsonl" --report "$TMP/b-report.json" >/dev/null
cmp "$TMP/a.jsonl" "$TMP/b.jsonl"
pytest -q
python -m src.cli audit-current --report output/v2/integrity_sprint/cli_audit_current.json
