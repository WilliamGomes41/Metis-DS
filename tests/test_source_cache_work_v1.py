"""Existing work commands recover only verified immutable source bytes.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.g2_source_store import G2SourceStoreError
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole, PRE_REVIEW_BLOCKED
from tests.test_v226_klasse_wijzigen import _accounts, _ingest_richtlijn, _ingest_boom
from tests.test_vsa_publish_document_v1 import MemorySourceStore, _console as pg_console
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore


def _system(tmp_path, *, boom=False):
    source = MemorySourceStore()
    console = OperationsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime", immutable_source_store=source)
    accounts = _accounts(console)
    receipt = (_ingest_boom if boom else _ingest_richtlijn)(console, accounts)
    return console, source, accounts, receipt


def _act(console, accounts, sid, action):
    actor = accounts["researcher"]["account_id"]
    if action == "extract":
        return console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    return console.promote_class(actor_id=actor, snapshot_id=sid, new_class="artikel", reextract=True)


@pytest.mark.parametrize("action", ["extract", "class", "cross_model"])
@pytest.mark.parametrize("cache", ["missing", "corrupt"])
def test_work_recovers_source_into_current_configured_cache(tmp_path, action, cache):
    console, source, accounts, receipt = _system(tmp_path, boom=action == "cross_model")
    sid = receipt["snapshot_id"]
    original = deepcopy(console._envelope(sid))
    old_path = Path(original["binary_path"])
    source_bytes = old_path.read_bytes()
    old_path.unlink()
    fresh = OperationsConsole(root=tmp_path, source_store=tmp_path / "new-cache", runtime=console.runtime, immutable_source_store=source)
    cache_path = fresh._source_cache_path(original)
    if cache == "corrupt":
        cache_path.parent.mkdir(parents=True)
        cache_path.write_bytes(b"corrupt")
    result = _act(fresh, accounts, sid, action)
    assert cache_path.read_bytes() == source_bytes
    assert not old_path.exists()
    for key in ("sha256", "locator", "immutable_storage_locator", "source_id", "document_id", "version"):
        assert result[key] == original[key]
    assert fresh.snapshot_objects(sid)


@pytest.mark.parametrize("action", ["extract", "class"])
@pytest.mark.parametrize("failure", ["missing", "wrong_hash"])
def test_failed_blob_read_does_not_change_work_or_review(tmp_path, monkeypatch, action, failure):
    console, source, accounts, receipt = _system(tmp_path)
    sid = receipt["snapshot_id"]
    Path(receipt["binary_path"]).unlink()
    before = (deepcopy(console._envelope(sid)), console.snapshot_objects(sid, include_blocked=True), deepcopy(console._bindings))
    def load(locator):
        if failure == "missing":
            raise G2SourceStoreError("missing")
        return b"wrong"
    monkeypatch.setattr(source, "load_verified", load)
    with pytest.raises(ConsoleError, match="immutable_source_recovery_failed"):
        _act(console, accounts, sid, action)
    assert (console._envelope(sid), console.snapshot_objects(sid, include_blocked=True), console._bindings) == before
    assert not Path(receipt["binary_path"]).exists()


@pytest.mark.parametrize("action", ["extract", "class"])
@pytest.mark.parametrize("race", ["published", "objects", "envelope"])
def test_change_during_blob_read_is_not_overwritten(tmp_path, monkeypatch, action, race):
    console, source, accounts, receipt = _system(tmp_path)
    sid = receipt["snapshot_id"]
    Path(receipt["binary_path"]).unlink()
    other = OperationsConsole(root=tmp_path, source_store=console.source_store, runtime=console.runtime, immutable_source_store=source)
    original_load = source.load_verified
    winner = {}
    def load(locator):
        data = original_load(locator)
        if race == "objects":
            rows = other._load_objects(sid)
            rows[0]["concurrent_review"] = "must survive"
            other._save_objects(sid, rows)
        else:
            other._envelopes[sid]["state" if race == "published" else "title"] = "published" if race == "published" else "Concurrent title"
            other._save_envelopes()
        winner["envelope"] = deepcopy(other._envelope(sid))
        winner["objects"] = other.snapshot_objects(sid, include_blocked=True)
        return data
    monkeypatch.setattr(source, "load_verified", load)
    with pytest.raises(ConsoleError, match="published_|snapshot_object_write_conflict"):
        _act(console, accounts, sid, action)
    assert console._envelope(sid) == winner["envelope"]
    assert console.snapshot_objects(sid, include_blocked=True) == winner["objects"]


def test_http_zero_object_blocked_work_can_reprocess_from_blob(recovery_postgres, tmp_path):
    source = MemorySourceStore()
    canonical = PostgresCanonicalPublicationStore(recovery_postgres)
    console = pg_console(tmp_path, recovery_postgres, canonical, source, runtime_name="runtime")
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    sid = receipt["snapshot_id"]
    console._envelopes[sid]["publication_eligibility"] = PRE_REVIEW_BLOCKED
    console._envelopes[sid]["processing_blocker"] = {"code": "empty_test_extract"}
    console._save_envelopes()
    from tests.semantic_fixture_support import install_fixture_history
    install_fixture_history(console, sid, [])
    Path(receipt["binary_path"]).unlink()
    client = TestClient(create_console_app(console))
    assert client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"}, follow_redirects=False).status_code == 303
    result = client.post("/tree/reprocess", data={"snapshot_id": sid}, follow_redirects=False)
    assert result.status_code == 303
    assert result.headers["location"] == f"/source-selection?document={sid}"
    assert not console.snapshot_objects(sid)
    with client:
        from tests.test_availability_repair import drain
        assert client.post("/source-selection/start", data={"document": sid, "command_id": "recover-cache",
            "expected_revision": console.objects_revision(sid)}, follow_redirects=False).status_code == 303
        drain(client, client.app)
    assert console.snapshot_objects(sid)
    assert console._envelope(sid)["sha256"] == receipt["sha256"]
    assert "processing_blocker" not in console._envelope(sid)


def test_pg_fresh_console_resumes_open_work_with_no_prior_files(recovery_postgres, tmp_path):
    source = MemorySourceStore()
    canonical = PostgresCanonicalPublicationStore(recovery_postgres)
    console = pg_console(tmp_path / "before", recovery_postgres, canonical, source, runtime_name="runtime")
    accounts = _accounts(console)
    receipt = _ingest_richtlijn(console, accounts)
    Path(receipt["binary_path"]).unlink()
    fresh = pg_console(tmp_path / "after", recovery_postgres, canonical, source, runtime_name="runtime")
    result = fresh.reextract_unpublished(actor_id=accounts["researcher"]["account_id"], snapshot_id=receipt["snapshot_id"])
    assert result["sha256"] == receipt["sha256"]
    assert fresh._source_cache_path(receipt).is_file()
    assert not Path(receipt["binary_path"]).exists()
    assert fresh.workflow_document_store.list_document_objects(receipt["snapshot_id"])
