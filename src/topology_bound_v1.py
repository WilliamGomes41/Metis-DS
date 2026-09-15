"""Fail-closed bounds for the supported console process topology.

The default remains one Gunicorn worker. Two workers are supported only on one
instance with every mutable production authority enabled. HTTP mutations are
then protected by authoritative PostgreSQL concurrency and the process-shared
commit lock on that single instance.
"""
from __future__ import annotations

import os
import re
from typing import Mapping

DEFAULT_WORKERS = 1
SUPPORTED_WORKERS = (1, 2)
SUPPORTED_INSTANCE_COUNT = 1
SUPPORTED_WRITE_MODE = "sequential"

DURABLE_MULTI_WORKER_SETTINGS = {
    "METIS_CANONICAL_STORE": "postgres",
    "METIS_WORKFLOW_STORE": "postgres",
    "METIS_WORKFLOW_DOCUMENT_STORE": "postgres",
    "METIS_WORKFLOW_REVIEW_STORE": "postgres",
    "METIS_WORKFLOW_REMAINING_STORE": "postgres",
    "CONSOLE_IMMUTABLE_SOURCE_STORE": "azure",
}

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
WORKER_COUNT_CONFLICT = "worker_count_conflict"
MULTI_WORKER_DURABLE_AUTHORITY_REQUIRED = "multi_worker_durable_authority_required"

_WORKER_FLAG_RE = re.compile(
    r"(?:^|(?<=\s))(?:--workers(?:=|\s+)|-w(?:=|\s+)?)([^\s]+)(?:\s|$)"
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


def _workers_from_gunicorn_cmd(args: str) -> list[int | None]:
    return [_parse_declared_int(raw) for raw in _WORKER_FLAG_RE.findall(args)]


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
        if value not in SUPPORTED_WORKERS:
            errors.append(MULTI_WORKER_OUT_OF_BOUND)

    cmd_args = str(env.get(GUNICORN_CMD_ARGS_KEY, "") or "").strip()
    if cmd_args:
        for cmd_workers in _workers_from_gunicorn_cmd(cmd_args):
            if cmd_workers is None or cmd_workers < 1:
                errors.append(INVALID_WORKER_COUNT)
                declared_workers.append(0)
            else:
                declared_workers.append(cmd_workers)
                if cmd_workers not in SUPPORTED_WORKERS:
                    errors.append(MULTI_WORKER_OUT_OF_BOUND)

    workers = declared_workers[0] if declared_workers else DEFAULT_WORKERS
    valid_declared_workers = [value for value in declared_workers if value >= 1]
    if len(set(valid_declared_workers)) > 1:
        errors.append(WORKER_COUNT_CONFLICT)

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

    if workers == 2 and any(
        str(env.get(name, "") or "").strip().lower() != required
        for name, required in DURABLE_MULTI_WORKER_SETTINGS.items()
    ):
        errors.append(MULTI_WORKER_DURABLE_AUTHORITY_REQUIRED)

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
            "workers": list(SUPPORTED_WORKERS),
            "default_workers": DEFAULT_WORKERS,
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
