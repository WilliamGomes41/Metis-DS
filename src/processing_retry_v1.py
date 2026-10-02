"""Retry attempt rules; durability belongs to the existing workflow document."""
from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone

from src.operations_console_v1 import ConsoleError

KEY = "processing_attempts"
VERSION = "source-reprocessing-v2"


def now() -> datetime:
    return datetime.now(timezone.utc)


def reserve(envelope: dict, *, command_id: str, actor_id: str, revision: str, clock: datetime, limits=None, kind="retry") -> tuple[dict, bool]:
    if not command_id or len(command_id) > 128 or not re.fullmatch(r"[A-Za-z0-9_-]+", command_id):
        raise ConsoleError("processing_command_id_invalid")
    from src.bounded_model_call_v1 import ModelCallLimits
    limits = limits or ModelCallLimits()
    attempts = envelope.setdefault(KEY, [])
    for attempt in attempts:
        if attempt["state"] == "running" and datetime.fromisoformat(attempt["expires_at"]) <= clock:
            attempt.update(state="interrupted", finished_at=clock.isoformat(), error_code="processing_attempt_expired")
    for attempt in attempts:
        if attempt["command_id"] == command_id:
            if attempt["actor_id"] != actor_id or attempt["source_hash"] != envelope["sha256"] or attempt.get("source_version", envelope["version"]) != envelope["version"]:
                raise ConsoleError("processing_command_conflict")
            return attempt, False
    if any(attempt["state"] == "running" for attempt in attempts):
        raise ConsoleError("processing_attempt_in_progress")
    if len(attempts) >= limits.max_attempts:
        raise ConsoleError("processing_attempt_limit_reached")
    if attempts and attempts[-1].get("retry_not_before") and datetime.fromisoformat(attempts[-1]["retry_not_before"]) > clock:
        raise ConsoleError("processing_retry_cooldown")
    if attempts and attempts[-1].get("error_code") in {"pre_review_llm_input_limit_exceeded", "pre_review_llm_output_limit_exceeded"}:
        raise ConsoleError("processing_structural_limit")
    attempt = {"version": VERSION, "attempt_id": "pa_" + uuid.uuid4().hex,
               "command_id": command_id, "actor_id": actor_id, "source_hash": envelope["sha256"],
               "expected_revision": revision, "source_version": envelope["version"], "kind":kind,
               "limits": limits.record(), "retry_of":attempts[-1]["attempt_id"] if attempts else None,
               "retry_not_before":None, "transport":None, "state": "running", "started_at": clock.isoformat(),
               "expires_at": (clock + timedelta(seconds=limits.attempt)).isoformat(), "finished_at": None,
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
        transport = getattr(error, "model_call_observation", None)
        if transport is not None:
            attach_transport(attempt, transport)
    return deepcopy(attempt)


TRANSPORT_FIELDS = {"version", "call_id", "limits", "started_at", "finished_at", "elapsed_seconds", "category",
                    "external_cancellation", "retry_not_before", "bytes_received", "phase", "http_status",
                    "error_code", "local_worker_reaped", "transport_pid"}


def attach_transport(attempt: dict, observation: dict):
    # Only observations emitted by the native supervised transport, never response prose.
    if isinstance(observation, dict) and observation.get("version") == "bounded-model-call-v1":
        attempt["transport"] = {key: deepcopy(value) for key, value in observation.items() if key in TRANSPORT_FIELDS}
        attempt["retry_not_before"] = observation.get("retry_not_before")


def status(envelope: dict, *, clock: datetime | None = None, retry_supported=True, policy=None) -> dict:
    clock = clock or now()
    attempts = envelope.get(KEY) or []
    latest = attempts[-1] if attempts else {}
    state = latest.get("state", "not_recorded")
    reason = latest.get("error_code") or envelope.get("processing_blocker")
    if state == "running" and datetime.fromisoformat(latest["expires_at"]) <= clock:
        state, reason = "expired", "processing_attempt_expired"
    allowed = bool(envelope.get("publication_eligibility") == "blocked_pending_pre_review"
                   and state != "running" and retry_supported)
    max_attempts = policy.max_attempts if policy is not None else (latest.get("limits") or {}).get("max_attempts", 4)
    retry_at = latest.get("retry_not_before")
    if len(attempts) >= max_attempts:
        allowed, reason = False, "processing_attempt_limit_reached"
    elif retry_at and datetime.fromisoformat(retry_at) > clock:
        allowed, reason = False, "processing_retry_cooldown"
    elif latest.get("error_code") in {"pre_review_llm_input_limit_exceeded", "pre_review_llm_output_limit_exceeded"}:
        allowed, reason = False, "processing_structural_limit"
    return {"state":state, "stored_state":latest.get("state"), "attempt_id":latest.get("attempt_id"),
            "reason_code":reason, "error_code":latest.get("error_code"), "retry_allowed":allowed, "retry_not_before":retry_at,
            "attempts_used":len(attempts), "max_attempts":max_attempts,
            "external_cancellation":(latest.get("transport") or {}).get("external_cancellation", "not_requested" if "replayed_call_id" in latest else "not_recorded")}
