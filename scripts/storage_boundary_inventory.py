#!/usr/bin/env python3
"""Read-only inventory of configured local Metis content surfaces.

Counts filesystem entries without opening content or printing names/paths.
This is a finding tool, never a compliance certificate: per-command archives,
temporary extraction files, telemetry and external destinations are not covered.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Mapping


def _entry_count(root: Path) -> int:
    if root.is_symlink():
        return 1
    if not root.exists():
        return 0
    if root.is_file():
        return 1
    if not root.is_dir():
        return 1

    count = 0
    pending = [root]
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                if entry.is_symlink():
                    count += 1  # Do not follow links out of the configured surface.
                elif entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                else:
                    count += 1
    return count


def inventory(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = os.environ if environ is None else environ
    data_root = Path(env.get("CONSOLE_DATA_ROOT") or "/home/data/metis-console")
    surfaces = (
        ("local_source_store", Path(env.get("CONSOLE_SOURCE_STORE") or data_root / "sources" / "private")),
        ("local_runtime", Path(env.get("CONSOLE_RUNTIME") or data_root / "output" / "runtime" / "operations-console")),
    )
    observations = []
    for category, path in surfaces:
        try:
            observations.append({"category": category, "entries": _entry_count(path), "scan": "ok"})
        except OSError:
            observations.append({"category": category, "entries": None, "scan": "failed"})

    return {
        "version": 1,
        "status": "FINDINGS" if any(item["scan"] != "ok" or item["entries"] for item in observations) else "INCOMPLETE",
        "surfaces": observations,
        "unverified": [
            "per_command_backup_destination",
            "temporary_extraction_files",
            "other_local_paths",
            "telemetry_destination",
            "browser_and_client_storage",
            "azure_resource_identity_and_retention",
        ],
        "production_compliance_proven": False,
    }


def main() -> int:
    report = inventory()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 2 if report["status"] == "FINDINGS" else 0


if __name__ == "__main__":
    sys.exit(main())
