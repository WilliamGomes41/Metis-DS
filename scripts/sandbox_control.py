#!/usr/bin/env python3
"""Control container for the sandbox runner (#653 T5).

Sole writer of the control volume (/sandbox-control). The workspace drops requests
in output/runtime/sandbox-requests; this process moves them into the control
volume, the runner (control volume read-only) executes them and writes only to
its artifact dir; this process copies the result into the control volume. The
verdict (ready/.exit/.log) MOET uitsluitend uit het control-volume komen.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import sys
import time

REQUESTS = Path("/workspaces/metis/output/runtime/sandbox-requests")
ARTIFACTS = Path("/workspaces/metis/output/runtime/sandbox-artifacts")
CONTROL = Path("/sandbox-control")
HEARTBEAT_MAX_AGE = 15.0
ALLOWED = {"check", "scan", "test", "test --local", "probe", "rt"}


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def dispatch(requests: Path, control: Path) -> None:
    jobs = control / "jobs"
    jobs.mkdir(parents=True, exist_ok=True)
    for request in sorted(requests.glob("*.request")):
        command = request.read_text().strip()
        if command == "rt":
            # The previous job's tree MAG NOOIT be reused: clear it, then require a
            # fresh payload, which is consumed (moved) so a next rt request finds none.
            shutil.rmtree(control / "rt", ignore_errors=True)
            payload = requests / "rt"
            if not payload.is_dir() or not any(payload.iterdir()):
                _atomic_write(jobs / f"{request.stem}.log", "rejected: rt without fresh payload\n")
                _atomic_write(jobs / f"{request.stem}.exit", "2\n")
                request.unlink()
                continue
            shutil.copytree(payload, control / "rt")
            shutil.rmtree(payload)
        if command in ALLOWED:
            _atomic_write(jobs / request.name, command)
        else:
            _atomic_write(jobs / f"{request.stem}.log", f"rejected: {command}\n")
            _atomic_write(jobs / f"{request.stem}.exit", "2\n")
        request.unlink()


def publish(control: Path, artifacts: Path, job_id: str) -> bool:
    """Copy a finished runner result into the control volume; unparseable MOET falen (1)."""
    rc_file = artifacts / f"{job_id}.rc"
    if not rc_file.exists():
        return False
    raw = rc_file.read_text().strip()
    code = int(raw) if raw.isdigit() else 1
    log = artifacts / f"{job_id}.log"
    jobs = control / "jobs"
    _atomic_write(jobs / f"{job_id}.log", log.read_text(errors="replace") if log.exists() else "")
    _atomic_write(jobs / f"{job_id}.exit", f"{code}\n")
    (jobs / f"{job_id}.request").unlink(missing_ok=True)
    return True


def refresh_ready(control: Path, artifacts: Path, *, now: float) -> None:
    try:
        fresh = now - float((artifacts / "heartbeat").read_text().strip()) <= HEARTBEAT_MAX_AGE
    except (OSError, ValueError):
        fresh = False
    if fresh:
        _atomic_write(control / "ready", "runner ready\n")
    else:
        (control / "ready").unlink(missing_ok=True)


def seal_for_tests(root: Path) -> None:
    """Test helper: make a directory tree read-only like the runner's :ro mount."""
    for path in sorted(root.rglob("*"), reverse=True) + [root]:
        path.chmod(stat.S_IRUSR | (stat.S_IXUSR if path.is_dir() else 0))


def unseal_for_tests(root: Path) -> None:
    for path in [root] + sorted(root.rglob("*")):
        path.chmod(stat.S_IRWXU)


def main() -> int:
    (CONTROL / "jobs").mkdir(parents=True, exist_ok=True)
    print("sandbox-control: started", flush=True)
    while True:
        dispatch(REQUESTS, CONTROL)
        for request in (CONTROL / "jobs").glob("*.request"):
            publish(CONTROL, ARTIFACTS, request.stem)
        refresh_ready(CONTROL, ARTIFACTS, now=time.time())
        time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
