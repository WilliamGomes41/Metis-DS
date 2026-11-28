"""A not-started document is not shown as stuck; Publiceren names its state once."""
from __future__ import annotations

from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from src.documents.document_status_v1 import DOCUMENT_STATUS_LABELS
from src.operations_console_v1 import PRE_REVIEW_BLOCKED, PROCESSING_NOT_STARTED
from tests.test_v225_beslisboom_path import _boom_freeze_bytes

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]

HTML = b"<html><body><h1>Zorg</h1><p>Geef dagelijks voldoende vocht.</p></body></html>"


def _received(production_console, production_app, *, klasse="richtlijn"):
    console = production_console()
    console.create_account("researcher.anne", "anne-secret",
                           roles=("researcher", "reviewer", "publisher"), display_name="Anne")
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    form = client.get("/ingest").text
    command = re.search(r'name="command_id" value="([^"]*)"', form)
    upload = (("boom.json", _boom_freeze_bytes(), "application/json") if klasse == "beslisboom"
              else ("bron.html", HTML, "text/html"))
    response = client.post("/ingest", data={
        "command_id": command.group(1) if command else "", "ingest_kind": "new", "title": "Vocht",
        "version": "1.0", "date": "2026-01-15", "class_": klasse, "family": "Zorg",
        "source_status": "unknown", "review_mode": "choice", "review_option": "uploader_sole",
    }, files={"file": upload}, follow_redirects=False)
    assert response.status_code == 303, response.text[:400]
    snapshot_id = re.search(r"document=([^&]+)", response.headers["location"]).group(1)
    return console, client, snapshot_id


def test_received_document_reads_not_started_while_the_derived_status_is_unchanged(production_console, production_app) -> None:
    console, client, snapshot_id = _received(production_console, production_app)
    child = next(c for node in console.family_tree()["families"].values() for c in node["children"])
    assert child["publication_eligibility"] == PRE_REVIEW_BLOCKED
    assert child["processing_blocker"] == PROCESSING_NOT_STARTED
    # The read model keeps its value; only the Documenten row words it differently.
    assert console.document_status(snapshot_id) == "blocked"
    tree = client.get("/tree").text
    assert 'data-tone="neutral"><span class="visually-hidden">Status: </span>nog niet gestart</span>' in tree
    assert f'href="/annotations?document={snapshot_id}"' in tree
    assert f'href="/source-selection?document={snapshot_id}"' not in tree
    assert client.get(f"/annotations?document={snapshot_id}").status_code == 200
    assert "vastgelopen" not in tree and "geblokkeerd" not in tree


def test_received_decision_tree_opens_formation(production_console, production_app):
    _, client, sid = _received(production_console, production_app, klasse="beslisboom")
    documents = client.get("/tree").text
    assert f'href="/source-selection?document={sid}"' in documents
    assert f'href="/annotations?document={sid}"' not in documents
    formation = client.get("/source-selection", params={"document": sid})
    assert formation.status_code == 200
    # #1191: a new decision tree is formed through annotation only.
    assert 'action="/annotations/source"' in formation.text
    assert 'action="/source-selection/start"' not in formation.text


def test_publisher_without_annotation_access_only_sees_status(production_console, production_app):
    console, client, sid = _received(production_console, production_app)
    console.create_account("publisher", "publisher-secret", roles=("publisher",))
    login = client.post("/login", data={"username": "publisher", "password": "publisher-secret"}, follow_redirects=False)
    assert login.status_code == 303
    page = client.get("/tree")
    assert page.status_code == 200
    assert "Na het annoteren" in page.text
    assert f'href="/annotations?document={sid}"' not in page.text
    assert f'href="/inzicht/document?document={sid}"' in page.text


def test_stuck_documents_are_called_vastgelopen() -> None:
    assert DOCUMENT_STATUS_LABELS["blocked"] == "vastgelopen"
    source = (Path(__file__).resolve().parents[1] / "src/vorming/source_selection_v1.py").read_text()
    assert source.count('state = "vastgelopen"') == 2 and '"geblokkeerd"' not in source


def test_publiceren_names_the_unchecked_state_once(production_console, production_app) -> None:
    _, client, snapshot_id = _received(production_console, production_app)
    page = client.get("/publish").text
    card = re.search(rf'<article class="doc-card" data-publish-document="{snapshot_id}">(.*?)</article>', page, re.S).group(1)
    assert card.count("volledigheid nog niet gecontroleerd") == 1
    assert "Status: volledigheid nog niet gecontroleerd." in card
    assert "Volledigheid controleren" in card
    assert "<span>klasse <b>richtlijn</b></span>" in card
