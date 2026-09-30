"""Issue #462: the full-guideline action reads the complete frozen source.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from html import unescape
import re
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.open_original_v1 import document_visible_prose

HTML = b'''<!doctype html><html><body><h1>Complete guideline</h1>
<p>Context before the selected recommendation.</p>
<p>Verwijs naar de huisarts.</p>
<p>Later appendix beyond the selected passage.</p>
<script>window.UPLOADED_SCRIPT=true</script><img src="https://evil.test/track" onerror="alert(1)">
</body></html>'''


def setup_source(tmp_path: Path, data: bytes = HTML, kind: str = "html"):
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources",
                                runtime=tmp_path / "runtime")
    reviewer = console.create_account(username="reviewer", password="secret", roles=("researcher", "reviewer"))
    uploader = console.create_account(username="uploader", password="secret", roles=("researcher",))
    receipt = console.ingest(actor_id=uploader["account_id"], filename=f"guideline.{kind}", data=data,
                             content_type=f"application/{kind}" if kind == "pdf" else "text/html",
                             ingest_kind="new", title="Guideline", version="1.0", date="2026-01-01",
                             live_url="https://example.test/guideline", class_="richtlijn", family="continentie",
                             named_reviewers=[reviewer["account_id"]])
    snapshot = receipt["snapshot_id"]
    objects = console.snapshot_objects(snapshot)
    target = next(row for row in objects if row["object_type"] != "document"
                  and "Verwijs" in (row.get("content") or {}).get("clean_text", ""))
    client = TestClient(create_console_app(console))
    assert client.post("/login", data={"username": "reviewer", "password": "secret"}).status_code == 200
    query = f'document={snapshot}&object={target["object_id"]}'
    return console, client, snapshot, target, query


def test_click_full_guideline_shows_all_frozen_html_and_returns_to_same_task(tmp_path):
    console, client, snapshot, target, query = setup_source(tmp_path)
    objects_before = deepcopy(console.snapshot_objects(snapshot))
    source_before = console._verified_source_bytes(console._envelope(snapshot))[1]
    card = client.get(f"/review?{query}&task=contextual").text
    link = re.search(r'href="([^"]+)">Open volledige richtlijn</a>', card)
    assert link, card
    response = client.get(unescape(link[1]))
    assert response.status_code == 200
    for text in ("Complete guideline", "Context before", "Later appendix", "Verwijs naar de huisarts."):
        assert text in response.text
    assert '<mark class="broncontext-marked">Verwijs naar de huisarts.</mark>' in response.text
    assert f'/review?{query.replace("&", "&amp;")}&amp;task=contextual' in response.text
    assert "window.UPLOADED_SCRIPT" not in response.text
    assert "evil.test" not in response.text
    assert "onerror" not in response.text
    download = client.get(f"/review/brondocument?{query}&download=true")
    assert download.content == HTML
    assert download.headers["content-disposition"].startswith("attachment;")
    assert download.headers["content-type"] == "application/octet-stream"
    assert download.headers["x-content-type-options"] == "nosniff"
    # Repeated reads must not create review evidence or change source/object state.
    assert client.get(unescape(link[1])).status_code == 200
    assert console.snapshot_objects(snapshot) == objects_before
    assert console._verified_source_bytes(console._envelope(snapshot))[1] == source_before


def test_full_pdf_preserves_every_page_and_uses_located_page(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Verwijs naar de huisarts.")
    doc.new_page().insert_text((72, 72), "Appendix on a second page.")
    data = doc.tobytes()
    doc.close()
    _, client, _, _, query = setup_source(tmp_path, data, "pdf")
    response = client.get(f"/review/bronpassage?{query}&task=history")
    assert response.status_code == 200
    assert 'type="application/pdf"' in response.text
    assert "#page=1" in response.text
    assert "task=history" in response.text
    original = client.get(f"/review/brondocument?{query}")
    assert original.content == data
    assert original.headers["content-type"] == "application/pdf"
    assert original.headers["cache-control"] == "no-store"
    with fitz.open(stream=original.content, filetype="pdf") as full:
        assert len(full) == 2
        assert "Appendix on a second page." in full[1].get_text()
    assert client.get(f"/review/brondocument?{query}&download=true").headers["content-disposition"].startswith("attachment;")


@pytest.mark.parametrize("route", ["bronpassage", "brondocument"])
def test_full_source_requires_session_and_valid_object(tmp_path, route):
    _, client, _, _, query = setup_source(tmp_path)
    assert client.get(f"/review/{route}?document=unknown&object=unknown").status_code == 400
    client.cookies.clear()
    assert client.get(f"/review/{route}?{query}").status_code == 401


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_corrupt_source_fails_closed(tmp_path, corrupt):
    console, client, snapshot, _, query = setup_source(tmp_path)
    path, _ = console._verified_source_bytes(console._envelope(snapshot))
    if corrupt:
        path.write_bytes(b"unverified replacement")
    else:
        path.unlink()
    for route in ("bronpassage", "brondocument"):
        response = client.get(f"/review/{route}?{query}")
        assert response.status_code == 400
        assert "origineel ontbreekt" in response.text
        assert "unverified replacement" not in response.text


def test_full_document_projection_keeps_blocks_and_json_literal():
    assert document_visible_prose(b"<p>First</p><p>Second</p><table><tr><td>A</td><td>B</td></tr></table>", "html") == "First\nSecond\nA\nB"
    assert document_visible_prose(b'{"text":"<not-a-tag>"}', "boom") == '{"text":"<not-a-tag>"}'


def test_full_source_does_not_bypass_missing_locator(tmp_path):
    console, client, snapshot, target, query = setup_source(tmp_path)
    rows = console.snapshot_objects(snapshot)
    for row in rows:
        if row["object_id"] == target["object_id"]:
            row.pop("source_locator", None)
            for fragment in (row.get("provenance") or {}).get("source_fragments") or []:
                fragment.pop("source_locator", None)
    console._save_objects(snapshot, rows)
    for route in ("bronpassage", "brondocument"):
        response = client.get(f"/review/{route}?{query}")
        assert response.status_code == 400
        assert "De bronpassage ontbreekt" in response.text


def test_boom_projection_escapes_literal_markup_and_downloads_json(tmp_path, monkeypatch):
    console, client, _, _, query = setup_source(tmp_path)
    original = b'{"text":"<script>alert(1)</script>"}'
    monkeypatch.setattr(console, "open_source_passage", lambda **kwargs: {
        "freeze_bytes": original, "content_kind": "boom", "passage": "a passage",
    })
    response = client.get(f"/review/bronpassage?{query}")
    assert response.status_code == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text
    download = client.get(f"/review/brondocument?{query}")
    assert download.content == original
    assert download.headers["content-disposition"] == 'attachment; filename="richtlijn.json"'
