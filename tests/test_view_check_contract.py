"""Bounded capability and scenario checks; no database/browser claims.
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from pathlib import Path
import subprocess

import pytest
from starlette.datastructures import QueryParams

from src.view_check import CHECK_IDS, allowed_request, validate_checks


@pytest.mark.parametrize('method,path,query', [
    ('POST', '/review', 'document=one&task=inventory'),
    ('GET', '/review', 'document=two&task=inventory'),
    ('GET', '/review', 'document=one&task=inventory&document=two'),
    ('GET', '/review', 'document=one&task=history'),
    ('GET', '/inzicht/document/passages', 'document=one&format=csv'),
    ('GET', '/inzicht/document/blokkade', 'document=one&checks=1'),
    ('GET', '/tree', 'document=one'),
])
def test_capability_does_not_authorize_mutations_other_documents_or_diagnostics(method, path, query):
    assert not allowed_request(method, path, QueryParams(query), 'one')


def test_capability_allows_only_the_fixed_read_scenario():
    assert allowed_request('GET', '/review', QueryParams('document=one&task=inventory'), 'one')
    assert allowed_request('GET', '/source-selection', QueryParams('document=one'), 'one')
    assert allowed_request('GET', '/inzicht/document/passages', QueryParams('document=one'), 'one')


def test_result_rejects_duplicate_checks_and_private_page_text():
    checks = [{'id': key, 'verdict': 'pass', 'expected': 1, 'observed': 1,
               'private': 'must not be retained'} for key in CHECK_IDS]
    assert all('private' not in row for row in validate_checks(checks))
    checks[-1] = checks[0]
    with pytest.raises(ValueError, match='invalid_checks'):
        validate_checks(checks)


def test_scenario_catches_wrong_identity_even_with_the_same_count_and_partition():
    script = Path(__file__).resolve().parents[1] / 'scripts/view_check.cjs'
    js = '''const {compareInventory}=require(process.argv[1]);
const expected=[{object_id:'a'},{object_id:'b'}];
const good=[{id:'a',source:false,linked:true},{id:'b',source:true,linked:true}];
const wrong=[{id:'wrong',source:false,linked:true},{id:'b',source:true,linked:true}];
console.log(JSON.stringify({good:compareInventory(expected,good,['b']),wrong:compareInventory(expected,wrong,['b'])}));'''
    result = json.loads(subprocess.check_output(['node', '-e', js, str(script)], text=True))
    assert all(row['verdict'] == 'pass' for row in result['good'])
    identity = result['wrong'][0]
    assert identity['expected'] == identity['observed'] == 2
    assert identity['verdict'] == 'fail'


def test_nested_read_scope_cannot_reenable_native_source_extraction():
    from src.operations_console_v1 import OperationsConsole
    state = OperationsConsole.__new__(OperationsConsole)
    with state.source_selection_read_scope(retained_only=True):
        with state.source_selection_read_scope():
            assert state._source_selection_reads()['retained_only']
    assert state._source_selection_reads() is None
