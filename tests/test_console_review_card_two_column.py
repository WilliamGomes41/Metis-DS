"""Review cockpit card (Protocol v2.30 Phase 3 / Block B).

# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

The new knowledge review page compares original source and object, with
three explicit answer groups and one approval action. Structural review
retains its existing controls. Approval stays blocked without the source.
No graph editor. No new locator scheme.
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.review.open_original_v1 import researcher_visible_prose
from src.operations_console_app import _esc, _render_review_index
from src.operations_console_v1 import ConsoleError, OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "assets/brand/console.css"
TWO_COLUMN_CLASS = "review-card-two-column"
OBJECT_COL = "review-card-object"
PASSAGE_COL = "review-card-bronpassage"


def _console(tmp_path: Path, *, production_console) -> OperationsConsole:
    return production_console(processing_binder=bind_fixture_selections,
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


def _review_page(console: OperationsConsole, snapshot_id: str, object_id: str | None=None, *, production_app) -> str:
    client = TestClient(production_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    url = f"/review?document={snapshot_id}"
    if object_id:
        url += f"&object={object_id}"
    return client.get(url).text


def _review_html(tmp_path: Path, data: bytes | None=None, object_id: str | None=None, *, production_app, production_console) -> tuple[str, dict, OperationsConsole]:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=data)
    client = TestClient(production_app(console))
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
    from tests.semantic_fixture_support import install_fixture_history
    install_fixture_history(console, snapshot_id, rows)


def test_review_document_index_does_not_open_passages(tmp_path: Path, *, production_app, production_console) -> None:
    html, receipt, console = _review_html(tmp_path, production_app=production_app, production_console=production_console)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    assert objects
    assert TWO_COLUMN_CLASS not in html
    assert PASSAGE_COL not in html
    assert 'data-workboard-document=' in html
    assert "review-task-dashboard" not in html
    assert "Onderbouwing uit het brondocument" not in html
    assert not any(obj["object_id"] in html for obj in objects)
    assert "envelope" not in html.lower()
    assert "Documenten" in html
    assert "Documentenhiërarchie" not in html
    assert "Documentenhierarchie" not in html
    assert "draggable" not in html.lower()
    assert "graaf-editor" not in html.lower()


def test_review_card_has_two_column_class(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    html = _review_page(console, receipt["snapshot_id"], target["object_id"], production_app=production_app)
    cards = _cards(html)
    assert cards, "review card must carry the two-column class"
    assert len(cards) == 1
    assert target["object_id"] in cards[0]
    assert "envelope" not in html.lower()
    assert "draggable" not in html.lower()
    assert "graaf-editor" not in html.lower()


def test_review_card_source_left_and_knowledge_object_right(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    rec = next(obj for obj in console.snapshot_objects(receipt['snapshot_id'])
               if 'Verwijs' in ((obj.get('content') or {}).get('clean_text') or ''))
    page = _review_page(console, receipt['snapshot_id'], rec['object_id'], production_app=production_app)
    opened = console.open_source_passage(snapshot_id=receipt['snapshot_id'], object_id=rec['object_id'])
    source = re.search(r'<details class="ko-document-context".*?</details>', page, re.S)
    assert source is not None
    assert page.index('class="ko-document-context"') < page.index('class="ko-object-panel"')
    assert 'Bronpassage en omliggende tekst' in source.group()
    assert 'Verwijs' in source.group()
    assert opened.get('passage')
    assert 'brxe-faadvp' not in source.group() and '&lt;p&gt;' not in source.group()
    assert page.count('class="ko-question"') == 3
    assert not re.search(r'<input[^>]+name="confirmed_object_type"', page)
    assert not re.search(r'<input[^>]+name="eindoordeel"', page)


def test_review_card_uses_clear_labels_and_requires_explicit_answers(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(obj for obj in console.snapshot_objects(receipt['snapshot_id'])
                  if obj['object_type'] not in {'document', 'heading'})
    page = _review_page(console, receipt['snapshot_id'], target['object_id'], production_app=production_app)
    for label in ('Te beoordelen kennisobject', 'Is dit toepasbaar?', 'Is dit compleet?',
                  'Staat dit op de juiste plek?', 'Goedkeuren en opslaan', 'Correctie nodig', 'Later beoordelen'):
        assert label in page
    assert not re.search(r'<input[^>]+type="radio"[^>]+checked', page)
    for name in ('applicable', 'complete', 'placed_correctly'):
        assert page.count('name="' + name + '"') == 2
    assert 'name="proposed_correction"' not in page
    assert 'data-ko-assessment-form' in page
    assert '/source-selection?' in page


def test_review_post_requires_explicit_decision_and_comment_when_needed(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    client = TestClient(production_app(console))
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

    no_revision_comment = client.post(
        "/review",
        data={
            **base,
            "eindoordeel": "goedkeuren_na_correctie",
            "comment": "",
            "suitability": "ja",
        },
    )
    assert no_revision_comment.status_code == 400
    assert "Geef een toelichting" in no_revision_comment.text
    with pytest.raises(ConsoleError, match="review_comment_required"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=target["object_id"],
            decision="revise",
            comment="",
        )


def test_blocked_passages_offer_correction_without_technical_diagnostics() -> None:
    blocked = {
        "object_id": "obj-incomplete",
        "object_type": "unclassified",
        "content": {"clean_text": "Deze bronzin is afgebroken"},
        "governance": {"validation_status": "needs_review"},
        "metadata": {
            "admission": {
                "gate_result": "blocked",
                "reason_codes": ["incomplete_sentence"],
            }
        },
    }

    html = _render_review_index("snap-1", [blocked], "richtlijn", task="control")

    assert "Passages corrigeren (1)" in html
    assert "task=repair" in html
    assert "incomplete_sentence" not in html
    assert "processing-diagnostics" not in html


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


def test_approve_remains_disabled_when_passage_cannot_open(tmp_path: Path, *, production_app, production_console) -> None:
    from tests.test_ko_new_pages import compact_submission
    from tests.test_review_command_bounded_http_v1 import physical_state
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    sid = receipt['snapshot_id']
    target = next(obj for obj in console.snapshot_objects(sid) if obj['object_type'] not in {'document', 'heading'})
    _strip_locator(console, sid, target['object_id'])
    with pytest.raises(ConsoleError):
        console.open_source_passage(snapshot_id=sid, object_id=target['object_id'])
    client = TestClient(production_app(console))
    client.post('/login', data={'username': 'reviewer.bert', 'password': 'bert-secret'})
    page = client.get('/review', params={'document': sid, 'object': target['object_id']})
    button = re.search(r'<button[^>]+value="approve"[^>]*>', page.text)
    assert button and 'disabled' in button.group()
    assert '/source-selection?' in page.text
    before = physical_state(console, sid)
    refused = client.post('/review', data=compact_submission(page), follow_redirects=False)
    assert refused.status_code == 400
    assert physical_state(console, sid) == before
    with pytest.raises(ConsoleError, match='blocked_candidate_not_reviewable'):
        console.confirm_object_type(actor_id=accounts['reviewer']['account_id'], snapshot_id=sid,
            object_id=target['object_id'], confirmed_object_type='explanation')
