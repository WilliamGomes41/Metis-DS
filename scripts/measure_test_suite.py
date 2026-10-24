#!/usr/bin/env python3
"""Record an executed suite, including failures/skips; optionally measure a Git base."""
import argparse
from contextlib import ExitStack
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
    parser.add_argument("--shard-index", type=int)
    parser.add_argument("--shard-count", type=int)
    args = parser.parse_args()
    sharded = args.shard_index is not None or args.shard_count is not None
    if sharded and (args.ref or args.shard_index is None or args.shard_count is None
                    or not 0 <= args.shard_index < args.shard_count):
        parser.error('shards require a current checkout and 0 <= index < count')
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    xml = output.with_suffix(".xml")
    xml.unlink(missing_ok=True)
    output.with_suffix('.selection.json').unlink(missing_ok=True)
    cwd = root
    worktree = None
    if args.ref:
        worktree = Path(tempfile.mkdtemp(prefix="metis-suite-baseline-")) / "checkout"
        subprocess.run(["git", "worktree", "add", "--detach", str(worktree), args.ref], cwd=root, check=True)
        cwd = worktree
    try:
        with ExitStack() as resources:
            suite_env = dict(os.environ)
            if suite_env.get("METIS_TEST_POSTGRES_DSN"):
                # Old baseline fixtures may reset tables. They must never run
                # against the supplied database or a previous suite's leftovers.
                sys.path.insert(0, str(root))
                from tests.postgres_support import database
                owned = resources.enter_context(database(suite_env["METIS_TEST_POSTGRES_DSN"]))
                suite_env["METIS_TEST_POSTGRES_DSN"] = owned.dsn
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cwd, text=True).strip()
            start = time.perf_counter()
            command = [sys.executable, "-m", "pytest", "-v", "--durations=30", f"--junitxml={xml}"]
            if sharded:
                command.extend(['-p', 'scripts.ci_test_shards',
                    '--metis-shard-index', str(args.shard_index),
                    '--metis-shard-count', str(args.shard_count),
                    '--metis-shard-manifest', str(output.with_suffix('.selection.json'))])
            result = subprocess.run(command, cwd=cwd, env=suite_env)
            elapsed = time.perf_counter() - start
            report = dict(commit=commit, python=platform.python_version(), platform=platform.platform(),
                          seconds=round(elapsed, 3), exit_code=result.returncode)
            if sharded:
                selection = output.with_suffix('.selection.json')
                if selection.exists():
                    report.update(json.loads(selection.read_text()))
                else:
                    report['selection_missing'] = True
                    report['exit_code'] = report['exit_code'] or 1
            if suite_env.get("METIS_TEST_POSTGRES_DSN"):
                import psycopg
                with psycopg.connect(suite_env["METIS_TEST_POSTGRES_DSN"], connect_timeout=3) as con:
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
                ratio = elapsed / before["seconds"]
                report["ratio"] = round(ratio, 4)
                report["within_twice_baseline"] = ratio <= 2
            output.write_text(json.dumps(report, indent=2) + "\n")
            print(json.dumps({key: value for key, value in report.items()
                              if key not in {'selected', 'finished'}}), flush=True)
            return report['exit_code'] or int(bool(report.get("postgres_skips")) or
                                           report.get("junit_missing", False) or
                                           not report.get("within_twice_baseline", True))
    finally:
        if worktree:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=root, check=True)
            worktree.parent.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
