#!/usr/bin/env python3
"""Check exported Azure app settings before a release, without touching Azure.

Input is the JSON of `az webapp config appsettings list` (a list of
{"name", "value"} rows), from a file or stdin. Read-only and offline: no Azure,
database or network call. Output names fixed codes and the non-secret mode,
extractor and model; it never prints a setting value such as the API key.

Exit codes: 0 = ready; 2 = at least one blocking finding; 1 = input unreadable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV, load_llm_provider_config
from src.passage_formation_policy_v1 import PassageFormationPolicyError, resolve_passage_formation_strategy
from src.source_bound_fields_v2 import MODE as DEFAULT_FORMATION_MODE

FORMATION_MODE_ENV = "METIS_PASSAGE_FORMATION_MODE"
RETIRED_FORMATION_MODE = "deterministic-v1"
PDF_EXTRACTOR_ENV = "METIS_PDF_EXTRACTOR"
PDF_EXTRACTORS = ("docling", "legacy-comparison")
SOURCE_STORE_ENV = "CONSOLE_IMMUTABLE_SOURCE_STORE"


def settings_map(rows: Any) -> dict[str, str]:
    if not isinstance(rows, list):
        raise ValueError("release_settings_not_a_list")
    settings = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            raise ValueError("release_settings_row_invalid")
        settings[row["name"]] = "" if row.get("value") is None else str(row["value"])
    return settings


def assess(settings: dict[str, str]) -> dict[str, Any]:
    blocking = []
    # Same reading as the runtime: empty means the default semantic contract.
    mode = settings.get(FORMATION_MODE_ENV, "").strip() or DEFAULT_FORMATION_MODE
    try:
        resolve_passage_formation_strategy(deployment_mode=mode)
    except PassageFormationPolicyError as error:
        blocking.append("passage_formation_mode_retired" if mode == RETIRED_FORMATION_MODE else error.code)
        mode = mode if mode == RETIRED_FORMATION_MODE else "invalid"
    provider = load_llm_provider_config(settings)
    if not provider.api_key:
        blocking.append("llm_api_key_missing")
    if not provider.model:
        blocking.append("llm_model_missing")
    extractor = settings.get(PDF_EXTRACTOR_ENV, "legacy-comparison")
    if extractor not in PDF_EXTRACTORS:
        blocking.append("docling_route_invalid")
    if settings.get(SOURCE_STORE_ENV, "") != "azure":
        blocking.append("azure_blob_source_store_required_in_azure")
    return {
        "preflight": "release_settings",
        "status": "blocked" if blocking else "ready",
        "blocking": blocking,
        "passage_formation_mode": mode,
        "passage_formation_mode_explicit": bool(settings.get(FORMATION_MODE_ENV, "").strip()),
        "pdf_extractor": extractor if extractor in PDF_EXTRACTORS else "invalid",
        LLM_MODEL_ENV: provider.model or None,
        LLM_API_KEY_ENV: "present" if provider.api_key else "missing",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings-file", type=Path, help="appsettings JSON; stdin when omitted")
    args = parser.parse_args(argv)
    try:
        text = args.settings_file.read_text(encoding="utf-8") if args.settings_file else sys.stdin.read()
        settings = settings_map(json.loads(text))
    except (OSError, ValueError, UnicodeError):
        print(json.dumps({"preflight": "release_settings", "status": "unreadable"}))
        return 1
    result = assess(settings)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
