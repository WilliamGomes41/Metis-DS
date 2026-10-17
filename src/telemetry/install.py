"""Process-level telemetry installation for the console host.

Called once from the composition root. Configures the bounded store, the logging
bridge, crash evidence (faulthandler stack dumps on fatal signals, including the
SIGABRT a server sends to a timed-out worker) and process lifecycle events.
"""
from __future__ import annotations

import atexit
import faulthandler
import os
import platform
import sys
import threading
from pathlib import Path

from src.telemetry.hub import HUB, record_event
from src.telemetry.logging_bridge import install_logging_bridge

_INSTALLED: dict[str, bool] = {}


def telemetry_directory(runtime: Path) -> Path:
    override = os.getenv("METIS_TELEMETRY_DIR", "").strip()
    return Path(override) if override else Path(runtime) / "telemetry"


def install_console_observability(app, runtime: Path) -> None:
    """Request diagnostics and the hub for a console app; one composition for every host."""
    from src.console_performance_v1 import install_console_performance
    from src.structured_logging_v1 import install_structured_logging
    # The hub on root disables Python's stderr fallback: keep a process log on every host.
    install_structured_logging()
    install_console_performance(app)
    install_telemetry(telemetry_directory(runtime))
    # The server configures its own loggers after composition: redact them, then join them.
    app.add_event_handler("startup", install_structured_logging)
    app.add_event_handler("startup", install_logging_bridge)


def install_telemetry(directory: Path | None) -> None:
    stored = HUB.configure(directory)
    install_logging_bridge()
    if not stored:
        record_event("telemetry_storage_unavailable", kind="telemetry")
    if _INSTALLED.get(str(os.getpid())):
        return
    _INSTALLED[str(os.getpid())] = True
    if not faulthandler.is_enabled():
        # Fatal-signal stacks go to stderr (file, function and line only; no values).
        # Optional evidence: an unusable stderr MAG NIET stop the console from booting.
        try:
            faulthandler.enable()
        except Exception:
            record_event("telemetry_crash_stacks_unavailable", kind="telemetry")
    _install_exception_hooks()
    record_event("process_started", kind="process", python=platform.python_version())
    atexit.register(_process_stopped)


def _process_stopped() -> None:
    record_event("process_stopped", kind="process")
    HUB.flush()


def _install_exception_hooks() -> None:
    from src.telemetry.errors import exception_evidence
    previous_thread_hook = threading.excepthook
    previous_sys_hook = sys.excepthook

    def thread_hook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            record_event("unhandled_exception", kind="error", origin="thread",
                         error=exception_evidence(args.exc_value))
        previous_thread_hook(args)

    def sys_hook(exc_type, exc_value, exc_tb) -> None:
        if exc_value is not None:
            record_event("unhandled_exception", kind="error", origin="process",
                         error=exception_evidence(exc_value))
        HUB.flush()
        previous_sys_hook(exc_type, exc_value, exc_tb)

    threading.excepthook = thread_hook
    sys.excepthook = sys_hook
