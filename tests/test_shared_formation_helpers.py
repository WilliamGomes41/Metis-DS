"""Frozen pre-transition source views and contract bytes remain historical evidence.
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
"""
import json
from pathlib import Path
import subprocess
import sys

from src.integrity_kernel import stable_hash
from src.vorming import prepared_source_views_v1 as views
from src.vorming import semantic_proposal_contract_v1 as contracts


def test_shared_helpers_preserve_frozen_historical_views_and_contracts():
    frozen = json.loads((Path(__file__).parent / 'fixtures/ha4_shared_helpers.json').read_text())
    raw = frozen['fragments']
    prepared = views.prepare(raw)
    for name, expected in frozen['filters'].items():
        helper = getattr(views, name)
        assert helper(raw) == expected
        assert helper(prepared.fragments) == expected
        assert stable_hash(helper(prepared.fragments)) == stable_hash(expected)
    for contract in frozen['contracts']:
        assert contracts.semantic_contract_version(**contract['flags']) == contract['version']
        assert stable_hash(contracts._proposal_schema(**contract['flags'])) == contract['schema_hash']


def test_source_and_historical_readers_and_tree_transport_load_without_old_executor():
    # Fresh interpreter: pytest's fixture imports must not hide an indirect dependency.
    code = '''
import sys, importlib.abc
class BlockExecutor(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'src.vorming.pre_review_semantic_v1':
            raise AssertionError('old prose executor imported')
sys.meta_path.insert(0, BlockExecutor())
from src.vorming import prepared_source_views_v1, semantic_proposal_contract_v1
from src.vorming import decision_tree_route_v1, source_selection_v1, processing_retry_v1
from src.workflows import formation_task_store_v1, formation_evidence_v1
from src import forensic_trace_v1
assert prepared_source_views_v1.prepare([]).fragments == []
assert semantic_proposal_contract_v1.semantic_contract_version()
'''
    subprocess.run([sys.executable, '-c', code], check=True)
