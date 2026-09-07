"""CSS URLs must change with content, even when ZIP mtimes stay fixed."""
from __future__ import annotations

import hashlib
import os
import re

import pytest
from fastapi.testclient import TestClient

from src import operations_console_app as console_app
from src.operations_console_v1 import OperationsConsole


def _stylesheet_url(page: str) -> str:
    match = re.search(r'<link rel="stylesheet" href="([^"]+)"', page)
    assert match is not None
    return match.group(1)


def test_content_changes_url_with_identical_mtime_and_size(tmp_path, monkeypatch):
    monkeypatch.setattr(console_app, "BRAND_DIR", tmp_path)
    stylesheet = tmp_path / "console.css"
    stylesheet.write_bytes(b"a { color: red; }")
    os.utime(stylesheet, (1767225600, 1767225600))
    first_url = _stylesheet_url(console_app._page(""))
    assert first_url == _stylesheet_url(console_app._page("other page"))

    stylesheet.write_bytes(b"a { color: tan; }")
    os.utime(stylesheet, (1767225600, 1767225600))
    second_url = _stylesheet_url(console_app._page(""))
    assert first_url != second_url
    expected = hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:16]
    assert second_url == f"/brand/console.css?v={expected}"


@pytest.mark.parametrize("path", ["/", "/login"])
def test_rendered_css_url_serves_current_tile_styles(tmp_path, path):
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    with TestClient(console_app.create_console_app(console)) as client:
        page = client.get(path)
        assert page.status_code == 200
        url = _stylesheet_url(page.text)
        expected_css = (console_app.BRAND_DIR / "console.css").read_bytes()
        expected_version = hashlib.sha256(expected_css).hexdigest()[:16]
        assert url == f"/brand/console.css?v={expected_version}"
        response = client.get(url)
        assert response.status_code == 200
        assert response.content == expected_css
        assert response.headers["content-type"].startswith("text/css")
        assert ".home-tiles" in response.text
        assert ".home-tile-icon" in response.text


def test_page_still_renders_when_optional_brand_assets_are_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(console_app, "BRAND_DIR", tmp_path)
    assert _stylesheet_url(console_app._page("")) == "/brand/console.css"
