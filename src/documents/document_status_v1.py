"""Derived lifecycle read model over existing Metis authorities.

Nothing in this module is persisted. Workflow/readiness, release history and
serving eligibility keep their existing owners; this module only combines their
read results for presentation and workflow-room decisions.
"""
from __future__ import annotations

from typing import Any


DOCUMENT_STATUS_LABELS = {
    "processing": "in verwerking",
    "in_review": "in review",
    "blocked": "vastgelopen",
    "ready_for_publication": "klaar voor publicatie",
    "closed": "afgesloten",
    "published": "gepubliceerd",
    "published_inactive": "gepubliceerd, niet actief",
    "superseded": "vervangen",
    "withdrawn": "ingetrokken",
}


def derive_workflow_status(
    *,
    readiness: dict[str, Any],
    release_status: str,
) -> str:
    """Derive mutable workflow state without overriding durable release truth."""
    if release_status != "none":
        return "closed"
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


def derive_presentation_status(
    *,
    workflow_status: str,
    release_status: str,
    serving_status: str,
) -> str:
    """Map lifecycle dimensions to one display label without creating authority."""
    if release_status == "withdrawn":
        return "withdrawn"
    if release_status == "superseded":
        return "superseded"
    if release_status == "published":
        return "published" if serving_status == "active" else "published_inactive"
    return workflow_status


def derive_lifecycle_status(
    *,
    readiness: dict[str, Any],
    release_status: str,
    serving_status: str,
) -> dict[str, str]:
    """Return the complete derived lifecycle read model."""
    workflow_status = derive_workflow_status(
        readiness=readiness,
        release_status=release_status,
    )
    return {
        "workflow_status": workflow_status,
        "release_status": release_status,
        "serving_status": serving_status,
        "presentation_status": derive_presentation_status(
            workflow_status=workflow_status,
            release_status=release_status,
            serving_status=serving_status,
        ),
    }


class DocumentStatusReadinessMixin:
    """Expose one read-only lifecycle model without widening action authority."""

    def document_readiness(self, snapshot_id: str) -> dict[str, Any]:
        """Read the shared publication-readiness contract without impersonation."""
        return self.publication_readiness(snapshot_id)  # type: ignore[attr-defined]

    def document_release_serving_status(
        self,
        snapshot_id: str,
        *,
        envelope: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Supported runtimes must use their canonical registry implementation."""
        from src.operations_console_v1 import ConsoleError
        raise ConsoleError("durable_publication_store_required")

    def document_lifecycle_status(self, snapshot_id: str) -> dict[str, str]:
        envelope = self._envelope(snapshot_id)  # type: ignore[attr-defined]
        durable = self.document_release_serving_status(
            snapshot_id,
            envelope=envelope,
        )
        release_status = str(durable.get("release_status") or "none")
        serving_status = str(durable.get("serving_status") or "inactive")
        readiness = (
            {}
            if release_status != "none"
            else self.document_readiness(snapshot_id)
        )
        return derive_lifecycle_status(
            readiness=readiness,
            release_status=release_status,
            serving_status=serving_status,
        )

    def document_status(self, snapshot_id: str) -> str:
        """Compatibility presentation accessor backed by the combined read model."""
        return self.document_lifecycle_status(snapshot_id)["presentation_status"]
