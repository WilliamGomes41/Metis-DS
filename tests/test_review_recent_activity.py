"""Review «Recent activity» read-only right panel (ROADMAP Item A).

Right panel on the Review screen for the current document. Newest first;
document-scoped only. Read-only view over the existing append-only /
hash-chained review ledger plus existing review-decision events.
MUST NOT Slack-style live presence / typing / page-open heartbeat.
No new write path; no DB; do not weaken single-writer topology.

PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here. publish()
stays G2-BLOCKED. Item B SHA-256 duplicate guard and Item C
OIDC/release-identity are out of scope.

Markers in this file are CI metadata pointing at these checks
(scripts/release_control_preflight.py and this suite). They are not
live-release evidence.

# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.review_ledger import append_event, read_events


pytestmark = [
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"
ACTIVITY_SOURCE = ROOT / "src/review_recent_activity_v1.py"
CONSOLE_V1_SOURCE = ROOT / "src/operations_console_v1.py"
LEDGER_SOURCE = ROOT / "src/review_ledger.py"

PRESENCE_NEEDLES = (
    "heartbeat",
    "page-open",
    "page_open",
    "is typing",
    "aan het typen",
    "live presence",
    "live-presence",
    "wie is online",
    "currently viewing",
    "presence-widget",
    "data-presence",
    "websocket",
    "who is here",
)

WRITE_NEEDLES = (
    "append_event(",
    "@app.post",
    "sqlite",
    "CREATE TABLE",
    "INSERT INTO",
)


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
    bert = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    dirk = console.create_account(
        username="reviewer.dirk",
        password="dirk-secret",
        roles=("reviewer",),
        display_name="Dirk Reviewer",
    )
    return {"researcher": researcher, "bert": bert, "dirk": dirk}


def _tiny_html(title: str) -> bytes:
    return (
        "<!doctype html><html lang='nl'><head><title>"
        f"{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>Dit is een aanbeveling voor {title} in de praktijk.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(console: OperationsConsole, accounts: dict, *, title: str) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="richtlijn.html",
        data=_tiny_html(title),
        content_type="text/html",
        ingest_kind="new",
        title=title,
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["bert"]["account_id"],
            accounts["dirk"]["account_id"],
        ],
    )


def _fresh_client(console: OperationsConsole) -> TestClient:
    return TestClient(create_console_app(console))


def _client(console: OperationsConsole, username: str = "researcher.anne") -> TestClient:
    client = _fresh_client(console)
    passwords = {
        "researcher.anne": "anne-secret",
        "reviewer.bert": "bert-secret",
        "reviewer.dirk": "dirk-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def _visible_text(html: str) -> str:
    parser = _VisibleTextParser()
    parser.feed(html)
    return " ".join(parser.parts)


def _content_objects(console: OperationsConsole, snapshot_id: str) -> list[dict]:
    return [
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
    ]


def _seed_ledger_event(
    console: OperationsConsole,
    *,
    event_type: str,
    object_id: str,
    object_version: str = "1.0",
    actor: str,
    details: dict | None = None,
) -> dict:
    return append_event(
        console.runtime / "review_ledger.jsonl",
        event_type=event_type,
        object_id=object_id,
        object_version=object_version,
        actor=actor,
        details=details or {},
    )


def _rewrite_occurred_at(console: OperationsConsole, event_hash: str, occurred_at: str) -> None:
    path = console.runtime / "review_ledger.jsonl"
    rows = read_events(path)
    out = []
    for row in rows:
        item = dict(row)
        if item.get("event_hash") == event_hash:
            item["occurred_at"] = occurred_at
        out.append(item)
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in out),
        encoding="utf-8",
    )


def _panel(html: str) -> str:
    match = re.search(
        r'<aside\b[^>]*class="[^"]*\brecent-activity\b[^"]*"[^>]*>.*?</aside>',
        html,
        flags=re.I | re.S,
    )
    assert match, "Review of the current document must render a Recent activity aside"
    return match.group(0)


def _panel_items(panel: str) -> list[str]:
    return re.findall(r"<li\b[^>]*>.*?</li>", panel, flags=re.I | re.S)


def test_review_shows_recent_activity_panel_for_current_document(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Continentie richtlijn")
    objects = _content_objects(console, receipt["snapshot_id"])
    assert objects
    target = objects[0]
    _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=target["object_id"],
        actor="reviewer.bert",
        details={
            "review_snapshot_hash": "hash-approve",
            "comment": "",
            "proposed_correction": "",
        },
    )
    client = _client(console)
    index = client.get(f"/review?document={receipt['snapshot_id']}").text
    card = client.get(
        f"/review?document={receipt['snapshot_id']}&object={target['object_id']}"
    ).text
    for html in (index, card):
        panel = _panel(html)
        visible = _visible_text(panel)
        assert "Recent activity" in visible
        assert "Bert" in visible
        assert target["object_id"] in panel
        assert re.search(r"approved|goedkeur", visible, flags=re.I)
        assert "<form" not in panel.lower()
        assert "<input" not in panel.lower()
        assert "<textarea" not in panel.lower()
        assert "<button" not in panel.lower()


def test_recent_activity_is_newest_first(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Volgorde richtlijn")
    objects = _content_objects(console, receipt["snapshot_id"])
    first, second = objects[0], objects[1] if len(objects) > 1 else objects[0]
    older = _seed_ledger_event(
        console,
        event_type="clinical_review_revise",
        object_id=first["object_id"],
        actor="reviewer.dirk",
        details={
            "review_snapshot_hash": "hash-old",
            "comment": "Graag aanscherpen",
            "proposed_correction": "Duidelijker formuleren",
        },
    )
    newer = _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=second["object_id"],
        actor="reviewer.bert",
        details={
            "review_snapshot_hash": "hash-new",
            "comment": "",
            "proposed_correction": "",
        },
    )
    _rewrite_occurred_at(console, older["event_hash"], "2026-01-01T10:00:00+00:00")
    _rewrite_occurred_at(console, newer["event_hash"], "2026-02-01T10:00:00+00:00")
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    panel = _panel(html)
    items = _panel_items(panel)
    assert items, "activity list must contain rows"
    bert_at = panel.find("Bert")
    dirk_at = panel.find("Dirk")
    assert bert_at != -1 and dirk_at != -1
    assert bert_at < dirk_at, "newest review decision must appear before older rows"
    visible_items = [_visible_text(item) for item in items]
    bert_index = next(i for i, text in enumerate(visible_items) if "Bert" in text)
    dirk_index = next(i for i, text in enumerate(visible_items) if "Dirk" in text)
    assert bert_index < dirk_index


def test_recent_activity_is_document_scoped_not_global(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    current = _ingest(console, accounts, title="Huidig document")
    other = _ingest(console, accounts, title="Ander document")
    current_obj = _content_objects(console, current["snapshot_id"])[0]
    other_obj = _content_objects(console, other["snapshot_id"])[0]
    _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=current_obj["object_id"],
        actor="reviewer.bert",
        details={"review_snapshot_hash": "here", "comment": "", "proposed_correction": ""},
    )
    _seed_ledger_event(
        console,
        event_type="clinical_review_revise",
        object_id=other_obj["object_id"],
        actor="reviewer.dirk",
        details={
            "review_snapshot_hash": "there",
            "comment": "niet dit document",
            "proposed_correction": "",
        },
    )
    html = _client(console).get(f"/review?document={current['snapshot_id']}").text
    panel = _panel(html)
    visible = _visible_text(panel)
    assert "Bert" in visible
    assert current_obj["object_id"] in panel
    assert other_obj["object_id"] not in panel
    assert "niet dit document" not in visible
    assert "Dirk" not in visible


def test_recent_activity_reads_existing_ledger_and_decision_fields(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Ledger velden")
    objects = _content_objects(console, receipt["snapshot_id"])
    approved = objects[0]
    revised = objects[1] if len(objects) > 1 else objects[0]
    type_changed = objects[-1]
    _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=approved["object_id"],
        object_version=str(approved.get("object_version") or "1.0"),
        actor="reviewer.bert",
        details={"review_snapshot_hash": "a", "comment": "", "proposed_correction": ""},
    )
    _seed_ledger_event(
        console,
        event_type="clinical_review_revise",
        object_id=revised["object_id"],
        object_version=str(revised.get("object_version") or "1.0"),
        actor="reviewer.dirk",
        details={
            "review_snapshot_hash": "b",
            "comment": "Graag herzien",
            "proposed_correction": "Zet de zin scherper",
        },
    )
    _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=type_changed["object_id"],
        actor="researcher.anne",
        details={
            "review_snapshot_hash": "c",
            "comment": "",
            "proposed_correction": "",
            "from_type": "explanation",
            "to_type": "condition",
        },
    )
    before = (console.runtime / "review_ledger.jsonl").read_text(encoding="utf-8")
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    after = (console.runtime / "review_ledger.jsonl").read_text(encoding="utf-8")
    assert after == before, "GET Review must not append to the ledger"
    panel = _panel(html)
    visible = _visible_text(panel)
    assert "clinical_review_approve" in panel
    assert "clinical_review_revise" in panel
    assert approved["object_id"] in panel
    assert revised["object_id"] in panel
    assert "reviewer.bert" in panel or "Bert" in visible
    assert "occurred_at" in panel or re.search(r"20\d\d", panel)
    assert "Graag herzien" in visible
    assert "Zet de zin scherper" in visible
    assert re.search(r"approved|goedkeur", visible, flags=re.I)
    assert re.search(r"revision|herziening", visible, flags=re.I)
    assert re.search(r"explanation|Toelichting", visible)
    assert re.search(r"condition|Voorwaarde", visible)
    assert "Anne" in visible
    assert re.search(r"upload|inlever|ingevoerd", visible, flags=re.I)


def test_recent_activity_empty_or_no_document_is_fail_closed(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    other = _ingest(console, accounts, title="Alleen ander document")
    other_obj = _content_objects(console, other["snapshot_id"])[0]
    _seed_ledger_event(
        console,
        event_type="clinical_review_approve",
        object_id=other_obj["object_id"],
        actor="reviewer.bert",
        details={"review_snapshot_hash": "x", "comment": "", "proposed_correction": ""},
    )
    client = _client(console)
    chooser = client.get("/review").text
    assert "recent-activity" not in chooser
    assert "Recent activity" not in _visible_text(chooser)
    unknown = client.get("/review?document=snap-does-not-exist").text
    assert "recent-activity" not in unknown
    empty_doc = _ingest(console, accounts, title="Leeg document")
    empty_html = client.get(f"/review?document={empty_doc['snapshot_id']}").text
    panel = _panel(empty_html)
    visible = _visible_text(panel)
    assert "Recent activity" in visible
    assert other_obj["object_id"] not in panel
    assert "Bert" not in visible
    assert (
        re.search(r"Nog geen|geen recente|geen activiteit", visible, flags=re.I)
        or "Anne" in visible
    )


def test_recent_activity_has_no_presence_widgets() -> None:
    app = APP_SOURCE.read_text(encoding="utf-8")
    activity = ACTIVITY_SOURCE.read_text(encoding="utf-8") if ACTIVITY_SOURCE.is_file() else ""
    blob = f"{app}\n{activity}"
    lowered = blob.lower()
    for needle in PRESENCE_NEEDLES:
        assert needle not in lowered, f"presence/heartbeat is out of scope: {needle}"
    assert ACTIVITY_SOURCE.is_file(), "read-only activity projection module must exist"


def test_recent_activity_has_no_new_write_path() -> None:
    assert ACTIVITY_SOURCE.is_file(), "read-only activity projection module must exist"
    activity = ACTIVITY_SOURCE.read_text(encoding="utf-8")
    app = APP_SOURCE.read_text(encoding="utf-8")
    assert "append_event" not in activity
    assert "append_event(" not in app or app.count("append_event") == 0
    assert "@app.post" not in activity
    assert "/recent-activity" not in app
    assert '"/activity"' not in app
    assert "CREATE TABLE" not in activity
    assert "sqlite" not in activity.lower()
    for needle in ("heartbeat", "presence", "typing indicator"):
        assert needle not in activity.lower()
    console_v1 = CONSOLE_V1_SOURCE.read_text(encoding="utf-8")
    ledger = LEDGER_SOURCE.read_text(encoding="utf-8")
    assert "def append_event" in ledger
    assert "append_event(" in console_v1
    assert "from src.review_ledger import append_event" in console_v1


def test_document_activity_rows_unit_newest_first_and_scoped() -> None:
    from src.review_recent_activity_v1 import document_activity_rows

    events = [
        {
            "event_type": "clinical_review_revise",
            "object_id": "obj-old",
            "object_version": "1.0",
            "actor": "reviewer.dirk",
            "occurred_at": "2026-01-01T09:00:00+00:00",
            "details": {
                "comment": "Graag herzien",
                "proposed_correction": "correctie",
            },
        },
        {
            "event_type": "clinical_review_approve",
            "object_id": "obj-new",
            "object_version": "1.1",
            "actor": "reviewer.bert",
            "occurred_at": "2026-03-01T09:00:00+00:00",
            "details": {"comment": "", "proposed_correction": ""},
        },
        {
            "event_type": "clinical_review_approve",
            "object_id": "obj-other",
            "object_version": "1.0",
            "actor": "reviewer.bert",
            "occurred_at": "2026-04-01T09:00:00+00:00",
            "details": {"comment": "ander document", "proposed_correction": ""},
        },
    ]
    rows = document_activity_rows(
        events=events,
        snapshot_id="snap-current",
        object_ids={"obj-old", "obj-new"},
        envelope={
            "snapshot_id": "snap-current",
            "uploader_account_id": "acc-anne",
            "acquired_at": "2025-12-01T08:00:00Z",
        },
        accounts=[
            {
                "account_id": "acc-anne",
                "username": "researcher.anne",
                "display_name": "Anne Onderzoeker",
            },
            {
                "account_id": "acc-bert",
                "username": "reviewer.bert",
                "display_name": "Bert Reviewer",
            },
            {
                "account_id": "acc-dirk",
                "username": "reviewer.dirk",
                "display_name": "Dirk Reviewer",
            },
        ],
    )
    summaries = " ".join(str(row.get("summary") or "") for row in rows)
    actors = [row.get("actor_label") or row.get("actor") for row in rows]
    assert actors[0] and "Bert" in str(actors[0])
    assert any("Dirk" in str(actor) for actor in actors)
    assert any("Anne" in str(actor) for actor in actors)
    assert "ander document" not in summaries
    assert rows[0]["object_id"] == "obj-new"
    assert all(row.get("object_id") != "obj-other" for row in rows)
    assert any(row.get("decision") == "approve" for row in rows)
    assert any(row.get("decision") == "revise" for row in rows)
    assert any(row.get("comment") == "Graag herzien" for row in rows)
    assert any(row.get("proposed_correction") == "correctie" for row in rows)
    assert any(row.get("source") == "envelope" for row in rows)
    assert any(row.get("source") == "ledger" for row in rows)
