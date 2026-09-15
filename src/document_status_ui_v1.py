"""Shared document-status presentation for existing workflow room cards.

Status calculation remains in the backend policy. This module supplies the
current request with derived statuses and makes the existing shared document
card renderer use them in Documenten, Review and Publiceren.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

from fastapi import FastAPI, Request

from src.document_status_v1 import DOCUMENT_STATUS_LABELS
from src.operations_console_v1 import ConsoleError


_STATUS_BY_SNAPSHOT: ContextVar[dict[str, str]] = ContextVar(
    "document_status_by_snapshot",
    default={},
)
_STATUS_PATHS = frozenset({"/tree", "/review", "/publish"})


def install_document_status_ui(app: FastAPI, console: Any) -> None:
    """Use one request-local status map with the existing shared card renderer."""
    if getattr(app.state, "document_status_ui_v1", False):
        return

    # Imports stay local to avoid a domain-policy -> HTML dependency direction.
    import src.operations_console_app as console_ui
    import src.publish_readiness_ui_v1 as publish_ui

    console_ui.STATUS_LABELS.update(DOCUMENT_STATUS_LABELS)

    current: Callable[[dict[str, Any]], str] = console_ui._document_card_heading
    if not getattr(current, "_document_status_v1", False):
        original = current

        def meaningful_document_card_heading(row: dict[str, Any]) -> str:
            shown = dict(row)
            snapshot_id = str(shown.get("snapshot_id") or "")
            meaningful = str(
                shown.get("meaningful_status")
                or _STATUS_BY_SNAPSHOT.get().get(snapshot_id)
                or ""
            )
            if meaningful:
                shown["status"] = meaningful
            return original(shown)

        meaningful_document_card_heading._document_status_v1 = True  # type: ignore[attr-defined]
        console_ui._document_card_heading = meaningful_document_card_heading

    # Slice 5 imported the renderer by name. Reuse the exact same wrapper.
    publish_ui._document_card_heading = console_ui._document_card_heading

    @app.middleware("http")
    async def document_status_context(request: Request, call_next: Callable[..., Any]):
        if request.url.path not in _STATUS_PATHS:
            return await call_next(request)
        try:
            console.session_account(request.cookies.get(console_ui.COOKIE))
        except ConsoleError:
            return await call_next(request)

        statuses: dict[str, str] = {}
        for row in console.list_envelopes():
            snapshot_id = str(row.get("snapshot_id") or "")
            if not snapshot_id:
                continue
            try:
                statuses[snapshot_id] = console.document_status(snapshot_id)
            except ConsoleError:
                # Presentation fails closed: no error can turn an unresolved
                # document into ready/published state.
                statuses[snapshot_id] = "processing"

        token = _STATUS_BY_SNAPSHOT.set(statuses)
        try:
            return await call_next(request)
        finally:
            _STATUS_BY_SNAPSHOT.reset(token)

    app.state.document_status_ui_v1 = True
