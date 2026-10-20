"""PR-a: Bronselectie lists documents from a light key list (no receipt deepcopy).

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Rules (B18):
- De HTML van `GET /source-selection` MOET identiek zijn aan het oude pad (golden).
- De lijst MAG NIET per document een `_receipt`-deepcopy maken.
"""
import re
import uuid

import pytest
from fastapi.testclient import TestClient

import src.source_selection_ui_v1 as ui
from src.operations_console_app import COOKIE
from tests.test_recoverable_formation_v1 import system
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401


def _legacy_keys(console):
    """The pre-PR-a route: ids taken from list_envelopes receipts (golden reference)."""
    return [row['snapshot_id'] for row in console.list_envelopes()]


def _freeze(monkeypatch):
    counter = iter(range(10 ** 6))
    monkeypatch.setattr(uuid, 'uuid4', lambda: uuid.UUID(int=next(counter)))
    import src.source_selection_v1 as selection
    from datetime import datetime, timezone
    monkeypatch.setattr(selection, 'now', lambda: datetime(2026, 10, 15, 6, tzinfo=timezone.utc))


def _client(console, user, *, production_app):
    client = TestClient(production_app(console))
    client.cookies.set(COOKIE, console.authenticate(user, 'strong-test-password')['token'])
    return client


def _pages(client, sid):
    return [client.get('/source-selection').text, client.get('/source-selection', params={'document': sid}).text]


def _norm(html):
    return re.sub(r'name="command_id" value="[0-9a-f]+"', 'name="command_id" value="X"', html)


@pytest.mark.parametrize('user', ['author', 'reviewer'])
def test_source_selection_html_identical_to_legacy_list(tmp_path, monkeypatch, user, *, production_app, production_console):
    console, sid, *_ = system(tmp_path, production_console=production_console)
    client = _client(console, user, production_app=production_app)
    _freeze(monkeypatch)
    new = [_norm(p) for p in _pages(client, sid)]
    _freeze(monkeypatch)
    monkeypatch.setattr(ui, 'document_keys', _legacy_keys)
    old = [_norm(p) for p in _pages(client, sid)]
    assert new == old
    assert sid in new[0] and sid in new[1]


def test_source_selection_list_makes_no_receipt_copies(tmp_path, monkeypatch, *, production_app, production_console):
    """Fail-first: the old route deep-copied one receipt per document."""
    console, sid, *_ = system(tmp_path, production_console=production_console)
    client = _client(console, 'author', production_app=production_app)
    calls = []
    real = type(console)._receipt
    monkeypatch.setattr(type(console), '_receipt', lambda self, env: calls.append(env['snapshot_id']) or real(self, env))
    assert client.get('/source-selection').status_code == 200
    assert calls == []


def test_key_order_matches_list_envelopes(tmp_path, *, production_console):
    console, *_ = system(tmp_path, production_console=production_console)
    assert ui.document_keys(console) == _legacy_keys(console)


def test_postgres_key_list_matches_authoritative_list(workflow_postgres, tmp_path):
    from tests.test_attempt_diagnostics_postgres import bound, ingest
    from tests.test_review_batch_atomic_postgres import _console
    console = _console(tmp_path, workflow_postgres)
    bound(console, reject=False)
    ingest(console)
    expected = [row['snapshot_id'] for row in console.list_envelopes()]
    assert console.list_snapshot_ids() == expected
    with console.source_selection_read_scope():
        assert ui.document_keys(console) == expected
        assert [console._envelope(s)['snapshot_id'] for s in ui.document_keys(console)] == expected
