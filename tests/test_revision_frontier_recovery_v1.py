"""Actual archive lifecycle plus derived-input preparation checks.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from tests import test_d5_pg_recovery_and_source_v1 as lifecycle
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows import revision_frontiers_postgres_v1 as frontiers


def test_archive_restore_preserves_authority_and_requires_explicit_preparation(complete_postgres, tmp_path, monkeypatch):
    original = lifecycle.restore_workflow_chain
    observed = []
    def checked(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result['ok']
        store = PostgresConcurrentWorkflowDocumentStore(complete_postgres)
        before = kwargs['database'].export_state()
        with store._connect() as con:
            assert not con.execute('SELECT 1 FROM workflow.object_revision_frontiers '
                                   'WHERE certificate IS NOT NULL LIMIT 1').fetchone()
            sids = [row['snapshot_id'] for row in con.execute('SELECT snapshot_id FROM workflow.documents').fetchall()]
        for sid in sids:
            ids = [obj['object_id'] for obj in store.list_document_objects(sid)]
            if ids:
                assert store.review_command_window(sid, ids) is None
                assert frontiers.prepare(store, sid)['status'] == 'prepared'
                assert store.review_command_window(sid, ids) is not None
        after = kwargs['database'].export_state()
        for group in ('tables', 'workflow_tables', 'api_access_tables'):
            assert after[group] == before[group]
        observed.append(True)
        return result
    monkeypatch.setattr(lifecycle, 'restore_workflow_chain', checked)
    lifecycle.test_pg_backup_restore_without_runtime_then_resume_lifecycle(
        complete_postgres, tmp_path, monkeypatch, 'durable')
    assert observed
