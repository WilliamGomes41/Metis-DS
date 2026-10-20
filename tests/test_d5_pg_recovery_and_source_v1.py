"""D5 native recovery, partial publication and source-authority evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError
from src.review_ledger import unregister_backend, verify_ledger
from src.workflows.workflow_chain_recovery_v1 import backup_workflow_chain, restore_workflow_chain
from tests.complete_workflow_support import complete_console, complete_postgres  # noqa: F401
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_pg_console_without_disk_mirrors import CONSOLES, PHASES, MirrorAccess, _run
from tests.test_live_v1_working_v2_v1 import _complete_review
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE, MemorySourceStore
from tests.test_workflow_chain_recovery_v1 import _install_schema


def _scenario(config, root, monkeypatch, kind):
    guard = MirrorAccess(root / "runtime", deny=True)
    completed = []
    context = _run(config, root, guard, monkeypatch, {}, completed, console_kind=kind)
    assert completed == list(PHASES)
    assert not guard.rows
    return context, guard


@pytest.mark.parametrize("kind", CONSOLES)
def test_pg_backup_restore_without_runtime_then_resume_lifecycle(complete_postgres, tmp_path, monkeypatch, kind):
    root = tmp_path / "original"
    restored_root = tmp_path / "restored"
    try:
        context, guard = _scenario(complete_postgres, root, monkeypatch, kind)
        before = context["adapter"].export_state()
        # Passing obsolete arguments must not revive old files as recovery data.
        legacy = root / "runtime" / "envelopes.json"
        legacy.write_text('{"poison":"not a recovery source"}')
        archive = tmp_path / "workflow.zip"
        with guard.installed(monkeypatch):
            manifest = backup_workflow_chain(archive, database=context["adapter"],
                source_store=context["source"], runtime_root=root)
        assert manifest["runtime"] is None
        _install_schema(complete_postgres.dsn)  # Only the fixture-owned database.
        source = MemorySourceStore()
        restored_guard = MirrorAccess(restored_root / "runtime", deny=True)
        with guard.installed(monkeypatch), restored_guard.installed(monkeypatch):
            result = restore_workflow_chain(archive, database=context["adapter"],
                source_store=source, runtime_dest=restored_root)
            assert result["ok"]
            after = context["adapter"].export_state()
            for group in ("tables", "workflow_tables", "api_access_tables"):
                assert after[group] == before[group]
            console = complete_console(restored_root, complete_postgres,
                console_cls=CONSOLES[kind], immutable_source_store=source)
            bind_fixture_selections(console)
            assert console.canonical_publication_store.active_publication_rows() == []
            accounts = context["accounts"]
            successor = console.ingest(actor_id=accounts["researcher"]["account_id"],
                filename="restored-successor.html", data=HTML_FIXTURE.read_bytes() + b"<!-- restored -->",
                content_type="text/html", ingest_kind="new_version",
                replaces_snapshot_id=context["successor"]["snapshot_id"], title="Restored successor",
                version="5.0", date="2026-09-16", live_url="https://example.test/d5",
                class_="richtlijn", family="d4",
                named_reviewers=[accounts["reviewer"]["account_id"], accounts["second"]["account_id"]])
            _complete_review(console, reviewer_id=accounts["reviewer"]["account_id"],
                snapshot_id=successor["snapshot_id"])
            assert console.snapshot_objects(successor["snapshot_id"])
            assert verify_ledger(console._ledger_path) == []
        assert not guard.rows and not restored_guard.rows
        assert legacy.read_text() == '{"poison":"not a recovery source"}'
    finally:
        for path in (root, restored_root):
            unregister_backend(path / "runtime" / "review_ledger.jsonl")


def test_azure_corrupt_blob_blocks_publish_and_build_app(complete_postgres, tmp_path, monkeypatch):
    try:
        context, guard = _scenario(complete_postgres, tmp_path, monkeypatch, "azure")
        console, accounts = context["console"], context["accounts"]
        sid = context["successor"]["snapshot_id"]
        with guard.installed(monkeypatch):
            published = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
            assert published["status"] == "PASS"
            envelope = console._envelope(sid)
            locator = envelope["immutable_storage_locator"]
            context["source"].blobs[locator] += b"corrupt"
            before = context["adapter"].export_state()
            with pytest.raises(ConsoleError, match="^azure_blob_source_sha256_mismatch$"):
                console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
            with pytest.raises(ConsoleError, match="^azure_blob_source_sha256_mismatch$"):
                context["build"]()
            after = context["adapter"].export_state()
            for group in ("tables", "workflow_tables", "api_access_tables"):
                assert after[group] == before[group]
        assert not guard.rows
    finally:
        unregister_backend(tmp_path / "runtime" / "review_ledger.jsonl")


def test_release_commit_survives_envelope_failure_and_startup_repairs_it(complete_postgres, tmp_path, monkeypatch):
    try:
        context, guard = _scenario(complete_postgres, tmp_path, monkeypatch, "durable")
        console = context["console"]
        sid = context["successor"]["snapshot_id"]
        original = console.workflow_document_store.write_bundle
        def fail_published_envelope(*args, **kwargs):
            envelope = kwargs.get("envelope") or {}
            if envelope.get("snapshot_id") == sid and envelope.get("published"):
                raise RuntimeError("injected_envelope_write_failure")
            return original(*args, **kwargs)
        with guard.installed(monkeypatch), monkeypatch.context() as fault:
            fault.setattr(console.workflow_document_store, "write_bundle", fail_published_envelope)
            with pytest.raises(ConsoleError) as caught:
                console.publish(actor_id=context["accounts"]["publisher"]["account_id"], snapshot_id=sid)
            assert caught.value.code == "durable_publication_local_copy_failed"
        release = context["canonical"].release_for_snapshot(sid)
        assert release is not None
        assert not console.workflow_document_store.get_envelope(sid).get("published")
        with guard.installed(monkeypatch):
            restarted = context["build"]()
            assert restarted._envelope(sid)["release_id"] == release["release_id"]
            assert restarted._envelope(sid)["published"]
            again = context["build"]()
            events = again.workflow_review_store.read_events()
            assert sum(event["event_type"] == "release_published" and
                event["details"].get("release_id") == release["release_id"] for event in events) == 1
            assert context["canonical"].release_for_snapshot(sid) == release
        assert not guard.rows
    finally:
        unregister_backend(tmp_path / "runtime" / "review_ledger.jsonl")


@pytest.mark.parametrize('kind', CONSOLES)
def test_process_exit_mid_command_rolls_back_before_restart(complete_postgres, tmp_path, monkeypatch, kind):
    """A real process exit closes the PG connection without COMMIT."""
    import os
    import subprocess
    import sys
    from tests.test_pg_console_without_disk_mirrors import ROOT
    try:
        context, guard = _scenario(complete_postgres, tmp_path, monkeypatch, kind)
        before = context['adapter'].export_state()
        sid = context['successor']['snapshot_id']
        child = r'''
import os
from pathlib import Path
import sys
import pytest
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.review_ledger import append_event
from tests.complete_workflow_support import complete_console
from tests.test_pg_console_without_disk_mirrors import CONSOLES, MirrorAccess
root, sid, kind = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
patch = pytest.MonkeyPatch()
guard = MirrorAccess(root / 'runtime', deny=True)
with guard.installed(patch):
    console = complete_console(root, PostgresCanonicalConfig(dsn=os.environ['METIS_TEST_POSTGRES_DSN']), console_cls=CONSOLES[kind])
    with console._store_command(sid, buffered=False):
        envelope = dict(console._envelope(sid))
        envelope['title'] = 'half command must roll back'
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
        append_event(console._ledger_path, event_type='d5_crash_probe', object_id=sid,
                     object_version='1', actor='d5', details={'snapshot_id': sid})
        assert console.workflow_document_store.get_envelope(sid)['title'] == envelope['title']
        assert not guard.rows
        os._exit(73)
'''
        result = subprocess.run([sys.executable, '-c', child, str(tmp_path), sid, kind],
            cwd=ROOT, env={**os.environ, 'PYTHONPATH': str(ROOT)}, capture_output=True, text=True, timeout=45)
        assert result.returncode == 73, result.stderr[-4000:]
        # Exact durable equality before startup separates PG rollback from the
        # existing reconciliation writes (which advance published row revisions).
        rolled_back = context['adapter'].export_state()
        for group in ('tables', 'workflow_tables', 'api_access_tables'):
            assert rolled_back[group] == before[group]
        envelope_before = context['console']._envelope(sid)
        objects_before = context['console']._load_objects(sid)
        events_before = context['console'].workflow_review_store.read_events()
        with guard.installed(monkeypatch):
            restarted = context['build']()
            assert restarted._envelope(sid) == envelope_before
            assert restarted._load_objects(sid) == objects_before
            assert restarted.workflow_review_store.read_events() == events_before
            assert restarted._envelope(sid)['title'] != 'half command must roll back'
            assert not any(e['event_type'] == 'd5_crash_probe' for e in events_before)
        assert not guard.rows
    finally:
        unregister_backend(tmp_path / 'runtime/review_ledger.jsonl')
