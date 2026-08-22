#!/usr/bin/env python3
"""Create or update a verified canonical-source registry from exact source bytes."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.integrity_kernel import sha256_file


def build_record(
    binary_path: Path,
    *,
    source_id: str,
    title: str,
    source_url: str,
    source_version: str,
    content_type: str,
    acquisition_method: str,
    acquired_at: str,
    immutable_storage_locator: str | None = None,
) -> dict[str, Any]:
    if not binary_path.exists() or not binary_path.is_file():
        raise ValueError("source_binary_missing")
    if not binary_path.is_absolute():
        raise ValueError("binary_path_must_be_absolute")
    if not source_id.strip():
        raise ValueError("source_id_missing")
    if not acquired_at.endswith("Z"):
        raise ValueError("acquired_at_must_be_utc")
    try:
        datetime.fromisoformat(acquired_at.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ValueError("acquired_at_invalid") from exc

    durably_stored = bool(immutable_storage_locator and immutable_storage_locator.strip())
    return {
        "source_id": source_id,
        "title": title,
        "source_url": source_url,
        "source_version": source_version,
        "source_type": "binary",
        "filename": binary_path.name,
        "content_type": content_type,
        "size_bytes": binary_path.stat().st_size,
        "checksum_algorithm": "sha256",
        "source_checksum": sha256_file(binary_path),
        "integrity_status": "verified" if durably_stored else "verified_local",
        "binary_path": str(binary_path.resolve()),
        "immutable_storage_locator": immutable_storage_locator if durably_stored else None,
        "acquisition_method": acquisition_method,
        "acquired_at": acquired_at,
        "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "publication_eligibility": (
            "eligible_for_transform_and_review"
            if durably_stored
            else "blocked_pending_immutable_storage"
        ),
    }


def update_registry(registry: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    rows = list(registry.get("sources", []))
    existing = [row for row in rows if row.get("source_id") == record["source_id"]]
    if existing and existing[0].get("source_checksum") != record["source_checksum"]:
        raise ValueError("source_id_checksum_conflict_requires_new_source_version")
    rows = [row for row in rows if row.get("source_id") != record["source_id"]]
    rows.append(record)
    rows.sort(key=lambda row: row["source_id"])
    return {"registry_version": "1.1", "sources": rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--source-version", required=True)
    parser.add_argument("--content-type", required=True)
    parser.add_argument("--acquisition-method", required=True)
    parser.add_argument("--acquired-at", required=True)
    parser.add_argument("--immutable-storage-locator")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    record = build_record(
        args.binary.resolve(),
        source_id=args.source_id,
        title=args.title,
        source_url=args.source_url,
        source_version=args.source_version,
        content_type=args.content_type,
        acquisition_method=args.acquisition_method,
        acquired_at=args.acquired_at,
        immutable_storage_locator=args.immutable_storage_locator,
    )
    updated = update_registry(registry, record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "source_id": record["source_id"], "sha256": record["source_checksum"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
