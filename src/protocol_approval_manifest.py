#!/usr/bin/env python3
"""Build an immutable approval manifest for an approved protocol document."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from src.integrity_kernel import sha256_file


COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(
    r"^\\*\\*(?:Protocol version|Protocol delta version):\\*\\*\\s+"
    r"(?P<version>\\d+\\.\\d+\\.\\d+)\\s*$",
    re.MULTILINE,
)
DATE_RE = re.compile(
    r"^\\*\\*(?:Approval date|Date):\\*\\*\\s+"
    r"(?P<date>\\d{4}-\\d{2}-\\d{2})\\s*$",
    re.MULTILINE,
)


def build_manifest(protocol: Path, commit_sha: str) -> dict[str, object]:
    if not protocol.exists() or not protocol.is_file():
        raise ValueError("protocol_file_missing")
    if not COMMIT_RE.fullmatch(commit_sha):
        raise ValueError("commit_sha_invalid")
    text = protocol.read_text(encoding="utf-8")
    if "**Status:** Approved for project use" not in text:
        raise ValueError("protocol_not_approved")
    version_match = VERSION_RE.search(text)
    if version_match is None:
        raise ValueError("protocol_version_missing")
    date_match = DATE_RE.search(text)
    if date_match is None:
        raise ValueError("approval_date_missing")
    return {
        "manifest_version": "1.0",
        "protocol_version": version_match.group("version"),
        "protocol_path": protocol.as_posix(),
        "protocol_sha256": sha256_file(protocol),
        "repository": "WilliamGomes41/VENVN-DS",
        "default_branch": "main",
        "commit_sha": commit_sha,
        "approval_date": date_match.group("date"),
        "approval_authority": "project_owner",
        "branch_protection_status": "temporary_procedural_control",
        "conformance_effect": "does_not_override_gate_status",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.protocol, args.commit_sha)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "protocol_sha256": manifest["protocol_sha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
