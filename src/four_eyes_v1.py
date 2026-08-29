"""High-risk four-eyes authorization on the Protocol v2.12 object tuple.

Four-eyes is an additional required reviewer on the exact object tuple.
It does not replace the tuple. Envelope review_passes MUST NOT authorize
publish. AI / Grok Bot / Metis / Implementation engineer / Auditor MUST NOT
count. Uploader MUST NOT be the only required reviewer. publish() remains
G2-BLOCKED.
"""
from __future__ import annotations

from typing import Any, Iterable

HIGH_RISK_FIELDS = (
    "age_boundary",
    "dosage",
    "unit",
    "score_points",
    "score_threshold",
    "operator",
    "contraindication",
    "exception",
    "escalation_decision",
)
FORBIDDEN_REVIEWER_IDENTITIES = frozenset(
    {
        "ai",
        "grok bot",
        "grok",
        "metis",
        "implementation engineer",
        "auditor",
    }
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def is_forbidden_reviewer(value: str) -> bool:
    return _norm(value) in FORBIDDEN_REVIEWER_IDENTITIES


def reviewer_is_agent(binding_or_account: dict[str, Any]) -> bool:
    for key in ("reviewer", "username", "display_name", "reviewer_id"):
        if is_forbidden_reviewer(str(binding_or_account.get(key) or "")):
            return True
    return False


def present_risk_fields(obj: dict[str, Any]) -> list[str]:
    risk = obj.get("risk") or {}
    found: list[str] = []
    for field in risk.get("risk_fields") or []:
        if field in HIGH_RISK_FIELDS and field not in found:
            found.append(field)
    logic = obj.get("logic") or {}
    if logic.get("score_points") is not None and "score_points" not in found:
        found.append("score_points")
    threshold = logic.get("result_threshold") or {}
    if threshold.get("threshold") is not None and "score_threshold" not in found:
        found.append("score_threshold")
    if threshold.get("operator") and "operator" not in found:
        found.append("operator")
    if threshold.get("unit") and "unit" not in found:
        found.append("unit")
    for predicate in logic.get("predicates") or []:
        if predicate.get("operator") and "operator" not in found:
            found.append("operator")
        if predicate.get("unit") and "unit" not in found:
            found.append("unit")
        field = str(predicate.get("field") or "")
        if "age" in field and "age_boundary" not in found:
            found.append("age_boundary")
        if "dose" in field or "dosering" in field:
            if "dosage" not in found:
                found.append("dosage")
    md = obj.get("metadata") or {}
    for field in HIGH_RISK_FIELDS:
        value = md.get(field)
        if value not in (None, "", False) and value != [] and field not in found:
            found.append(field)
    return found


def requires_four_eyes(obj: dict[str, Any], *, confirmed_type: str | None = None) -> bool:
    confirmed = confirmed_type or obj.get("confirmed_object_type")
    if confirmed == "exception":
        return True
    risk = obj.get("risk") or obj.get("metadata") or {}
    if (risk.get("risk_level") or (obj.get("metadata") or {}).get("risk_level")) == "high":
        return True
    fields = present_risk_fields(obj)
    if fields:
        return True
    if confirmed == "recommendation" and fields:
        return True
    return False


def mark_four_eyes_on_object(obj: dict[str, Any], *, confirmed_type: str | None = None) -> None:
    confirmed = confirmed_type or obj.get("confirmed_object_type")
    needed = requires_four_eyes(obj, confirmed_type=confirmed)
    risk = obj.setdefault("risk", {})
    fields = present_risk_fields(obj)
    if confirmed == "exception" and "exception" not in fields:
        fields.append("exception")
    risk["risk_fields"] = fields
    if needed:
        if confirmed == "exception" or risk.get("risk_level") == "high":
            risk["risk_level"] = "high"
        else:
            risk.setdefault("risk_level", "standard")
        risk["requires_second_review"] = True
        governance = obj.setdefault("governance", {})
        second = governance.setdefault(
            "second_review",
            {
                "required": True,
                "status": "pending",
                "reviewer": None,
                "review_date": None,
                "snapshot_hash": None,
            },
        )
        second["required"] = True
        if second.get("status") in {None, "not_required"}:
            second["status"] = "pending"
    else:
        risk.setdefault("risk_level", "standard")
        risk.setdefault("requires_second_review", False)


def eligible_tuple_reviewers(
    bindings: Iterable[dict[str, Any]],
    *,
    object_id: str,
    uploader_id: str | None = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in bindings:
        if not row.get("valid"):
            continue
        if row.get("decision") != "approve":
            continue
        if row.get("object_id") != object_id:
            continue
        if reviewer_is_agent(row):
            continue
        reviewer_id = str(row.get("reviewer_id") or row.get("reviewer") or "")
        if not reviewer_id or reviewer_id in seen:
            continue
        seen.add(reviewer_id)
        out.append(row)
    return out


def four_eyes_satisfied(
    bindings: Iterable[dict[str, Any]],
    *,
    object_id: str,
    uploader_id: str,
) -> bool:
    eligible = eligible_tuple_reviewers(bindings, object_id=object_id, uploader_id=uploader_id)
    if len(eligible) < 2:
        return False
    others = [row for row in eligible if str(row.get("reviewer_id")) != str(uploader_id)]
    if not others:
        return False
    return True


def publish_authorization_contract(
    *,
    obj: dict[str, Any],
    bindings: Iterable[dict[str, Any]],
    uploader_id: str,
    immutable_locator: str | None,
    envelope_review_passes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Contract any future publish path MUST check. Does not convert G2 to PASS."""
    blockers: list[str] = []
    object_id = obj.get("object_id") or ""
    eligible = eligible_tuple_reviewers(bindings, object_id=object_id, uploader_id=uploader_id)
    independence = any(str(row.get("reviewer_id")) != str(uploader_id) for row in eligible)
    if not eligible:
        blockers.append("object_tuple_required")
    if not independence:
        blockers.append("second_named_reviewer_required")
    four_eyes_needed = requires_four_eyes(obj)
    four_ok = four_eyes_satisfied(bindings, object_id=object_id, uploader_id=uploader_id) if four_eyes_needed else True
    if four_eyes_needed and not four_ok:
        blockers.append("four_eyes_required")
    # Envelope ticks never authorize publish, even when present.
    _ = envelope_review_passes
    if not immutable_locator:
        blockers.append("blocked_pending_immutable_locator")
    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "object_id": object_id,
        "tuple_authorization": bool(eligible),
        "independence_satisfied": independence,
        "four_eyes_required": four_eyes_needed,
        "four_eyes_satisfied": four_ok if four_eyes_needed else True,
        "envelope_review_passes_authorizes": False,
        "publish_allowed": False,
        "g2": "BLOCKED",
        "blockers": unique_blockers,
    }
