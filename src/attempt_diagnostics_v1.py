"""Attempt-owned evidence. Never an admission or validated replay authority."""
from __future__ import annotations

import hashlib
import json
import platform
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

VERSION = "attempt-diagnostics-v1"
MAX_DIAGNOSTIC_BYTES = 16_000_000
VALIDATOR_FILES = ("semantic_passage_v1.py", "recommendation_semantics_v1.py",
                   "source_bound_fields_v2.py", "object_taxonomy_v1.py",
                   "semantic_replay_v1.py", "knowledge_relations_v1.py", "knowledge_relation_proposal_v1.py",
                   "source_reconstruction_v1.py", "source_layout_v1.py",
                   "serving_relations_v1.py", "source_context_review_v1.py",
                   "attempt_diagnostics_v1.py", "pre_review_semantic_v1.py",
                   "source_evidence_resolution_v1.py")


def validator_identity():
    root = Path(__file__).parent
    return {"python_version": platform.python_version(),
            **{name: hashlib.sha256((root / name).read_bytes()).hexdigest()
               for name in VALIDATOR_FILES}}


def classification(code):
    """Preserve the exact code; categories are only an operator-facing projection."""
    if code.startswith(("semantic_", "recommendation_", "source_bound_")):
        return "validation", "inspect_exact_source_evidence"
    if any(word in code for word in ("timeout", "connect", "network", "rate_limit", "provider")):
        return "transport", "inspect_transport_before_retry"
    if any(word in code for word in ("response", "abstain", "output_limit", "input_limit")):
        return "model_output", "inspect_recorded_request_and_output"
    if any(word in code for word in ("source", "freeze", "extract", "reconstruct")):
        return "source", "verify_immutable_source_and_extraction"
    if any(word in code for word in ("permission", "role", "named")):
        return "authorization", "verify_document_permissions"
    if any(word in code for word in ("conflict", "revision", "expired", "attempt", "cooldown", "existing_work", "published")):
        return "workflow", "inspect_current_work_and_attempt_history"
    if any(word in code for word in ("store", "database", "persist", "diagnostic")):
        return "persistence", "verify_storage_before_recovery"
    return "unknown", "inspect_failure_phase_no_automatic_retry"


def deployment_identity():
    try:
        commit = (Path(__file__).resolve().parents[1] / "config/deployed_commit.txt").read_text().strip()
    except OSError:
        return None
    return commit if len(commit) == 40 and all(c in "0123456789abcdef" for c in commit) else None


def checkpoint(attempt, phase, values):
    diagnostic = attempt.setdefault("diagnostic", {"version": VERSION, "checkpoints": []})
    proposed = {**diagnostic, **deepcopy(values)}
    if len(json.dumps(proposed, ensure_ascii=False).encode()) > MAX_DIAGNOSTIC_BYTES:
        omitted = []
        for key in sorted(values, key=lambda k: len(json.dumps(values[k], ensure_ascii=False)), reverse=True):
            proposed.pop(key, None)
            omitted.append(key)
            if len(json.dumps(proposed, ensure_ascii=False).encode()) <= MAX_DIAGNOSTIC_BYTES:
                break
        proposed["omitted_evidence"] = sorted(set(diagnostic.get("omitted_evidence", []) + omitted))
        proposed["evidence_limit_bytes"] = MAX_DIAGNOSTIC_BYTES
    diagnostic.clear()
    diagnostic.update(proposed)
    diagnostic["phase"] = phase
    diagnostic["checkpoints"].append({"phase": phase, "at": datetime.now(timezone.utc).isoformat()})


def finish_diagnostic(attempt, error=None):
    diagnostic = attempt.setdefault("diagnostic", {"version": VERSION, "checkpoints": []})
    code = attempt.get("validation_code") or attempt.get("error_code") or "succeeded"
    category, advice = classification(code) if error else ("success", "continue_review")
    diagnostic.update(outcome=attempt["state"], reason_code=code, category=category,
                      recovery_advice=advice,
                      evidence_availability="partial_limit" if diagnostic.get("omitted_evidence") else "recorded" if "validator_input" in diagnostic else "not_recorded")


def comparable_envelope(envelope):
    result = deepcopy(envelope)
    for attempt in result.get("processing_attempts", []):
        attempt.pop("diagnostic", None)
    return result


def merge_diagnostics(prepared, current):
    by_id = {a["attempt_id"]: a for a in current.get("processing_attempts", [])}
    for attempt in prepared.get("processing_attempts", []):
        recorded = by_id.get(attempt["attempt_id"], {})
        if "diagnostic" in recorded:
            attempt["diagnostic"] = deepcopy(recorded["diagnostic"])


def replay_diagnostic(attempt):
    """Validate recorded input without calling a provider or changing workflow state."""
    diagnostic = attempt.get("diagnostic") or {}
    if not diagnostic:
        return {"status": "unavailable", "reason_code": "diagnostic_input_not_recorded"}
    if diagnostic.get("validator_identity") != validator_identity():
        return {"status": "unavailable", "reason_code": "diagnostic_validator_version_unavailable"}
    data = diagnostic.get("validator_input")
    if not isinstance(data, dict) or "proposal" not in diagnostic:
        return {"status": "unavailable", "reason_code": "diagnostic_input_not_recorded"}
    if diagnostic.get("proposal_hash") != hashlib.sha256(json.dumps(diagnostic["proposal"], sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest():
        return {"status": "unavailable", "reason_code": "diagnostic_input_integrity_failed"}
    expected = diagnostic.get("validator_input_hash")
    if expected != hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest():
        return {"status": "unavailable", "reason_code": "diagnostic_input_integrity_failed"}
    from src.pre_review_semantic_v1 import validate_provider_proposal
    from src.operations_console_v1 import ConsoleError
    try:
        validate_provider_proposal(diagnostic["proposal"], field_contract_v2=data.get("field_contract_v2", False))
    except ConsoleError as error:
        finding = getattr(error, "validation_finding", {"reason_code": error.code})
        return {"status": "rejected", "reason_code": finding["reason_code"], "finding": finding}
    from src.semantic_passage_v1 import semantic_units_from_proposal, semantic_source_blocks, SemanticPassageError
    from src.source_evidence_resolution_v1 import resolve_proposal_evidence
    try:
        proposal = resolve_proposal_evidence(diagnostic["proposal"],
            blocks=semantic_source_blocks(data["fragments"]),
            evidence_blocks=semantic_source_blocks(data["evidence_fragments"]))
        units = semantic_units_from_proposal(**deepcopy(data), proposal=proposal)
    except SemanticPassageError as error:
        return {"status": "rejected", "reason_code": error.code, "finding": error.finding}
    return {"status": "validated", "unit_count": len(units), "admission_authority": False}
