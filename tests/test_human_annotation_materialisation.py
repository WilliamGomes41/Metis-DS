"""Human selections still use the only creator; context is part of the claim.

# release-control-evidence: scope/belofte
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
from uuid import uuid4

import pytest

from src.vorming.human_annotation_projection_v1 import FIELDS,ORIGIN,validate_object_fields
from src.vorming.knowledge_materialisation_v1 import materialise_knowledge_candidates,resolve_source_selection
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.semantic_transform_generic_v1 import transform
from tests.test_t7_creator_cut import _fragment,_manifest,_gate


def inputs():
    fragments=[_fragment('core','De huid is droog.'),_fragment('condition','Alleen bij jeuk.'),
               _fragment('support','Onderzoek beschrijft de bevinding.')]
    blocks=semantic_source_blocks(fragments)
    spans=[{'block_id':blocks[0]['block_id'],'start':0,'end':len(blocks[0]['text'])}]
    fields={f:{'span':None,'missing_reason':'uncertain'} for f in FIELDS}
    fields.update(subject_span={'span':{**spans[0],'end':len('De huid')},'missing_reason':None},
        predicate_span={'span':{**spans[0],'start':len('De huid '),'end':len('De huid is droog')},'missing_reason':None},
        type_evidence_spans={'core':True},factual_claim_span={'core':True})
    ranges=[{**s,'role':r,'required_for_meaning':r=='condition','evidence_function':'supported_by' if r=='evidence' else None}
            for s,r in zip([spans[0],*({'block_id':b['block_id'],'start':0,'end':len(b['text'])} for b in blocks[1:])],['core','condition','evidence'])]
    from src.vorming.human_annotation_v1 import relationship_id
    annotation_id=str(uuid4())
    for anchor in ranges:
        if anchor['role']!='core': anchor['relationship_id']=relationship_id(annotation_id,anchor)
    decision={'decision_kind':'semantic_selection','selection_origin':ORIGIN,'spans':spans,
              'source_text':resolve_source_selection(spans,fragments=fragments)['source_text'],
              'emit_proposed_type':True,'proposed_object_type':'factual_finding','field_evidence':fields,
              'annotation_ranges':ranges,'evidence_not_applicable':False,
              'human_annotation':{'annotation_id':annotation_id,'revision':1,'payload_hash':'a'*64}}
    return fragments,decision


def canonical(fragments,decision):
    candidates=materialise_knowledge_candidates([decision],document_id='human',fragments=fragments)
    spec={'spec_version':'console-ingest-1.0','document_id':'human','object_version':'1.0',
          'target_group':[],'care_setting':[],'topic':[],'objects':candidates}
    return transform(spec,_manifest(),fragments)[0]


def test_human_claim_keeps_source_context_and_functions_without_second_candidate():
    fragments,decision=inputs()
    obj=canonical(fragments,decision)
    assert obj['content']['clean_text']=='De huid is droog.'
    assert obj['metadata']['semantic_passage']['selection_origin']==ORIGIN
    assert 'model' not in obj['metadata']['semantic_passage']
    context=obj['metadata']['source_bound_context']['entries']
    assert context[0]['role']=='condition' and context[0]['required_for_meaning'] is True
    assert context[1]['evidence_function']=='supported_by'
    validate_object_fields(obj,fragments)
    before=(obj['object_id'],deepcopy(obj['content']),deepcopy(obj['provenance']))
    allowed=_gate([obj],fragments)[0]
    assert (allowed['object_id'],allowed['content'],allowed['provenance'])==before
    assert allowed['metadata']['admission']['gate_result']=='allowed',allowed['metadata']['admission']['reason_codes']
    changed=deepcopy(decision);changed['annotation_ranges'][-1]['evidence_function']='explains'
    other=canonical(fragments,changed)
    assert other['object_id']==obj['object_id'] and other['content']==obj['content']
    assert other['metadata']['source_bound_context']['entries'][-1]['evidence_function']=='explains'


def test_materialiser_rejects_human_free_text_and_mismatched_core():
    fragments,decision=inputs()
    for field in ('object_id','clean_text'):
        with pytest.raises(ValueError,match='selection_decision_is_not_a_candidate'):
            materialise_knowledge_candidates([{**decision,field:'invented'}],document_id='human',fragments=fragments)
    bad=deepcopy(decision);bad['annotation_ranges'][0]['end']-=1
    with pytest.raises(ValueError,match='annotation_core_source_mismatch'):
        canonical(fragments,bad)
    obj=canonical(fragments,decision)
    obj['metadata']['source_bound_context']['entries'][0]['text']='Andere voorwaarde.'
    with pytest.raises(ValueError,match='source_bound_context_stale'):
        validate_object_fields(obj,fragments)
