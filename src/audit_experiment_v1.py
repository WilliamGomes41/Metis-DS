"""Experiment-specific evidence for the Audit room.

This module stores frozen experiment datasets only. It contains no model/provider
integration and has no write path into canonical knowledge or publication state.
"""
from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.operations_console_v1 import ConsoleError, _atomic_write


_AUDIT_ID_RE = re.compile(r"^audit-[0-9a-f]{16}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_FREEZE_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _dataset_path(runtime: Path, audit_id: str) -> Path:
    safe_audit_id = str(audit_id or "").strip()
    if _AUDIT_ID_RE.fullmatch(safe_audit_id) is None:
        raise ConsoleError("invalid_audit_id")
    return Path(runtime) / "audit_experiments" / safe_audit_id / "dataset.json"


def _normalize_item(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ConsoleError("experiment_dataset_item_invalid")
    item_id = str(item.get("item_id") or "").strip()
    snapshot_id = str(item.get("snapshot_id") or "").strip()
    source_hash = str(item.get("source_hash") or "").strip().lower()
    source_text = item.get("source_text")
    source_locator = item.get("source_locator")
    if not item_id or not snapshot_id:
        raise ConsoleError("experiment_dataset_item_invalid")
    if _SHA256_RE.fullmatch(source_hash) is None:
        raise ConsoleError("experiment_dataset_source_hash_invalid")
    if not isinstance(source_text, str) or not source_text:
        raise ConsoleError("experiment_dataset_source_text_invalid")
    if not (
        (isinstance(source_locator, str) and bool(source_locator.strip()))
        or (isinstance(source_locator, dict) and bool(source_locator))
    ):
        raise ConsoleError("experiment_dataset_locator_invalid")
    return {
        "item_id": item_id,
        "snapshot_id": snapshot_id,
        "source_hash": source_hash,
        "source_locator": deepcopy(source_locator),
        "source_text": source_text,
    }


def freeze_dataset(
    runtime: Path,
    *,
    audit_id: str,
    baseline_commit: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Freeze one experiment dataset once; never silently replace it."""

    safe_commit = str(baseline_commit or "").strip().lower()
    if _COMMIT_RE.fullmatch(safe_commit) is None:
        raise ConsoleError("experiment_baseline_commit_invalid")
    if not isinstance(items, list) or not items:
        raise ConsoleError("experiment_dataset_empty")

    normalized = [_normalize_item(item) for item in items]
    item_ids = [item["item_id"] for item in normalized]
    if len(item_ids) != len(set(item_ids)):
        raise ConsoleError("experiment_dataset_duplicate_item")

    record = {
        "schema_version": 1,
        "audit_id": str(audit_id).strip(),
        "frozen_at": _now(),
        "baseline_commit": safe_commit,
        "items": normalized,
    }
    path = _dataset_path(runtime, audit_id)
    with _FREEZE_LOCK:
        if path.exists():
            raise ConsoleError("experiment_dataset_already_frozen")
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, record)
    return deepcopy(record)


def load_frozen_dataset(runtime: Path, audit_id: str) -> dict[str, Any] | None:
    path = _dataset_path(runtime, audit_id)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConsoleError("experiment_dataset_corrupt") from exc
    if not isinstance(record, dict) or record.get("audit_id") != str(audit_id).strip():
        raise ConsoleError("experiment_dataset_corrupt")
    if _COMMIT_RE.fullmatch(str(record.get("baseline_commit") or "")) is None:
        raise ConsoleError("experiment_dataset_corrupt")
    raw_items = record.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ConsoleError("experiment_dataset_corrupt")
    try:
        normalized = [_normalize_item(item) for item in raw_items]
    except ConsoleError as exc:
        raise ConsoleError("experiment_dataset_corrupt") from exc
    if normalized != raw_items:
        raise ConsoleError("experiment_dataset_corrupt")
    return deepcopy(record)
