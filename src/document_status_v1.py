"""One derived, user-facing document status over existing workflow truth.

No status in this module is persisted. Publication readiness remains owned by
the existing review/publication gate chain; this layer only reads that result
for presentation in workflow rooms.
"""
from __future__ import annotations

from typing import Any


DOCUMENT_STATUS_LABELS = {
    "processing": "in verwerking",
    "in_review": "in review",
    "blocked": "geblokkeerd",
    "ready_for_publication": "klaar voor publicatie",
    "published": "gepubliceerd",
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
    """Expose deterministic document status without action authorization."""

    def document_readiness(self, snapshot_id: str) -> dict[str, Any]:
        """Read the shared publication-readiness contract without impersonation."""
        return self.publication_readiness(snapshot_id)  # type: ignore[attr-defined]

    def document_status(self, snapshot_id: str) -> str:
        envelope = self._envelope(snapshot_id)  # type: ignore[attr-defined]
        readiness = self.document_readiness(snapshot_id)
        return derive_document_status(
            envelope_state=str(envelope.get("state") or ""),
            readiness=readiness,
        )
