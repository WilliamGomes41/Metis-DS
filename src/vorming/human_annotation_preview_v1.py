"""Inspect immutable human input before sealing; never create candidates.

Findings name the original annotation or exact unaccounted source range. This
is an input check, not Admission, source-role confirmation or review approval.
The build still has to validate the sole materialiser's actual output.
"""
from copy import deepcopy

from src.integrity_kernel import stable_hash
from src.vorming.admission_gate_v1 import literal_field_codes
from src.vorming.human_annotation_projection_v1 import bind_context, bind_fields
from src.vorming.human_annotation_v1 import validate_stored_selection
from src.vorming.knowledge_materialisation_v1 import resolve_source_selection
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.source_accountability_v1 import uncovered_ranges, validate_assessments
from src.vorming.source_bound_fields_v3 import TYPE_FIELDS, VIA_RELATION


def _span(anchor):
    return {key: anchor[key] for key in ('block_id', 'start', 'end')}


def inspect_annotation(entry, *, fragments, require_ready=True, blocks=None):
    """The same per-entry inspection for document sealing and the editor.

    Draft preflight omits only the workflow-status finding. Readiness validation
    is reused without saving or inferring missing answers. Cross-entry identity
    and document coverage remain exclusively in inspect_document.
    """
    payload = entry['payload']
    if stable_hash(payload) != entry['payload_hash']:
        raise ValueError('annotation_integrity_failed')
    validate_stored_selection(payload, fragments=fragments, annotation_id=entry['annotation_id'])
    if payload['status'] == 'withdrawn':
        return []
    blocks = semantic_source_blocks(fragments) if blocks is None else blocks
    by_id = {block['block_id']: block for block in blocks}
    codes = []
    if not require_ready:
        ready = deepcopy(payload)
        ready['status'] = 'ready'
        try:
            validate_stored_selection(ready, fragments=fragments, annotation_id=entry['annotation_id'])
        except ValueError as error:
            codes.append(getattr(error, 'code', str(error)))
    if require_ready and payload['status'] != 'ready':
        codes.append('annotation_not_ready')
    if payload.get('pending_range') is not None:
        codes.append('annotation_pending_range')
    if any(link['required_for_meaning'] for link in payload.get('required_links') or []):
        codes.append('annotation_required_relationship_missing')
    core = [_span(anchor) for anchor in payload['ranges'] if anchor['role'] == 'core']
    disposition = payload.get('disposition')
    if disposition is None:
        if not payload.get('field_evidence'):
            codes.append('annotation_fields_required')
        if core and payload.get('field_evidence') and payload.get('object_type'):
            # The existing source resolver supplies a transient literal
            # witness. No canonical text, identity or mapping is created.
            literal = resolve_source_selection(core, fragments=fragments)['source_text']
            context = bind_context(payload['ranges'], fragments=fragments)
            selected_literals = [{**span, 'text': by_id[span['block_id']]['text'][span['start']:span['end']]}
                                 for span in core]
            try:
                bound = bind_fields(payload['field_evidence'], selected=selected_literals,
                                    candidate_text=literal, proposed_type=payload['object_type'], context=context)
                row = {**bound['values'], 'candidate_text': literal, 'source_text_exact': literal,
                       'proposed_type': payload['object_type'], 'source_bound_context_entries': context}
                if payload['object_type'] == 'recommendation':
                    from src.vorming.semantic_passage_v1 import _recommendation_semantics_from_proposal
                    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
                    from src.vorming.recommendation_semantics_v1 import validate_recommendation_semantics
                    raw = payload.get('recommendation_semantics')
                    if raw is None:
                        codes.append('recommendation_semantics_invalid')
                    else:
                        semantics, _ = _recommendation_semantics_from_proposal(raw,
                            proposed_type='recommendation', selected=[{**span, 'section_path':
                                by_id[span['block_id']]['section_path']} for span in selected_literals],
                            evidence_by_id=_read_source_blocks(fragments, include_headings=True))
                        row['proposed_recommendation_semantics'] = semantics
                        if validate_recommendation_semantics(semantics, confirmed=False):
                            codes.append('recommendation_semantics_invalid')
                        if semantics.get('strength_status') == 'unmapped':
                            codes.append('recommendation_strength_unmapped')
                codes.extend(literal_field_codes(row, v3=True, check_locator=False))
                for field in TYPE_FIELDS.get(payload['object_type'], ()):
                    if payload['field_evidence'][field].get('missing_reason') == VIA_RELATION:
                        codes.append('annotation_relation_target_missing')
            except ValueError as error:
                # Existing binders use closed error codes; never exception
                # prose or invented repaired values in the overview.
                codes.append(str(error))
        elif not core:
            codes.append('annotation_core_required')
    return list(dict.fromkeys(codes))


def inspect_document(entries, *, fragments):
    """Accept stored {annotation_id,revision,payload,payload_hash} entries.

    Duplicate core identities are refused without merging. Shared context and
    equal words at different source locations do not collide. This inspection
    alone never authorizes object activation.
    """
    blocks = semantic_source_blocks(fragments)
    findings, checked, selected, assessments, covered = [], [], [], [], {}
    if not blocks:
        findings.append({'annotation_id': None, 'code': 'annotation_source_empty'})
    seen = set()
    core_owners = {}
    for entry in entries:
        payload = entry['payload']
        core = tuple((a['block_id'], a['start'], a['end']) for a in payload['ranges'] if a['role'] == 'core')
        if core and payload['status'] != 'withdrawn' and payload.get('disposition') is None:
            core_owners.setdefault(core, []).append(entry['annotation_id'])
    for entry in entries:
        annotation_id = entry['annotation_id']
        if annotation_id in seen:
            raise ValueError('annotation_integrity_failed')
        seen.add(annotation_id)
        payload = entry['payload']
        codes = inspect_annotation(entry, fragments=fragments, blocks=blocks)
        if payload['status'] == 'withdrawn':
            checked.append({'annotation_id': annotation_id, 'revision': entry['revision'], 'codes': []})
            continue
        core = [_span(anchor) for anchor in payload['ranges'] if anchor['role'] == 'core']
        disposition = payload.get('disposition')
        owners = core_owners.get(tuple((a['block_id'], a['start'], a['end']) for a in core), [])
        if disposition is None and len(owners) > 1:
            # Keep the established document finding order.
            index = sum(code in {'annotation_not_ready','annotation_pending_range','annotation_required_relationship_missing'} for code in codes)
            codes.insert(index, 'annotation_core_duplicate')
        elif disposition is not None and payload['status'] == 'ready':
            assessments.extend({'span': span, **disposition} for span in core)
        codes = list(dict.fromkeys(codes))
        checked.append({'annotation_id': annotation_id, 'revision': entry['revision'], 'codes': codes})
        for code in codes:
            finding = {'annotation_id': annotation_id, 'code': code}
            if code == 'annotation_core_duplicate':
                finding['related_annotation_ids'] = [owner for owner in owners if owner != annotation_id]
            findings.append(finding)
        if not codes and disposition is None:
            selected.append({'spans': core})
            for anchor in payload['ranges']:
                covered.setdefault(anchor['block_id'], []).append((anchor['start'], anchor['end']))
    try:
        validate_assessments(assessments, blocks, selected)
    except ValueError as error:
        findings.append({'annotation_id': None, 'code': str(error)})
        assessments = []
    for assessment in assessments:
        span = assessment['span']
        covered.setdefault(span['block_id'], []).append((span['start'], span['end']))
    gaps = []
    for block in blocks:
        for start, end in uncovered_ranges(len(block['text']), covered.get(block['block_id'], [])):
            if block['text'][start:end].strip():
                gaps.append({'block_id': block['block_id'], 'start': start, 'end': end,
                             'quote': block['text'][start:end]})
    if gaps:
        findings.append({'annotation_id': None, 'code': 'annotation_source_unaccounted'})
    return {'entries': checked, 'findings': findings, 'unaccounted_ranges': gaps,
            'source_assessments': deepcopy(assessments)}
