"""Human producer projection into the existing single candidate creator."""
from collections import defaultdict
from copy import deepcopy

from src.vorming.document_spec_v1 import document_spec
from src.vorming.human_annotation_preview_v1 import inspect_document
from src.vorming.human_annotation_contract_v1 import MODE
from src.vorming.knowledge_materialisation_v1 import materialise_knowledge_candidates, resolve_source_selection
from src.vorming.semantic_passage_v1 import SELECTION_ORIGIN_HUMAN, _reconstructed_blocks, _coverage_remainders


def build_objects(seal, entries, *, fragments):
    from src.vorming.source_accountability_v1 import VERSION, CONTAINERS_VERSION
    # Missing policy is the immutable HA-2 producer contract. Never reinterpret
    # existing seals while new seals opt into the existing T10 source policy.
    source_version = seal.get('source_accountability_version', VERSION)
    if source_version not in {VERSION, CONTAINERS_VERSION}:
        raise ValueError('annotation_source_policy_invalid')
    inspection = inspect_document(entries, fragments=fragments)
    if inspection['findings']:
        raise ValueError('annotation_document_incomplete')
    decisions, occupied, context_spans = [], defaultdict(list), []
    for entry in entries:
        payload = entry['payload']
        if payload['status'] == 'withdrawn' or payload.get('disposition') is not None:
            continue
        core = [{key: anchor[key] for key in ('block_id', 'start', 'end')}
                for anchor in payload['ranges'] if anchor['role'] == 'core']
        decisions.append({'decision_kind': 'semantic_selection', 'selection_origin': SELECTION_ORIGIN_HUMAN,
            'spans': core, 'source_text': resolve_source_selection(core, fragments=fragments)['source_text'],
            'emit_proposed_type': True, 'proposed_object_type': payload['object_type'],
            'field_evidence': deepcopy(payload['field_evidence']),
            'annotation_ranges': deepcopy(payload['ranges']),
            'evidence_not_applicable': payload['evidence_not_applicable'],
            'required_links': deepcopy(payload.get('required_links') or []),
            'recommendation_semantics': deepcopy(payload.get('recommendation_semantics')),
            'human_annotation': {key: entry[key] for key in ('annotation_id', 'revision', 'payload_hash')}})
        for anchor in payload['ranges']:
            if anchor['role'] == 'core':
                occupied[anchor['block_id']].append((anchor['start'], anchor['end']))
            else:
                context_spans.append({key: anchor[key] for key in ('block_id', 'start', 'end')})
    context = seal['context']
    units = materialise_knowledge_candidates(decisions, document_id=context['document_id'], fragments=fragments)
    # These are retained source records under the existing accountability owner,
    # never KnowledgeCandidates or an automatic source-role confirmation.
    units += [unit for _, unit in _coverage_remainders(_reconstructed_blocks(fragments),
        document_id=context['document_id'], selected_ranges_by_block=occupied,
        assessments=inspection['source_assessments'], context_spans=context_spans, source_version=source_version)]
    from src.operations_console_v1 import canonical_source_manifest, transform_generic
    from src.vorming.admission_gate_v1 import apply_admission_gate
    from src.vorming.passage_register_v1 import apply_passage_register
    spec = document_spec(document_id=context['document_id'], title=context['title'], family=context['family'],
                         class_=context['class'], content_kind=context['content_kind'], units=units)
    objects = transform_generic(spec, canonical_source_manifest(context), fragments)
    objects = apply_admission_gate(objects, klasse=context['class'], fragments=fragments,
                                   document_version=context['version'], source_hash=context['sha256'])
    objects = apply_passage_register(objects)
    if context.get('review_policy'):
        from src.review.review_policy_v1 import project_policy
        project_policy(objects, context['review_policy'])
    return objects
