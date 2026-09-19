"""Shared lifecycle-status presentation for existing workflow room cards.

Lifecycle calculation remains in backend policy. This module supplies the
current request with one combined derived read model and makes the existing
shared document-card renderer use its presentation status in Documenten,
Review and Publiceren.
"""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from typing import Any, Callable

from fastapi import FastAPI, Request

from src.document_status_v1 import DOCUMENT_STATUS_LABELS
from src.operations_console_v1 import ConsoleError


_LIFECYCLE_BY_SNAPSHOT: ContextVar[dict[str, dict[str, str]]] = ContextVar(
    "document_lifecycle_by_snapshot",
    default={},
)
_STATUS_PATHS = frozenset({"/tree", "/review", "/publish"})


def _closed_fallback() -> dict[str, str]:
    return {
        "workflow_status": "processing",
        "release_status": "none",
        "serving_status": "inactive",
        "presentation_status": "processing",
    }


def current_document_lifecycle_status(snapshot_id: str) -> dict[str, str] | None:
    """Return the request-local presentation status when middleware populated it."""
    row = _LIFECYCLE_BY_SNAPSHOT.get().get(str(snapshot_id or ""))
    return dict(row) if row else None


def _is_list_request(request: Request) -> bool:
    return request.url.path in {"/tree", "/review"}


def install_document_status_ui(app: FastAPI, console: Any) -> None:
    """Use one request-local lifecycle map with the existing shared card renderer."""
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
            lifecycle = _LIFECYCLE_BY_SNAPSHOT.get().get(snapshot_id) or {}
            meaningful = str(
                shown.get("meaningful_status")
                or lifecycle.get("presentation_status")
                or ""
            )
            if meaningful:
                shown["status"] = meaningful
            return original(shown)

        meaningful_document_card_heading._document_status_v1 = True  # type: ignore[attr-defined]
        console_ui._document_card_heading = meaningful_document_card_heading

    # Slice 5 imported the renderer by name. Reuse the exact same wrapper.
    publish_ui._document_card_heading = console_ui._document_card_heading

    def read_status_context(
        session_token: str | None,
        *,
        list_request: bool,
    ) -> dict[str, dict[str, str]] | None:
        try:
            console.session_account(session_token)
        except ConsoleError:
            return None

        lifecycle_by_snapshot: dict[str, dict[str, str]] = {}
        list_reader = getattr(console, "list_document_lifecycle_statuses", None)
        if list_request and callable(list_reader):
            # Production PostgreSQL presentation GETs use one light workflow aggregate
            # plus one canonical release read. Never enter full publish-readiness here.
            try:
                lifecycle_by_snapshot = {
                    str(snapshot_id): dict(row)
                    for snapshot_id, row in list_reader().items()
                }
            except (AttributeError, ConsoleError):
                lifecycle_by_snapshot = {}
        else:
            # Publish keeps its existing full lifecycle semantics. Local/non-PostgreSQL
            # runtimes also retain the compatibility path when no list reader exists.
            for row in console.list_envelopes():
                snapshot_id = str(row.get("snapshot_id") or "")
                if not snapshot_id:
                    continue
                try:
                    lifecycle_by_snapshot[snapshot_id] = dict(
                        console.document_lifecycle_status(snapshot_id)
                    )
                except (AttributeError, ConsoleError):
                    lifecycle_by_snapshot[snapshot_id] = _closed_fallback()
        return lifecycle_by_snapshot

    @app.middleware("http")
    async def document_status_context(request: Request, call_next: Callable[..., Any]):
        if request.url.path not in _STATUS_PATHS:
            return await call_next(request)

        lifecycle_by_snapshot = await asyncio.to_thread(
            read_status_context,
            request.cookies.get(console_ui.COOKIE),
            list_request=_is_list_request(request),
        )
        if lifecycle_by_snapshot is None:
            return await call_next(request)

        token = _LIFECYCLE_BY_SNAPSHOT.set(lifecycle_by_snapshot)
        try:
            return await call_next(request)
        finally:
            _LIFECYCLE_BY_SNAPSHOT.reset(token)

    app.state.document_status_ui_v1 = True
