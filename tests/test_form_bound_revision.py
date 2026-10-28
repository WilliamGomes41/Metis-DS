"""Form-bound snapshot revision (post-#120 audit remediation 1).

Overlapping review forms MUST carry an explicit snapshot revision from
GET to POST. The pin is bound to the edit, not ``threading.local`` /
worker-thread reuse. A stale form keeps the reviewer's draft and shows
current store differences. The same-POST inject tests in
``test_stale_write_ux.py`` stay; this file adds the cross-client
regressions the audit reproduced.

# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import re
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import OperationsConsole

ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
SNAPSHOT_WRITE_CONFLICT = "snapshot_object_write_conflict"
ANNE_COMMENT = "G1-form-rev-anne-comment-42"
BERT_COMMENT = "G1-form-rev-bert-comment-99"
ANNE_SUIT = "geen_kenniseenheid"
BERT_SUIT = "samenvoegen"

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


def _client(console: OperationsConsole, username: str, *, production_app) -> TestClient:
    client = TestClient(production_app(console))
    passwords = {
        "researcher.anne": "anne-secret",
        "reviewer.bert": "bert-secret",
    }
    client.post("/login", data={"username": username, "password": passwords[username]})
    return client


def _hidden(html: str, name: str) -> str:
    match = re.search(
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="([^"]*)"',
        html,
    )
    if not match:
        match = re.search(
            rf'<input[^>]*value="([^"]*)"[^>]*name="{re.escape(name)}"',
            html,
        )
    return match.group(1) if match else ""


def _textarea_value(html: str, name: str) -> str:
    match = re.search(
        rf'<textarea[^>]*name="{re.escape(name)}"[^>]*>(.*?)</textarea>',
        html,
        flags=re.S,
    )
    return match.group(1) if match else ""


def _radio_checked(html: str, name: str, value: str) -> bool:
    pattern = (
        rf'<input[^>]*name="{re.escape(name)}"[^>]*value="{re.escape(value)}"[^>]*>'
        rf'|<input[^>]*value="{re.escape(value)}"[^>]*name="{re.escape(name)}"[^>]*>'
    )
    for match in re.finditer(pattern, html):
        if re.search(r"\bchecked\b", match.group(0)):
            return True
    return False


def _passage_suitability(row: dict) -> str:
    return str(((row.get("metadata") or {}).get("review_passage") or {}).get("suitability") or "")


def _review_payload(
    snapshot_id: str,
    object_id: str,
    *,
    snapshot_revision: str,
    suitability: str,
    comment: str,
) -> dict[str, str]:
    return {
        "snapshot_id": snapshot_id,
        "object_id": object_id,
        "snapshot_revision": snapshot_revision,
        "suitability": suitability,
        "documentpositie_action": "dit_klopt",
        "type_action": "dit_klopt",
        "eindoordeel": "afwijzen",
        "comment": comment,
        "proposed_correction": "",
    }


def _open_review_form(
    client: TestClient,
    snapshot_id: str,
    object_id: str,
) -> tuple[str, str]:
    opened = client.get(f"/review?document={snapshot_id}&object={object_id}")
    assert opened.status_code == 200
    assert "data-review-form" in opened.text
    revision = _hidden(opened.text, "snapshot_revision")
    assert revision, "review GET MUST embed snapshot_revision on the edit form"
    return opened.text, revision


def test_review_form_get_embeds_snapshot_revision(tmp_path: Path, *, production_app, production_console) -> None:
    from src.review.review_passage_read_v1 import PREFIX, resolve_review_revision
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    first = _content_rows(console, snapshot_id)[0]
    client = _client(console, "researcher.anne", production_app=production_app)
    body, revision = _open_review_form(client, snapshot_id, first["object_id"])
    expected = console.objects_revision(snapshot_id)
    assert revision.startswith(PREFIX)
    assert resolve_review_revision(console, snapshot_id, revision) == expected
    assert f'name="snapshot_revision" value="{revision}"' in body or (
        f'value="{revision}"' in body and 'name="snapshot_revision"' in body
    )
    assert "data-review-form" in body


def test_two_clients_overlapping_forms_conflict_on_stale_revision(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    anne = _client(console, "researcher.anne", production_app=production_app)
    bert = _client(console, "reviewer.bert", production_app=production_app)
    _opened_a, rev_a = _open_review_form(anne, snapshot_id, target["object_id"])
    _opened_b, rev_b = _open_review_form(bert, snapshot_id, target["object_id"])
    assert rev_a == rev_b

    posted_b = bert.post(
        "/review",
        data=_review_payload(
            snapshot_id,
            target["object_id"],
            snapshot_revision=rev_b,
            suitability=BERT_SUIT,
            comment=BERT_COMMENT,
        ),
        follow_redirects=False,
    )
    assert posted_b.status_code in {303, 200}
    live = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    assert _passage_suitability(live) == BERT_SUIT

    posted_a = anne.post(
        "/review",
        data=_review_payload(
            snapshot_id,
            target["object_id"],
            snapshot_revision=rev_a,
            suitability=ANNE_SUIT,
            comment=ANNE_COMMENT,
        ),
        follow_redirects=False,
    )
    assert posted_a.status_code != 303
    assert posted_a.status_code in {200, 409}
    body = posted_a.text
    assert SNAPSHOT_WRITE_CONFLICT in body or "data-stale-write-conflict" in body
    assert "succes" not in body.lower()
    assert ANNE_COMMENT in _textarea_value(body, "comment")
    assert _radio_checked(body, "suitability", ANNE_SUIT)
    assert "data-stale-write-differences" in body
    assert BERT_SUIT in body
    after = next(
        row
        for row in production_console(processing_binder=bind_fixture_selections,
            root=tmp_path,
            source_store=tmp_path / "sources" / "private",
            runtime=tmp_path / "output" / "runtime" / "operations-console",
        ).snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    assert _passage_suitability(after) == BERT_SUIT
    assert ANNE_SUIT != _passage_suitability(after)


def test_overlapping_forms_conflict_survives_worker_thread_reuse(tmp_path: Path, *, production_app, production_console) -> None:
    """TLS / reused worker must not let a stale form win after another client saved."""
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    anne = _client(console, "researcher.anne", production_app=production_app)
    bert = _client(console, "reviewer.bert", production_app=production_app)
    _opened_a, rev_a = _open_review_form(anne, snapshot_id, target["object_id"])
    _opened_b, rev_b = _open_review_form(bert, snapshot_id, target["object_id"])

    posted_b = bert.post(
        "/review",
        data=_review_payload(
            snapshot_id,
            target["object_id"],
            snapshot_revision=rev_b,
            suitability=BERT_SUIT,
            comment=BERT_COMMENT,
        ),
        follow_redirects=False,
    )
    assert posted_b.status_code in {303, 200}

    console.refresh_objects_expected_revision(snapshot_id)
    errors: list[BaseException] = []
    posted: dict[str, object] = {}

    def reused_worker() -> None:
        try:
            console._objects_tls.expected = {
                snapshot_id: console.objects_revision(snapshot_id)
            }
            posted["response"] = anne.post(
                "/review",
                data=_review_payload(
                    snapshot_id,
                    target["object_id"],
                    snapshot_revision=rev_a,
                    suitability=ANNE_SUIT,
                    comment=ANNE_COMMENT,
                ),
                follow_redirects=False,
            )
        except Exception as exc:  # pragma: no cover - unexpected
            errors.append(exc)

    thread = threading.Thread(target=reused_worker)
    thread.start()
    thread.join(timeout=15)
    assert not thread.is_alive()
    assert errors == []
    response = posted["response"]
    assert response.status_code != 303
    assert response.status_code in {200, 409}
    body = response.text
    assert SNAPSHOT_WRITE_CONFLICT in body or "data-stale-write-conflict" in body
    assert ANNE_COMMENT in _textarea_value(body, "comment")
    assert "data-stale-write-differences" in body
    live = next(
        row
        for row in console.snapshot_objects(snapshot_id)
        if row["object_id"] == target["object_id"]
    )
    assert _passage_suitability(live) == BERT_SUIT


def test_stale_form_keeps_draft_and_shows_current_differences(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    anne = _client(console, "researcher.anne", production_app=production_app)
    bert = _client(console, "reviewer.bert", production_app=production_app)
    _opened_a, rev_a = _open_review_form(anne, snapshot_id, target["object_id"])
    _opened_b, rev_b = _open_review_form(bert, snapshot_id, target["object_id"])
    bert.post(
        "/review",
        data=_review_payload(
            snapshot_id,
            target["object_id"],
            snapshot_revision=rev_b,
            suitability=BERT_SUIT,
            comment=BERT_COMMENT,
        ),
        follow_redirects=False,
    )
    posted = anne.post(
        "/review",
        data=_review_payload(
            snapshot_id,
            target["object_id"],
            snapshot_revision=rev_a,
            suitability=ANNE_SUIT,
            comment=ANNE_COMMENT,
        ),
        follow_redirects=False,
    )
    body = posted.text
    assert posted.status_code in {200, 409}
    assert "data-review-form" in body
    assert ANNE_COMMENT in _textarea_value(body, "comment")
    assert _radio_checked(body, "suitability", ANNE_SUIT)
    assert "data-stale-write-differences" in body
    lowered = body.lower()
    assert "huidige" in lowered or "verschil" in lowered
    assert BERT_SUIT in body
    fresh = _hidden(body, "snapshot_revision")
    assert fresh
    assert fresh != rev_a
    assert fresh == console.objects_revision(snapshot_id)


def test_batch_confirm_carries_and_compares_form_revision(tmp_path: Path, *, production_app, production_console) -> None:
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    client = _client(console, "researcher.anne", production_app=production_app)
    index = client.get(f"/review?document={snapshot_id}&task=headings")
    assert index.status_code == 200
    revision = _hidden(index.text, "snapshot_revision")
    assert revision, "batch-confirm form MUST carry snapshot_revision"
    heading_ids = re.findall(r'name="object_ids"[^>]*value="([^"]+)"', index.text)
    if not heading_ids:
        heading_ids = re.findall(r'value="([^"]+)"[^>]*name="object_ids"', index.text)
    assert heading_ids
    other = production_console(processing_binder=bind_fixture_selections,
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
    rows = other._load_objects(snapshot_id)
    rows[0]["reliability_marker"] = "batch-concurrent-winner"
    other._save_objects(snapshot_id, rows)
    posted = client.post(
        "/review/headings/batch-confirm",
        data={"snapshot_id": snapshot_id, "snapshot_revision": revision, "object_ids": heading_ids[:1]},
        follow_redirects=False,
    )
    assert posted.status_code != 303
    body = posted.text
    assert SNAPSHOT_WRITE_CONFLICT in body or "data-stale-write-conflict" in body
    stored = {row["object_id"]: row for row in console._load_objects(snapshot_id)}
    assert any(row.get("reliability_marker") == "batch-concurrent-winner" for row in stored.values())


def test_form_content_and_revision_are_co_read_not_separate_gets(tmp_path: Path, monkeypatch, *, production_app, production_console) -> None:
    """A commit after SQL capture must not change the captured form's pin."""
    import src.review.review_passage_read_v1 as reads
    from src.operations_console_v1 import ConsoleError
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    snapshot_id = receipt["snapshot_id"]
    target = _content_rows(console, snapshot_id)[0]
    original = console.objects_revision(snapshot_id)
    real = reads.read_review_passage
    other = _console(tmp_path, production_console=production_console)
    captured = []

    def raced(*args, **kwargs):
        inputs = real(*args, **kwargs)
        assert reads.resolve_review_revision(console, snapshot_id, inputs.revision) == original
        captured.append(inputs)
        loaded = other._load_objects(snapshot_id)
        for row in loaded:
            if row["object_id"] == target["object_id"]:
                row["reliability_marker"] = "form-coread-winner"
        other._save_objects(snapshot_id, loaded)
        return inputs

    monkeypatch.setattr(reads, 'read_review_passage', raced)
    client = _client(console, "researcher.anne", production_app=production_app)
    body, revision = _open_review_form(client, snapshot_id, target["object_id"])
    live = console.objects_revision(snapshot_id)
    assert len(captured) == 1 and live != original
    assert revision == captured[0].revision
    assert all(row.get('reliability_marker') != 'form-coread-winner' for row in captured[0].objects)
    assert 'form-coread-winner' not in body
    with pytest.raises(ConsoleError) as error:
        reads.resolve_review_revision(console, snapshot_id, revision)
    assert error.value.code == SNAPSHOT_WRITE_CONFLICT
