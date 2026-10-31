"""MET-41 expand: diagnostic archives are not activation/publication proof.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import time

import psycopg
import pytest

from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_workflow_runtime_privileges_v1 import runtime_role  # noqa: F401


@pytest.fixture(params=[False, True], ids=['local-source', 'azure-source'])
def archived_system(tmp_path, production_console, request):
    def factory(**options):
        return production_console(azure=request.param, **options)
    console, users, sid, _ = _system(tmp_path, production_console=factory)
    return console, FormationTaskStore(console.workflow_document_store), console._envelope(sid)


def preparation(store, envelope, *, key='run-1', payload=None):
    return store.prepare_processing_archive(envelope, kind='quality_processing_run',
        record_key=key, observed_revision='captured-object-revision',
        payload={'run_id': key, 'values': [True, 1, 1.0, None, {}, []]} if payload is None else payload)


def test_archive_is_exact_idempotent_and_does_not_mutate_document(archived_system):
    console, store, envelope = archived_system
    before = store.documents.get_envelope(envelope['snapshot_id'])
    objects = console.snapshot_objects(envelope['snapshot_id'])
    prepared = preparation(store, envelope)
    ref = store.retain_processing_archive(prepared)
    assert store.retain_processing_archive(prepared) == ref
    assert store.processing_archive_header(envelope, kind='quality_processing_run', record_key='run-1') == ref
    assert store.read_processing_archive(ref, envelope=envelope) == json.loads(prepared.payload_text)
    assert store.documents.get_envelope(envelope['snapshot_id']) == before
    assert console.snapshot_objects(envelope['snapshot_id']) == objects
    for payload in ({'run_id': 'run-1', 'values': [1, 1, 1.0, None, {}, []]}, {'changed': True}):
        with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_conflict'):
            store.retain_processing_archive(preparation(store, envelope, payload=payload))

    real_revision = console.objects_revision(envelope['snapshot_id'])
    real = store.prepare_processing_archive(envelope, kind='semantic_replay', record_key='real-revision',
        observed_revision=real_revision, payload=envelope['semantic_replay'])
    assert store.read_processing_archive(store.retain_processing_archive(real), envelope=envelope) == envelope['semantic_replay']


def test_original_replay_and_quality_json_remain_exact(archived_system):
    _, store, envelope = archived_system
    payloads = [('semantic_replay', 'replay-original', envelope['semantic_replay']),
                ('quality_processing_run', 'quality-original', envelope['quality_processing_runs'][0]),
                ('quality_processing_run', 'numeric', {'n': [1e20, 1.0, 1, True], 'unicode': 'ë',
                                                     'empty': [], 'null': None})]
    for kind, key, payload in payloads:
        prepared = store.prepare_processing_archive(envelope, kind=kind, record_key=key,
            observed_revision='original-capture', payload=payload)
        ref = store.retain_processing_archive(prepared)
        result = store.read_processing_archive(ref, envelope=envelope)
        # Plain Python equality would hide True==1 and 1.0==1.
        assert json.dumps(result, sort_keys=True) == json.dumps(payload, sort_keys=True)


def test_absent_missing_incompatible_corrupt_and_wrong_source_are_distinct(archived_system):
    _, store, envelope = archived_system
    assert store.processing_archive_header(envelope, kind='quality_processing_run', record_key='absent') is None
    prepared = preparation(store, envelope)
    ref = store.retain_processing_archive(prepared)
    cases = [({**ref, 'layout': 99}, 'layout_unsupported'),
             ({**ref, 'archive_id': '0'*64}, 'missing'),
             ({**ref, 'payload_hash': '0'*64}, 'integrity_failed')]
    for altered, error in cases:
        with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_' + error):
            store.read_processing_archive(altered, envelope=envelope)
    with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_source_mismatch'):
        store.read_processing_archive(ref, envelope={**envelope, 'sha256': '0'*64})
    with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_integrity_failed'):
        store.retain_processing_archive(replace(prepared, payload_text='{}'))
    wrong = preparation(store, {**envelope, 'sha256': '0'*64}, key='wrong-source')
    with pytest.raises(psycopg.Error, match='processing_archive_source_mismatch'):
        store.retain_processing_archive(wrong)
    # Simulate storage damage, bypassing trusted runtime privileges/triggers.
    with store.documents._connect() as con:
        con.execute('ALTER TABLE workflow.processing_archives DISABLE TRIGGER guard_processing_archive')
        con.execute("UPDATE workflow.processing_archives SET payload_text='{}' WHERE archive_id=%s", (ref['archive_id'],))
        con.execute('ALTER TABLE workflow.processing_archives ENABLE TRIGGER guard_processing_archive')
    with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_integrity_failed'):
        store.read_processing_archive(ref, envelope=envelope)


@pytest.mark.parametrize('invalid_json', ['[]', '{"n":NaN}', '{"n":1, "n":2}'])
def test_direct_sql_cannot_make_invalid_diagnostic_json_readable(archived_system, invalid_json):
    from src.workflows.processing_archives_v1 import archive_id, digest, encoded
    _, store, envelope = archived_system
    prepared = preparation(store, envelope)
    header = json.loads(prepared.header_text)
    header['payload_hash'] = digest(invalid_json)
    header['archive_id'] = archive_id(header)
    # A trusted SQL writer can insert a source-bound record but that alone is
    # not a carrier validation. The reader still rejects invalid root/JSON.
    with store.documents._connect() as con:
        con.execute('INSERT INTO workflow.processing_archives '
            '(archive_id,layout,snapshot_id,kind,record_key,binding,revision_hash,payload_hash,payload_text,observed_revision) '
            'VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)',
            (header['archive_id'], header['layout'], header['snapshot_id'], header['kind'],
             header['record_key'], encoded(header['binding']), header['revision_hash'], header['payload_hash'],
             invalid_json, prepared.observed_revision))
    from src.workflows.processing_archives_v1 import reference
    with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_json_invalid'):
        store.read_processing_archive(reference(header), envelope=envelope)


def test_sql_mutations_fail_but_existing_document_cascade_is_allowed(archived_system):
    _, store, envelope = archived_system
    ref = store.retain_processing_archive(preparation(store, envelope))
    for sql, params in [
        ('UPDATE workflow.processing_archives SET record_key=record_key WHERE archive_id=%s', (ref['archive_id'],)),
        ('DELETE FROM workflow.processing_archives WHERE archive_id=%s', (ref['archive_id'],)),
        ('TRUNCATE workflow.processing_archives', ())]:
        with pytest.raises(psycopg.Error, match='processing_archive_immutable'):
            with store.documents._connect() as con:
                con.execute(sql, params)
    assert store.read_processing_archive(ref, envelope=envelope)
    store.documents.delete_document(envelope['snapshot_id'])
    with store.documents._connect() as con:
        assert con.execute('SELECT count(*) AS n FROM workflow.processing_archives').fetchone()['n'] == 0


def test_duplicate_and_conflicting_concurrent_appends(archived_system):
    _, store, envelope = archived_system
    prepared = preparation(store, envelope)
    with ThreadPoolExecutor(max_workers=2) as executor:
        refs = list(executor.map(store.retain_processing_archive, [prepared, prepared]))
    assert refs[0] == refs[1]
    choices = [preparation(store, envelope, key='race', payload={'value': n}) for n in [1, 2]]
    def append(candidate):
        try:
            return store.retain_processing_archive(candidate)
        except WorkflowDocumentStoreError as error:
            assert str(error) == 'processing_archive_conflict'
            return None
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(append, choices))
    winner = next(ref for ref in outcomes if ref is not None)
    assert outcomes.count(None) == 1
    assert store.read_processing_archive(winner, envelope=envelope)['value'] in {1, 2}


def test_real_transaction_failure_and_new_process_read(archived_system, tmp_path):
    _, store, envelope = archived_system
    prepared = preparation(store, envelope)
    with store.documents._connect() as con:
        con.execute("""CREATE FUNCTION workflow.test_archive_failure() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN PERFORM 1/0; RETURN NEW; END $$""")
        con.execute('CREATE TRIGGER test_archive_failure AFTER INSERT ON workflow.processing_archives '
                    'FOR EACH ROW EXECUTE FUNCTION workflow.test_archive_failure()')
    with pytest.raises(psycopg.errors.DivisionByZero):
        store.retain_processing_archive(prepared)
    assert store.processing_archive_header(envelope, kind='quality_processing_run', record_key='run-1') is None
    with store.documents._connect() as con:
        con.execute('DROP TRIGGER test_archive_failure ON workflow.processing_archives')
    ref = store.retain_processing_archive(prepared)
    handoff = tmp_path / 'archive.json'
    handoff.write_text(json.dumps({'ref': ref, 'envelope': envelope}))
    code = '''
import json, sys
from pathlib import Path
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore
from src.workflows.formation_task_store_v1 import FormationTaskStore
data = json.loads(Path(sys.argv[2]).read_text())
store = FormationTaskStore(PostgresWorkflowDocumentStore(PostgresCanonicalConfig(dsn=sys.argv[1])))
print(json.dumps(store.read_processing_archive(data['ref'], envelope=data['envelope']), sort_keys=True))
'''
    child = subprocess.run([sys.executable, '-c', code, store.documents.config.dsn, str(handoff)],
                           capture_output=True, text=True, timeout=20)
    assert child.returncode == 0, child.stderr
    assert json.loads(child.stdout) == json.loads(prepared.payload_text)


def test_outer_transaction_is_rejected_before_preparation_or_write(archived_system):
    from src.workflows.workflow_transaction_v1 import workflow_transaction
    _, store, envelope = archived_system
    prepared = preparation(store, envelope)
    with workflow_transaction(store.documents):
        for operation in [lambda: preparation(store, envelope), lambda: store.retain_processing_archive(prepared)]:
            with pytest.raises(WorkflowDocumentStoreError, match='processing_archive_requires_independent_transaction'):
                operation()


def test_migration_is_repeatable_and_narrow_runtime_grants_can_append(archived_system, runtime_role, monkeypatch):
    _, store, envelope = archived_system
    admin, role = runtime_role
    admin.execute(f'GRANT SELECT, UPDATE ON workflow.documents TO "{role}"')
    admin.execute(f'GRANT SELECT, INSERT ON workflow.processing_archives TO "{role}"')
    original_connect = store.documents._connect
    @contextmanager
    def runtime_connect():
        with original_connect() as con:
            con.execute(f'SET LOCAL ROLE "{role}"')
            yield con
    with monkeypatch.context() as patch:
        patch.setattr(store.documents, '_connect', runtime_connect)
        ref = store.retain_processing_archive(preparation(store, envelope))
        assert store.retain_processing_archive(preparation(store, envelope)) == ref
        before = store.read_processing_archive(ref, envelope=envelope)
    sql = (Path(__file__).resolve().parents[1] / 'db/migrations/028_processing_archives.sql').read_text()
    with store.documents._connect() as con:
        con.execute(sql)
        con.execute(sql)
    assert store.read_processing_archive(ref, envelope=envelope) == before


def test_header_cost_does_not_transfer_independent_archive_payloads(archived_system, record_property, monkeypatch):
    from src.console_performance_v1 import performance_scope
    from src.request_diagnostics_v1 import RequestEvidence, _CURRENT
    console, store, envelope = archived_system
    prepared = store.prepare_processing_archive(envelope, kind='quality_processing_run', record_key='run-1',
        observed_revision=console.objects_revision(envelope['snapshot_id']), payload={'run_id': 'run-1'})
    store.retain_processing_archive(prepared)
    original_connect = store.documents._connect
    text_sizes = []
    @contextmanager
    def measured_connect():
        with original_connect() as con:
            base = con.adapters.get_loader(25, 0)  # text; archive payload is deliberately TEXT
            class MeasuredText(psycopg.adapt.Loader):
                def __init__(self, oid, context=None):
                    super().__init__(oid, context)
                    self.original = base(oid, context)
                def load(self, data):
                    text_sizes.append(len(data))
                    return self.original.load(data)
            con.adapters.register_loader(25, MeasuredText)
            yield con
    samples = []
    for count in [0, 24]:
        if count:
            # About 25 MB independent history, not a production/Smetten benchmark.
            # Canonical text preserves exact historical hashes/values.
            for index in range(count):
                store.retain_processing_archive(preparation(store, envelope, key=f'large-{index}',
                    payload={'data': 'x' * (1024 * 1024), 'index': index}))
        evidence = RequestEvidence('archive-test', '/review', lambda _: None)
        token = _CURRENT.set(evidence)
        try:
            with performance_scope() as metrics:
                started = time.perf_counter()
                text_sizes.clear()
                with monkeypatch.context() as patch:
                    patch.setattr(store.documents, '_connect', measured_connect)
                    ref = store.processing_archive_header(envelope, kind='quality_processing_run', record_key='run-1')
        finally:
            _CURRENT.reset(token)
        samples.append({'archives': count + 1, 'seconds': time.perf_counter() - started,
            'queries': metrics.queries, 'json_bytes': metrics.json_bytes, 'reference_bytes': len(json.dumps(ref)),
            'wire_value_bytes': metrics.json_bytes + sum(text_sizes),
            'execute_ms': evidence.totals['db_execute']['inclusive_ms'],
            'fetch_ms': evidence.totals['db_fetch']['inclusive_ms']})
    assert samples[0]['json_bytes'] == samples[1]['json_bytes']
    assert samples[0]['queries'] == samples[1]['queries'] == 1
    assert samples[0]['reference_bytes'] == samples[1]['reference_bytes'] < 512
    assert samples[0]['wire_value_bytes'] == samples[1]['wire_value_bytes'] < 2048
    record_property('archive_header_measurements', json.dumps(samples))
