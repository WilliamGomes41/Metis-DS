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
    assert recovery.WORKFLOW_RECOVERY_VERSION == 7
    columns = recovery._WORKFLOW_COLUMNS['publication_refusals']
    assert columns[0] == 'refusal_id' and 'dedup_key' in columns and 'reason_codes' in columns
    assert recovery._WORKFLOW_JSON_COLUMNS['publication_refusals'] == {'reason_codes'}


def test_version_6_backup_upgrades_with_empty_refusals():
    state = {'workflow_recovery_version': 6, 'workflow_tables': {'documents': []}}
    upgraded = recovery._upgrade_workflow_state(state)
    assert upgraded['workflow_recovery_version'] == 7
    assert upgraded['workflow_tables']['publication_refusals'] == []
    assert 'publication_refusals' not in state['workflow_tables']  # input NOOIT mutated


def test_version_6_backup_with_refusals_key_is_a_conflict():
    state = {'workflow_recovery_version': 6, 'workflow_tables': {'publication_refusals': [{'refusal_id': 1}]}}
    with pytest.raises(recovery.PublicationChainRecoveryError, match='refusal_version_conflict'):
        recovery._upgrade_workflow_state(state)
