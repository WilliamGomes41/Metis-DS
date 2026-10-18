"""#750 follow-up: one Review GET reads each document envelope once.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
import re

from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401
from tests.complete_workflow_support import complete_console as _console
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_attempt_diagnostics_postgres import ingest
from tests.test_review_batch_atomic_postgres import _client


def _norm(html):
    return re.sub(r'name="command_id" value="[0-9a-f]+"', 'name="command_id" value="X"', html)


def test_review_get_reuses_the_request_envelope_reads(workflow_postgres, tmp_path, monkeypatch):
    console = _console(tmp_path, workflow_postgres)
    bind_fixture_selections(console)
    sid, _researcher, _reviewer = ingest(console)
    client = _client(console)
    expected = client.get("/review", params={"document": sid})
    assert expected.status_code == 200 and sid in expected.text

    store = console.workflow_document_store
    single, listed = [], []
    real_get, real_list = store.get_envelope, store.list_envelopes
    monkeypatch.setattr(store, "get_envelope", lambda snapshot_id: single.append(snapshot_id) or real_get(snapshot_id))
    monkeypatch.setattr(store, "list_envelopes", lambda: listed.append(1) or real_list())
    response = client.get("/review", params={"document": sid})
    assert response.status_code == 200
    assert single == [] and len(listed) == 1

    # Same page as the unscoped route, which re-read and copied each envelope.
    monkeypatch.setattr(type(console), "_source_selection_reads", lambda self: None)
    unscoped = client.get("/review", params={"document": sid})
    assert _norm(response.text) == _norm(unscoped.text)
    assert len(single) == 3
