"""Browser filename normalization and readable PDF review rows.

Release-control evidence: upload route and traversal guards (toegang),
byte-preserving local storage (opslag), readable rows without ID dumps
(scope/belofte, slop), and these executable regressions (releasebewijs).
Concurrent/stale persistence remains covered by test_pilot_review_write_serialization.py;
this change does not alter commit serialization or snapshot revisions.

# release-control-evidence: opslag concurrent stale
"""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import parse_qs, urlparse

import pymupdf
import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import GATE_BLOCKED
from src.operations_console_app import FILENAME_HINT, _render_review_index, create_console_app
from src.operations_console_v1 import (
    ConsoleError, OperationsConsole, normalize_upload_filename, safe_path_under,
)

pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class VisibleRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.rows = []
        self.link = None
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "a" and attrs.get("class") == "review-row-title":
            self.link = [attrs["href"], ""]

    def handle_data(self, data):
        if not self.skip:
            self.text.append(data)
            if self.link is not None:
                self.link[1] += data

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip -= 1
        if tag == "a" and self.link is not None:
            self.rows.append(self.link)
            self.link = None


@pytest.fixture
def upload(tmp_path):
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources" / "private", runtime=tmp_path / "runtime")
    password = token_urlsafe(24)
    actor = console.create_account("uploader", password, roles=("researcher", "reviewer"), display_name="Onderzoeker")
    reviewer = console.create_account("reviewer", token_urlsafe(24), roles=("reviewer",), display_name="Reviewer")
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Eenzaamheid bij ouderen", fontsize=18)
        page.insert_text((72, 112), "Eenzaamheid is het ervaren gemis van betekenisvolle sociale contacten.")
        page.insert_text((72, 142), "Bespreek als verpleegkundige met de oudere welke sociale contacten steun bieden.")
        page.insert_text((72, 172), "De vragenlijst bevat zes vragen over sociale contacten.")
        payload = pdf.tobytes()
    form = dict(ingest_kind="new", title="Eenzaamheid bij ouderen", version="1.2", date="2026-09-05", class_="richtlijn", family="Eenzaamheid", named_reviewers=[reviewer["account_id"]])
    with TestClient(create_console_app(console), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "uploader", "password": password}).status_code == 200
        yield console, client, payload, form, actor


@pytest.mark.parametrize(("name", "expected"), [
    (r"C:\Users\x\Doc.pdf", "Doc.pdf"),
    ("/tmp/Doc.pdf", "Doc.pdf"),
    ("folder/Doc.pdf", "Doc.pdf"),
    ("Eenzaamheid bij ouderen.pdf", "Eenzaamheid-bij-ouderen.pdf"),
    ("Patiënt (kopie).pdf", "Patient-kopie-.pdf"),
])
def test_browser_filename_ingest_preserves_bytes_and_stays_under_store(upload, name, expected):
    console, client, payload, form, _ = upload
    assert normalize_upload_filename(name) == expected
    response = client.post("/ingest", data=form, files={"file": (name, payload, "application/pdf")})
    assert response.status_code == 200
    assert "Document ingeleverd" in response.text
    envelope, = console.list_envelopes()
    stored = Path(envelope["binary_path"])
    assert stored.name == expected
    stored.resolve().relative_to(console.source_store.resolve())
    assert stored.read_bytes() == payload
    assert envelope["sha256"] == hashlib.sha256(payload).hexdigest()
    assert envelope["title"] == form["title"]


@pytest.mark.parametrize("name", ["", None, "..", ".", "../doc.pdf", r"C:\Users\..\Doc.pdf", "foo/../doc.pdf", "trailing/", "💙", ".pdf", "a" * 201 + ".pdf"])
def test_unusable_names_and_traversal_remain_rejected(name):
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        normalize_upload_filename(name)


@pytest.mark.parametrize("name", [None, "", ".."])
def test_ingest_rejects_missing_or_traversal_name_before_storage(upload, name):
    console, _, payload, form, actor = upload
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        console.ingest(actor_id=actor["account_id"], filename=name, data=payload, content_type="application/pdf", live_url="", **form)
    assert console.list_envelopes() == []
    assert not list(console.source_store.rglob("*.pdf"))


def test_path_joins_remain_strict_and_symlink_escape_is_rejected(tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (store / "link").symlink_to(outside, target_is_directory=True)
    for parts in [("../outside", "doc.pdf"), ("nested/doc.pdf",), ("link", "doc.pdf")]:
        with pytest.raises(ConsoleError, match="invalid_store_path"):
            safe_path_under(store, *parts)


def test_filename_error_has_same_hint_and_keeps_valid_session(upload):
    console, client, payload, form, _ = upload
    assert FILENAME_HINT in client.get("/ingest").text
    response = client.post("/ingest", data=form, files={"file": ("..", payload, "application/pdf")})
    assert response.status_code == 400
    assert FILENAME_HINT in response.text
    assert "De bestandsnaam kan niet veilig worden verwerkt" in response.text
    assert 'href="/ingest">Terug naar Inleveren' in response.text
    assert "Naar aanmelden" not in response.text
    assert "Deze actie is niet toegestaan" not in response.text
    assert client.get("/ingest").status_code == 200
    assert console.list_envelopes() == []
    assert not list(console.source_store.rglob("*.pdf"))


def test_pdf_review_index_uses_human_labels_and_working_object_links(upload):
    console, client, payload, form, _ = upload
    assert client.post("/ingest", data=form, files={"file": ("Eenzaamheid bij ouderen.pdf", payload, "application/pdf")}).status_code == 200
    envelope, = console.list_envelopes()
    response = client.get("/review", params={"document": envelope["snapshot_id"], "task": "control"})
    assert response.status_code == 200
    visible = VisibleRows()
    visible.feed(response.text)
    objects = {obj["object_id"] for obj in console.snapshot_objects(envelope["snapshot_id"])}
    assert visible.rows
    assert not any(object_id in " ".join(visible.text) for object_id in objects)
    for href, label in visible.rows:
        object_id = parse_qs(urlparse(href).query)["object"][0]
        assert object_id in objects
        assert label.strip() and label != object_id
    assert client.get(visible.rows[0][0]).status_code == 200


def test_other_blocked_candidates_are_readable_and_remain_accessible():
    objects = [
        {"object_id": f"console-eenzaamheid-p001-f{index:03d}-u01", "object_type": "unclassified", "proposed_object_type": "unclassified", "content": {"clean_text": text}, "metadata": {"admission": {"gate_result": GATE_BLOCKED}}}
        for index, text in enumerate(["Een passage over sociale contacten.", "Een passage over het netwerk van de oudere."], 1)
    ]
    rendered = _render_review_index("snap-test", objects, "richtlijn", task="control")
    visible = VisibleRows()
    visible.feed(rendered)
    assert "Technisch herstel nodig (2)" in rendered
    assert len(visible.rows) == 2
    for obj, (_, label) in zip(objects, visible.rows):
        assert label == obj["content"]["clean_text"]
        assert obj["object_id"] not in " ".join(visible.text)
