"""PostgreSQL document cut-over regressions.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import hashlib
import json
import threading
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator

import pytest

from src.operations_console_v1 import (
    SNAPSHOT_OBJECT_WRITE_CONFLICT,
    OperationsConsole,
    _objects_jsonl_bytes,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_cutover_v1 import (
    PostgresWorkflowDocumentRuntimeStore,
    _PostgresWorkflowDocumentsMixin,
)
from src.workflows.workflow_review_cutover_v1 import _PostgresWorkflowReviewMixin
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore

ROOT = Path(__file__).resolve().parents[1]


def _seed_documents(production_console, *, paragraphs=1, documents=2):
    from types import SimpleNamespace
    from tests.test_live_v1_working_v2_v1 import MemorySourceStore
    console = production_console(processing_binder=bind_fixture_selections, immutable_source_store=MemorySourceStore())
    author = console.create_account(username='author',password='fixture-password',roles=['researcher'])
    reviewer = console.create_account(username='reviewer',password='fixture-password',roles=['reviewer'])
    snapshots = []
    for index in range(documents):
        data = ('<html><h1>Bron '+str(index)+'</h1>'+''.join(
            '<p>Een observatie '+str(index)+'-'+str(j)+' is een systematische waarneming.</p>' for j in range(paragraphs))+'</html>').encode()
        snapshots.append(console.ingest(actor_id=author['account_id'],filename=f'source-{index}.html',data=data,
            content_type='text/html',ingest_kind='new',title=f'Bron {index}',version='1',date='2026-10-20',live_url='',
            class_='richtlijn',family=f'fixture-{index}',named_reviewers=[reviewer['account_id']])['snapshot_id'])
    return SimpleNamespace(console=console,author=author,reviewer=reviewer,snapshots=snapshots)


@pytest.fixture
def documents(production_console):
    return _seed_documents(production_console)


def _change_type(subject, console=None):
    console = console or subject.console
    sid = subject.snapshots[0]
    obj = next(o for o in console.snapshot_objects(sid) if o['object_type'] not in {'document','heading'}
               and o.get('proposed_object_type')!='heading')
    console.confirm_object_type(actor_id=subject.reviewer['account_id'],snapshot_id=sid,
        object_id=obj['object_id'],confirmed_object_type='explanation',expected_revision=console.objects_revision(sid))


def test_cutover_revision_preserves_object_order() -> None:
    rows = [
        {"object_id": "z", "object_version": "1.0", "text": "first"},
        {"object_id": "a", "object_version": "1.0", "text": "second"},
    ]
    expected = hashlib.sha256(_objects_jsonl_bytes(rows)).hexdigest()
    assert PostgresWorkflowDocumentRuntimeStore._revision(rows) == expected
    assert PostgresWorkflowDocumentRuntimeStore._revision(list(reversed(rows))) != expected


def test_concurrent_store_revision_for_rows_uses_object_aware_token() -> None:
    rows = [
        {"object_id": "a", "object_version": "1.0", "text": "A"},
        {"object_id": "b", "object_version": "1.0", "text": "B"},
    ]
    store = object.__new__(PostgresConcurrentWorkflowDocumentStore)

    revision = store.revision_for_rows(rows)

    assert revision.startswith(PostgresConcurrentWorkflowDocumentStore.REVISION_PREFIX)
    assert revision != PostgresWorkflowDocumentRuntimeStore._revision(rows)


def test_cutover_schema_preserves_full_envelope_and_object_position() -> None:
    sql = (ROOT / "db" / "migrations" / "003_workflow_document_envelope_payload.sql").read_text(encoding="utf-8")
    assert "envelope_payload JSONB" in sql
    assert "position INTEGER" in sql


def test_cutover_is_explicit_and_never_runs_legacy_migration_on_startup(monkeypatch) -> None:
    from tests.test_workflow_remaining_cutover_v1 import _refused_partial_configurations
    _refused_partial_configurations(monkeypatch, "METIS_WORKFLOW_DOCUMENT_STORE")
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "migrate_legacy_runtime" not in asgi
    assert "prepare_legacy_cutover" not in asgi


def test_cutover_runtime_reads_objects_by_migrated_position() -> None:
    source = (ROOT / "src" / "workflows" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "ORDER BY position" in source
    assert "workflow_document_cutover_not_prepared" in source
    assert "expected_revision" in source
    assert SNAPSHOT_OBJECT_WRITE_CONFLICT == "snapshot_object_write_conflict"


def test_local_files_are_unused_in_postgres() -> None:
    source = (ROOT / "src" / "workflows" / "workflow_documents_cutover_v1.py").read_text(encoding="utf-8")
    assert "workflow files are unused in this topology" in source
    assert "authoritative in PostgreSQL" in source


def test_two_console_process_models_rebase_distinct_envelope_commits(documents):
    from tests.production_support import restart_production
    first = documents.console
    second = restart_production(first)
    first.refresh_workflow_documents(); second.refresh_workflow_documents()
    a,b = documents.snapshots
    prepared_a,prepared_b = deepcopy(first._envelopes),deepcopy(second._envelopes)
    prepared_a[a]['family']='new-a'; prepared_b[b]['family']='new-b'
    barrier,errors = threading.Barrier(2),[]
    def commit(console,sid,prepared):
        try:
            barrier.wait(timeout=5)
            console._commit_prepared_store(envelopes=prepared,snapshot_id=sid)
        except BaseException as exc:
            errors.append(exc)
    threads=[threading.Thread(target=commit,args=(first,a,prepared_a)),threading.Thread(target=commit,args=(second,b,prepared_b))]
    for thread in threads:thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert errors==[]
    assert first.workflow_document_store.get_envelope(a)['family']=='new-a'
    assert second.workflow_document_store.get_envelope(b)['family']=='new-b'



def test_snapshot_objects_and_revision_uses_one_authoritative_object_fetch(production_console,monkeypatch):
    subject = _seed_documents(production_console,paragraphs=250,documents=1)
    console,sid = subject.console,subject.snapshots[0]
    store = console.workflow_document_store
    expected = store.list_document_objects(sid)
    assert len(expected)>=250
    calls=[]
    real=store.list_document_objects
    def observe(snapshot_id):
        calls.append(snapshot_id)
        return real(snapshot_id)
    monkeypatch.setattr(store,'list_document_objects',observe)
    objects,revision=console.snapshot_objects_and_revision(sid,include_blocked=True)
    assert calls==[sid]
    assert objects==expected and revision==store.revision_for_rows(expected)



def test_snapshot_objects_and_revision_uses_store_concurrency_token(documents,monkeypatch):
    console,sid=documents.console,documents.snapshots[0]
    store=console.workflow_document_store
    calls=[]
    real=store.list_document_objects
    def observe(snapshot_id):
        calls.append(snapshot_id)
        return real(snapshot_id)
    monkeypatch.setattr(store,'list_document_objects',observe)
    monkeypatch.setattr(store,'revision_for_rows',lambda rows:'m2.object-aware')
    _,revision=console.snapshot_objects_and_revision(sid,include_blocked=True)
    assert calls==[sid] and revision=='m2.object-aware'



def test_authoritative_object_read_replaces_stale_worker_revision(documents):
    from tests.production_support import restart_production
    console,sid=documents.console,documents.snapshots[0]
    console._load_objects(sid,remember=True)
    first=console._objects_expected_revs()[sid]
    _change_type(documents,restart_production(console))
    console._load_objects(sid,remember=True)
    fresh=console.workflow_document_store.objects_revision(sid)
    assert fresh!=first and console._objects_expected_revs()[sid]==fresh



def test_separate_authoritative_snapshot_reads_detect_intervening_change(documents,monkeypatch):
    from tests.production_support import restart_production
    console,sid=documents.console,documents.snapshots[0]
    other=restart_production(console)
    calls=[]
    real=console.workflow_document_store.list_document_objects
    def observe(snapshot_id):
        calls.append(snapshot_id)
        return real(snapshot_id)
    monkeypatch.setattr(console.workflow_document_store,'list_document_objects',observe)
    first_objects,first_revision=console.snapshot_objects_and_revision(sid,include_blocked=True)
    _change_type(documents,other)
    second_objects,second_revision=console.snapshot_objects_and_revision(sid,include_blocked=True)
    assert calls==[sid,sid]
    assert first_objects!=second_objects and first_revision!=second_revision



def test_postgres_document_startup_leaves_corrupt_envelope_mirror_untouched(documents):
    from tests.production_support import restart_production
    console=documents.console
    path=console.runtime/'envelopes.json'
    path.write_text('{"broken":',encoding='utf-8')
    fresh=restart_production(console)
    assert {r['snapshot_id'] for r in fresh.list_envelopes()}==set(documents.snapshots)
    assert path.read_text()=='{"broken":'



@pytest.mark.parametrize('fail_commit', [True, False])
def test_delete_source_cleanup_follows_transaction_commit_and_restart(documents,fail_commit):
    import psycopg,traceback
    from src.operations_console_v1 import ConsoleError
    from src.workflows.workflow_transaction_v1 import workflow_transaction,workflow_transaction_active
    from tests.production_support import restart_production
    console,sid=documents.console,documents.snapshots[0]
    source=console.immutable_source_store
    config=console.workflow_document_store.config
    envelope=console._envelope(sid)
    locator=envelope['immutable_storage_locator']
    before=deepcopy(console._load_objects(sid,remember=False))
    original=source.load_verified(locator)
    deletes=[]
    real=source.delete_verified
    def delete_after_commit(value):
        assert not workflow_transaction_active()
        with psycopg.connect(config.dsn) as other:
            assert other.execute('SELECT count(*) FROM workflow.documents WHERE snapshot_id=%s',(sid,)).fetchone()[0]==0
        deletes.append(value)
        return real(value)
    source.delete_verified=delete_after_commit
    command=dict(actor_id=documents.author['account_id'],snapshot_id=sid,confirmed=True,confirm_title=envelope['title'])
    with workflow_transaction(console.workflow_document_store):
        with pytest.raises(ConsoleError,match='unpublished_delete_requires_independent_transaction'):
            console.delete_unpublished_snapshot(**command)
    assert deletes==[] and source.load_verified(locator)==original
    if fail_commit:
        with psycopg.connect(config.dsn) as connection:
            connection.execute("CREATE FUNCTION workflow.fail_fixture_delete() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'fixture_commit_failure'; END; $$")
            connection.execute('CREATE CONSTRAINT TRIGGER fail_fixture_delete AFTER DELETE ON workflow.documents DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.fail_fixture_delete()')
        try:
            with pytest.raises(Exception) as caught:
                console.delete_unpublished_snapshot(**command)
            assert 'fixture_commit_failure' in ''.join(traceback.format_exception(caught.value))
            assert deletes==[] and source.load_verified(locator)==original
            assert restart_production(console)._load_objects(sid,remember=False)==before
        finally:
            with psycopg.connect(config.dsn) as connection:
                connection.execute('DROP TRIGGER fail_fixture_delete ON workflow.documents')
                connection.execute('DROP FUNCTION workflow.fail_fixture_delete()')
    result=console.delete_unpublished_snapshot(**command)
    assert result['deleted'] and result['freeze_bytes_removed']
    assert deletes==[locator]
    fresh=restart_production(console)
    assert sid not in [row["snapshot_id"] for row in fresh.list_document_cards()]
    with pytest.raises(ConsoleError,match='unknown_snapshot'):
        fresh.delete_unpublished_snapshot(**command)
    assert deletes==[locator]



# Native PostgreSQL proof for #467. Only immutable blob storage is in-memory;
# transaction commit/rollback, document authority and restart use PostgreSQL.
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: E402,F401


def test_native_postgres_commit_failure_preserves_source_and_restart(recovery_postgres, tmp_path):
    import psycopg
    import traceback
    from tests.test_live_v1_working_v2_v1 import MemorySourceStore, _console
    from src.operations_console_v1 import ConsoleError

    cfg = recovery_postgres
    source = MemorySourceStore()
    console = _console(tmp_path, cfg, source, runtime_name='delete-native-before')
    actor = console.create_account('delete-native-author', 'test-password', ['researcher', 'reviewer'])
    reviewer = console.create_account('delete-native-reviewer', 'test-password', ['reviewer'])
    receipt = console.ingest(
        actor_id=actor['account_id'], filename='native-delete.html',
        data=b'<html><h1>Bron</h1><p>Bespreek passende ondersteuning met de client.</p></html>',
        content_type='text/html', ingest_kind='new', title='Bron', version='1.0',
        date='2026-09-30', live_url='', class_='richtlijn', family='test',
        named_reviewers=[reviewer['account_id']],
    )
    sid = receipt['snapshot_id']
    locator = console._envelope(sid)['immutable_storage_locator']
    original = source.load_verified(locator)
    before = console.snapshot_objects(sid)
    command = dict(actor_id=actor['account_id'], snapshot_id=sid, confirmed=True, confirm_title='Bron')
    # A deferred constraint trigger fails at the real transaction commit, after
    # the DELETE statement itself succeeded. No mock transaction exit is used.
    with psycopg.connect(cfg.dsn) as con:
        con.execute("""CREATE FUNCTION workflow.fail_delete_commit_test() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'test_commit_failure'; END; $$""")
        con.execute("""CREATE CONSTRAINT TRIGGER fail_delete_commit_test
            AFTER DELETE ON workflow.documents DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION workflow.fail_delete_commit_test()""")
    try:
        with pytest.raises(Exception) as failure:
            console.delete_unpublished_snapshot(**command)
        assert "test_commit_failure" in "".join(traceback.format_exception(failure.value))
        assert source.load_verified(locator) == original
        fresh = _console(tmp_path, cfg, source, runtime_name='delete-native-restart')
        assert fresh.snapshot_objects(sid) == before
        assert fresh._envelope(sid)['snapshot_id'] == sid
    finally:
        with psycopg.connect(cfg.dsn) as con:
            con.execute('DROP TRIGGER fail_delete_commit_test ON workflow.documents')
            con.execute('DROP FUNCTION workflow.fail_delete_commit_test()')
    deleted = []
    original_delete = source.delete_verified
    def verify_committed_then_delete(value):
        with psycopg.connect(cfg.dsn) as other:
            assert other.execute('SELECT count(*) FROM workflow.documents WHERE snapshot_id=%s', (sid,)).fetchone()[0] == 0
        deleted.append(value)
        return original_delete(value)
    source.delete_verified = verify_committed_then_delete
    result = fresh.delete_unpublished_snapshot(**command)
    assert result['freeze_bytes_removed'] is True
    assert deleted == [locator]
    restarted = _console(tmp_path, cfg, source, runtime_name='delete-native-after')
    with pytest.raises(ConsoleError, match='unknown_snapshot'):
        restarted._envelope(sid)
    with pytest.raises(ConsoleError, match='unknown_snapshot'):
        restarted.delete_unpublished_snapshot(**command)
    assert deleted == [locator]
