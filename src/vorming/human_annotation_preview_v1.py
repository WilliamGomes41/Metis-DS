"""Inspect immutable human input before sealing; never create candidates.

Findings name the original annotation or exact unaccounted source range. This
is an input check, not Admission, source-role confirmation or review approval.
The build still has to validate the sole materialiser's actual output.
"""
from copy import deepcopy
import json

from src.integrity_kernel import stable_hash
from src.vorming.admission_gate_v1 import literal_field_codes
from src.vorming.human_annotation_projection_v1 import bind_context, bind_fields
from src.vorming.human_annotation_v1 import historical_finding, validate_historical_display, validate_stored_selection
from src.vorming.knowledge_materialisation_v1 import resolve_source_selection
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.source_accountability_v1 import ROLES, uncovered_ranges, validate_assessments
from src.vorming.source_bound_fields_v3 import TYPE_FIELDS, VIA_RELATION


def _span(anchor):
    return {key: anchor[key] for key in ('block_id', 'start', 'end')}


def source_range_key(span):
    return json.dumps([span['block_id'], span['start'], span['end']], separators=(',', ':'))


def source_work(inspection, blocks):
    """Project exact open ranges and conservative B6 proposals without accounting for them."""
    from src.review.source_context_review_v1 import GROUP_MAX
    from src.vorming.source_containers_v1 import accounting_reason

    roles = {reason: role for role in ('metadata', 'structure') for reason in ROLES[role]}
    by_id = {block['block_id']: block for block in blocks}
    ranges, grouped = [], {}
    for gap in inspection['unaccounted_ranges']:
        block = by_id[gap['block_id']]
        reason = None
        # A remnant detached from a mixed block can look like metadata by itself.
        if gap['quote'].strip() == block['text'].strip():
            reason = accounting_reason(gap['quote'], require_known_navigation=True)
        proposal = f'{roles[reason]}:{reason}' if reason in roles else None
        member = {**gap, 'key': source_range_key(gap), 'proposal': proposal}
        ranges.append(member)
        if proposal:
            section = tuple(block.get('section_path') or ())
            grouped.setdefault((section, proposal), []).append(member['key'])
    groups = []
    for (section, proposal), members in grouped.items():
        for start in range(0, len(members), GROUP_MAX):
            batch = members[start:start + GROUP_MAX]
            groups.append({'key': stable_hash([section, proposal, batch]), 'section': section,
                           'proposal': proposal, 'members': batch})
    return {'ranges': ranges, 'groups': groups}


def usable_annotation_semantics(payload, *, fragments):
    """#1067: Metis' direction/strength proposal as it may be built, or None.

    The worker never answers for it. A proposal that is incomplete, does not
    bind to the source or fails its contract is no proposal: the reviewer
    chooses. The stored annotation is not changed.
    """
    from src.vorming.recommendation_semantics_v1 import (
        complete_annotation_semantics, validate_recommendation_semantics)
    raw = payload.get('recommendation_semantics')
    if payload.get('object_type') != 'recommendation' or not complete_annotation_semantics(raw):
        return None
    from src.vorming.semantic_passage_v1 import _recommendation_semantics_from_proposal, semantic_source_blocks
    from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
    by_id = {block['block_id']: block for block in semantic_source_blocks(fragments)}
    selected = []
    for anchor in payload['ranges']:
        if anchor['role'] != 'core' or anchor['block_id'] not in by_id:
            continue
        block = by_id[anchor['block_id']]
        selected.append({
            **{key: anchor[key] for key in ('block_id', 'start', 'end')},
            'section_path': block['section_path'],
            'text': block['text'][anchor['start']:anchor['end']],
        })
    if not selected:
        return None
    try:
        semantics, _ = _recommendation_semantics_from_proposal(raw, proposed_type='recommendation', selected=selected,
            evidence_by_id=_read_source_blocks(fragments, include_headings=True))
    except (ValueError, KeyError, TypeError):
        return None
    if not semantics or validate_recommendation_semantics(semantics, confirmed=False):
        return None
    return semantics


def inspect_annotation(entry, *, fragments, require_ready=True, blocks=None, signals=None):
    """The same per-entry inspection for document sealing and the editor.

    Draft preflight omits only the workflow-status finding. Readiness validation
    is reused without saving or inferring missing answers. Cross-entry identity
    and document coverage remain exclusively in inspect_document.

    Returns the blocking codes. Missing sentence/type parts are signals under
    the admission owner's single policy; pass a list as ``signals`` to receive
    them. They never block readiness, sealing or admission.
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
                    if payload.get('recommendation_strength_label'):
                        from src.vorming.semantic_passage_v1 import annotation_strength_label
                        annotation_strength_label(payload, fragments=fragments)
                    semantics = usable_annotation_semantics(payload, fragments=fragments)
                    if semantics is None:
                        codes.append('recommendation_semantics_open')  # the reviewer decides (#1067)
                    else:
                        row['proposed_recommendation_semantics'] = semantics
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
    from src.vorming.admission_gate_v1 import split_human_signals
    blocking, found = split_human_signals(codes)
    if signals is not None:
        signals.extend(found)
    return blocking


def inspect_for_overview(entries, *, fragments, confirmed_headings=(), allow_unselected=False):
    """Preview historical heads without making them eligible for a new seal."""
    current, historical = [], []
    for entry in entries:
        code = historical_finding(entry['payload'])
        if code is None:
            current.append(entry)
            continue
        if stable_hash(entry['payload']) != entry['payload_hash']:
            raise ValueError('annotation_integrity_failed')
        validate_historical_display(entry['payload'], fragments=fragments, annotation_id=entry['annotation_id'])
        historical.append((entry, code))

    result = inspect_document(current, fragments=fragments, confirmed_headings=confirmed_headings,
                              allow_unselected=allow_unselected)
    if historical:
        # Coverage of the current subset cannot establish gaps in this document.
        result['findings'] = [f for f in result['findings'] if f['code'] != 'annotation_source_unaccounted']
        result['unaccounted_ranges'] = []
        for entry, code in historical:
            result['entries'].append({'annotation_id': entry['annotation_id'], 'revision': entry['revision'], 'codes':[code]})
            result['findings'].append({'annotation_id': entry['annotation_id'], 'code': code})
    return result


from src.vorming.source_reconstruction_v1 import with_reconstruction_cache


@with_reconstruction_cache
def inspect_document(entries, *, fragments, confirmed_headings=(), allow_unselected=False):
    """Accept stored {annotation_id,revision,payload,payload_hash} entries.

    Duplicate core identities are refused without merging. Shared context and
    equal words at different source locations do not collide. This inspection
    alone never authorizes object activation.
    """
    from src.vorming.prepared_source_views_v1 import freeze_extraction
    fragments = freeze_extraction(fragments)
    blocks = semantic_source_blocks(fragments)
    findings, checked, selected, assessments, covered = [], [], [], [], {}
    strength_labels = {}
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
        signals = []
        codes = inspect_annotation(entry, fragments=fragments, blocks=blocks, signals=signals)
        if payload['status'] == 'withdrawn':
            checked.append({'annotation_id': annotation_id, 'revision': entry['revision'], 'codes': []})
            continue
        core = [_span(anchor) for anchor in payload['ranges'] if anchor['role'] == 'core']
        disposition = payload.get('disposition')
        owners = core_owners.get(tuple((a['block_id'], a['start'], a['end']) for a in core), [])
        if disposition is None and len(owners) > 1:
            # Keep the established document finding order.
            index = sum(code in {'annotation_not_ready','annotation_pending_range'} for code in codes)
            codes.insert(index, 'annotation_core_duplicate')
        elif disposition is not None and payload['status'] == 'ready':
            assessments.extend({'span': span, **disposition} for span in core)
        codes = list(dict.fromkeys(codes))
        checked.append({'annotation_id': annotation_id, 'revision': entry['revision'], 'codes': codes,
                        **({'signals': signals} if signals else {})})
        for code in codes:
            finding = {'annotation_id': annotation_id, 'code': code}
            if code == 'annotation_core_duplicate':
                finding['related_annotation_ids'] = [owner for owner in owners if owner != annotation_id]
            findings.append(finding)
        if not codes and disposition is None:
            selected.append({'spans': core})
            for anchor in payload['ranges']:
                covered.setdefault(anchor['block_id'], []).append((anchor['start'], anchor['end']))
            if payload.get('object_type') == 'recommendation':
                from src.vorming.semantic_passage_v1 import annotation_strength_label
                label = annotation_strength_label(payload, fragments=fragments)
                if label:
                    strength_labels[annotation_id] = label
                    anchor = label['label']
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
    for block in () if allow_unselected else blocks:
        if block['block_id'] in confirmed_headings:
            continue
        for start, end in uncovered_ranges(len(block['text']), covered.get(block['block_id'], [])):
            if block['text'][start:end].strip():
                gaps.append({'block_id': block['block_id'], 'start': start, 'end': end,
                             'quote': block['text'][start:end]})
    if gaps:
        findings.append({'annotation_id': None, 'code': 'annotation_source_unaccounted'})
    return {'entries': checked, 'findings': findings, 'unaccounted_ranges': gaps,
            'source_assessments': deepcopy(assessments), 'strength_labels': strength_labels}
