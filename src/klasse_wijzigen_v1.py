"""Protocol v2.26 first wave: Klasse wijzigen helpers.

Same-model vs cross-model matrix. Selective invalidation is later code.
"""
from __future__ import annotations

from typing import Any

from src.beslisboom_path_v1 import CLOSED_KLASSEN, review_path_for_klasse

DOCUMENT_CLASS_CHANGED_EVENT = "document_class_changed"
RICHTLIJN_PATH_KLASSEN = frozenset(CLOSED_KLASSEN) - {"beslisboom"}


def review_model_for_klasse(klasse: str) -> str:
    return review_path_for_klasse(klasse)


def is_cross_model_class_change(from_class: str, to_class: str) -> bool:
    return review_model_for_klasse(from_class) != review_model_for_klasse(to_class)


def class_change_consequence(from_class: str, to_class: str) -> dict[str, Any]:
    cross = is_cross_model_class_change(from_class, to_class)
    return {
        "source_unchanged": True,
        "model": "cross_model" if cross else "same_model",
        "objects": "re_extract_required" if cross else "kept",
        "review": "full_re_review",
        "direct_change_allowed": not cross,
        "from_class": from_class,
        "to_class": to_class,
    }


def source_identity_fields(envelope: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha256": envelope.get("sha256"),
        "title": envelope.get("title"),
        "version": envelope.get("version"),
        "locator": envelope.get("locator"),
        "source_id": envelope.get("source_id"),
        "live_url": envelope.get("live_url"),
        "immutable_storage_locator": envelope.get("immutable_storage_locator"),
        "binary_path": envelope.get("binary_path"),
        "date": envelope.get("date"),
    }
