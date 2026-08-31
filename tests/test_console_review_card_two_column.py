"""Split-screen review card (owner lock 2026-08-29).

Two columns on the review card: knowledge object left, exact freeze
bronpassage right. Narrow screens stack. Type/approve stay blocked when
the passage cannot open. Relations stay proposed checkboxes + confirm.
No graph editor. No new locator scheme.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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


def _review_html(tmp_path: Path, data: bytes | None = None) -> tuple[str, dict, OperationsConsole]:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=data)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    html = client.get(f"/review?document={receipt['snapshot_id']}").text
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


def test_review_card_has_two_column_class(tmp_path: Path) -> None:
    html, receipt, console = _review_html(tmp_path)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    assert objects
    cards = _cards(html)
    assert cards, "review card must carry the two-column class"
    assert len(cards) == len(objects)
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    assert "Documentenhierarchie" not in html
    assert "draggable" not in html.lower()
    assert "graaf-editor" not in html.lower()


def test_review_card_object_left_bronpassage_right(tmp_path: Path) -> None:
    html, receipt, console = _review_html(tmp_path)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    rec = next(obj for obj in objects if "Verwijs" in ((obj.get("content") or {}).get("clean_text") or ""))
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
    )
    assert opened.get("passage")
    card = next(block for block in _cards(html) if rec["object_id"] in block)
    object_idx = card.find(f'class="{OBJECT_COL}"')
    if object_idx < 0:
        object_idx = card.find(f"class='{OBJECT_COL}'")
    passage_idx = card.find(f'class="{PASSAGE_COL}"')
    if passage_idx < 0:
        passage_idx = card.find(f"class='{PASSAGE_COL}'")
    assert object_idx >= 0
    assert passage_idx >= 0
    assert object_idx < passage_idx
    left = card[object_idx:passage_idx]
    right = card[passage_idx:]
    assert f'id="type-{rec["object_id"]}"' in left
    assert f'id="decision-{rec["object_id"]}"' in left
    assert 'name="relation"' in left
    assert "Bevestig type" in left
    assert "Besluit" in left
    assert _esc(opened["passage"]) in right
    assert "Bronpassage" in right
    assert "Bevestig type" not in right
    assert "Besluit" not in right


def test_review_card_css_two_column_and_stacks_on_narrow() -> None:
    css = CSS.read_text(encoding="utf-8")
    assert f".{TWO_COLUMN_CLASS}" in css
    default = re.search(
        rf"\.{re.escape(TWO_COLUMN_CLASS)}\s*\{{([^}}]+)\}}",
        css,
    )
    assert default is not None
    body = default.group(1)
    assert "grid-template-columns" in body or "display: flex" in body or "display:grid" in body.replace(" ", "")
    two_track = re.search(
        r"grid-template-columns:\s*[^;]*1fr[^;]*1fr",
        body,
    ) or re.search(
        r"grid-template-columns:\s*repeat\(\s*2\s*,",
        body,
    )
    flex_row = "flex-direction: row" in body or (
        "display: flex" in body and "flex-direction: column" not in body
    )
    assert two_track or flex_row
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
    html = client.get(f"/review?document={receipt['snapshot_id']}").text
    assert TWO_COLUMN_CLASS in html
    card = next(block for block in _cards(html) if target["object_id"] in block)
    assert PASSAGE_COL in card
    type_block = html[
        html.find(f'id="type-{target["object_id"]}"') : html.find(f'id="decision-{target["object_id"]}"') + 400
    ]
    assert "disabled" in type_block
    approve_line = next(line for line in type_block.split("<") if 'value="approve"' in line)
    assert "disabled" in approve_line
    assert 'value="revise"' in html
    assert 'value="reject"' in html

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
