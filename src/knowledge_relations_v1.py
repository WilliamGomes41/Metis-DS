"""D4.1 canonical KnowledgeRelation contract.

This module is deliberately pure. It defines the new-format, version-bound
relation value object, deterministic identity/canonical ordering, and read-only
legacy compatibility views.

It does not infer relations from source text, mutate canonical objects, perform
review confirmation, migrate legacy relation fields, or serve relations.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable

from src.serving_relations_v1 import CLOSED_RELATION_SET, serving_relation_type


KNOWLEDGE_RELATION_VERSION = "knowledge-relation-v1"

PROPOSED_FIELD = "proposed_knowledge_relations"
CONFIRMED_FIELD = "confirmed_knowledge_relations"
LEGACY_PROPOSED_FIELD = "relations"
LEGACY_CONFIRMED_FIELD = "confirmed_relations"

SEMANTIC_RELATION_TYPES = frozenset(
    {
        "applies_if",
        "except_if",
        "defines",
        "explains",
        "supported_by",
        "supersedes",
    }
)
STRUCTURAL_RELATION_TYPES = frozenset({"parent", "child"})

_REQUIRED_KEYS = frozenset(
    {
        "version",
        "relation_id",
        "relation_type",
        "target_object_id",
        "target_object_version",
    }
)


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def relation_kind(relation_type: str | None) -> str | None:
    """Return semantic/structural for one serving-law relation type."""

    served = serving_relation_type(relation_type)
    if served in SEMANTIC_RELATION_TYPES:
        return "semantic"
    if served in STRUCTURAL_RELATION_TYPES:
        return "structural"
    return None


def relation_identity_payload(
    *,
    source_object_id: str,
    source_object_version: str,
    relation_type: str,
    target_object_id: str,
    target_object_version: str,
) -> dict[str, str]:
    """Return the exact version-bound identity payload for one relation."""

    return {
        "version": KNOWLEDGE_RELATION_VERSION,
        "source_object_id": str(source_object_id),
        "source_object_version": str(source_object_version),
        "relation_type": str(relation_type),
        "target_object_id": str(target_object_id),
        "target_object_version": str(target_object_version),
    }


def relation_id_for(
    *,
    source_object_id: str,
    source_object_version: str,
    relation_type: str,
    target_object_id: str,
    target_object_version: str,
) -> str:
    """Return deterministic relation identity for exact endpoint versions."""

    digest = hashlib.sha256(
        _canonical_json(
            relation_identity_payload(
                source_object_id=source_object_id,
                source_object_version=source_object_version,
                relation_type=relation_type,
                target_object_id=target_object_id,
                target_object_version=target_object_version,
            )
        )
    ).hexdigest()
    return f"rel-{digest}"


def build_knowledge_relation(
    *,
    source_object_id: str,
    source_object_version: str,
    relation_type: str,
    target_object_id: str,
    target_object_version: str,
) -> dict[str, str]:
    """Build one canonical new-format relation value object.

    The source endpoint is owned by the containing KnowledgeObject and is
    therefore not duplicated inside the embedded relation value.
    """

    served = str(relation_type or "").strip()
    if served not in CLOSED_RELATION_SET:
        raise ValueError("knowledge_relation_type_invalid")
    if not _nonempty_string(source_object_id):
        raise ValueError("knowledge_relation_source_object_id_missing")
    if not _nonempty_string(source_object_version):
        raise ValueError("knowledge_relation_source_object_version_missing")
    if not _nonempty_string(target_object_id):
        raise ValueError("knowledge_relation_target_object_id_missing")
    if not _nonempty_string(target_object_version):
        raise ValueError("knowledge_relation_target_object_version_missing")
    if str(source_object_id).strip() == str(target_object_id).strip():
        raise ValueError("knowledge_relation_self_relation")

    value = {
        "version": KNOWLEDGE_RELATION_VERSION,
        "relation_id": relation_id_for(
            source_object_id=str(source_object_id).strip(),
            source_object_version=str(source_object_version).strip(),
            relation_type=served,
            target_object_id=str(target_object_id).strip(),
            target_object_version=str(target_object_version).strip(),
        ),
        "relation_type": served,
        "target_object_id": str(target_object_id).strip(),
        "target_object_version": str(target_object_version).strip(),
    }
    return value


def validate_knowledge_relation(
    value: Any,
    *,
    source_object_id: str,
    source_object_version: str,
) -> list[str]:
    """Validate one version-bound relation value without mutating it."""

    if not isinstance(value, dict):
        return ["knowledge_relation_not_object"]

    errors: list[str] = []
    keys = set(value)
    missing = sorted(_REQUIRED_KEYS - keys)
    unknown = sorted(keys - _REQUIRED_KEYS)
    errors.extend(f"knowledge_relation_missing:{key}" for key in missing)
    errors.extend(f"knowledge_relation_unknown:{key}" for key in unknown)

    if value.get("version") != KNOWLEDGE_RELATION_VERSION:
        errors.append("knowledge_relation_version_invalid")

    relation_type = str(value.get("relation_type") or "").strip()
    if relation_type not in CLOSED_RELATION_SET:
        errors.append("knowledge_relation_type_invalid")

    target_id = value.get("target_object_id")
    target_version = value.get("target_object_version")
    if not _nonempty_string(target_id):
        errors.append("knowledge_relation_target_object_id_missing")
    if not _nonempty_string(target_version):
        errors.append("knowledge_relation_target_object_version_missing")

    if not _nonempty_string(source_object_id):
        errors.append("knowledge_relation_source_object_id_missing")
    if not _nonempty_string(source_object_version):
        errors.append("knowledge_relation_source_object_version_missing")

    if (
        _nonempty_string(source_object_id)
        and _nonempty_string(target_id)
        and str(source_object_id).strip() == str(target_id).strip()
    ):
        errors.append("knowledge_relation_self_relation")

    if (
        relation_type in CLOSED_RELATION_SET
        and _nonempty_string(source_object_id)
        and _nonempty_string(source_object_version)
        and _nonempty_string(target_id)
        and _nonempty_string(target_version)
    ):
        expected = relation_id_for(
            source_object_id=str(source_object_id).strip(),
            source_object_version=str(source_object_version).strip(),
            relation_type=relation_type,
            target_object_id=str(target_id).strip(),
            target_object_version=str(target_version).strip(),
        )
        if value.get("relation_id") != expected:
            errors.append("knowledge_relation_id_mismatch")
    elif not _nonempty_string(value.get("relation_id")):
        errors.append("knowledge_relation_id_missing")

    return errors


def relation_sort_key(value: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(value.get("relation_type") or ""),
        str(value.get("target_object_id") or ""),
        str(value.get("target_object_version") or ""),
        str(value.get("relation_id") or ""),
    )


def _semantic_key(value: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(value.get("relation_type") or ""),
        str(value.get("target_object_id") or ""),
        str(value.get("target_object_version") or ""),
    )


def validate_knowledge_relation_set(
    value: Any,
    *,
    source_object_id: str,
    source_object_version: str,
    require_canonical_order: bool = True,
) -> list[str]:
    """Validate one relation set, including uniqueness and canonical ordering."""

    if not isinstance(value, list):
        return ["knowledge_relation_set_not_array"]

    errors: list[str] = []
    semantic_keys: set[tuple[str, str, str]] = set()
    valid_rows: list[dict[str, Any]] = []

    for index, row in enumerate(value):
        row_errors = validate_knowledge_relation(
            row,
            source_object_id=source_object_id,
            source_object_version=source_object_version,
        )
        errors.extend(f"{index}:{error}" for error in row_errors)
        if not isinstance(row, dict):
            continue
        valid_rows.append(row)
        key = _semantic_key(row)
        if key in semantic_keys:
            errors.append(f"{index}:knowledge_relation_duplicate")
        semantic_keys.add(key)

    if require_canonical_order and valid_rows:
        actual = [relation_sort_key(row) for row in valid_rows]
        expected = sorted(actual)
        if actual != expected:
            errors.append("knowledge_relation_set_not_canonical_order")

    return errors


def canonicalize_knowledge_relation_set(
    relations: Iterable[dict[str, Any]],
    *,
    source_object_id: str,
    source_object_version: str,
) -> list[dict[str, Any]]:
    """Return a validated, deterministic relation-set ordering."""

    rows = [deepcopy(row) for row in relations]
    errors = validate_knowledge_relation_set(
        rows,
        source_object_id=source_object_id,
        source_object_version=source_object_version,
        require_canonical_order=False,
    )
    if errors:
        raise ValueError("|".join(errors))
    rows.sort(key=relation_sort_key)

    duplicate_errors = validate_knowledge_relation_set(
        rows,
        source_object_id=source_object_id,
        source_object_version=source_object_version,
        require_canonical_order=True,
    )
    if duplicate_errors:
        raise ValueError("|".join(duplicate_errors))
    return rows


def knowledge_relation_set_hash(
    relations: Iterable[dict[str, Any]],
    *,
    source_object_id: str,
    source_object_version: str,
) -> str:
    """Hash the canonical relation set independently of caller input order."""

    canonical = canonicalize_knowledge_relation_set(
        relations,
        source_object_id=source_object_id,
        source_object_version=source_object_version,
    )
    return hashlib.sha256(_canonical_json(canonical)).hexdigest()


def knowledge_relation_errors(obj: dict[str, Any]) -> list[str]:
    """Validate D4.1 object-level authority and version binding."""

    errors: list[str] = []
    source_id = str(obj.get("object_id") or "")
    source_version = str(obj.get("object_version") or "")

    if PROPOSED_FIELD in obj:
        errors.extend(
            f"proposed:{error}"
            for error in validate_knowledge_relation_set(
                obj.get(PROPOSED_FIELD),
                source_object_id=source_id,
                source_object_version=source_version,
            )
        )
        if obj.get(LEGACY_PROPOSED_FIELD):
            errors.append("proposed_knowledge_relations_legacy_authority_conflict")

    if CONFIRMED_FIELD in obj:
        errors.extend(
            f"confirmed:{error}"
            for error in validate_knowledge_relation_set(
                obj.get(CONFIRMED_FIELD),
                source_object_id=source_id,
                source_object_version=source_version,
            )
        )
        if obj.get(LEGACY_CONFIRMED_FIELD):
            errors.append("confirmed_knowledge_relations_legacy_authority_conflict")

    return errors


def proposed_knowledge_relations_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    value = obj.get(PROPOSED_FIELD)
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def confirmed_knowledge_relations_of(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Return only persisted new-format confirmed relations.

    Legacy relation rows are intentionally not promoted through this accessor.
    """

    value = obj.get(CONFIRMED_FIELD)
    if not isinstance(value, list):
        return []
    return [dict(row) for row in value if isinstance(row, dict)]


def legacy_knowledge_relations_view(
    obj: dict[str, Any],
    *,
    confirmed: bool = True,
) -> list[dict[str, Any]]:
    """Return non-persisted compatibility views of legacy relation rows.

    The view never invents a relation_id or missing target version, so callers
    cannot mistake compatibility data for new-format authority.
    """

    field = LEGACY_CONFIRMED_FIELD if confirmed else LEGACY_PROPOSED_FIELD
    rows = obj.get(field)
    if not isinstance(rows, list):
        return []

    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        served = serving_relation_type(raw.get("relation_type"))
        target_id = str(raw.get("target_object_id") or "").strip()
        if served not in CLOSED_RELATION_SET or not target_id:
            continue
        target_version = raw.get("target_object_version")
        out.append(
            {
                "authority": "legacy_compatibility",
                "persisted": False,
                "legacy_field": field,
                "relation_type": served,
                "relation_kind": relation_kind(served),
                "target_object_id": target_id,
                "target_object_version": (
                    str(target_version).strip()
                    if _nonempty_string(target_version)
                    else None
                ),
            }
        )
    return out
