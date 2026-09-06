"""Stale-write reviewer UX (wave-1 residual).

When a review/object save is rejected as stale /
``snapshot_object_write_conflict``, the reviewer MUST NOT see a success
flash or a next-object redirect. Concurrent stale rejection MUST keep
the submitted input on the form so it can be retried against a fresh
revision. PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
publish() stays G2-BLOCKED. Wave 2 ingest and wave 3 stay out of scope.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
SNAPSHOT_WRITE_CONFLICT = "snapshot_object_write_conflict"
UNIQUE_COMMENT = "G1-stale-write-ux-comment-ANNE-42"
UNIQUE_CORRECTION = "G1-stale-write-ux-correctie-ANNE-42"
UNIQUE_SUITABILITY = "geen_kenniseenheid"
CONFLICT_COPY = (
    "niet opgeslagen",
    "tussentijds gewijzigd",
)

pytestmark = [
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


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


def _ingest(console: OperationsConsole, accounts: dict) -> dict:
    return console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=HTML_FIXTURE.read_bytes(),
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


def _content_rows(console: OperationsConsole, snapshot_id: str) -> list[dict]:
    rows = [
        row
        for row in console.snapshot_objects(snapshot_id)
        if row.get("object_type") != "document"
    ]
    assert len(rows) >= 2
    return rows


def _client(console: OperationsConsole, username: str = "researcher.anne") -> TestClient:
    client = TestClient(create_console_app(console))
    passwords = {
        "researcher.anne": "anne-secret",
        "reviewer.bert": "bert-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


def _passage_suitability(row: dict) -> str:
    return str(((row.get("metadata") or {}).get("review_passage") or {}).get("suitability") or "")


def _radio_checked(html: str, name: str, value: str) -> bool:
    pattern = (
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="{re.escape(value)}"[^>]*>'
        rf'|<input[^>]*value="{re.escape(value)}"[^>]*name="{re.escape(name)}"[^>]*>'
    )
    for match in re.finditer(pattern, html):
        if re.search(r"\bchecked\b", match.group(0)):
            return True
    return False


def _textarea_value(html: str, name: str) -> str:
    match = re.search(
        rf'<textarea[^>]*name="{re.escape(name)}"[^>]*>(.*?)</textarea>',
        html,
        flags=re.S,
    )
    return match.group(1) if match else ""


def _review_payload(snapshot_id: str, object_id: str) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "object_id": object_id,
        "suitability": UNIQUE_SUITABILITY,
        "documentpositie_action": "dit_klopt",
        "type_action": "dit_klopt",
        "eindoordeel": "later_beoordelen",
        "comment": UNIQUE_COMMENT,
        "proposed_correction": UNIQUE_CORRECTION,
    }


def _install_concurrent_winner(
    console: OperationsConsole,
    snapshot_id: str,
    other_object_id: str,
) -> None:
    """On the first save of this snapshot, a concurrent console wins the file.

    TestClient may run the POST on another thread, so thread-local expected
    pins from the test thread do not apply. The winner must land between this
    request's remember and its ``_save_objects``.
    """
    real_save = OperationsConsole._save_objects
    fired = {"done": False}

    def losing_save(self: OperationsConsole, target_snapshot: str, rows: list[dict]) -> None:
        if target_snapshot == snapshot_id and not fired["done"]:
            fired["done"] = True
            other = OperationsConsole(
                root=self.root,
                source_store=self.source_store,
                runtime=self.runtime,
            )
            other_rows = other._load_objects(target_snapshot)
            for row in other_rows:
                if row["object_id"] == other_object_id:
                    row["reliability_marker"] = "concurrent-winner"
            other._save_objects(target_snapshot, other_rows)
        return real_save(self, target_snapshot, rows)

    console._save_objects = losing_save.__get__(console, OperationsConsole)  # type: ignore[method-assign]


def _stale_review_post(tmp_path: Path) -> tuple[TestClient, dict, str, object]:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first, second = _content_rows(console, snapshot_id)[:2]
    client = _client(console)
    opened = client.get(f"/review?document={snapshot_id}&object={first['object_id']}")
    assert opened.status_code == 200
    assert 'data-review-form' in opened.text
    _install_concurrent_winner(console, snapshot_id, second["object_id"])
    posted = client.post(
        "/review",
        data=_review_payload(snapshot_id, first["object_id"]),
        follow_redirects=False,
    )
    return client, receipt, first["object_id"], posted


def test_stale_review_save_does_not_show_success_or_redirect_next(tmp_path: Path) -> None:
    _client, receipt, object_id, posted = _stale_review_post(tmp_path)
    location = posted.headers.get("location") or ""
    body = posted.text
    assert posted.status_code != 303, "stale write MUST NOT follow the success redirect"
    assert posted.status_code in {200, 409}
    assert not location or object_id in location
    assert "succes" not in body.lower()
    assert SNAPSHOT_WRITE_CONFLICT in body or 'data-stale-write-conflict' in body
    lowered = body.lower()
    for phrase in CONFLICT_COPY:
        assert phrase in lowered, phrase
    assert 'data-review-form' in body
    assert f'name="object_id" value="{object_id}"' in body
    live = next(
        row
        for row in OperationsConsole(
            root=tmp_path,
            source_store=tmp_path / "sources" / "private",
            runtime=tmp_path / "output" / "runtime" / "operations-console",
        ).snapshot_objects(receipt["snapshot_id"])
        if row["object_id"] == object_id
    )
    assert _passage_suitability(live) != UNIQUE_SUITABILITY
    assert UNIQUE_COMMENT not in str(live)


def test_stale_review_save_keeps_submitted_input_in_the_form(tmp_path: Path) -> None:
    _client, _receipt, object_id, posted = _stale_review_post(tmp_path)
    body = posted.text
    assert posted.status_code != 303
    assert 'data-review-form' in body
    assert UNIQUE_COMMENT in _textarea_value(body, "comment")
    assert UNIQUE_CORRECTION in _textarea_value(body, "proposed_correction")
    assert _radio_checked(body, "suitability", UNIQUE_SUITABILITY)
    assert _radio_checked(body, "eindoordeel", "later_beoordelen")
    assert f'name="object_id" value="{object_id}"' in body
    assert "Actie niet uitgevoerd" not in body


def test_stale_review_save_retry_applies_input_after_fresh_revision(tmp_path: Path) -> None:
    client, receipt, object_id, posted = _stale_review_post(tmp_path)
    assert posted.status_code != 303
    assert UNIQUE_COMMENT in posted.text
    retried = client.post(
        "/review",
        data=_review_payload(receipt["snapshot_id"], object_id),
        follow_redirects=False,
    )
    assert retried.status_code in {303, 200}
    location = retried.headers.get("location") or ""
    if retried.status_code == 303:
        assert "/review" in location
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    live = next(
        row
        for row in console.snapshot_objects(receipt["snapshot_id"])
        if row["object_id"] == object_id
    )
    assert _passage_suitability(live) == UNIQUE_SUITABILITY
    stored = {row["object_id"]: row for row in console._load_objects(receipt["snapshot_id"])}
    assert any(row.get("reliability_marker") == "concurrent-winner" for row in stored.values())
