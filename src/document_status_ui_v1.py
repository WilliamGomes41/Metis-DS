"""Shared document-status presentation for existing workflow room cards.

The backend supplies ``meaningful_status`` on envelope/tree copies. This module
only makes the existing shared card renderer prefer that derived field, so
Documenten, Review and Publiceren cannot invent separate status labels.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import FastAPI

from src.document_status_v1 import DOCUMENT_STATUS_LABELS


def install_document_status_ui(app: FastAPI) -> None:
    """Teach the one shared document-card renderer the derived status field."""
    if getattr(app.state, "document_status_ui_v1", False):
        return

    # Imports stay local to avoid creating a new dependency direction from the
    # domain policy into the HTML console.
    import src.operations_console_app as console_ui
    import src.publish_readiness_ui_v1 as publish_ui

    console_ui.STATUS_LABELS.update(DOCUMENT_STATUS_LABELS)

    current: Callable[[dict[str, Any]], str] = console_ui._document_card_heading
    if not getattr(current, "_document_status_v1", False):
        original = current

        def meaningful_document_card_heading(row: dict[str, Any]) -> str:
            shown = dict(row)
            meaningful = str(shown.get("meaningful_status") or "")
            if meaningful:
                shown["status"] = meaningful
            return original(shown)

        meaningful_document_card_heading._document_status_v1 = True  # type: ignore[attr-defined]
        console_ui._document_card_heading = meaningful_document_card_heading

    # Slice 5 imported the shared renderer by name. Point that existing alias at
    # the same renderer so Publish does not grow a second status presentation.
    publish_ui._document_card_heading = console_ui._document_card_heading
    app.state.document_status_ui_v1 = True
