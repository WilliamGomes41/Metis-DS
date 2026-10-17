"""Bridge Python logging into the hub, and stamp correlation ids on every record.

- ``CorrelationFilter`` fills ``request_id``/``trace_id``/``attempt_id`` on records that do not carry them, so every JSON log line can
  be joined to its request.
- ``HubHandler`` forwards the ``metis_diagnostic`` stream (request diagnostics,
  processing trace, publication evidence, publish refusals) as structured
  events, and every WARNING+ record from any logger as a ``log`` event.
"""
from __future__ import annotations

import json
import logging

from src.telemetry.hub import HUB, correlation

DIAGNOSTIC_LOGGER = "metis.console.diagnostics"
_FIELDS = ("request_id", "trace_id", "attempt_id")


class CorrelationFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            context = correlation()
        except Exception:
            return True
        for name in _FIELDS:
            if getattr(record, name, None) is None and context.get(name):
                setattr(record, name, context[name])
        return True


CORRELATION_FILTER = CorrelationFilter()


class HubHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name == DIAGNOSTIC_LOGGER:
                payload = _diagnostic_payload(record)
                if payload is not None:
                    HUB.record({"kind": _kind(payload.get("event")), **payload})
                return
            if record.levelno < logging.WARNING:
                return
            event = {"kind": "log", "event": "log_record", "level": record.levelname,
                     "logger": record.name, "message": record.getMessage()}
            if record.exc_info and record.exc_info[1] is not None:
                from src.telemetry.errors import exception_evidence
                event["error"] = exception_evidence(record.exc_info[1])
            for name in _FIELDS:
                value = getattr(record, name, None)
                if isinstance(value, str):
                    event[name] = value
            HUB.record(event)
        except Exception:
            HUB.dropped += 1


def _diagnostic_payload(record: logging.LogRecord) -> dict | None:
    if record.msg != "metis_diagnostic %s" or not record.args:
        return None
    raw = record.args[0] if isinstance(record.args, tuple) else None
    if not isinstance(raw, str):
        return None
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else None


def _kind(event: object) -> str:
    name = str(event or "")
    if name.startswith(("request_", "response_", "phase_")):
        return "request"
    if name.startswith("processing_"):
        return "processing"
    if name.startswith(("publication_", "publish_")):
        return "publication"
    if name.startswith("telemetry_"):
        return "telemetry"
    return "diagnostic"


HUB_HANDLER = HubHandler()


def install_logging_bridge() -> None:
    """Idempotent: one hub handler and one correlation filter per logger."""
    diagnostics = logging.getLogger(DIAGNOSTIC_LOGGER)
    root = logging.getLogger()
    for logger in (diagnostics, root):
        if HUB_HANDLER not in logger.handlers:
            logger.addHandler(HUB_HANDLER)
    for name in ("", "metis.console.performance", "uvicorn.error", "gunicorn.error"):
        for handler in logging.getLogger(name).handlers:
            if CORRELATION_FILTER not in handler.filters:
                handler.addFilter(CORRELATION_FILTER)
