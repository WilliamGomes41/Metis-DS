"""Literal human selections behind the existing deterministic candidate creator.

This module binds fields and context. It never assigns candidate identity or
candidate text. Human-origin is producer provenance, never review approval.
"""
from copy import deepcopy

from src.integrity_kernel import stable_hash
from src.vorming.source_bound_fields_v3 import FIELDS, bind_fields as bind_v3
from src.vorming.semantic_passage_v1 import SELECTION_ORIGIN_HUMAN as ORIGIN

from src.vorming.human_annotation_contract_v1 import (MODE,FIELDS_VERSION,CONTEXT_VERSION,
    REFERENCE_KEY,CORE_FIELDS,TYPE_CORE_FIELDS,ROLE_MAP)


def bind_fields(raw, *, selected, candidate_text, proposed_type, context=()):
    """Preserve v3 obligations; a composite normative core names the core group.

    The researcher already designated exactly that group as the statement of
    the chosen type. This does not guess subject, predicate, action, actor,
    applicability, strength or direction from a whole paragraph.
    """
    if not isinstance(raw,dict) or set(raw)!=set(FIELDS):
        raise ValueError('source_bound_fields_invalid')
    ordinary = deepcopy(raw)
    core_fields = []
    for field, evidence in raw.items():
        if isinstance(evidence,dict) and set(evidence)=={'core'} and evidence['core'] is True:
            if field not in CORE_FIELDS:
                raise ValueError('human_field_core_not_allowed')
            core_fields.append(field)
            ordinary[field] = {'span':None,'missing_reason':'uncertain'}
    bound = bind_v3(ordinary,selected=selected,candidate_text=candidate_text,
                    proposed_type=proposed_type,context=context)
    values = bound['values']
    for field in core_fields:
        values[field] = [candidate_text] if field=='type_evidence_spans' else candidate_text
    payload = {'version':FIELDS_VERSION,'candidate_text':candidate_text,'proposed_type':proposed_type,
               'values':values,'evidence':deepcopy(raw),'context_hash':stable_hash(list(context))}
    return {**payload,'binding_hash':stable_hash(payload)}


def bound_values(record, *, text, proposed_type, context=()):
    if not isinstance(record,dict) or set(record)!={'version','candidate_text','proposed_type','values','evidence','context_hash','binding_hash'}:
        raise ValueError('source_bound_fields_invalid')
    payload = {k:v for k,v in record.items() if k!='binding_hash'}
    if record['version']!=FIELDS_VERSION or record['binding_hash']!=stable_hash(payload):
        raise ValueError('source_bound_fields_invalid')
    if record['candidate_text']!=text or record['proposed_type']!=proposed_type or record['context_hash']!=stable_hash(list(context)):
        raise ValueError('source_bound_fields_stale')
    if set(record['evidence'])!=set(FIELDS):
        raise ValueError('source_bound_fields_invalid')
    ordinary_evidence, ordinary_values = deepcopy(record['evidence']),deepcopy(record['values'])
    for field,evidence in record['evidence'].items():
        if isinstance(evidence,dict) and set(evidence)=={'core'} and evidence['core'] is True:
            expected = [text] if field=='type_evidence_spans' else text
            if field not in CORE_FIELDS or ordinary_values.pop(field,None)!=expected:
                raise ValueError('human_field_core_not_allowed')
            ordinary_evidence[field]={'span':None,'missing_reason':'uncertain'}
    from src.vorming.source_bound_fields_v3 import VERSION, bound_values as read_v3
    legacy = {**payload,'version':VERSION,'values':ordinary_values,'evidence':ordinary_evidence}
    legacy['binding_hash']=stable_hash(legacy)
    read_v3(legacy,text=text,proposed_type=proposed_type,context=context)
    return deepcopy(record['values'])


def bind_context(ranges, *, fragments):
    """Keep role/function/essentiality on each entry-specific relationship."""
    from src.vorming.source_bound_fields_v2 import resolve_context_literal
    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
    blocks=_read_source_blocks(fragments,include_headings=True)
    result=[]
    for anchor in ranges:
        if anchor['role']=='core':
            continue
        role=ROLE_MAP.get(anchor['role'])
        if role is None:
            raise ValueError('annotation_role_invalid')
        if type(anchor['required_for_meaning']) is not bool or (
            anchor['role']=='evidence' and anchor['evidence_function'] not in {'supported_by','explains'}
            or anchor['role']!='evidence' and anchor['evidence_function'] is not None):
            raise ValueError('annotation_relationship_invalid')
        raw={'role':role,'span':{k:anchor[k] for k in ('block_id','start','end')},'unresolved_reason':None}
        resolved=resolve_context_literal(raw['span'],fragments=fragments,blocks=blocks)
        result.append({**raw,**resolved,'annotation_role':anchor['role'],
                       'relationship_id':anchor['relationship_id'],
                       'required_for_meaning':anchor['required_for_meaning'],
                       'evidence_function':anchor['evidence_function']})
    return result


def context_record(entries, *, obj):
    from src.review.source_context_review_v1 import literal_identity
    return {'version':CONTEXT_VERSION,'target_object_id':obj['object_id'],
            'target_object_version_at_binding':obj['object_version'],
            'target_literal_hash':literal_identity(obj),'source':deepcopy(obj['source']),
            'entries':deepcopy(entries)}


def validate_context(obj, fragments, source_hash):
    record=(obj.get('metadata') or {}).get('source_bound_context')
    if not isinstance(record,dict) or record.get('version')!=CONTEXT_VERSION:
        raise ValueError('source_bound_context_invalid')
    human=(obj.get('metadata') or {}).get(REFERENCE_KEY)
    if not isinstance(human,dict):
        raise ValueError('annotation_reference_invalid')
    entries=bind_context(human['ranges'],fragments=fragments)
    expected=context_record(entries,obj=obj)
    expected['target_object_version_at_binding']=record['target_object_version_at_binding']
    if record!=expected or record['source'].get('source_checksum')!=source_hash:
        raise ValueError('source_bound_context_stale')
    return entries


def bind_candidate(candidate, decision, *, fragments):
    """Called by the creator after canonical literal/ID/mapping are determined."""
    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
    if [{k:a[k] for k in ('block_id','start','end')} for a in decision['annotation_ranges'] if a['role']=='core']!=decision['spans']:
        raise ValueError('annotation_core_source_mismatch')
    if type(decision['evidence_not_applicable']) is not bool:
        raise ValueError('annotation_evidence_required')
    reference=decision.get(REFERENCE_KEY)
    if not isinstance(reference,dict) or set(reference)!={'annotation_id','revision','payload_hash'}:
        raise ValueError('annotation_reference_invalid')
    from uuid import UUID
    if str(UUID(reference['annotation_id']))!=reference['annotation_id'] or type(reference['revision']) is not int or reference['revision']<1:
        raise ValueError('annotation_reference_invalid')
    if not isinstance(reference['payload_hash'],str) or len(reference['payload_hash'])!=64 or any(c not in '0123456789abcdef' for c in reference['payload_hash']):
        raise ValueError('annotation_reference_invalid')
    context=bind_context(decision['annotation_ranges'],fragments=fragments)
    blocks=_read_source_blocks(fragments)
    selected=[{**s,'text':blocks[s['block_id']][0]['text'][s['start']:s['end']]} for s in decision['spans']]
    fields=bind_fields(decision['field_evidence'],selected=selected,candidate_text=candidate['clean_text'],
                       proposed_type=decision['proposed_object_type'],context=context)
    candidate['source_bound_fields']=fields
    candidate['source_bound_context']=context
    candidate['metadata']={REFERENCE_KEY:{**deepcopy(reference),
        'ranges':deepcopy(decision['annotation_ranges']),
        'required_links':deepcopy(decision.get('required_links') or []),
        'evidence_not_applicable':decision['evidence_not_applicable']}}
    candidate['semantic_passage'].update(formation_mode=MODE,annotation_ref=deepcopy(reference))
    if decision.get('recommendation_semantics') is not None:
        from src.vorming.semantic_passage_v1 import _recommendation_semantics_from_proposal
        selected_with_sections=[{**s,'section_path':blocks[s['block_id']][0]['section_path']} for s in selected]
        semantics,binding=_recommendation_semantics_from_proposal(decision['recommendation_semantics'],
            proposed_type=decision['proposed_object_type'],selected=selected_with_sections,
            evidence_by_id=_read_source_blocks(fragments,include_headings=True))
        candidate['proposed_recommendation_semantics']=semantics
        candidate['recommendation_semantics_evidence']=binding


def validate_object_fields(obj, fragments):
    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks, validate_materialised_candidate
    validate_materialised_candidate(obj,fragments=fragments)
    metadata=obj.get('metadata') or {}
    human=metadata.get(REFERENCE_KEY) or {}
    if metadata['semantic_passage'].get('annotation_ref')!={key:human.get(key) for key in ('annotation_id','revision','payload_hash')}:
        raise ValueError('annotation_reference_invalid')
    context=validate_context(obj,fragments,(obj.get('source') or {}).get('source_checksum'))
    blocks=_read_source_blocks(fragments)
    selected=[{**s,'text':blocks[s['block_id']][0]['text'][s['start']:s['end']]}
              for s in metadata['semantic_passage']['spans']]
    record=metadata['source_bound_fields']
    rebuilt=bind_fields(record['evidence'],selected=selected,candidate_text=obj['content']['clean_text'],
                        proposed_type=obj.get('proposed_object_type') or 'unclassified',context=context)
    if record!=rebuilt:
        raise ValueError('source_bound_fields_invalid')
