"""Protocol v2.27 first wave: Documentenhiërarchie-only unpublished delete + type-to-confirm.

Surface restriction + exact title confirmation. Prior v2.20 kernel behaviour
stays except those two locks. publish() stays G2-BLOCKED.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review_ledger import read_events


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"
KERNEL_SOURCE = ROOT / "src/operations_console_v1.py"
ASGI_SOURCE = ROOT / "src/console_asgi.py"
DELETE_LABEL = "Verwijder unpublished document"
CONFIRM_COPY = "Ik bevestig dat ik dit unpublished document wil verwijderen"
TITLE_FIELD = "confirm_title"
NO_DELETE_ROOMS = (
    ("/ingest", "Inleveren"),
    ("/review", "Review"),
    ("/publish", "Publiceren"),
    ("/accounts", "Accounts"),
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
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    return {"researcher": researcher, "reviewer": reviewer, "publisher": publisher}


def _tiny_html(title: str) -> bytes:
    return (
        "<!doctype html><html lang='nl'><head><title>"
        f"{title}</title></head><body>"
        f"<h1>{title}</h1>"
        f"<p>Dit is een aanbeveling voor {title} in de praktijk.</p>"
        "</body></html>"
    ).encode("utf-8")


def _ingest(
    console: OperationsConsole,
    accounts: dict,
    *,
    data: bytes | None = None,
    filename: str = "richtlijn.html",
    title: str = "Test richtlijn",
    family: str = "continentie",
    **kwargs,
) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename=filename,
        data=data if data is not None else _tiny_html(title),
        content_type="text/html",
        ingest_kind="new",
        title=title,
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/richtlijn",
        class_="richtlijn",
        family=family,
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )
    defaults.update(kwargs)
    return console.ingest(**defaults)


def _client(console: OperationsConsole, username: str = "researcher.anne") -> TestClient:
    client = TestClient(create_console_app(console))
    passwords = {
        "reviewer.bert": "bert-secret",
        "researcher.anne": "anne-secret",
        "publisher.carla": "carla-secret",
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


def _has_delete_control(html: str) -> bool:
    return (
        DELETE_LABEL in html
        or 'action="/documents/delete"' in html
        or "delete-unpublished" in html
    )


def _delete_forms(html: str) -> list[str]:
    return re.findall(
        r'<form[^>]*class="[^"]*delete-unpublished[^"]*"[^>]*>.*?</form>',
        html,
        flags=re.S,
    )


# ---------------------------------------------------------------------------
# 1. Delete control absent from every room except Documentenhiërarchie
# ---------------------------------------------------------------------------


def test_delete_control_absent_from_inleveren_review_publiceren_accounts(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Continentie fixture")
    snap = receipt["snapshot_id"]
    client = _client(console)

    for path, heading in NO_DELETE_ROOMS:
        html = client.get(path).text
        assert heading in html
        assert DELETE_LABEL not in html
        assert not _has_delete_control(html)
        if heading in {"Inleveren", "Review"}:
            assert snap in html

    chosen = client.get(f"/review?document={snap}").text
    assert "Beoordeel" in chosen
    assert DELETE_LABEL not in chosen
    assert not _has_delete_control(chosen)

    ingest_receipt = client.get("/ingest").text
    assert "Inleveren" in ingest_receipt
    assert DELETE_LABEL not in ingest_receipt


def test_no_separate_delete_room_or_kamer(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest(console, accounts, title="Geen delete-kamer")
    client = _client(console)
    tree = client.get("/tree").text
    visible = _visible_text(tree)
    assert "Documentenhiërarchie" in tree
    assert re.search(r">Verwijderen<", tree) is None
    assert "Delete" not in visible
    assert client.get("/delete").status_code in {404, 405}
    rooms = re.findall(r'<a href="(/[a-z]+)(?:\?[^"]*)?"', tree)
    assert "/ingest" in rooms
    assert "/tree" in rooms
    assert "/review" in rooms
    assert "/publish" in rooms
    assert "/accounts" in rooms
    assert "/delete" not in rooms


def test_delete_control_present_on_documentenhierarchie_only(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Alleen hiërarchie")
    snap = receipt["snapshot_id"]
    client = _client(console)

    tree = client.get("/tree").text
    assert "Documentenhiërarchie" in tree
    assert DELETE_LABEL in tree
    assert snap in tree
    forms = _delete_forms(tree)
    assert forms
    assert all('action="/documents/delete"' in form for form in forms)
    assert all(TITLE_FIELD in form for form in forms)

    for path, _heading in NO_DELETE_ROOMS:
        assert DELETE_LABEL not in client.get(path).text

    assert "envelope" not in _visible_text(tree).lower()


# ---------------------------------------------------------------------------
# 2. Type-to-confirm shows exact title; wrong/empty title does not delete
# ---------------------------------------------------------------------------


def test_type_to_confirm_shows_exact_title_on_documentenhierarchie(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Continentie bij ouderen"
    _ingest(console, accounts, title=title)
    html = _client(console).get("/tree").text
    visible = _visible_text(html)
    assert title in visible
    forms = _delete_forms(html)
    assert forms
    form = forms[0]
    assert title in form
    assert f'name="{TITLE_FIELD}"' in form
    assert CONFIRM_COPY in form
    assert DELETE_LABEL in form
    assert "snapshot" not in _visible_text(form).lower()
    assert "envelope" not in _visible_text(form).lower()


def test_kernel_wrong_or_empty_title_does_not_delete(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Exacte titel"
    receipt = _ingest(console, accounts, title=title)
    snap = receipt["snapshot_id"]
    actor = accounts["researcher"]["account_id"]
    for typed in ("", "Exacte", "exacte titel", "Exacte titel ", " Andere titel"):
        with pytest.raises(ConsoleError, match="delete_title_confirmation_required"):
            console.delete_unpublished_snapshot(
                actor_id=actor,
                snapshot_id=snap,
                confirmed=True,
                confirm_title=typed,
            )
    assert snap in {row["snapshot_id"] for row in console.list_envelopes()}
    assert console._objects_path(snap).is_file()


def test_kernel_generic_confirm_without_exact_title_does_not_delete(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Bevestig alleen")
    snap = receipt["snapshot_id"]
    with pytest.raises(ConsoleError, match="delete_title_confirmation_required"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snap,
            confirmed=True,
        )
    assert snap in {row["snapshot_id"] for row in console.list_envelopes()}


def test_http_wrong_empty_or_partial_title_does_not_delete(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "HTTP titel"
    receipt = _ingest(console, accounts, title=title)
    snap = receipt["snapshot_id"]
    client = _client(console)
    for typed in ("", "HTTP", "HTTP titelX", "andere"):
        response = client.post(
            "/documents/delete",
            data={
                "snapshot_id": snap,
                "confirm": "1",
                "confirm_title": typed,
                "next": "/tree",
            },
            follow_redirects=False,
        )
        assert response.status_code == 400
        assert snap in {row["snapshot_id"] for row in console.list_envelopes()}
    assert DELETE_LABEL in client.get("/tree").text


def test_exact_title_match_required_then_delete_runs(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Weg na exacte titel"
    receipt = _ingest(console, accounts, title=title)
    snap = receipt["snapshot_id"]
    deleted = console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=snap,
        confirmed=True,
        confirm_title=title,
    )
    assert deleted["deleted"] is True
    assert deleted["title"] == title
    assert snap not in {row["snapshot_id"] for row in console.list_envelopes()}


def test_http_exact_title_match_deletes_from_documentenhierarchie(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Weg via hiërarchie"
    receipt = _ingest(console, accounts, title=title)
    snap = receipt["snapshot_id"]
    client = _client(console)
    response = client.post(
        "/documents/delete",
        data={
            "snapshot_id": snap,
            "confirm": "1",
            "confirm_title": title,
            "next": "/tree",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 302}
    assert snap not in {row["snapshot_id"] for row in console.list_envelopes()}
    tree = client.get("/tree").text
    assert snap not in tree
    assert title not in _visible_text(tree)


# ---------------------------------------------------------------------------
# 3. Unpublished-only; published projection not deleted; audit ledger
# ---------------------------------------------------------------------------


def test_unpublished_only_published_projection_not_deleted(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    unpublished = _ingest(console, accounts, title="Live unpublished")
    planted = _ingest(console, accounts, title="In projectie", filename="proj.html")
    rows = console._load_objects(planted["snapshot_id"])
    rows[0]["governance"]["publication_status"] = "published"
    console._save_objects(planted["snapshot_id"], rows)
    with pytest.raises(ConsoleError, match="published_projection_must_not_be_deleted"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=planted["snapshot_id"],
            confirmed=True,
            confirm_title="In projectie",
        )
    client = _client(console)
    tree = client.get("/tree").text
    assert DELETE_LABEL in tree
    assert unpublished["snapshot_id"] in tree
    planted_forms = [
        form
        for form in _delete_forms(tree)
        if planted["snapshot_id"] in form
    ]
    assert planted_forms == []
    assert planted["snapshot_id"] in {row["snapshot_id"] for row in console.list_envelopes()}


def test_audit_ledger_row_still_recorded_after_type_to_confirm(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Audit na type-to-confirm"
    receipt = _ingest(console, accounts, title=title)
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title=title,
    )
    events = [
        row
        for row in read_events(console._ledger_path)
        if row.get("event_type") == "unpublished_snapshot_deleted"
    ]
    assert len(events) == 1
    event = events[0]
    assert event["actor"] == "researcher.anne"
    assert event["occurred_at"]
    details = event["details"]
    assert details["snapshot_id"] == receipt["snapshot_id"]
    assert details["sha256"] == receipt["sha256"]
    assert details["title"] == title


# ---------------------------------------------------------------------------
# 4. No SSH/wipe; four-eyes not required; G2 still blocks publish
# ---------------------------------------------------------------------------


def test_no_ssh_wipe_and_four_eyes_not_required_for_unpublished_delete(
    tmp_path: Path,
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    title = "Geen four-eyes"
    receipt = _ingest(console, accounts, title=title)
    deleted = console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title=title,
    )
    assert deleted["four_eyes_required"] is False
    assert deleted["second_named_reviewer_required"] is False
    kernel = KERNEL_SOURCE.read_text(encoding="utf-8")
    app = APP_SOURCE.read_text(encoding="utf-8")
    asgi = ASGI_SOURCE.read_text(encoding="utf-8")
    delete_fn = kernel.split("def delete_unpublished_snapshot", 1)[1].split("\n    def ", 1)[0]
    assert "/home/data" not in delete_fn
    assert "ssh" not in delete_fn.lower()
    assert "rmtree" not in delete_fn
    assert "wipe" not in delete_fn.lower()
    combined = f"{kernel}\n{app}"
    assert "rmtree(\"/home/data\")" not in combined
    assert "rm -rf /home/data" not in combined
    assert "/home/data/metis-console" in asgi


def test_g2_still_blocks_publish_after_v227_delete_surface(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    keep = _ingest(console, accounts, title="Nog live", filename="live.html")
    gone = _ingest(console, accounts, title="Opruimen", filename="opruimen.html")
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=gone["snapshot_id"],
        confirmed=True,
        confirm_title="Opruimen",
    )
    published = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=keep["snapshot_id"],
    )
    assert published["g2"] == "BLOCKED"
    assert published["status"] == "BLOCKED"
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=keep["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    html = _client(console, "publisher.carla").get("/publish").text
    assert "geblokkeerd" in html.lower() or "BLOCKED" in html
    assert DELETE_LABEL not in html


def test_app_source_does_not_offer_delete_outside_tree() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")
    ingest_list = source.split("def _ingested_document_list", 1)[1].split("\ndef ", 1)[0]
    assert "_unpublished_delete_control" not in ingest_list
    ingest_get = source.split("def ingest_get", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in ingest_get
    ingest_post = source.split("def ingest_post", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in ingest_post
    review = source.split("def review_get", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in review
    publish = source.split("def publish_get", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in publish
    accounts = source.split("def accounts_get", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" not in accounts
    tree = source.split("def tree(", 1)[1].split("\n    @app.", 1)[0]
    assert "_unpublished_delete_control" in tree
    assert TITLE_FIELD in source
    assert DELETE_LABEL in source
    assert "PROTOCOL_V2_27" not in source
    assert "documentenhierarchie_type_confirm" not in source
