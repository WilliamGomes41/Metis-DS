"""One derived, user-facing document status over existing workflow truth.

No status in this module is persisted. Publication readiness remains owned by
the existing review/publication gate chain; this layer only reads that result
for presentation in workflow rooms.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


DOCUMENT_STATUS_LABELS = {
    "processing": "in verwerking",
    "in_review": "in review",
    "blocked": "geblokkeerd",
    "ready_for_publication": "klaar voor publicatie",
    "published": "gepubliceerd",
}

# Internal object identity, not a user/account identifier. It can only satisfy
# the read-only publisher check while deriving readiness below.
_READ_ONLY_STATUS_ACTOR = object()
_READ_ONLY_STATUS_ACCOUNT = {
    "account_id": "document-status-read",
    "username": "document-status-read",
    "display_name": "document-status-read",
    "roles": ["publisher"],
}


def derive_document_status(
    *,
    envelope_state: str,
    readiness: dict[str, Any],
) -> str:
    """Map existing durable lifecycle + readiness to one presentation state."""
    if envelope_state in {"published", "superseded", "withdrawn"}:
        return "published"
    if readiness.get("publication_ready") is True:
        return "ready_for_publication"
    if readiness.get("curation_ready") is False:
        return "in_review"
    if (
        readiness.get("curation_ready") is True
        and readiness.get("technical_ready") is False
    ):
        return "blocked"
    return "processing"


class DocumentStatusReadinessMixin:
    """Expose deterministic document status without widening action authority."""

    def _require_role(self, account_id: Any, role: str) -> dict[str, Any]:
        if account_id is _READ_ONLY_STATUS_ACTOR and role == "publisher":
            return deepcopy(_READ_ONLY_STATUS_ACCOUNT)
        return super()._require_role(account_id, role)  # type: ignore[misc]

    def document_readiness(self, snapshot_id: str) -> dict[str, Any]:
        """Evaluate the existing publication gates without granting an action role."""
        return self.consider_publish(  # type: ignore[attr-defined]
            actor_id=_READ_ONLY_STATUS_ACTOR,
            snapshot_id=snapshot_id,
        )

    def document_status(self, snapshot_id: str) -> str:
        envelope = self._envelope(snapshot_id)  # type: ignore[attr-defined]
        readiness = self.document_readiness(snapshot_id)
        return derive_document_status(
            envelope_state=str(envelope.get("state") or ""),
            readiness=readiness,
        )

    def list_envelopes(self) -> list[dict[str, Any]]:
        rows = super().list_envelopes()  # type: ignore[misc]
        for row in rows:
            snapshot_id = str(row.get("snapshot_id") or "")
            row["meaningful_status"] = (
                self.document_status(snapshot_id) if snapshot_id else "processing"
            )
        return rows

    def family_tree(self) -> dict[str, Any]:
        tree = super().family_tree()  # type: ignore[misc]
        for node in (tree.get("families") or {}).values():
            for child in node.get("children") or []:
                snapshot_id = str(child.get("snapshot_id") or "")
                child["meaningful_status"] = (
                    self.document_status(snapshot_id) if snapshot_id else "processing"
                )
        return tree
