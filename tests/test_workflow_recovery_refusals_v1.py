"""#636 P2 (Sherlock): workflow backup/restore MOET include workflow.publication_refusals.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: releasebewijs

Recovery version 7 adds the table; a version-6 backup is upgraded with an empty refusal table
(it predates the table), NOOIT with invented rows.
"""
import pytest

from src.workflows import workflow_chain_recovery_v1 as recovery


def test_refusals_are_part_of_the_workflow_recovery_boundary():
    assert 'publication_refusals' in recovery.WORKFLOW_TABLES
    assert recovery.WORKFLOW_RECOVERY_VERSION == 9
    columns = recovery._WORKFLOW_COLUMNS['publication_refusals']
    assert columns[0] == 'refusal_id' and 'dedup_key' in columns and 'reason_codes' in columns
    assert recovery._WORKFLOW_JSON_COLUMNS['publication_refusals'] == {'reason_codes'}


def test_version_6_backup_upgrades_with_empty_refusals():
    state = {'workflow_recovery_version': 6, 'workflow_tables': {'documents': []}}
    upgraded = recovery._upgrade_workflow_state(state)
    assert upgraded['workflow_recovery_version'] == 9
    assert upgraded['workflow_tables']['publication_refusals'] == []
    assert 'publication_refusals' not in state['workflow_tables']  # input NOOIT mutated


def test_version_6_backup_with_refusals_key_is_a_conflict():
    state = {'workflow_recovery_version': 6, 'workflow_tables': {'publication_refusals': [{'refusal_id': 1}]}}
    with pytest.raises(recovery.PublicationChainRecoveryError, match='refusal_version_conflict'):
        recovery._upgrade_workflow_state(state)


def test_version_6_restore_roundtrip_compares_against_the_upgraded_archive(monkeypatch, tmp_path):
    # 4291505161: after a successful v6 restore the export is v7 (with publication_refusals);
    # the round-trip check MOET compare against the same upgraded state, NOOIT the raw v6 JSON.
    import io, json, zipfile
    v6 = {'workflow_recovery_version': 6, 'workflow_tables': {'documents': []}, 'api_access_tables': {}}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zipf:
        zipf.writestr('database.json', json.dumps(v6))
    buf.seek(0)
    restored = recovery._upgrade_workflow_state(v6)

    class DB:
        def export_state(self):
            return restored
    monkeypatch.setattr(recovery, 'verify_workflow_chain_backup', lambda archive: {'ok': True, 'errors': []})
    monkeypatch.setattr(recovery, '_guarded_restore', lambda archive, **kw: {'restored': True})
    monkeypatch.setattr(recovery, 'check_workflow_integrity', lambda state: {'ok': True, 'errors': []})
    monkeypatch.setattr(recovery, 'check_chain_integrity', lambda state, **kw: {'ok': True, 'errors': []})
    recovery.restore_workflow_chain(buf, database=DB(), source_store=None)
