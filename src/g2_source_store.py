"""G2 canonical source-store coordinates.

Records the V&VN Azure Blob store. Does not upload bytes, does not
store keys, and does not convert G2 to PASS.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "g2_source_store.v1.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
LOCATOR_RE = re.compile(
    r"^azure://(?P<account>[a-z0-9]+)/(?P<container>[a-z0-9-]+)"
    r"/(?P<sha256>[0-9a-f]{64})/(?P<filename>[A-Za-z0-9._-]+)$"
)


def load_g2_store() -> dict[str, Any]:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def g2_gate_status() -> str:
    store = load_g2_store()
    status = str(store.get("g2_status") or "BLOCKED")
    return status if status == "BLOCKED" else "BLOCKED"


def build_g2_locator(*, sha256: str, filename: str) -> str:
    digest = sha256.strip().lower()
    raw = filename.replace("\\", "/")
    name = Path(raw).name
    if not SHA256_RE.fullmatch(digest):
        raise ValueError("g2_locator_checksum_invalid")
    if raw != name or not FILENAME_RE.fullmatch(name):
        raise ValueError("g2_locator_filename_invalid")
    store = load_g2_store()
    return f"azure://{store['storage_account']}/{store['container']}/{digest}/{name}"


def parse_g2_locator(locator: str | None) -> dict[str, str] | None:
    if not locator or not str(locator).strip():
        return None
    match = LOCATOR_RE.fullmatch(str(locator).strip())
    if match is None:
        return None
    parts = match.groupdict()
    store = load_g2_store()
    if parts["account"] != store["storage_account"]:
        return None
    if parts["container"] != store["container"]:
        return None
    return parts


def is_g2_locator(locator: str | None) -> bool:
    return parse_g2_locator(locator) is not None
