"""Retry attempt rules; durability belongs to the existing workflow document."""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.operations_console_v1 import ConsoleError

KEY = "processing_attempts"
VERSION = "source-reprocessing-v1"


def now() -> datetime:
    return datetime.now(timezone.utc)


def reserve(envelope: dict, *, command_id: str, actor_id: str, revision: str, clock: datetime) -> tuple[dict, bool]:
    if not command_id or len(command_id) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", command_id):
        raise ConsoleError("processing_command_id_invalid")
    attempts = envelope.setdefault(KEY, [])
    for attempt in attempts:
        if attempt["state"] == "running" and datetime.fromisoformat(attempt["expires_at"]) <= clock:
            attempt.update(state="interrupted", finished_at=clock.isoformat(), error_code="processing_attempt_expired")
    for attempt in attempts:
        if attempt["command_id"] == command_id:
            if attempt["actor_id"] != actor_id or attempt["source_hash"] != envelope["sha256"]:
                raise ConsoleError("processing_command_conflict")
            return attempt, False
    if any(attempt["state"] == "running" for attempt in attempts):
        raise ConsoleError("processing_attempt_in_progress")
    attempt = {"version": VERSION, "attempt_id": "pa_" + uuid.uuid4().hex,
               "command_id": command_id, "actor_id": actor_id, "source_hash": envelope["sha256"],
               "expected_revision": revision, "state": "running", "started_at": clock.isoformat(),
               "expires_at": (clock + timedelta(minutes=30)).isoformat(), "finished_at": None,
               "error_code": None, "validation_code": None, "processing_reference": None,
               "phase": "source_and_validation"}
    attempts.append(attempt)
    return attempt, True


def assert_active(envelope: dict, attempt_id: str, clock: datetime) -> dict:
    attempt = next((a for a in envelope.get(KEY, []) if a["attempt_id"] == attempt_id), None)
    if attempt is None or attempt["state"] != "running":
        raise ConsoleError("processing_attempt_not_active")
    if datetime.fromisoformat(attempt["expires_at"]) <= clock:
        raise ConsoleError("processing_attempt_expired")
    return attempt


def finish(envelope: dict, attempt_id: str, *, state: str, error: Exception | None = None) -> dict:
    attempt = next(a for a in envelope[KEY] if a["attempt_id"] == attempt_id)
    attempt.update(state=state, finished_at=now().isoformat(), phase="activated" if state == "succeeded" else "stopped")
    if error is not None:
        code = getattr(error, "code", "processing_timeout" if isinstance(error, TimeoutError) else "processing_dependency_failed")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", str(code)):
            code = "processing_dependency_failed"
        attempt["error_code"] = code
        # Validator subcodes are already bounded by the semantic wrapper. No exception prose.
        diagnostics = getattr(error, "pre_review_diagnostics", {})
        validation = str(diagnostics.get("reason_code") or "")
        reference = str(diagnostics.get("reference") or "")
        attempt["validation_code"] = validation if re.fullmatch(r"(?:semantic|recommendation|source_bound)_[a-z_]{1,100}", validation) else None
        attempt["processing_reference"] = reference if re.fullmatch(r"[A-Za-z0-9_-]{1,80}", reference) else None
    return deepcopy(attempt)
