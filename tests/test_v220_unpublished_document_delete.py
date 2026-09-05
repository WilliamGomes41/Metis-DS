"""Acceptance tests for Protocol v2.20 unpublished document delete.

Unpublished captured snapshots MAY be removed from the operations console by
an authorized researcher/reviewer. Tests hit the real functions.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.atomic_split_v1 import fusion_is_forbidden, split_meaning_units
from src.extract_html_v1 import extract as extract_html
from src.four_eyes_v1 import requires_four_eyes
from src.object_taxonomy_v1 import (
    is_advice_weight,
    is_continuation_fragment,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_strength_stamp,
    is_tiny_confirmable_text,
    published_object_type,
    recommendation_strength_ui_applies,
)
from src.open_original_v1 import researcher_visible_prose
from src.operations_console_app import create_console_app
from src.operations_console_v1 import (
    CAPTURED,
    ConsoleError,
    OperationsConsole,
    remaining_unclassified,
    review_card_sentence,
    review_stacks,
    safe_store_filename,
    slow_review_duty,
)
from src.review_ledger import read_events


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
APP_SOURCE = ROOT / "src/operations_console_app.py"
KERNEL_SOURCE = ROOT / "src/operations_console_v1.py"
ASGI_SOURCE = ROOT / "src/console_asgi.py"
SLOGAN = "Dit wordt wat een EPD MAG zeggen."
DELETE_LABEL = "Verwijder unpublished document"
CHROME_LABELS = ("Tools", "Home", "Richtlijnen", "Meedenken")
EVENTUEEL = "Eventueel met hulp van de mantelzorger."
OVERWEEG = (
    "Overweeg om bij ouderen met urine-incontinentie én een cognitieve "
    "beperking het advies te geven om op vaste tijden te gaan plassen."
)
CONFIRM_COPY = "Ik bevestig dat ik dit unpublished document wil verwijderen"


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


def _non_document(objects: list[dict]) -> list[dict]:
    return [obj for obj in objects if obj.get("object_type") != "document"]


def _text_of(obj: dict) -> str:
    return re.sub(
        r"\s+",
        " ",
        ((obj.get("content") or {}).get("clean_text") or ""),
    ).strip()


class _VisibleTextParser(HTMLParser):
    """Visible page text without script/style payloads (avoids tag-filter regexes)."""

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


def _objects_path(console: OperationsConsole, snapshot_id: str) -> Path:
    return console._objects_path(snapshot_id)


def _freeze_path(console: OperationsConsole, envelope: dict) -> Path:
    return Path(envelope["binary_path"])


# ---------------------------------------------------------------------------
# 1. Delete control on Documentenhiërarchie only (v2.27 supersedes card/chooser)
# ---------------------------------------------------------------------------


def test_delete_control_on_document_card_and_review_chooser(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Continentie fixture")
    snap = receipt["snapshot_id"]
    client = _client(console)

    ingest_html = client.get("/ingest").text
    assert DELETE_LABEL not in ingest_html
    assert snap in ingest_html

    chooser = client.get("/review").text
    assert DELETE_LABEL not in chooser
    assert snap in chooser
    assert "Beoordeel" in chooser

    tree = client.get("/tree").text
    assert "Documentenhiërarchie" in tree
    assert DELETE_LABEL in tree
    assert snap in tree
    assert CONFIRM_COPY in tree
    assert 'name="confirm_title"' in tree
    assert "Continentie fixture" in _visible_text(tree)

    chosen = client.get(f"/review?document={snap}").text
    assert DELETE_LABEL not in chosen
    assert "Beoordeel" in chosen

    assert "envelope" not in _visible_text(chooser).lower()
    assert "envelope" not in _visible_text(tree).lower()
    assert "envelope" not in _visible_text(ingest_html).lower()


def test_delete_control_absent_for_published_projection(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Gepubliceerd")
    rows = console._load_objects(receipt["snapshot_id"])
    rows[0]["governance"]["publication_status"] = "published"
    console._save_objects(receipt["snapshot_id"], rows)
    client = _client(console)
    chooser = client.get("/review").text
    assert DELETE_LABEL not in chooser
    tree = client.get("/tree").text
    assert DELETE_LABEL not in tree
    ingest_html = client.get("/ingest").text
    assert DELETE_LABEL not in ingest_html


def test_delete_label_is_researcher_dutch() -> None:
    source = APP_SOURCE.read_text(encoding="utf-8")
    assert DELETE_LABEL in source
    assert "Verwijder unpublished document" in source
    assert 'name="confirm"' in source
    assert 'name="confirm_title"' in source


# ---------------------------------------------------------------------------
# 2. Confirmation required; no-confirm does not delete
# ---------------------------------------------------------------------------


def test_kernel_no_confirm_does_not_delete(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Bevestiging")
    snap = receipt["snapshot_id"]
    with pytest.raises(ConsoleError, match="delete_confirmation_required"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snap,
            confirmed=False,
        )
    with pytest.raises(ConsoleError, match="delete_confirmation_required"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snap,
        )
    assert snap in {row["snapshot_id"] for row in console.list_envelopes()}
    assert _objects_path(console, snap).is_file()


def test_http_no_confirm_does_not_delete(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="HTTP bevestiging")
    snap = receipt["snapshot_id"]
    client = _client(console)
    response = client.post(
        "/documents/delete",
        data={"snapshot_id": snap, "next": "/review"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert snap in {row["snapshot_id"] for row in console.list_envelopes()}
    assert _objects_path(console, snap).is_file()
    assert DELETE_LABEL not in client.get("/review").text
    assert DELETE_LABEL in client.get("/tree").text


def test_confirmed_delete_runs(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Weg")
    snap = receipt["snapshot_id"]
    deleted = console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=snap,
        confirmed=True,
        confirm_title="Weg",
    )
    assert deleted["snapshot_id"] == snap
    assert deleted["deleted"] is True
    assert snap not in {row["snapshot_id"] for row in console.list_envelopes()}


# ---------------------------------------------------------------------------
# 3. After delete: gone from Inleveren, Review, Documentenhiërarchie
# ---------------------------------------------------------------------------


def test_after_delete_snapshot_gone_from_inleveren_review_tree(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    keep = _ingest(console, accounts, title="Blijft", filename="blijft.html", family="wondzorg")
    gone = _ingest(console, accounts, title="Weg", filename="weg.html", family="continentie")
    client = _client(console)
    response = client.post(
        "/documents/delete",
        data={
            "snapshot_id": gone["snapshot_id"],
            "confirm": "1",
            "confirm_title": "Weg",
            "next": "/tree",
        },
        follow_redirects=False,
    )
    assert response.status_code in {303, 302}
    ingest_html = client.get("/ingest").text
    review_html = client.get("/review").text
    tree_html = client.get("/tree").text
    assert gone["snapshot_id"] not in ingest_html
    assert gone["snapshot_id"] not in review_html
    assert gone["snapshot_id"] not in tree_html
    assert "Weg" not in _visible_text(ingest_html) or gone["snapshot_id"] not in ingest_html
    assert keep["snapshot_id"] in ingest_html
    assert keep["snapshot_id"] in review_html
    assert keep["snapshot_id"] in tree_html
    assert "Blijft" in _visible_text(tree_html)
    assert "Documentenhiërarchie" in tree_html


# ---------------------------------------------------------------------------
# 4. Objects + envelope gone; freeze bytes MAY be removed
# ---------------------------------------------------------------------------


def test_after_delete_objects_and_envelope_gone(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Objecten weg")
    snap = receipt["snapshot_id"]
    objects_path = _objects_path(console, snap)
    assert objects_path.is_file()
    assert console.snapshot_objects(snap)
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=snap,
        confirmed=True,
        confirm_title="Objecten weg",
    )
    assert snap not in console._envelopes
    assert objects_path.exists() is False
    with pytest.raises(ConsoleError, match="unknown_snapshot"):
        console.snapshot_objects(snap)
    with pytest.raises(ConsoleError, match="unknown_snapshot"):
        console._envelope(snap)
    assert console._bindings.get(snap, []) == [] or snap not in console._bindings


def test_freeze_bytes_of_unpublished_source_may_be_removed(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Freeze mee")
    freeze = _freeze_path(console, receipt)
    digest_dir = freeze.parent
    assert freeze.is_file()
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title="Freeze mee",
    )
    assert freeze.exists() is False
    assert digest_dir.exists() is False or any(digest_dir.iterdir()) is False


def test_shared_freeze_bytes_kept_when_other_snapshot_remains(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    data = _tiny_html("Gedeelde freeze")
    first = _ingest(
        console, accounts, data=data, filename="gedeeld.html", title="Eerste"
    )
    second = _ingest(
        console, accounts, data=data, filename="gedeeld.html", title="Tweede"
    )
    assert first["sha256"] == second["sha256"]
    freeze = _freeze_path(console, first)
    assert freeze.is_file()
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=first["snapshot_id"],
        confirmed=True,
        confirm_title="Eerste",
    )
    assert freeze.is_file()
    assert second["snapshot_id"] in {row["snapshot_id"] for row in console.list_envelopes()}
    assert console.snapshot_objects(second["snapshot_id"])


# ---------------------------------------------------------------------------
# 5. Audit ledger: who, when, snapshot_id, source SHA-256, title
# ---------------------------------------------------------------------------


def test_audit_ledger_records_who_when_snapshot_sha_title(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Audit titel")
    deleted = console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title="Audit titel",
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
    assert details["title"] == "Audit titel"
    assert deleted["capture_is_publication"] is False
    assert "Metis" not in event["actor"]
    assert "Implementation engineer" not in event["actor"]
    assert "Auditor" not in event["actor"]


# ---------------------------------------------------------------------------
# 6. Published projection MUST NOT be deleted
# ---------------------------------------------------------------------------


def test_published_objects_must_not_be_deleted(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Gepubliceerde objecten")
    snap = receipt["snapshot_id"]
    rows = console._load_objects(snap)
    rows[0]["governance"]["publication_status"] = "published"
    console._save_objects(snap, rows)
    with pytest.raises(ConsoleError, match="published_projection_must_not_be_deleted"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snap,
            confirmed=True,
            confirm_title="Gepubliceerde objecten",
        )
    assert snap in {row["snapshot_id"] for row in console.list_envelopes()}
    assert _objects_path(console, snap).is_file()
    assert _freeze_path(console, receipt).is_file()


def test_published_projection_file_is_not_deleted(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    live = _ingest(console, accounts, title="Live unpublished")
    planted = _ingest(console, accounts, title="In projectie", filename="proj.html")
    projection = console.runtime / "published_projection.jsonl"
    payload = [
        {
            "snapshot_id": planted["snapshot_id"],
            "metadata": {"snapshot_id": planted["snapshot_id"], "object_id": "ko-1"},
            "answerability": "supported",
        }
    ]
    projection.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in payload),
        encoding="utf-8",
    )
    original = projection.read_bytes()
    with pytest.raises(ConsoleError, match="published_projection_must_not_be_deleted"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=planted["snapshot_id"],
            confirmed=True,
            confirm_title="In projectie",
        )
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=live["snapshot_id"],
        confirmed=True,
        confirm_title="Live unpublished",
    )
    assert projection.is_file()
    assert projection.read_bytes() == original
    assert planted["snapshot_id"] in {row["snapshot_id"] for row in console.list_envelopes()}


def test_published_envelope_state_must_not_be_deleted(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="State published")
    envelope = console._envelope(receipt["snapshot_id"])
    envelope["state"] = "published"
    console._save_envelopes()
    with pytest.raises(ConsoleError, match="published_projection_must_not_be_deleted"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            confirmed=True,
            confirm_title="State published",
        )


# ---------------------------------------------------------------------------
# 7. Hiding selected objects in a freeze that stays in Review is forbidden
# ---------------------------------------------------------------------------


def test_hide_selected_objects_in_staying_freeze_is_forbidden(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Niet verbergen")
    snap = receipt["snapshot_id"]
    objects = console.snapshot_objects(snap)
    leftover = remaining_unclassified(_non_document(objects))
    target = leftover[0] if leftover else _non_document(objects)[0]
    client = _client(console)
    before = client.get(f"/review?document={snap}").text
    response = client.post(
        "/documents/delete",
        data={
            "snapshot_id": snap,
            "confirm": "1",
            "confirm_title": "Niet verbergen",
            "object_ids": target["object_id"],
            "next": "/review",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    after_objects = {row["object_id"] for row in console.snapshot_objects(snap)}
    assert target["object_id"] in after_objects
    assert {row["object_id"] for row in objects} == after_objects
    after = client.get(f"/review?document={snap}").text
    assert "hide this card" not in APP_SOURCE.read_text(encoding="utf-8").lower()
    assert not hasattr(OperationsConsole, "hide_selected_objects")
    assert not hasattr(OperationsConsole, "delete_object")
    assert "Beoordeel" in before


def test_delete_is_whole_unpublished_snapshot_only() -> None:
    kernel = KERNEL_SOURCE.read_text(encoding="utf-8")
    app = APP_SOURCE.read_text(encoding="utf-8")
    assert "hide_selected_objects_forbidden" in app
    assert "object-picker-delete" not in kernel
    assert "delete_unpublished_snapshot" in kernel


# ---------------------------------------------------------------------------
# 8. Other snapshots untouched; no /home/data global wipe; no SSH path
# ---------------------------------------------------------------------------


def test_other_snapshots_untouched(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    keep = _ingest(console, accounts, title="Houden", filename="houden.html", family="wondzorg")
    gone = _ingest(console, accounts, title="Verwijderen", filename="verwijderen.html")
    keep_objects = console.snapshot_objects(keep["snapshot_id"])
    keep_freeze = _freeze_path(console, keep).read_bytes()
    keep_sha = keep["sha256"]
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=gone["snapshot_id"],
        confirmed=True,
        confirm_title="Verwijderen",
    )
    still = console._envelope(keep["snapshot_id"])
    assert still["title"] == "Houden"
    assert still["sha256"] == keep_sha
    assert still["state"] == CAPTURED
    assert console.snapshot_objects(keep["snapshot_id"]) == keep_objects
    assert _freeze_path(console, still).read_bytes() == keep_freeze


def test_delete_does_not_wipe_home_data_or_unrelated_files(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Geen wipe")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep", encoding="utf-8")
    fake_home = tmp_path / "home" / "data" / "keep-me.txt"
    fake_home.parent.mkdir(parents=True)
    fake_home.write_text("store", encoding="utf-8")
    accounts_path = console.runtime / "accounts.json"
    assert accounts_path.is_file()
    console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title="Geen wipe",
    )
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert fake_home.read_text(encoding="utf-8") == "store"
    assert accounts_path.is_file()
    assert console.runtime.is_dir()
    source_root = (tmp_path / "sources" / "private").resolve()
    assert source_root.is_dir()


def test_no_ssh_or_home_data_wipe_as_product_path() -> None:
    kernel = KERNEL_SOURCE.read_text(encoding="utf-8")
    app = APP_SOURCE.read_text(encoding="utf-8")
    asgi = ASGI_SOURCE.read_text(encoding="utf-8")
    delete_fn = kernel.split("def delete_unpublished_snapshot", 1)[1].split("\n    def ", 1)[0]
    assert "/home/data" not in delete_fn
    assert "ssh" not in delete_fn.lower()
    assert "rmtree" not in delete_fn
    assert "wipe" not in delete_fn.lower()
    combined = f"{kernel}\n{app}"
    assert "ssh " not in combined.lower()
    assert "ssh/" not in combined.lower()
    # Azure host adapter may name /home/data/metis-console as the data root.
    # Delete must not treat a wipe of that path as the product path.
    assert "rmtree(\"/home/data\")" not in combined
    assert "rmtree('/home/data')" not in combined
    assert "rm -rf /home/data" not in combined
    assert "/home/data/metis-console" in asgi


# ---------------------------------------------------------------------------
# 9. No four-eyes / second named reviewer; operator is the logged-in researcher
# ---------------------------------------------------------------------------


def test_uploader_may_delete_without_second_reviewer_or_four_eyes(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Uploader delete")
    deleted = console.delete_unpublished_snapshot(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title="Uploader delete",
    )
    assert deleted["deleted"] is True
    assert deleted["four_eyes_required"] is False
    assert deleted["second_named_reviewer_required"] is False


def test_reviewer_may_delete_unpublished_they_did_not_upload(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Reviewer delete")
    console.delete_unpublished_snapshot(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        confirmed=True,
        confirm_title="Reviewer delete",
    )
    assert receipt["snapshot_id"] not in {row["snapshot_id"] for row in console.list_envelopes()}


def test_publisher_only_is_not_the_delete_operator(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, title="Publisher niet")
    with pytest.raises(ConsoleError, match="unpublished_delete_role_required"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["publisher"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            confirmed=True,
        )
    assert receipt["snapshot_id"] in {row["snapshot_id"] for row in console.list_envelopes()}
    client = _client(console, "publisher.carla")
    html = client.get("/review").text
    assert DELETE_LABEL not in html
    assert DELETE_LABEL not in client.get("/tree").text


def test_forbidden_identities_are_not_the_delete_operator() -> None:
    kernel = KERNEL_SOURCE.read_text(encoding="utf-8")
    assert "FORBIDDEN_REVIEWER_IDENTITIES" in kernel
    assert "implementation engineer" in kernel
    assert "metis" in kernel
    assert "auditor" in kernel


# ---------------------------------------------------------------------------
# 10. Capture is not publication; G2 still blocks publish; serving fail-closed
# ---------------------------------------------------------------------------


def test_delete_is_not_publication_and_g2_still_blocks(tmp_path: Path) -> None:
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
    events = read_events(console._ledger_path)
    delete_events = [row for row in events if row.get("event_type") == "unpublished_snapshot_deleted"]
    assert delete_events
    assert all(row.get("event_type") != "published" for row in delete_events)


def test_unclassified_still_never_served() -> None:
    unclassified = {
        "object_id": "ko-u",
        "object_type": "unclassified",
        "confirmed_object_type": None,
        "content": {"clean_text": "Een zin."},
        "provenance": {"source_locator": {"page": 1}},
    }
    assert published_object_type(unclassified) == "unclassified"
    assert is_advice_weight("action_advice", "unclassified") is False
    assert is_advice_weight("action_advice", "recommendation") is True


# ---------------------------------------------------------------------------
# 11. v2.16–v2.19 review/extract behaviour still holds
# ---------------------------------------------------------------------------


def test_v216_through_v219_review_extract_still_holds(tmp_path: Path) -> None:
    freeze = (
        "<html><body>"
        "<nav>Tools</nav><a>Home</a><span>Richtlijnen</span><p>Meedenken</p>"
        "<h2>1.1 Inleiding</h2>"
        "<h2>2. Inleiding</h2>"
        "<h2>DOEN</h2>"
        "<p>1.</p>"
        f"<p>{OVERWEEG}</p>"
        f"<p>{EVENTUEEL}</p>"
        "<p>Bespreek het onderwerp met de zorgvrager.</p>"
        "</body></html>"
    ).encode("utf-8")
    html_path = tmp_path / "hold.html"
    html_path.write_bytes(freeze)
    fragments = extract_html(html_path, document_id="doc-hold", source_id="src-hold")
    texts = [row["clean_text"] for row in fragments]
    for label in CHROME_LABELS:
        assert label not in texts
    assert "1.1 Inleiding" in texts
    assert "2. Inleiding" in texts
    fused = split_meaning_units(f"{OVERWEEG} {EVENTUEEL}")
    assert len(fused) == 1
    assert EVENTUEEL in fused[0]
    assert is_continuation_fragment(EVENTUEEL) is True
    fused_exception = (
        "Verwijs de cliënt naar de huisarts. "
        "Tenzij samen met de cliënt hiervan wordt afgezien."
    )
    assert fusion_is_forbidden(fused_exception) is True
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts, data=freeze, filename="hold.html", title="Hold")
    objects = _non_document(console.snapshot_objects(receipt["snapshot_id"]))
    stored = [_text_of(obj) for obj in objects]
    for label in CHROME_LABELS:
        assert all(label.casefold() != text.casefold() for text in stored)
    assert all(not is_strength_stamp(_text_of(obj)) for obj in objects)
    assert all(not is_list_number_only(_text_of(obj)) for obj in objects)
    assert all(not is_tiny_confirmable_text(_text_of(obj)) for obj in objects)
    assert EVENTUEEL not in stored
    assert any(OVERWEEG in text and EVENTUEEL in text for text in stored)
    koppen, _inhoud = review_stacks(objects)
    duty = slow_review_duty(objects)
    leftover = remaining_unclassified(objects)
    assert koppen
    assert all(obj.get("proposed_object_type") == "heading" or obj.get("object_type") == "heading" for obj in koppen)
    assert leftover
    rec = next(obj for obj in objects if OVERWEEG in _text_of(obj))
    html = _client(console).get(f"/review?document={receipt['snapshot_id']}").text
    assert SLOGAN not in html
    assert "wat een EPD MAG zeggen" not in html
    assert "envelope" not in html.lower()
    assert "Documentenhiërarchie" in html
    assert "Bevestig geselecteerde koppen als structuur" in html
    assert f"Koppen ({len(koppen)})" in html
    if leftover:
        assert f"Resterend unclassified: {len(leftover)}" in _visible_text(html)
    duty_ids = {obj["object_id"] for obj in duty}
    leftover_ids = {obj["object_id"] for obj in leftover}
    assert duty_ids.isdisjoint(leftover_ids)
    heading = review_card_sentence(rec)
    card = _client(console).get(
        f"/review?document={receipt['snapshot_id']}&object={rec['object_id']}"
    ).text
    object_text = re.search(
        r'<div class="object-text">\s*<p>(.*?)</p>\s*</div>', card, flags=re.S
    )
    body = _visible_text(object_text.group(1)) if object_text else ""
    assert body == "" or re.sub(r"\s+", " ", body) != re.sub(r"\s+", " ", heading)
    assert is_kennisplatform_chrome_text("Tools") is True
    stored = rec.get("confirmed_object_type") or (
        rec.get("object_type") if rec.get("object_type") not in {None, "", "unclassified"} else None
    )
    assert recommendation_strength_ui_applies(rec) is (stored in {"recommendation", "outcome"})
    passage = researcher_visible_prose(
        console.open_source_passage(
            snapshot_id=receipt["snapshot_id"], object_id=rec["object_id"]
        )["passage"]
    )
    assert "<" not in passage
    assert "class=" not in passage
    ingest_form = _client(console).get("/ingest").text
    family_input = re.search(r'<input id="family"[^>]*>', ingest_form)
    assert family_input is not None
    assert "value=" not in family_input.group(0)
    assert requires_four_eyes(rec) in {True, False}


def test_fixture_html_still_extracts_when_present() -> None:
    if not HTML_FIXTURE.is_file():
        pytest.skip("Continentie HTML fixture not in this checkout")
    assert HTML_FIXTURE.is_file()


# ---------------------------------------------------------------------------
# 12. Freeze store paths remain confined (CodeQL / commit 2cc34c1)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename",
    [
        "../escape.html",
        "..\\escape.html",
        "foo/../../etc/passwd",
        "foo/bar.html",
        "..",
        ".",
        "/tmp/escape.html",
        "continentie/../escape.html",
    ],
)
def test_v220_ingest_filename_cannot_escape_source_store(
    tmp_path: Path, filename: str
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    store = (tmp_path / "sources" / "private").resolve()
    with pytest.raises(ConsoleError, match="invalid_store_path"):
        _ingest(console, accounts, filename=filename)
    assert list(tmp_path.rglob("escape.html")) == []
    assert list(tmp_path.rglob("passwd")) == []
    for path in store.rglob("*") if store.exists() else []:
        if path.is_file():
            path.resolve().relative_to(store)


@pytest.mark.parametrize(
    "snapshot_id",
    [
        "../escape",
        "..\\escape",
        "foo/../../etc/passwd",
        "snap-../abcd",
        "snap-0123456789abcdef-01234567/../x",
        "/tmp/snap-0123456789abcdef-01234567",
        "snap-0123456789abcdef-01234567/../../etc/passwd",
    ],
)
def test_v220_delete_snapshot_id_cannot_escape_store(
    tmp_path: Path, snapshot_id: str
) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    _ingest(console, accounts, title="Pad")
    store = (tmp_path / "sources" / "private").resolve()
    objects_dir = (tmp_path / "output" / "runtime" / "operations-console" / "objects").resolve()
    with pytest.raises(ConsoleError, match="unknown_snapshot|invalid_store_path"):
        console.delete_unpublished_snapshot(
            actor_id=accounts["researcher"]["account_id"],
            snapshot_id=snapshot_id,
            confirmed=True,
        )
    assert list(tmp_path.rglob("passwd")) == []
    for directory in (store, objects_dir):
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                path.resolve().relative_to(directory)


def test_v220_safe_filename_still_accepts_plain_basenames() -> None:
    assert safe_store_filename("continentie.html") == "continentie.html"
    assert safe_store_filename("richtlijn-v2.html") == "richtlijn-v2.html"
