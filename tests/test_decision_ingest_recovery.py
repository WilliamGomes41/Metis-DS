"""Failure after immutable source storage does not lose bytes or overwrite review.

# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: releasebewijs
"""
from tests.semantic_fixture_support import bind_fixture_selections
import pytest

from tests.test_decision_graph_chain import _accounts, _ingest_boom, policy, source_pdf


@pytest.mark.parametrize("backend", ["local", "postgres"])
def test_timeout_after_source_storage_then_retry_and_restart(tmp_path, monkeypatch, backend, *, complete_postgres, production_console):
    if backend == "postgres":
        from tests.decision_graph_native_support import native_state
        state, _, source = native_state(tmp_path, config=complete_postgres)
    else:
        from src.publication.durable_publication_console_v1 import DurablePublicationConsole
        from tests.test_durable_publication_console_v1 import MemorySourceStore
        source = MemorySourceStore()
        def state():
            return production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / "sources",
                runtime=tmp_path / "runtime", immutable_source_store=source)
    console = state()
    accounts = _accounts(console)
    data = source_pdf()
    kwargs = dict(data=data, filename="retry.pdf", content_type="application/pdf", named_reviewers=[],
                  review_policy=policy(accounts), command_id="recover-upload")
    def fail(*args, **kwargs):
        raise TimeoutError("simulated_processing_timeout_after_blob")
    monkeypatch.setattr(console, "_fragments_and_spec", fail)
    with pytest.raises(TimeoutError):
        _ingest_boom(console, accounts, **kwargs)
    assert len(source.blobs) == 1
    assert next(iter(source.blobs.values())) == data
    restarted = state()
    # The bound runtime retains the failed attempt; it never activates objects.
    for envelope in restarted.list_envelopes():
        assert envelope["processing_attempts"][-1]["state"] == "failed"
        assert restarted.snapshot_objects(envelope["snapshot_id"]) == []
    receipt = _ingest_boom(restarted, accounts, **kwargs)
    assert _ingest_boom(state(), accounts, **kwargs)["snapshot_id"] == receipt["snapshot_id"]
    assert len(state().list_envelopes()) == 1
    assert len(source.blobs) == 1
