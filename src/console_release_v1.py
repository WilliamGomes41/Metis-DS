"""Read-only product release projection from the running package, never main.

Release metadata is build configuration, not document/publication domain state.
The commit remains the technical evidence identity; a product version never
replaces it in stored diagnostics or historical reports.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BUILD_FILE = "config/console_build.json"
RELEASE_FILE = "config/console_release.json"


def release_definition(root: Path | None = None) -> dict:
    root = root or ROOT
    data = json.loads((root / RELEASE_FILE).read_text(encoding="utf-8"))
    if (not isinstance(data, dict)
            or type(data.get("generation")) is not int or data["generation"] < 1
            or type(data.get("release")) is not int or data["release"] < 0
            or not isinstance(data.get("changes"), list) or not data["changes"]
            or any(not isinstance(item, str) or not item.strip() for item in data["changes"])):
        raise ValueError("console_release_invalid")
    return data


def console_release(root: Path | None = None) -> dict:
    """Missing/inconsistent build evidence must not invent a deployed version."""
    root = root or ROOT
    try:
        definition = release_definition(root)
    except (OSError, ValueError, TypeError):
        return {"version": None, "label": "Versie niet beschikbaar", "changes": []}
    result = {"version": None, "label": "Ontwikkelversie", "changes": definition["changes"]}
    try:
        build = json.loads((root / BUILD_FILE).read_text(encoding="utf-8"))
        marker = (root / "config/deployed_commit.txt").read_text(encoding="ascii").strip()
        prefix = f'{definition["generation"]}.{definition["release"]}.'
        if (not isinstance(build, dict)
                or not isinstance(build.get("version"), str)
                or not re.fullmatch(re.escape(prefix) + r"[1-9][0-9]*", build["version"])
                or not re.fullmatch(r"[0-9a-f]{40}", marker)
                or build.get("commit") != marker):
            raise ValueError("console_build_invalid")
        return {**result, "version": build["version"], "label": f'Versie {build["version"]}'}
    except (OSError, ValueError, TypeError):
        if (root / BUILD_FILE).exists() or (root / "config/deployed_commit.txt").exists():
            result["label"] = "Versie niet beschikbaar"
        return result
