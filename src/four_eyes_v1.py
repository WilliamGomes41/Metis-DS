"""High-risk four-eyes authorization on the Protocol v2.12 object tuple.

Four-eyes is an additional required reviewer on the exact object tuple.
It does not replace the tuple. Envelope review_passes MUST NOT authorize
publish. AI / Grok Bot / Metis / Implementation engineer / Auditor MUST NOT
count. Uploader MUST NOT be the only required reviewer. publish() remains
G2-BLOCKED.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.g2_source_store import is_g2_locator

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
    for key in ("reviewer", "username", "display_name", "reviewer_id", "reviewer_account_id", "account_id"):
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
    """Policy with two required reviewers, or content that demands two approvals.

    Content-bound four eyes holds regardless of the review policy (besluit William
    2026-10-23): a policy can raise the requirement, never lower it.
    """
    from src.review_policy_v1 import object_policy, required_reviewers
    policy = object_policy(obj)
    if policy is not None and len(required_reviewers(policy)) > 1:
        return True
    return content_requires_four_eyes(obj, confirmed_type=confirmed_type)


def historical_requires_four_eyes(obj: dict[str, Any], *, confirmed_type: str | None = None) -> bool:
    """The rule before 2026-10-23, where a policy replaced the content check.

    Only for re-verifying releases that were published under that rule.
    """
    from src.review_policy_v1 import object_policy, required_reviewers
    policy = object_policy(obj)
    if policy is not None:
        return len(required_reviewers(policy)) > 1
    return content_requires_four_eyes(obj, confirmed_type=confirmed_type)


def content_requires_four_eyes(obj: dict[str, Any], *, confirmed_type: str | None = None) -> bool:
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
    from src.review_policy_v1 import object_policy, MANAGED_CONTRACT
    policy = object_policy(obj)
    confirmed = confirmed_type or obj.get("confirmed_object_type")
    needed = requires_four_eyes(obj, confirmed_type=confirmed)
    risk = obj.setdefault("risk", {})
    fields = present_risk_fields(obj)
    if confirmed == "exception" and "exception" not in fields:
        fields.append("exception")
    risk["risk_fields"] = fields
    if policy and policy["contract"] == MANAGED_CONTRACT:
        # Risk facts still follow content/type changes. Membership itself does
        # not rewrite hash-bound risk flags; gates read effective governance.
        return
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
        from src.review_policy_v1 import object_policy
        if object_policy(obj) is not None:
            risk["requires_second_review"] = False
            obj.setdefault("governance", {})["second_review"] = {
                "required": False, "status": "not_required", "reviewer": None,
                "review_date": None, "snapshot_hash": None,
            }
        else:
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


# D-SEC-3: de enige contractblocker die de console zelf afhandelt (met de echte
# G2-readback). Elke andere contractblocker MOET publicatie weigeren. Deze set
# MAG NIET breder worden zonder contractwijziging en test.
CONSOLE_VERIFIED_BLOCKERS = frozenset({"blocked_pending_immutable_locator"})


def publish_authorization_contract(
    *,
    obj: dict[str, Any],
    bindings: Iterable[dict[str, Any]],
    uploader_id: str,
    immutable_locator: str | None,
    envelope_review_passes: dict[str, Any] | None = None,
    review_path: str = "richtlijn",
    fragments: Iterable[dict[str, Any]] | None = None,
    review_configuration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Contract any future publish path MUST check. Does not convert G2 to PASS."""
    bindings = list(bindings)
    blockers: list[str] = []
    if not isinstance(uploader_id, str) or not uploader_id.strip():
        # Sherlock-voorwaarde 3: zonder uploader-identiteit MOET de poort dicht.
        blockers.append("uploader_identity_missing")
        uploader_id = ""
    object_id = obj.get("object_id") or ""
    eligible = eligible_tuple_reviewers(bindings, object_id=object_id, uploader_id=uploader_id)
    from src.knowledge_path_v1 import knowledge_publication_blockers
    from src.admission_gate_v1 import is_boom_object
    if review_path == "boom":
        knowledge_blockers = [] if is_boom_object(obj) else ["invalid_boom_object"]
    elif review_path == "richtlijn":
        knowledge_blockers = knowledge_publication_blockers(obj, fragments=fragments)
    else:
        knowledge_blockers = ["invalid_review_path"]
    if knowledge_blockers:
        eligible = []
        blockers.extend(knowledge_blockers)
    else:
        from src.review_duty_v1 import exact_current_approver_ids
        current_ids = set(exact_current_approver_ids(obj, bindings))
        eligible = [
            row
            for row in eligible
            if str(row.get("reviewer_id") or "") in current_ids
        ]
    independence = any(str(row.get("reviewer_id")) != str(uploader_id) for row in eligible)
    from src.review_policy_v1 import object_policy, missing_reviewers
    policy = object_policy(obj)
    if policy is not None:
        missing = missing_reviewers(obj, eligible)
        independence = not missing
        if missing:
            blockers.append("required_policy_review_missing")
    configured = None
    if policy is None and review_configuration is not None and review_configuration.get("source") == "chosen":
        from src.review_configuration_v1 import configured_approval, validate_configuration
        try:
            configured = validate_configuration(review_configuration, uploader_id=uploader_id)
        except ValueError:
            blockers.append("review_configuration_invalid")
            independence = False
        else:
            approver_ids = {str(row.get("reviewer_id") or "") for row in eligible}
            independence, configured_four_ok = configured_approval(configured, approver_ids, uploader_id=uploader_id)
            if not independence:
                blockers.append("review_configuration_approval_missing")
    if not eligible:
        blockers.append("object_tuple_required")
    if policy is None and configured is None and not independence:
        blockers.append("second_named_reviewer_required")
    four_eyes_needed = requires_four_eyes(obj) or bool(configured and configured["four_eyes_required"])
    four_ok = four_eyes_satisfied(eligible, object_id=object_id, uploader_id=uploader_id) if four_eyes_needed else True
    if policy is not None:
        # Required reviewers first; content-bound four eyes also needs two
        # distinct approvers, one of them not the uploader.
        four_ok = not missing and (not content_requires_four_eyes(obj) or four_eyes_satisfied(
            eligible, object_id=object_id, uploader_id=uploader_id))
    elif configured is not None:
        four_ok = configured_four_ok
    if four_eyes_needed and not four_ok:
        blockers.append("four_eyes_required")
        if configured is not None and configured["option"] == "uploader_sole":
            # OPENVRAAG-2b3-1: hoe een tweede reviewer wordt toegevoegd, beslist William.
            blockers.append("review_configuration_uploader_sole_high_risk")
    # Envelope ticks never authorize publish, even when present.
    _ = envelope_review_passes
    if not is_g2_locator(immutable_locator):
        blockers.append("blocked_pending_immutable_locator")
    unique_blockers = list(dict.fromkeys(blockers))
    authorization_blockers = [code for code in unique_blockers if code not in CONSOLE_VERIFIED_BLOCKERS]
    return {
        "authorization_blockers": authorization_blockers,
        "authorization_ok": not authorization_blockers,
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
