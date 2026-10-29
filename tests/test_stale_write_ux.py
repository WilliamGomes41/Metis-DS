"""Stale-write reviewer UX (wave-1 residual).

When a review/object save is rejected as stale /
``snapshot_object_write_conflict``, the reviewer MUST NOT see a success
flash or a next-object redirect. Concurrent stale rejection MUST keep
the submitted draft without issuing a new mutation precondition. A retry
requires explicit inspection of the current passage through GET.
PROTOCOL.md and docs/PROTOCOL_V2_* are not edited here.
publish() stays G2-BLOCKED. Wave 2 ingest and wave 3 stay out of scope.
Package migration regression evidence: storage concurrency and stale-write behavior must remain unchanged.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import html
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import OperationsConsole
from src.review.review_ledger import read_events

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


def _client(console: OperationsConsole, username: str='researcher.anne', *, production_app) -> TestClient:
    client = TestClient(production_app(console))
    passwords = {
        "researcher.anne": "anne-secret",
        "reviewer.bert": "bert-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


def _passage_suitability(row: dict) -> str:
    return str(((row.get("metadata") or {}).get("review_passage") or {}).get("suitability") or "")


def _retained_value(body: str, name: str) -> str:
    match = re.search(rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]*)"', body)
    assert match, f"stale draft must retain {name}"
    return html.unescape(match.group(1))


def _textarea_value(html: str, name: str) -> str:
    match = re.search(
        rf'<textarea[^>]*name="{re.escape(name)}"[^>]*>(.*?)</textarea>',
        html,
        flags=re.S,
    )
    return match.group(1) if match else ""


def _form_revision(body: str) -> str:
    match = re.search(r'<input[^>]*name="snapshot_revision"[^>]*value="([^"]+)"', body)
    assert match, "The inspected current GET must expose the revision being reviewed"
    return html.unescape(match.group(1))


def _assert_stale_draft(response, snapshot_id, object_id, *, comment=UNIQUE_COMMENT,
                        correction=UNIQUE_CORRECTION):
    assert response.status_code == 409
    body = response.text
    assert 'data-stale-write-conflict' in body
    assert 'data-review-draft' in body
    assert not re.search(r'<form\b[^>]*\bdata-review-form\b', body)
    assert 'name="snapshot_revision"' not in body
    assert html.unescape(_textarea_value(body, "comment")) == comment
    assert html.unescape(_textarea_value(body, "proposed_correction")) == correction
    assert re.search(r'<textarea[^>]*name="proposed_correction"[^>]*readonly', body)
    assert _retained_value(body, "suitability") == UNIQUE_SUITABILITY
    assert _retained_value(body, "eindoordeel") == "afwijzen"
    link = re.search(r'<a href="([^"]+)">Bekijk de actuele passage</a>', body)
    assert link
    location = html.unescape(link.group(1))
    query = parse_qs(urlsplit(location).query)
    assert query["document"] == [snapshot_id]
    assert query["object"] == [object_id]
    return location


def _inspect_current(client, console, response, snapshot_id, object_id, previous_revision,
                     *, comment=UNIQUE_COMMENT, correction=UNIQUE_CORRECTION):
    from src.review.review_passage_read_v1 import PREFIX, resolve_review_revision
    location = _assert_stale_draft(response, snapshot_id, object_id,
                                  comment=comment, correction=correction)
    before = console.snapshot_objects(snapshot_id)
    current = client.get(location)
    assert current.status_code == 200
    fresh = _form_revision(current.text)
    assert fresh.startswith(PREFIX) and fresh != previous_revision
    assert resolve_review_revision(console, snapshot_id, fresh) == console.objects_revision(snapshot_id)
    assert comment not in html.unescape(current.text)
    assert correction not in html.unescape(current.text)
    assert console.snapshot_objects(snapshot_id) == before
    return fresh


def _review_payload(snapshot_id: str, object_id: str, revision: str) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "object_id": object_id,
        "snapshot_revision": revision,
        "suitability": UNIQUE_SUITABILITY,
        "documentpositie_action": "dit_klopt",
        "type_action": "dit_klopt",
        "eindoordeel": "afwijzen",
        "comment": UNIQUE_COMMENT,
        "proposed_correction": UNIQUE_CORRECTION,
    }


def _install_concurrent_winner(console: OperationsConsole, snapshot_id: str, other_object_id: str, *, marker: str='concurrent-winner', production_console) -> None:
    """Commit a real competing writer after form read, before review takes its lock.

    A second console cannot synchronously acquire the same store lock from inside
    the first console's save callback. The submitted form retains its old revision,
    so this exercises the real stale-request path and preserves the winning write.
    """
    other = production_console(processing_binder=bind_fixture_selections,
        root=console.root, source_store=console.source_store, runtime=console.runtime)
    other_rows = other._load_objects(snapshot_id)
    for row in other_rows:
        if row["object_id"] == other_object_id:
            row["reliability_marker"] = marker
    other._save_objects(snapshot_id, other_rows)


def _stale_review_post(tmp_path: Path, *, production_app, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first, second = _content_rows(console, snapshot_id)[:2]
    client = _client(console, production_app=production_app)
    opened = client.get(f"/review?document={snapshot_id}&object={first['object_id']}")
    assert opened.status_code == 200
    assert 'data-review-form' in opened.text
    _install_concurrent_winner(console, snapshot_id, second["object_id"], production_console=production_console)
    posted = client.post(
        "/review",
        data=_review_payload(snapshot_id, first["object_id"], _form_revision(opened.text)),
        follow_redirects=False,
    )
    return client, receipt, first["object_id"], posted, console, _form_revision(opened.text)


def test_stale_review_save_does_not_show_success_or_redirect_next(tmp_path: Path, *, production_app, production_console) -> None:
    _client, receipt, object_id, posted, _console_instance, _revision = _stale_review_post(tmp_path, production_app=production_app, production_console=production_console)
    location = posted.headers.get("location") or ""
    body = posted.text
    _assert_stale_draft(posted, receipt["snapshot_id"], object_id)
    assert not location or object_id in location
    assert "succes" not in body.lower()
    assert SNAPSHOT_WRITE_CONFLICT in body or 'data-stale-write-conflict' in body
    lowered = body.lower()
    for phrase in CONFLICT_COPY:
        assert phrase in lowered, phrase
    live = next(
        row
        for row in production_console(processing_binder=bind_fixture_selections,
            root=tmp_path,
            source_store=tmp_path / "sources" / "private",
            runtime=tmp_path / "output" / "runtime" / "operations-console",
        ).snapshot_objects(receipt["snapshot_id"])
        if row["object_id"] == object_id
    )
    assert _passage_suitability(live) != UNIQUE_SUITABILITY
    assert UNIQUE_COMMENT not in str(live)


def test_stale_review_save_keeps_submitted_input_in_the_form(tmp_path: Path, *, production_app, production_console) -> None:
    _client, receipt, object_id, posted, _console_instance, _revision = _stale_review_post(tmp_path, production_app=production_app, production_console=production_console)
    body = posted.text
    _assert_stale_draft(posted, receipt["snapshot_id"], object_id)
    assert UNIQUE_COMMENT in _textarea_value(body, "comment")
    assert UNIQUE_CORRECTION in _textarea_value(body, "proposed_correction")
    assert re.search(r'<textarea[^>]*name="proposed_correction"[^>]*readonly', body)
    assert "Actie niet uitgevoerd" not in body


def test_stale_review_save_retry_applies_input_after_fresh_revision(tmp_path: Path, *, production_app, production_console) -> None:
    client, receipt, object_id, posted, console, revision = _stale_review_post(tmp_path, production_app=production_app, production_console=production_console)
    fresh = _inspect_current(client, console, posted, receipt["snapshot_id"], object_id, revision)
    assert UNIQUE_COMMENT in posted.text
    retried = client.post(
        "/review",
        data=_review_payload(receipt["snapshot_id"], object_id, fresh),
        follow_redirects=False,
    )
    assert retried.status_code == 303
    location = retried.headers.get("location") or ""
    if retried.status_code == 303:
        assert "/review" in location
    console = production_console(processing_binder=bind_fixture_selections,
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


def test_stale_review_conflicts_preserve_special_characters_exactly(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first, second = _content_rows(console, snapshot_id)[:2]
    client = _client(console, production_app=production_app)
    opened = client.get(f"/review?document={snapshot_id}&object={first['object_id']}")
    assert opened.status_code == 200

    comment = 'Bij A & B: waarde < 5; "controle" > 1; café ☕ <script>alert("x")</script>'
    correction = "Gebruik 'één' & controleer > 2 < 9 — patiënt"
    payload = _review_payload(snapshot_id, first["object_id"], _form_revision(opened.text))
    payload["comment"] = comment
    payload["proposed_correction"] = correction

    _install_concurrent_winner(
        console, snapshot_id, second["object_id"], marker="concurrent-winner-1"
    , production_console=production_console)
    first_conflict = client.post("/review", data=payload, follow_redirects=False)

    assert first_conflict.status_code == 409
    raw_comment = _textarea_value(first_conflict.text, "comment")
    raw_correction = _textarea_value(first_conflict.text, "proposed_correction")
    assert html.unescape(raw_comment) == comment
    assert html.unescape(raw_correction) == correction
    assert "<script>" not in raw_comment
    assert "&lt;script&gt;" in raw_comment

    retry_payload = dict(payload)
    retry_payload["snapshot_revision"] = _inspect_current(client, console, first_conflict,
        snapshot_id, first["object_id"], payload["snapshot_revision"], comment=comment, correction=correction)
    retry_payload["comment"] = html.unescape(raw_comment)
    retry_payload["proposed_correction"] = html.unescape(raw_correction)

    _install_concurrent_winner(
        console, snapshot_id, second["object_id"], marker="concurrent-winner-2"
    , production_console=production_console)
    second_conflict = client.post("/review", data=retry_payload, follow_redirects=False)

    assert second_conflict.status_code == 409
    second_raw_comment = _textarea_value(second_conflict.text, "comment")
    second_raw_correction = _textarea_value(second_conflict.text, "proposed_correction")
    assert html.unescape(second_raw_comment) == comment
    assert html.unescape(second_raw_correction) == correction
    assert second_raw_comment == raw_comment
    assert second_raw_correction == raw_correction

    final_payload = dict(retry_payload)
    final_payload["snapshot_revision"] = _inspect_current(client, console, second_conflict,
        snapshot_id, first["object_id"], retry_payload["snapshot_revision"], comment=comment, correction=correction)
    final_payload["comment"] = html.unescape(second_raw_comment)
    final_payload["proposed_correction"] = html.unescape(second_raw_correction)
    final_payload["eindoordeel"] = "afwijzen"
    saved = client.post("/review", data=final_payload, follow_redirects=False)

    assert saved.status_code == 303
    events = read_events(console._ledger_path)
    saved_review = next(
        event
        for event in reversed(events)
        if (event.get("details") or {}).get("comment") == comment
    )
    details = saved_review["details"]
    assert details["comment"] == comment
    assert details["proposed_correction"] == correction
    assert "&amp;" not in details["comment"]
    assert "&lt;script&gt;" not in details["comment"]
    stored = console.snapshot_objects(snapshot_id)
    assert next(row for row in stored if row["object_id"] == second["object_id"])["reliability_marker"] == "concurrent-winner-2"
