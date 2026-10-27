"""Stamp identical version metadata into ZIP and container build contexts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from src.console_release_v1 import BUILD_FILE, release_definition


def stamp_release(source: Path, target: Path, commit: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("console_build_commit_invalid")
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                             cwd=source, check=True, capture_output=True, text=True).stdout.strip()
    if shallow != "false":
        raise ValueError("console_build_requires_full_history")
    count = int(subprocess.run(["git", "rev-list", "--first-parent", "--count", commit],
                              cwd=source, check=True, capture_output=True, text=True).stdout.strip())
    if count < 1:
        raise ValueError("console_build_number_invalid")
    definition = release_definition(target)
    build = {"version": f'{definition["generation"]}.{definition["release"]}.{count}', "commit": commit}
    (target / BUILD_FILE).write_text(json.dumps(build, sort_keys=True) + "\n", encoding="utf-8")
    return build


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    stamp_release(args.source, args.target, args.commit)
