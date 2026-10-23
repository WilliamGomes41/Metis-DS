#!/usr/bin/env python3
"""Check or reproduce the approved plugin skill snapshot, without networking."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


def local_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path: {relative}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Path escapes checkout: {relative}")
    return target


def claude_adapter(relative: str, content: bytes) -> bytes:
    # Approved upstream metadata is single-line YAML; no new skill body is made.
    header = content.decode("utf-8").split("---", 2)[1]
    fields = [line for line in header.splitlines()
              if line.startswith(("name:", "description:"))]
    if len(fields) != 2:
        raise ValueError(f"Expected name and description in {relative}")
    # Keep upstream opt-in skills unloaded until a user names them.
    fields += [line for line in header.splitlines()
               if line.strip() == "disable-model-invocation: true"]
    text = "---\n" + "\n".join(fields) + "\n---\n\n"
    text += "Read repository-root `AGENTS.md` and `docs/agents/shared-skills.md`.\n"
    text += f"Then follow the [shared skill](../../../{relative}).\n"
    text += "The linked file owns the procedure; do not maintain another copy here.\n"
    return text.encode()


def synchronize(root: Path, source: Path | None = None) -> list[str]:
    lock = json.loads((root / "config/shared_agent_skills.v1.json").read_text())
    if lock["version"] != 1 or not re.fullmatch(r"[0-9a-f]{40}", lock["commit"]):
        raise ValueError("Expected lock version 1 and a full upstream commit SHA")
    if not lock["files"]:
        raise ValueError("The reviewed file selection must not be empty")
    candidates: dict[str, bytes] = {}
    for item in lock["files"]:
        relative = item["destination"]
        if not relative.startswith((".agents/skills/", ".agents/licenses/")):
            raise ValueError(f"Destination is outside shared skills: {relative}")
        if relative in candidates:
            raise ValueError(f"Duplicate destination: {relative}")
        target = local_path(root, relative)
        # Validate source paths even though git show reads committed blobs only.
        local_path(root, item["source"])
        if source is None:
            content = target.read_bytes()
        else:
            content = subprocess.run(
                ["git", "-C", str(source), "show", f'{lock["commit"]}:{item["source"]}'],
                check=True, capture_output=True,
            ).stdout
        if hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Checksum mismatch: {relative}")
        candidates[relative] = content
        if relative.endswith("/SKILL.md"):
            name = Path(relative).parent.name
            candidates[f".claude/skills/{name}/SKILL.md"] = claude_adapter(relative, content)

    # Validate every candidate and local edit before writing any file.
    for relative, content in candidates.items():
        target = local_path(root, relative)
        if target.exists() and target.read_bytes() != content:
            raise ValueError(f"Local drift: {relative}; review it before changing the snapshot")
        if source is None and not target.is_file():
            raise ValueError(f"Missing shared skill or adapter: {relative}")
    if source is not None:
        for relative, content in candidates.items():
            target = local_path(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
    return list(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="Offline integrity check (default)")
    mode.add_argument("--source", type=Path, help="Local plugin clone containing the pinned commit")
    args = parser.parse_args()
    try:
        files = synchronize(Path(__file__).resolve().parents[1], args.source)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        print(f"Shared skill check failed: {error}", file=sys.stderr)
        return 1
    print(f"Shared skills: {len(files)} files verified; no upstream code or hooks executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
