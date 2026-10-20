"""D5 supersedes #708's post-commit ledger projection: the ledger stays in PG.

The former buffer-copy, tail-rebuild and divergence-warning tests concerned
the removed copy. Keep the durable event/chain contract and attack present
stale copies instead. Transaction/rollback proofs remain in #678 and #708.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import psycopg
import pytest

from src.review_ledger import read_events, verify_ledger
from tests.complete_workflow_support import complete_postgres  # noqa: F401
from tests.test_708_reprocessing_guard_postgres import _assert_mirrors, _change_all, prepared  # noqa: F401
from tests.test_pg_console_without_disk_mirrors import MirrorAccess
from tests.test_r2_rollback_remirror_postgres import _approve


@pytest.mark.parametrize("buffered", [True, False], ids=["review", "reprocessing"])
def test_committed_events_read_postgres_without_projection(prepared, monkeypatch, buffered):
    console, reviewer, sid, obj = prepared
    before = read_events(console._ledger_path)
    guard = MirrorAccess(console._ledger_path.parent, deny=True)
    with guard.installed(monkeypatch):
        if buffered:
            _approve(console, reviewer, sid, obj)
        else:
            with console._reprocessing_transaction(sid):
                _change_all(console, reviewer, sid, obj)
        events = read_events(console._ledger_path)
        assert events == console.workflow_review_store.read_events()
        assert verify_ledger(console._ledger_path) == []
    assert not guard.rows
    assert events[:len(before)] == before
    assert any(e["event_type"] == "clinical_review_approve" for e in events[len(before):])
    _assert_mirrors(console, sid)


@pytest.mark.parametrize("poison", [b"", b'{"stale": true}\n', b"invalid json\n"])
def test_present_ledger_copy_is_ignored_and_untouched(prepared, monkeypatch, poison):
    console, reviewer, sid, obj = prepared
    console._ledger_path.write_bytes(poison)
    guard = MirrorAccess(console._ledger_path.parent, deny=True)
    with guard.installed(monkeypatch):
        _approve(console, reviewer, sid, obj)
        assert read_events(console._ledger_path) == console.workflow_review_store.read_events()
        assert verify_ledger(console._ledger_path) == []
    assert not guard.rows
    assert console._ledger_path.read_bytes() == poison


def test_pg_chain_corruption_remains_detectable_without_a_disk_copy(prepared):
    console, reviewer, sid, obj = prepared
    _approve(console, reviewer, sid, obj)
    event = console.workflow_review_store.read_events()[-1]
    with psycopg.connect(console.workflow_document_store.config.dsn) as connection:
        connection.execute(
            "UPDATE workflow.review_events SET event_payload = "
            "jsonb_set(event_payload, '{details,tampered}', 'true') WHERE event_hash=%s",
            (event["event_hash"],),
        )
    assert any(error.startswith("event_hash_mismatch:") for error in verify_ledger(console._ledger_path))
    assert not console._ledger_path.exists()
