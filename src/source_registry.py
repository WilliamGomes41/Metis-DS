#!/usr/bin/env python3
"""Create and verify immutable source-binary registry records."""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from src.integrity_kernel import verify_source_binary


def register_source(source_id: str, binary_path: Path, source_url: str, version: str | None = None) -> dict[str, Any]:
    check = verify_source_binary(binary_path)
    if not check["verified"]:
        raise ValueError(check.get("error", "source_verification_failed"))
    return {
        "source_id": source_id,
        "source_url": source_url,
        "version": version,
        "checksum_algorithm": "sha256",
        "source_checksum": check["sha256"],
        "binary_path": check["path"],
        "size_bytes": check["size_bytes"],
        "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "integrity_status": "verified",
    }


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--source-id',required=True); ap.add_argument('--binary',type=Path,required=True)
    ap.add_argument('--source-url',required=True); ap.add_argument('--version'); ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args(); rec=register_source(a.source_id,a.binary,a.source_url,a.version)
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(rec,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
