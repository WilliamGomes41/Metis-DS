"""D3.1 canonical recommendation-semantics contract.

This module is deliberately pure. It defines the new-format value object and
read-only legacy compatibility projection. It does not infer semantics from
source text, mutate canonical objects, perform review confirmation, or serve
recommendations.
"""
from __future__ import annotations

from typing import Any


RECOMMENDATION_SEMANTICS_VERSION = "recommendation-semantics-v1"
DIRECTIONS = ("for", "against")
STRENGTHS = ("strong", "weak")
STRENGTH_STATUSES = ("explicit", "not_stated", "unmapped")
NORMALIZATION_SCHEMES = ("source_literal_v1",)

PROPOSED_FIELD = "proposed_recommendation_semantics"
CONFIRMED_FIELD = "confirmed_recommendation_semantics"
LEGACY_PROPOSED_FIELD = "proposed_recommendation_strength"
LEGACY_CONFIRMED_FIELD = "confirmed_recommendation_strength"

_REQUIRED_KEYS = frozenset(
    {
        "version",
        "direction",
        "strength",
        "strength_status",
        "direction_evidence_span",
        "strength_evidence_span",
        "source_label",
        "normalization_scheme",
    }
)

_LEGACY_MAP = {
    "doen": ("for", "strong", "DOEN"),
    "overweeg": ("for", "weak", "OVERWEEG"),
    "niet_doen": ("against", "strong", "NIET DOEN"),
}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_recommendation_semantics(
    value: Any,
    *,
    confirmed: bool = False,
) -> list[str]:
    """Validate one semantics value object without mutating it."""

    if not isinstance(value, dict):
        return ["recommendation_semantics_not_object"]

    errors: list[str] = []
    keys = set(value)
    missing = sorted(_REQUIRED_KEYS - keys)
    unknown = sorted(keys - _REQUIRED_KEYS)
    errors.extend(f"recommendation_semantics_missing:{key}" for key in missing)
    errors.extend(f"recommendation_semantics_unknown:{key}" for key in unknown)

    if value.get("version") != RECOMMENDATION_SEMANTICS_VERSION:
        errors.append("recommendation_semantics_version_invalid")

    if value.get("direction") not in DIRECTIONS:
        errors.append("recommendation_direction_invalid")
    if not _nonempty_string(value.get("direction_evidence_span")):
        errors.append("recommendation_direction_evidence_missing")

    status = value.get("strength_status")
    strength = value.get("strength")
    evidence = value.get("strength_evidence_span")
    source_label = value.get("source_label")

    if status not in STRENGTH_STATUSES:
        errors.append("recommendation_strength_status_invalid")
    elif status == "explicit":
        if strength not in STRENGTHS:
            errors.append("recommendation_strength_invalid")
        if not _nonempty_string(evidence):
            errors.append("recommendation_strength_evidence_missing")
    elif status == "not_stated":
        if strength is not None:
            errors.append("recommendation_strength_must_be_null_when_not_stated")
        if evidence is not None:
            errors.append("recommendation_strength_evidence_forbidden_when_not_stated")
    elif status == "unmapped":
        if confirmed:
            errors.append("confirmed_recommendation_strength_unmapped")
        if strength is not None:
            errors.append("recommendation_strength_must_be_null_when_unmapped")
        if not _nonempty_string(evidence):
            errors.append("recommendation_strength_evidence_missing")
        if not _nonempty_string(source_label):
            errors.append("recommendation_source_label_missing_when_unmapped")

    if source_label is not None and not isinstance(source_label, str):
        errors.append("recommendation_source_label_invalid")

    if value.get("normalization_scheme") not in NORMALIZATION_SCHEMES:
        errors.append("recommendation_normalization_scheme_invalid")

    return errors


def recommendation_semantics_errors(obj: dict[str, Any]) -> list[str]:
    """Validate object-level authority and type binding for D3.1 fields."""

    errors: list[str] = []

    if PROPOSED_FIELD in obj:
        errors.extend(
            f"proposed:{error}"
            for error in validate_recommendation_semantics(
                obj.get(PROPOSED_FIELD),
                confirmed=False,
            )
        )
        if str(obj.get("proposed_object_type") or "") != "recommendation":
            errors.append("proposed_recommendation_semantics_requires_recommendation_type")
        if LEGACY_PROPOSED_FIELD in obj:
            errors.append("proposed_recommendation_semantics_legacy_authority_conflict")

    if CONFIRMED_FIELD in obj:
        errors.extend(
            f"confirmed:{error}"
            for error in validate_recommendation_semantics(
                obj.get(CONFIRMED_FIELD),
                confirmed=True,
            )
        )
        if str(obj.get("confirmed_object_type") or "") != "recommendation":
            errors.append("confirmed_recommendation_semantics_requires_recommendation_type")
        if LEGACY_CONFIRMED_FIELD in obj:
            errors.append("confirmed_recommendation_semantics_legacy_authority_conflict")

    return errors


def proposed_recommendation_semantics_of(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get(PROPOSED_FIELD)
    return dict(value) if isinstance(value, dict) else {}


def confirmed_recommendation_semantics_of(obj: dict[str, Any]) -> dict[str, Any]:
    """Return only persisted new-format confirmed semantics.

    Legacy values are intentionally not promoted through this accessor.
    """

    value = obj.get(CONFIRMED_FIELD)
    return dict(value) if isinstance(value, dict) else {}


def legacy_recommendation_semantics_view(
    obj: dict[str, Any],
    *,
    confirmed: bool = True,
) -> dict[str, Any]:
    """Return a non-persisted compatibility view of one legacy stamp value."""

    field = LEGACY_CONFIRMED_FIELD if confirmed else LEGACY_PROPOSED_FIELD
    raw = str(obj.get(field) or "").strip()
    mapped = _LEGACY_MAP.get(raw)
    if mapped is None:
        return {}
    direction, strength, label = mapped
    return {
        "authority": "legacy_compatibility",
        "persisted": False,
        "legacy_field": field,
        "legacy_value": raw,
        "direction": direction,
        "strength": strength,
        "strength_status": "explicit",
        "source_label": label,
    }
