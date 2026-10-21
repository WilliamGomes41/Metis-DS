"""Safe exception evidence: where it broke, never what the data said.

Only the exception type, a validated ``ConsoleError`` code and in-repository
frames (``src/module.py:function:line``) leave this module. No message text,
locals, arguments or third-party paths: those may carry clinical content,
credentials or personal data.
"""
from __future__ import annotations

import hashlib
import re
import traceback
from pathlib import Path
from typing import Any

MAX_FRAMES = 12
_REPO_SRC = Path(__file__).resolve().parents[1]
_CODE = re.compile(r"[a-z][a-z0-9_]{1,80}")
_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.<>]{0,120}")
# HTTP middleware wrappers sit above every route frame; they say nothing about
# where a defect is. Guarded by tests/test_telemetry_v1.py against new middleware.
MIDDLEWARE_FUNCTIONS = frozenset({
    "console_performance", "document_status_context", "document_status_calculation",
    "renew_on_navigation", "request_id_middleware", "require_same_origin",
    "simplify_duplicate_doors", "source_read_calculation", "restricted_browser",
})


def _frame(entry: traceback.FrameSummary) -> str | None:
    try:
        path = Path(entry.filename).resolve()
        relative = path.relative_to(_REPO_SRC.parent)
    except (OSError, ValueError):
        return None
    if relative.parts[:1] != ("src",):
        return None
    function = entry.name if _NAME.fullmatch(entry.name or "") else "?"
    if function in MIDDLEWARE_FUNCTIONS or (function == "__call__" and relative.name == "request_diagnostics_v1.py"):
        return None
    return f"{relative.as_posix()}:{function}:{int(entry.lineno or 0)}"


def exception_evidence(exc: BaseException) -> dict[str, Any]:
    """Type, code, in-repo frames (deepest last) and a stable fingerprint."""
    error_type = type(exc).__name__
    code = getattr(exc, "code", None)
    code = code if isinstance(code, str) and _CODE.fullmatch(code) else None
    frames: list[str] = []
    try:
        for entry in traceback.extract_tb(exc.__traceback__):
            frame = _frame(entry)
            if frame is not None:
                frames.append(frame)
    except Exception:
        frames = []
    frames = frames[-MAX_FRAMES:]
    # Line numbers move with every edit; module:function keeps one group per defect.
    anchor = [frame.rsplit(":", 1)[0] for frame in frames[-3:]]
    digest = hashlib.sha256("|".join([error_type, code or "", *anchor]).encode()).hexdigest()[:12]
    return {"type": error_type if _NAME.fullmatch(error_type) else "Exception",
            "code": code, "frames": frames, "fingerprint": digest}
