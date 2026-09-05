"""Review cockpit card (Protocol v2.30 Phase 3 / Block B).

A–F stack: selected passage, real broncontext, suitability, documentpositie,
type proposal, eindoordeel. One save. Type/approve stay blocked when the
passage cannot open. Relatie bevestigen is not on the primary surface.
No graph editor. No new locator scheme.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.open_original_v1 import researcher_visible_prose
from src.operations_console_app import _esc, create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "assets/brand/console.css"
TWO_COLUMN_CLASS = "review-card-two-column"
OBJECT_COL = "review-card-object"
PASSAGE_COL = "review-card-bronpassage"


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    return {"researcher": researcher, "reviewer": reviewer}


def _fused_html() -> bytes:
    return (
        "<!doctype html><html lang=\"nl\"><body>"
        "<h1>Voorbeeldrichtlijn</h1>"
        "<p>Bij een cliënt van 70 jaar of ouder. Verwijs naar de huisarts.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict, data: bytes | None = None) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=data if data is not None else _fused_html(),
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )


def _review_page(console: OperationsConsole, snapshot_id: str, object_id: str | None = None) -> str:
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    url = f"/review?document={snapshot_id}"
    if object_id:
        url += f"&object={object_id}"
    return client.get(url).text


def _review_html(
    tmp_path: Path, data: bytes | None = None, object_id: str | None = None
) -> tuple[str, dict, OperationsConsole]:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=data)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    url = f"/review?document={receipt['snapshot_id']}"
    if object_id:
        url += f"&object={object_id}"
    html = client.get(url).text
    return html, receipt, console


def _cards(html: str) -> list[str]:
    return re.findall(
        rf'<article class="[^"]*{re.escape(TWO_COLUMN_CLASS)}[^"]*".*?</article>',
        html,
        flags=re.S,
    )


def _strip_locator(console: OperationsConsole, snapshot_id: str, object_id: str) -> None:
    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] != object_id:
            continue
        provenance = row.setdefault("provenance", {})
        for frag in provenance.get("source_fragments") or []:
            frag.pop("source_locator", None)
        row.pop("source_locator", None)
    console._save_objects(snapshot_id, rows)


def test_review_document_index_does_not_open_passages(tmp_path: Path) -> None:
    html, receipt, console = _review_html(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    assert objects
    assert TWO_COLUMN_CLASS not in html
    assert PASSAGE_COL not in html
    assert "object-index" in html
    assert "Onderbouwing uit het brondocument" not in html
    for obj in objects:
        assert obj["object_id"] in html
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    assert "Documentenhierarchie" not in html
    assert "draggable" not in html.lower()
    assert "graaf-editor" not in html.lower()


def test_review_card_has_two_column_class(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    html = _review_page(console, receipt["snapshot_id"], target["object_id"])
    cards = _cards(html)
    assert cards, "review card must carry the two-column class"
    assert len(cards) == 1
    assert target["object_id"] in cards[0]
    assert "envelope" not in html.lower()
    assert "draggable" not in html.lower()
    assert "graaf-editor" not in html.lower()


def test_review_card_object_left_bronpassage_right(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    rec = next(obj for obj in objects if "Verwijs" in ((obj.get("content") or {}).get("clean_text") or ""))
    html = _review_page(console, receipt["snapshot_id"], rec["object_id"])
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
    )
    assert opened.get("passage")
    card = next(block for block in _cards(html) if rec["object_id"] in block)
    object_idx = card.find(OBJECT_COL)
    passage_idx = card.find(PASSAGE_COL)
    assert object_idx >= 0
    assert passage_idx >= 0
    assert object_idx < passage_idx
    left = card[object_idx:passage_idx]
    right = card[passage_idx:]
    assert "Geselecteerde passage" in left or "Geselecteerd omdat" in left
    assert "Relatie bevestigen" not in left
    assert 'name="relation"' not in left
    assert f'id="type-{rec["object_id"]}"' in card
    assert f'id="decision-{rec["object_id"]}"' in card
    prose = researcher_visible_prose(opened["passage"])
    assert "Broncontext" in right
    assert _esc(prose) in right or prose in right or "Verwijs" in right
    assert "brxe-faadvp" not in right
    assert "&lt;p&gt;" not in right
    assert "&lt;div" not in right
    assert "Welk type kennisobject is dit?" not in right
    assert "Wat is je besluit over dit kennisobject?" not in right


def test_review_card_uses_clear_labels_and_requires_an_explicit_decision(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    html = _review_page(console, receipt["snapshot_id"], target["object_id"])
    card = next(block for block in _cards(html) if target["object_id"] in block)
    assert "Geselecteerde passage" in card
    assert "Metis stelt voor:" in card
    assert re.search(r'<option value="heading"[^>]*>Kop</option>', card)
    assert "Broncontext" in card
    assert 'name="eindoordeel"' in card
    assert 'value="goedkeuren"' in card
    assert 'value="goedkeuren" selected' not in card
    assert "Review opslaan en volgende" in card
    assert 'data-comment-field hidden' in card
    assert 'data-correction-field hidden' in card
    assert 'data-submit-review' in card


def test_review_post_requires_explicit_decision_and_comment_when_needed(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    base = {"snapshot_id": receipt["snapshot_id"], "object_id": target["object_id"]}
    no_decision = client.post("/review", data={**base, "decision": "", "eindoordeel": ""})
    assert no_decision.status_code == 400
    assert "Kies een eindoordeel" in no_decision.text
    no_comment = client.post(
        "/review",
        data={**base, "eindoordeel": "afwijzen", "comment": "", "suitability": "ja"},
    )
    assert no_comment.status_code == 400
    assert "Geef een toelichting" in no_comment.text


def test_review_card_css_two_column_and_stacks_on_narrow() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert f".{TWO_COLUMN_CLASS}" in css
    default = re.search(
        rf"\.{re.escape(TWO_COLUMN_CLASS)}\s*\{{([^}}]+)\}}",
        css,
    )
    assert default is not None
    body = default.group(1)
    stacked_default = (
        "flex-direction: column" in body
        or "display: flex" in body
        or "display:flex" in body.replace(" ", "")
        or "grid-template-columns" in body
        or "display:grid" in body.replace(" ", "")
    )
    assert stacked_default, "A–F cockpit stacks as a column (or legacy two-track grid)"
    media = re.search(
        r"@media\s*\(\s*max-width:\s*(\d+)px\s*\)\s*\{(.{0,800})\}",
        css,
        flags=re.S,
    )
    assert media is not None
    assert int(media.group(1)) <= 800
    stacked = media.group(2)
    assert TWO_COLUMN_CLASS in stacked
    assert (
        re.search(r"grid-template-columns:\s*1fr\b", stacked)
        or "flex-direction: column" in stacked
    )


def test_type_and_approve_still_disabled_when_passage_cannot_open(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    _strip_locator(console, receipt["snapshot_id"], target["object_id"])
    with pytest.raises(ConsoleError):
        console.open_source_passage(snapshot_id=receipt["snapshot_id"], object_id=target["object_id"])

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = _review_page(console, receipt["snapshot_id"], target["object_id"])
    assert TWO_COLUMN_CLASS in html
    card = next(block for block in _cards(html) if target["object_id"] in block)
    assert PASSAGE_COL in card
    type_block = html[
        html.find(f'id="type-{target["object_id"]}"') : html.find(f'id="decision-{target["object_id"]}"') + 800
    ]
    assert "disabled" in type_block
    approve_line = next(line for line in card.split("<") if 'value="goedkeuren"' in line)
    assert "disabled" in approve_line
    assert 'value="goedkeuren_na_correctie"' in html
    assert 'value="afwijzen"' in html

    with pytest.raises(ConsoleError, match="open_original|source_locator"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            decision="approve",
            confirmed_object_type="explanation",
        )
    with pytest.raises(ConsoleError, match="open_original|source_locator"):
        console.confirm_object_type(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            confirmed_object_type="explanation",
        )
