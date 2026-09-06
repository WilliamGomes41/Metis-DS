"""Supported console topology bound (Post-#120 audit remediation 5).

CONFIGURE only. Current supported topology:

- one Gunicorn worker
- one instance
- sequential writes

Accidental multi-worker / multi-instance / multi-writer assumptions
fail closed. EXTEND for multiple writers (consistent mutate-path for
accounts/envelopes/bindings, session reload/lock) is out of scope until
scaling is separately GO'd. publish() stays G2-BLOCKED.
"""
from __future__ import annotations

import os
import re
from typing import Mapping

SUPPORTED_WORKERS = 1
SUPPORTED_INSTANCE_COUNT = 1
SUPPORTED_WRITE_MODE = "sequential"

WORKER_ENV_KEYS = (
    "CONSOLE_GUNICORN_WORKERS",
    "WEB_CONCURRENCY",
    "GUNICORN_WORKERS",
)
INSTANCE_ENV_KEY = "CONSOLE_INSTANCE_COUNT"
WRITE_MODE_ENV_KEY = "CONSOLE_WRITE_MODE"
GUNICORN_CMD_ARGS_KEY = "GUNICORN_CMD_ARGS"

MULTI_WORKER_OUT_OF_BOUND = "multi_worker_out_of_bound"
MULTI_INSTANCE_OUT_OF_BOUND = "multi_instance_out_of_bound"
MULTI_WRITER_MODE_OUT_OF_BOUND = "multi_writer_mode_out_of_bound"
INVALID_WORKER_COUNT = "invalid_worker_count"
INVALID_INSTANCE_COUNT = "invalid_instance_count"

_WORKER_FLAG_RE = re.compile(
    r"(?:^|(?<=\s))(?:--workers(?:=|\s+)|-w(?:=|\s+)?)(\d+)(?:\s|$)"
)


class TopologyBoundError(RuntimeError):
    """Fail-closed when the process is configured outside the supported topology."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _parse_declared_int(raw: str) -> int | None:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _workers_from_gunicorn_cmd(args: str) -> int | None:
    match = _WORKER_FLAG_RE.search(args)
    if match is None:
        return None
    return _parse_declared_int(match.group(1))


def evaluate_topology(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    env = environ if environ is not None else os.environ
    errors: list[str] = []
    declared_workers: list[int] = []

    for key in WORKER_ENV_KEYS:
        raw = str(env.get(key, "") or "").strip()
        if not raw:
            continue
        value = _parse_declared_int(raw)
        if value is None or value < 1:
            errors.append(INVALID_WORKER_COUNT)
            declared_workers.append(0)
            continue
        declared_workers.append(value)
        if value != SUPPORTED_WORKERS:
            errors.append(MULTI_WORKER_OUT_OF_BOUND)

    cmd_args = str(env.get(GUNICORN_CMD_ARGS_KEY, "") or "").strip()
    if cmd_args:
        cmd_workers = _workers_from_gunicorn_cmd(cmd_args)
        if cmd_workers is None:
            pass
        elif cmd_workers < 1:
            errors.append(INVALID_WORKER_COUNT)
            declared_workers.append(0)
        else:
            declared_workers.append(cmd_workers)
            if cmd_workers != SUPPORTED_WORKERS:
                errors.append(MULTI_WORKER_OUT_OF_BOUND)

    workers = declared_workers[0] if declared_workers else SUPPORTED_WORKERS
    if any(value != SUPPORTED_WORKERS for value in declared_workers):
        workers = next(
            (value for value in declared_workers if value != SUPPORTED_WORKERS),
            workers,
        )

    raw_instances = str(env.get(INSTANCE_ENV_KEY, "") or "").strip()
    if raw_instances:
        instances = _parse_declared_int(raw_instances)
        if instances is None or instances < 1:
            errors.append(INVALID_INSTANCE_COUNT)
            instances = 0
        elif instances != SUPPORTED_INSTANCE_COUNT:
            errors.append(MULTI_INSTANCE_OUT_OF_BOUND)
    else:
        instances = SUPPORTED_INSTANCE_COUNT

    raw_mode = str(env.get(WRITE_MODE_ENV_KEY, "") or "").strip().lower().replace("-", "_")
    write_mode = raw_mode or SUPPORTED_WRITE_MODE
    if write_mode != SUPPORTED_WRITE_MODE:
        errors.append(MULTI_WRITER_MODE_OUT_OF_BOUND)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique_errors: list[str] = []
    for code in errors:
        if code not in seen:
            seen.add(code)
            unique_errors.append(code)

    status = "BLOCKED" if unique_errors else "PASS"
    return {
        "status": status,
        "workers": workers,
        "instances": instances,
        "write_mode": write_mode,
        "errors": unique_errors,
        "supported": {
            "workers": SUPPORTED_WORKERS,
            "instances": SUPPORTED_INSTANCE_COUNT,
            "write_mode": SUPPORTED_WRITE_MODE,
        },
    }


def assert_supported_topology(environ: Mapping[str, str] | None = None) -> dict[str, object]:
    result = evaluate_topology(environ)
    if result["status"] != "PASS":
        errors = result["errors"]
        code = str(errors[0]) if errors else MULTI_WORKER_OUT_OF_BOUND
        raise TopologyBoundError(code)
    return result
