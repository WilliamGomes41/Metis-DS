"""Atomically replaced published projection for Product API serving.

The API MUST read only this derived document. Publish, withdraw and supersede
MUST replace it in one atomic write. Reconstructing live governance per query
MUST NOT produce supported.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_replace_projection(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


class PublishedProjection:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def records(self) -> list[dict[str, Any]]:
        return _read_jsonl(self.path)

    def replace(self, records: Iterable[dict[str, Any]]) -> None:
        atomic_replace_projection(self.path, records)

    def withdraw(self, object_ids: Iterable[str]) -> None:
        drop = set(object_ids)
        kept = [
            row
            for row in self.records()
            if (row.get("metadata") or {}).get("object_id") not in drop
        ]
        self.replace(kept)

    def supersede(self, old_object_id: str, new_record: dict[str, Any]) -> None:
        kept = [
            row
            for row in self.records()
            if (row.get("metadata") or {}).get("object_id") != old_object_id
        ]
        kept.append(new_record)
        self.replace(kept)
