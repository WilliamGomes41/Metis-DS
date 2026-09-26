"""Document actions share the existing publication-history guard.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, PRE_REVIEW_BLOCKED
from src.review_closure_v1 import ReviewClosureConsole
from tests.test_v226_klasse_wijzigen import _accounts, _ingest_richtlijn


def _system(tmp_path):
    console = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    client = TestClient(create_console_app(console))
    assert client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"}, follow_redirects=False).status_code == 303
    return console, receipt["snapshot_id"], client


@pytest.mark.parametrize("status", ["published", "superseded", "withdrawn"])
def test_closed_document_has_no_mutation_forms_and_stale_posts_fail(tmp_path, status):
    console, sid, client = _system(tmp_path)
    assert 'action="/tree/move"' in client.get("/tree").text
    console._envelopes[sid]["state"] = status
    # Even a stale blocker projection must not offer reprocessing closed work.
    console._envelopes[sid]["publication_eligibility"] = PRE_REVIEW_BLOCKED
    console._save_envelopes()
    before = (deepcopy(console._envelope(sid)), console.snapshot_objects(sid, include_blocked=True))
    page = client.get("/tree")
    assert page.status_code == 200 and "wijzigacties niet beschikbaar" in page.text
    assert 'href="/ingest"' in page.text
    for path in ("/tree/move", "/tree/promote", "/tree/reprocess", "/documents/delete"):
        assert f'action="{path}"' not in page.text
    for path, fields in (
        ("/tree/move", {"new_family": "Ander onderwerp"}),
        ("/tree/promote", {"new_class": "artikel", "confirm": "1"}),
        ("/tree/reprocess", {}),
    ):
        response = client.post(path, data={"snapshot_id": sid, **fields}, follow_redirects=False)
        assert response.status_code in {400, 409}
    assert (console._envelope(sid), console.snapshot_objects(sid, include_blocked=True)) == before
    restarted = ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert restarted._envelope(sid) == before[0]


def test_unknown_publication_authority_hides_all_mutation_forms(tmp_path, monkeypatch):
    console, sid, client = _system(tmp_path)
    def unavailable(snapshot_id):
        raise ConsoleError("durable_publication_lookup_failed")
    monkeypatch.setattr(console, "snapshot_is_published", unavailable)
    page = client.get("/tree")
    assert page.status_code == 200
    for path in ("/tree/move", "/tree/promote", "/tree/reprocess", "/documents/delete"):
        assert f'action="{path}"' not in page.text


def test_open_actions_share_one_history_read_and_do_not_mutate_state(tmp_path, monkeypatch):
    console, sid, client = _system(tmp_path)
    calls = []
    original = console.snapshot_is_published
    def counted(snapshot_id):
        calls.append(snapshot_id)
        return original(snapshot_id)
    monkeypatch.setattr(console, "snapshot_is_published", counted)
    monkeypatch.setattr(console, "waiting_task_counts", lambda _account: {})
    before = (deepcopy(console._envelope(sid)), console.snapshot_objects(sid, include_blocked=True))
    page = client.get("/tree")
    assert page.status_code == 200
    for path in ("/tree/move", "/tree/promote", "/documents/delete"):
        assert f'action="{path}"' in page.text
    assert calls == [sid]
    assert (console._envelope(sid), console.snapshot_objects(sid, include_blocked=True)) == before
