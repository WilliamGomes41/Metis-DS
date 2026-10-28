"""D5: two actual worker processes, one PG authority and one runtime directory.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import multiprocessing
from pathlib import Path

import pytest

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from src.review.review_ledger import unregister_backend, verify_ledger
from tests.complete_workflow_support import complete_console, complete_postgres  # noqa: F401
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_pg_console_without_disk_mirrors import CONSOLES, MirrorAccess
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE, MemorySourceStore


def _worker(dsn, root, kind, command, barrier, outcomes):
    root = Path(root)
    guard = MirrorAccess(root / 'runtime', deny=True)
    patch = pytest.MonkeyPatch()
    try:
        with guard.installed(patch):
            console = complete_console(root, PostgresCanonicalConfig(dsn=dsn), console_cls=CONSOLES[kind])
            bind_fixture_selections(console)
            barrier.wait(timeout=20)
            try:
                console.review_object(**command)
                result = 'PASS'
            except ConsoleError as exc:
                result = exc.code
            assert not guard.rows
            outcomes.put(result)
    except BaseException as exc:
        outcomes.put(type(exc).__name__)
        raise
    finally:
        unregister_backend(root / 'runtime/review_ledger.jsonl')


@pytest.mark.parametrize('kind', CONSOLES)
def test_two_worker_review_conflicts_without_any_disk_mirror(complete_postgres, tmp_path, monkeypatch, kind):
    guard = MirrorAccess(tmp_path / 'runtime', deny=True)
    processes = []
    try:
        with guard.installed(monkeypatch):
            console = complete_console(tmp_path, complete_postgres, console_cls=CONSOLES[kind],
                immutable_source_store=MemorySourceStore())
            bind_fixture_selections(console)
            author = console.create_account('author', 'worker-test-password', roles=['researcher'])
            reviewer = console.create_account('reviewer', 'worker-test-password', roles=['reviewer'])
            receipt = console.ingest(actor_id=author['account_id'], filename='two-workers.html',
                data=HTML_FIXTURE.read_bytes(), content_type='text/html', ingest_kind='new',
                title='Two worker fixture', version='1.0', date='2026-09-16', live_url='',
                class_='richtlijn', family='d5-workers', named_reviewers=[reviewer['account_id']])
            sid = receipt['snapshot_id']
            target = next(obj for obj in console.snapshot_objects(sid) if obj.get('object_type') == 'unclassified')
            command = dict(actor_id=reviewer['account_id'], snapshot_id=sid, object_id=target['object_id'],
                decision='approve', confirmed_object_type='explanation', expected_revision=console.objects_revision(sid))
            before = console.workflow_review_store.read_events()
        spawn = multiprocessing.get_context('spawn')
        barrier, outcomes = spawn.Barrier(2), spawn.Queue()
        for _ in range(2):
            process = spawn.Process(target=_worker, args=(complete_postgres.dsn, str(tmp_path), kind, command, barrier, outcomes))
            process.start()
            processes.append(process)
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
        results = [outcomes.get(timeout=5) for _ in processes]
        assert sorted(results) == sorted(['PASS', SNAPSHOT_OBJECT_WRITE_CONFLICT])
        with guard.installed(monkeypatch):
            events = console.workflow_review_store.read_events()[len(before):]
            assert sum(event['event_type'] == 'clinical_review_approve' for event in events) == 1
            bindings = console.workflow_review_store.read_bindings()[sid]
            assert sum(row['object_id'] == target['object_id'] for row in bindings) == 1
            assert verify_ledger(console._ledger_path) == []
        assert not guard.rows
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        unregister_backend(tmp_path / 'runtime/review_ledger.jsonl')
