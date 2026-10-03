"""Supervise real model conversion; existing processing_attempts own recovery."""
from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from contextlib import ExitStack

from src.docling_contract_v1 import DoclingError, translate

ROOT = Path(__file__).resolve().parents[1]


def enabled() -> bool:
    # Staged cutover only, never a fallback. Unset remains the explicit existing
    # release until real quality/runtime acceptance. No user-facing parser switch.
    route = os.environ.get("METIS_PDF_EXTRACTOR", "legacy-comparison")
    if route not in {"docling", "legacy-comparison"}:
        raise DoclingError("docling_route_invalid")
    return route == "docling"


def _positive(name: str, default: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
        if not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError()
        return value
    except ValueError as error:
        raise DoclingError("docling_limits_invalid") from error


def _rss(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        pass
    return 0


def supervise(command: list[str], *, pass_fds: tuple[int, ...], env: dict,
              timeout: float, max_rss_bytes: int) -> dict:
    """Actual termination/reaping, including native code; no timeout thread."""
    started, peak = time.monotonic(), 0
    process = subprocess.Popen(command, cwd=ROOT, env=env, pass_fds=pass_fds,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        while process.poll() is None:
            peak = max(peak, _rss(process.pid))
            if peak > max_rss_bytes:
                raise DoclingError("docling_memory_limit_exceeded")
            if time.monotonic() - started >= timeout:
                raise DoclingError("docling_timeout")
            try:
                process.wait(timeout=min(.05, max(.001, timeout - (time.monotonic() - started))))
            except subprocess.TimeoutExpired:
                pass
        if time.monotonic() - started >= timeout:
            raise DoclingError("docling_timeout")
        if process.returncode:
            raise DoclingError("docling_worker_failed")
        return {"elapsed_seconds": time.monotonic() - started, "observed_peak_rss_bytes": peak,
                "worker_reaped": True}
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=2)


def extract(pdf: Path, *, document_id: str, source_id: str, pages=None,
            deadline: float | None = None):
    if sys.platform != "linux":
        raise DoclingError("docling_requires_linux")
    python = os.environ.get("METIS_DOCLING_PYTHON", "")
    artifacts = os.environ.get("METIS_DOCLING_ARTIFACTS_PATH", "")
    if not python or not Path(python).is_file() or not artifacts or not Path(artifacts).is_dir():
        raise DoclingError("docling_runtime_not_configured")
    timeout = _positive("METIS_DOCLING_TIMEOUT_SECONDS", 1200, 3540)
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic() - 2)
    if timeout <= 0:
        raise DoclingError("docling_timeout")
    config = {"timeout": timeout, "max_pages": 1000, "max_bytes": 64 * 1024 * 1024,
              "max_output_bytes": 64 * 1024 * 1024, "artifacts_path": str(Path(artifacts).resolve())}
    # Default leaves room for console on existing B1; NOT a claim Docling fits.
    rss = int(_positive("METIS_DOCLING_MAX_RSS_MIB", 768, 16384) * 1024 * 1024)
    gate_path = Path(os.environ.get("METIS_DOCLING_LOCK_PATH", "/tmp/metis-docling-conversion.lock"))
    with ExitStack() as stack:
        gate = stack.enter_context(gate_path.open("a"))
        try:
            fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DoclingError("docling_capacity_busy") from error
        # Anonymous descriptors disappear after crash; no source temp files.
        handles = []
        for name in ("config", "input", "result"):
            fd = os.memfd_create("metis-docling-" + name)
            handles.append(stack.enter_context(os.fdopen(fd, "w+b")))
        c, data, output = handles
        c.write(json.dumps(config).encode()); c.seek(0)
        digest = hashlib.sha256()
        with Path(pdf).open("rb") as source:
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > config["max_bytes"]:
                    raise DoclingError("docling_input_limit_exceeded")
                digest.update(chunk); data.write(chunk)
        data.seek(0)
        env = {k: v for k, v in os.environ.items() if k in {"PATH", "LANG", "LC_ALL", "LD_LIBRARY_PATH"}}
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_DATASETS_OFFLINE="1",
                   OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", PYTHONPATH=str(ROOT))
        metrics = supervise([python, "-m", "src.docling_worker_v1", str(c.fileno()),
            str(data.fileno()), str(output.fileno()), str(os.getpid())],
            pass_fds=tuple(h.fileno() for h in handles), env=env, timeout=timeout, max_rss_bytes=rss)
        output.seek(0)
        encoded = output.read(config["max_output_bytes"] + 1)
        if len(encoded) > config["max_output_bytes"]:
            raise DoclingError("docling_output_limit_exceeded")
        try:
            payload = json.loads(encoded)
        except (ValueError, UnicodeError) as error:
            raise DoclingError("docling_worker_result_invalid") from error
        if "error_code" in payload:
            code = payload["error_code"]
            if not isinstance(code, str) or not code.startswith("docling_") or len(code) > 95:
                code = "docling_worker_result_invalid"
            raise DoclingError(code)
        payload["result"]["metrics"].update(metrics)
        return translate(payload["result"], document_id=document_id, source_id=source_id,
                         source_sha256=digest.hexdigest(), pages=pages)
