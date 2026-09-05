"""Per-section passage-register coverage (Protocol v2.30 Phase 4).

No duty to objectify every sentence. Duty remains normative and
application-critical knowledge. Researcher/ops surface uses ordinary Dutch.
"""
from __future__ import annotations

from typing import Any

from src.passage_register_v1 import (
    PASSAGE_REGISTER_STATUSES,
    apply_passage_register,
    passage_register_of,
    section_path_of,
)


DUTCH_STATUS_LABELS = {
    "selected_as_candidate": "Geselecteerd",
    "used_as_context": "Als context gebruikt",
    "linked_as_support": "Als onderbouwing gekoppeld",
    "excluded_with_reason": "Uitgesloten (met reden)",
    "not_yet_assessed": "Nog niet beoordeeld",
}


def _section_key(obj: dict[str, Any]) -> str:
    path = section_path_of(obj)
    if path:
        return path[-1]
    heading = str((obj.get("structure") or {}).get("heading") or "").strip()
    return heading or "Onbekende kop"


def coverage_by_section(objects: list[dict[str, Any]]) -> dict[str, Any]:
    stamped = apply_passage_register(list(objects))
    sections: dict[str, dict[str, Any]] = {}
    for obj in stamped:
        if obj.get("object_type") == "document":
            continue
        key = _section_key(obj)
        row = sections.setdefault(
            key,
            {
                "section": key,
                "section_path": section_path_of(obj),
                "counts": {status: 0 for status in PASSAGE_REGISTER_STATUSES},
                "passages": 0,
            },
        )
        status = passage_register_of(obj).get("status") or "not_yet_assessed"
        if status not in row["counts"]:
            raise ValueError("unknown_passage_register_status")
        row["counts"][status] += 1
        row["passages"] += 1
    return {
        "objectify_every_sentence": False,
        "duty": "normative_application_critical",
        "sections": sections,
    }


def coverage_panel_rows(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    report = coverage_by_section(objects)
    rows: list[dict[str, Any]] = []
    for key, section in report["sections"].items():
        counts = section.get("counts") or {}
        rows.append(
            {
                "section": key,
                "passages": int(section.get("passages") or 0),
                "labels": {
                    DUTCH_STATUS_LABELS[status]: int(counts.get(status) or 0)
                    for status in PASSAGE_REGISTER_STATUSES
                },
            }
        )
    return rows
