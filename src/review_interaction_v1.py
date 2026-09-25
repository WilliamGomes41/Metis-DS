"""D5.4 review-interaction evidence and burden projection.

This module records evidence about committed human review interactions. It does
not grant review authority, create ReviewDuties, or change KnowledgeObjects.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable
from uuid import uuid4

from src.integrity_kernel import compute_canonical_object_hash, stable_hash
from src.review_context_v1 import review_context

REVIEW_INTERACTION_VERSION = "review-interaction-v1"
REVIEW_INTERACTION_KINDS = frozenset(
    {"structure", "contextual", "batch", "second_review"}
)
REVIEW_INTERACTION_PREFIX = "ri_"


def new_review_interaction_id() -> str:
    return REVIEW_INTERACTION_PREFIX + uuid4().hex


def _tuple(obj: dict[str, Any]) -> dict[str, str]:
    return {
        "object_id": str(obj.get("object_id") or ""),
        "object_version": str(obj.get("object_version") or ""),
        "canonical_object_hash": compute_canonical_object_hash(obj),
        "confirmed_object_type": str(
            obj.get("confirmed_object_type")
            or obj.get("object_type")
            or ""
        ),
    }


def _context_manifest(
    focal: dict[str, Any],
    *,
    objects: Iterable[dict[str, Any]],
    review_path: str,
    stage: str,
) -> dict[str, Any]:
    rows = list(objects)
    current_by_id = {
        str(row.get("object_id") or ""): row
        for row in rows
        if str(row.get("object_id") or "")
    }
    context = review_context(
        focal,
        objects=rows,
        review_path=review_path,
        stage=stage,
    )
    links: list[dict[str, Any]] = []
    for link in context.get("links") or []:
        source = link.get("source") if isinstance(link.get("source"), dict) else {}
        target = link.get("target") if isinstance(link.get("target"), dict) else {}
        links.append(
            {
                "relation_id": str(link.get("relation_id") or ""),
                "relation_type": str(link.get("relation_type") or ""),
                "authority": str(link.get("authority") or ""),
                "direction": str(link.get("direction") or ""),
                "resolution": str(link.get("resolution") or ""),
                "source": {
                    "object_id": str(source.get("object_id") or ""),
                    "expected_version": str(source.get("expected_version") or ""),
                    "current_version": str(source.get("current_version") or ""),
                    "resolution": str(source.get("resolution") or ""),
                    "current_canonical_object_hash": (
                        compute_canonical_object_hash(
                            current_by_id[str(source.get("object_id") or "")]
                        )
                        if str(source.get("object_id") or "") in current_by_id
                        else ""
                    ),
                },
                "target": {
                    "object_id": str(target.get("object_id") or ""),
                    "expected_version": str(target.get("expected_version") or ""),
                    "current_version": str(target.get("current_version") or ""),
                    "resolution": str(target.get("resolution") or ""),
                    "current_canonical_object_hash": (
                        compute_canonical_object_hash(
                            current_by_id[str(target.get("object_id") or "")]
                        )
                        if str(target.get("object_id") or "") in current_by_id
                        else ""
                    ),
                },
            }
        )
    return {
        "focal": _tuple(focal),
        "links": links,
        "issues": deepcopy(context.get("issues") or []),
    }


def build_review_interaction_evidence(
    *,
    interaction_id: str,
    interaction_kind: str,
    reviewer_account_id: str,
    snapshot_id: str,
    review_stage: str,
    focal: dict[str, Any] | None = None,
    objects: Iterable[dict[str, Any]] = (),
    review_path: str = "",
    members: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    interaction_id = str(interaction_id or "").strip()
    if not interaction_id.startswith(REVIEW_INTERACTION_PREFIX):
        raise ValueError("review_interaction_id_invalid")
    if interaction_kind not in REVIEW_INTERACTION_KINDS:
        raise ValueError("review_interaction_kind_invalid")
    reviewer_account_id = str(reviewer_account_id or "").strip()
    snapshot_id = str(snapshot_id or "").strip()
    if not reviewer_account_id or not snapshot_id:
        raise ValueError("review_interaction_identity_invalid")

    member_rows = [_tuple(row) for row in members]
    manifest: dict[str, Any]
    if interaction_kind in {"contextual", "second_review"}:
        if focal is None:
            raise ValueError("review_interaction_focal_required")
        manifest = _context_manifest(
            focal,
            objects=objects,
            review_path=review_path,
            stage=review_stage,
        )
    else:
        if not member_rows:
            if focal is None:
                raise ValueError("review_interaction_members_required")
            member_rows = [_tuple(focal)]
        manifest = {"members": member_rows}

    return {
        "version": REVIEW_INTERACTION_VERSION,
        "interaction_id": interaction_id,
        "interaction_kind": interaction_kind,
        "canonical_task": interaction_kind,
        "snapshot_id": snapshot_id,
        "reviewer_account_id": reviewer_account_id,
        "review_stage": str(review_stage or ""),
        "requested_count": len(member_rows) if member_rows else 1,
        "context_manifest": manifest,
        "context_manifest_hash": stable_hash(manifest),
    }


def validate_review_interaction_identity(
    evidence: dict[str, Any],
    events: Iterable[dict[str, Any]],
) -> None:
    """Reject reuse of one id for a different reviewer/snapshot/task."""

    interaction_id = str(evidence.get("interaction_id") or "")
    identity = (
        str(evidence.get("reviewer_account_id") or ""),
        str(evidence.get("snapshot_id") or ""),
        str(evidence.get("canonical_task") or ""),
    )
    for event in events:
        details = event.get("details")
        if not isinstance(details, dict):
            continue
        prior = details.get("review_interaction")
        if not isinstance(prior, dict):
            continue
        if str(prior.get("interaction_id") or "") != interaction_id:
            continue
        prior_identity = (
            str(prior.get("reviewer_account_id") or ""),
            str(prior.get("snapshot_id") or ""),
            str(prior.get("canonical_task") or ""),
        )
        if prior_identity != identity:
            raise ValueError("review_interaction_identity_conflict")


def _is_decision_event(event: dict[str, Any]) -> bool:
    event_type = str(event.get("event_type") or "")
    if event_type == "second_review_approve":
        return True
    return (
        event_type.endswith("_review_approve")
        or event_type.endswith("_review_revise")
        or event_type.endswith("_review_reject")
    )


def review_burden_projection(
    events: Iterable[dict[str, Any]],
    *,
    snapshot_id: str = "",
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    legacy_unmeasured = 0
    invalid_evidence = 0

    for event in events:
        if not _is_decision_event(event):
            continue
        details = event.get("details")
        details = details if isinstance(details, dict) else {}
        event_snapshot = str(details.get("snapshot_id") or "")
        if snapshot_id and event_snapshot and event_snapshot != snapshot_id:
            continue
        evidence = details.get("review_interaction")
        if not isinstance(evidence, dict):
            if not snapshot_id or event_snapshot == snapshot_id:
                legacy_unmeasured += 1
            continue
        if str(evidence.get("version") or "") != REVIEW_INTERACTION_VERSION:
            invalid_evidence += 1
            continue
        if snapshot_id and str(evidence.get("snapshot_id") or "") != snapshot_id:
            continue
        manifest = evidence.get("context_manifest")
        if (
            not isinstance(manifest, dict)
            or str(evidence.get("context_manifest_hash") or "") != stable_hash(manifest)
        ):
            invalid_evidence += 1
            continue

        interaction_id = str(evidence.get("interaction_id") or "")
        if not interaction_id:
            continue
        row = grouped.setdefault(
            interaction_id,
            {
                "interaction_id": interaction_id,
                "interaction_kind": str(evidence.get("interaction_kind") or ""),
                "reviewer_account_id": str(
                    evidence.get("reviewer_account_id") or ""
                ),
                "requested_count": int(evidence.get("requested_count") or 1),
                "decisions": set(),
            },
        )
        row["requested_count"] = max(
            int(row["requested_count"]),
            int(evidence.get("requested_count") or 1),
        )
        row["decisions"].add(
            (
                str(event.get("object_id") or ""),
                str(event.get("object_version") or ""),
                str(event.get("event_type") or ""),
            )
        )

    interactions: list[dict[str, Any]] = []
    for row in grouped.values():
        committed = len(row["decisions"])
        requested = int(row["requested_count"])
        interactions.append(
            {
                "interaction_id": row["interaction_id"],
                "interaction_kind": row["interaction_kind"],
                "reviewer_account_id": row["reviewer_account_id"],
                "requested_count": requested,
                "committed_decisions": committed,
                "outcome": "partial" if committed < requested else "complete",
            }
        )
    interactions.sort(key=lambda row: row["interaction_id"])

    by_kind = {
        kind: sum(row["interaction_kind"] == kind for row in interactions)
        for kind in sorted(REVIEW_INTERACTION_KINDS)
    }
    object_decisions = sum(row["committed_decisions"] for row in interactions)
    interaction_count = len(interactions)
    return {
        "review_interactions": interaction_count,
        "object_decisions": object_decisions,
        "objects_per_interaction": (
            object_decisions / interaction_count if interaction_count else 0.0
        ),
        "partial_batch_interactions": sum(
            row["interaction_kind"] in {"batch", "structure"}
            and row["outcome"] == "partial"
            for row in interactions
        ),
        "legacy_unmeasured_decisions": legacy_unmeasured,
        "invalid_evidence_events": invalid_evidence,
        "by_kind": by_kind,
        "interactions": interactions,
    }
