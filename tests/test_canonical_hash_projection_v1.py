"""Hash optimization retains exact persisted prechange identities and isolation.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from src.integrity_kernel import canonical_object_payload, compute_canonical_object_hash, stable_hash

pytestmark = pytest.mark.pure_function


def cases():
    base = {'object_id':'synthetic-object', 'object_version':'1.0', 'document_id':'synthetic-document',
        'parent_object_id':None, 'object_type':'definition', 'proposed_object_type':'definition',
        'confirmed_object_type':None, 'source':{'source_checksum':'a'*64,'version':'1'},
        'structure':{'sequence':1,'section_path':['A']}, 'content':{'clean_text':'Synthetic definition.','measure':1},
        'logic':{}, 'relations':[], 'decision_graph':None,
        'risk':{'requires_second_review':False}, 'uncertainty':{'has_uncertainty':False},
        'governance':{'validation_status':'needs_review'},
        'provenance':{'source_fragments':[{'fragment_id':'synthetic','text':'Synthetic definition.'}],
                      'content_hash':'derived','canonical_object_hash':'derived','contract':'fixture'},
        'metadata':{'admission':{'gate_result':'allowed'}, 'passage_register':{'status':'pending'},
                    'candidate_eligibility':{'value':True}, 'clinical':{'meaning':'A','values':[1,2]}}}
    result = {'base':base}
    for name, value in [('empty',{}),('null',None),('derived_only',{'admission':{},'passage_register':{},'candidate_eligibility':{}})]:
        row = deepcopy(base); row['metadata'] = value; result['metadata_'+name] = row
    row=deepcopy(base);row.pop('metadata');result['metadata_absent']=row
    row=deepcopy(base);row['content']['measure']=1.0;result['float_measure']=row
    row=deepcopy(base);row['governance']['validation_status']='approved';result['governance_only']=row
    row=deepcopy(base);row['provenance']['canonical_object_hash']='another-derived';result['derived_hash_only']=row
    row=deepcopy(base);row['metadata']['admission']['gate_result']='blocked';result['admission_only']=row
    row=deepcopy(base);row['metadata']['clinical']['meaning']='B';result['clinical_change']=row
    row=deepcopy(base);row['source']['source_checksum']='b'*64;result['source_change']=row
    row=deepcopy(base);row['content']['clean_text']='Changed clinical definition.';result['text_change']=row
    row=deepcopy(base);row['provenance']['source_fragments'][0]['text']='Changed source fragment.';result['fragment_change']=row
    return result


@pytest.mark.parametrize('name', sorted(cases()))
def test_hash_matches_persisted_prechange_identity_and_never_mutates_input(name):
    from src.vorming.prepared_source_views_v1 import freeze
    expected = json.loads((Path(__file__).parent/'fixtures/canonical_hash_projection_v1.json').read_text())['hashes']
    row = cases()[name]
    before = deepcopy(row)
    assert compute_canonical_object_hash(row) == expected[name]
    assert stable_hash(canonical_object_payload(row)) == expected[name]
    assert compute_canonical_object_hash(freeze(row)) == expected[name]
    assert row == before


def test_public_projection_remains_deeply_detached():
    row = cases()['base']; before=deepcopy(row)
    projection = canonical_object_payload(row)
    projection['source']['version'] = 'caller-mutation'
    projection['content']['clean_text'] = 'caller-mutation'
    projection['structure']['section_path'].append('caller-mutation')
    projection['provenance']['source_fragments'][0]['text'] = 'caller-mutation'
    projection['metadata']['clinical']['values'].append('caller-mutation')
    assert row == before
    hashes = {name:compute_canonical_object_hash(value) for name,value in cases().items()}
    assert hashes['base'] == hashes['governance_only'] == hashes['derived_hash_only'] == hashes['admission_only']
    assert hashes['base'] != hashes['float_measure']
    assert len({hashes[name] for name in ['base','clinical_change','source_change','text_change','fragment_change']}) == 5
