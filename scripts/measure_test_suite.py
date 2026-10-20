#!/usr/bin/env python3
"""Record an executed suite, including failures/skips; optionally measure a Git base."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ref")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    xml = output.with_suffix(".xml")
    xml.unlink(missing_ok=True)
    cwd = root
    worktree = None
    if args.ref:
        worktree = Path(tempfile.mkdtemp(prefix="metis-suite-baseline-")) / "checkout"
        subprocess.run(["git", "worktree", "add", "--detach", str(worktree), args.ref], cwd=root, check=True)
        cwd = worktree
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
        start = time.perf_counter()
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={xml}"], cwd=cwd)
        elapsed = time.perf_counter() - start
        report = dict(commit=commit, python=platform.python_version(), platform=platform.platform(),
                      seconds=round(elapsed, 3), exit_code=result.returncode)
        if os.environ.get("METIS_TEST_POSTGRES_DSN"):
            import psycopg
            with psycopg.connect(os.environ["METIS_TEST_POSTGRES_DSN"], connect_timeout=3) as con:
                report["postgres_version"] = con.info.server_version
        if xml.exists():
            tree = ET.parse(xml)
            cases = list(tree.iter("testcase"))
            report.update(tests=len(cases), failures=len(list(tree.iter("failure"))),
                          errors=len(list(tree.iter("error"))), skipped=len(list(tree.iter("skipped"))))
            pg_skips = [c.get("classname", "") + "::" + c.get("name", "") for c in cases
                        if c.find("skipped") is not None and
                        ("postgres" in c.get("classname", "").lower() or
                         "postgres" in ET.tostring(c.find("skipped"), encoding="unicode").lower())]
            report["postgres_skips"] = pg_skips
        else:
            report["junit_missing"] = True
        if args.compare:
            before = json.loads(args.compare.read_text())
            report["baseline_seconds"] = before["seconds"]
            report["ratio"] = round(elapsed / before["seconds"], 4)
            report["within_twice_baseline"] = report["ratio"] <= 2
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report), flush=True)
        return result.returncode or int(bool(report.get("postgres_skips")) or
                                       report.get("junit_missing", False) or
                                       not report.get("within_twice_baseline", True))
    finally:
        if worktree:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=root, check=True)
            worktree.parent.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
