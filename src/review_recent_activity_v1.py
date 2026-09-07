"""Read-only Review «Recent activity» projection.

Projects existing append-only / hash-chained ledger events and existing
review-decision fields (reviewer, decision, comment, proposed correction)
plus the current document envelope upload fact. Newest first; document-
scoped only. This module does not write the ledger or any store.
"""
from __future__ import annotations

from typing import Any, Iterable


TYPE_LABELS = {
    "unclassified": "Nog niet geclassificeerd",
    "factual_finding": "Feitelijke constatering",
    "heading": "Kop",
    "definition": "Definitie",
    "explanation": "Toelichting",
    "condition": "Voorwaarde",
    "exception": "Uitzondering",
    "recommendation": "Aanbeveling",
    "path": "Pad",
    "node": "Knoop",
    "outcome": "Uitkomst",
}

_TYPE_PAIRS = (
    ("from_type", "to_type"),
    ("from_object_type", "to_object_type"),
    ("previous_type", "confirmed_object_type"),
)

_DECISIONS = ("approve", "revise", "reject")


def _actor_label(actor: str, accounts: Iterable[dict[str, Any]] | None) -> str:
    wanted = (actor or "").strip()
    if not wanted:
        return ""
    for row in accounts or ():
        if row.get("username") == wanted or row.get("account_id") == wanted:
            return str(row.get("display_name") or wanted)
    return wanted


def _event_in_document(
    event: dict[str, Any],
    snapshot_id: str,
    object_ids: set[str],
) -> bool:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    if details.get("snapshot_id") == snapshot_id:
        return True
    object_id = event.get("object_id")
    return object_id == snapshot_id or object_id in object_ids


def _decision_of(event_type: str) -> str | None:
    text = (event_type or "").strip()
    for decision in _DECISIONS:
        if text.endswith(f"_review_{decision}") or text.endswith(f"review_{decision}"):
            return decision
    return None


def _type_pair(details: dict[str, Any]) -> tuple[str, str] | None:
    for left_key, right_key in _TYPE_PAIRS:
        left = str(details.get(left_key) or "").strip()
        right = str(details.get(right_key) or "").strip()
        if left and right and left != right:
            return left, right
    return None


def _type_label(value: str) -> str:
    return TYPE_LABELS.get(value, value)


def _summary(row: dict[str, Any]) -> str:
    actor = str(row.get("actor_label") or row.get("actor") or "")
    if row.get("source") == "envelope" or row.get("event_type") == "document_uploaded":
        return f"{actor} heeft het document ingeleverd"
    pair = _type_pair(row.get("details") or {})
    if pair:
        return f"{actor} wijzigde type {_type_label(pair[0])}→{_type_label(pair[1])}"
    decision = row.get("decision")
    object_id = str(row.get("object_id") or "")
    if decision == "approve":
        return f"{actor} keurde object {object_id} goed"
    if decision == "revise":
        return f"{actor} vroeg om herziening"
    if decision == "reject":
        return f"{actor} wees object {object_id} af"
    event_type = str(row.get("event_type") or "")
    if event_type == "document_class_changed":
        return f"{actor} wijzigde de documentklasse"
    if event_type == "revision_created":
        return f"{actor} maakte een revisie"
    if event_type:
        return f"{actor} · {event_type}"
    return actor


def document_activity_rows(
    *,
    events: Iterable[dict[str, Any]] | None,
    snapshot_id: str,
    object_ids: Iterable[str] | None,
    envelope: dict[str, Any] | None = None,
    accounts: Iterable[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return newest-first document-scoped activity rows. Read-only."""
    known_ids = {str(item) for item in (object_ids or ()) if str(item)}
    rows: list[dict[str, Any]] = []
    for index, event in enumerate(events or ()):
        if not _event_in_document(event, snapshot_id, known_ids):
            continue
        details = dict(event["details"]) if isinstance(event.get("details"), dict) else {}
        actor = str(event.get("actor") or "")
        row = {
            "source": "ledger",
            "event_type": str(event.get("event_type") or ""),
            "object_id": str(event.get("object_id") or ""),
            "object_version": str(event.get("object_version") or ""),
            "actor": actor,
            "actor_label": _actor_label(actor, accounts),
            "occurred_at": str(event.get("occurred_at") or ""),
            "details": details,
            "decision": _decision_of(str(event.get("event_type") or "")),
            "comment": str(details.get("comment") or ""),
            "proposed_correction": str(details.get("proposed_correction") or ""),
            "_index": index,
        }
        row["summary"] = _summary(row)
        rows.append(row)

    if envelope and envelope.get("acquired_at"):
        already = any(row.get("event_type") == "document_uploaded" for row in rows)
        if not already:
            uploader = str(envelope.get("uploader_account_id") or "")
            upload = {
                "source": "envelope",
                "event_type": "document_uploaded",
                "object_id": str(envelope.get("snapshot_id") or snapshot_id),
                "object_version": str(envelope.get("version") or ""),
                "actor": uploader,
                "actor_label": _actor_label(uploader, accounts),
                "occurred_at": str(envelope.get("acquired_at") or ""),
                "details": {"snapshot_id": snapshot_id},
                "decision": None,
                "comment": "",
                "proposed_correction": "",
                "_index": -1,
            }
            upload["summary"] = _summary(upload)
            rows.append(upload)

    rows.sort(key=lambda row: (str(row.get("occurred_at") or ""), int(row.get("_index") or 0)), reverse=True)
    for row in rows:
        row.pop("_index", None)
    return rows
