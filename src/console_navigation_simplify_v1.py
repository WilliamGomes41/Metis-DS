"""Remove duplicate links on the Review and Inleveren pages."""
from __future__ import annotations

import re
from typing import Callable

from fastapi import FastAPI, Request, Response


_BATCH_SOURCE_LINK = re.compile(
    r'\s*<a href="/review/bronpassage\?document=[^"]+">Bronpassage</a>', re.S
)
_POST_INGEST_DOCUMENTS_LINK = re.compile(
    r'\s*<a class="btn-secondary" href="/tree">Naar Documenten</a>', re.S
)
_PARENT_CHOOSER = re.compile(
    r'(<div data-parent-choice-list>.*?</div>)', re.S
)
_PARENT_OBJECT_LINK = re.compile(
    r'<a href="/review\?document=[^"]+&object=[^"]+">(.*?)</a>', re.S
)


def simplify_console_html(path: str, body: str) -> str:
    """Return the same page with redundant navigation doors removed."""
    html = body

    if path == "/review":
        # In a batch row the object-review link already exposes source context
        # and the full-source action. Do not offer a second direct source door.
        html = _BATCH_SOURCE_LINK.sub("", html)

        # A parent chooser is a chooser, not parallel navigation. Keep the label
        # and radio selection but make the heading text non-navigational.
        def _plain_parent_labels(match: re.Match[str]) -> str:
            return _PARENT_OBJECT_LINK.sub(r"\1", match.group(1))

        html = _PARENT_CHOOSER.sub(_plain_parent_labels, html)

    if path == "/ingest":
        # After receipt, Vorming is the workflow continuation. Document
        # management remains reachable through normal navigation.
        html = _POST_INGEST_DOCUMENTS_LINK.sub("", html)

    return html


def install_navigation_simplification(app: FastAPI) -> None:
    """Install a presentation-only response transform for console HTML."""

    @app.middleware("http")
    async def simplify_duplicate_doors(
        request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return response

        chunks = [chunk async for chunk in response.body_iterator]
        raw = b"".join(chunks)
        charset = getattr(response, "charset", None) or "utf-8"
        body = raw.decode(charset)
        simplified = simplify_console_html(request.url.path, body)
        if simplified == body:
            return Response(
                content=raw,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
                background=response.background,
            )

        headers = dict(response.headers)
        headers.pop("content-length", None)
        return Response(
            content=simplified.encode(charset),
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
