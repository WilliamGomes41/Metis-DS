"""Read-only access to existing formation, source and Admission owners.

No problem status is persisted here. Closure remains a source/review decision;
the stable identifier is only a link, never permission to close a finding.
"""
from copy import deepcopy
from urllib.parse import urlencode

from src.semantic_replay_v1 import stable_json_hash
from src.recoverable_formation_v1 import unresolved_rejections, pending_rejections
from src.source_accountability_v1 import is_source_record
from src.source_containers_v1 import source_accountability
from src.admission_gate_v1 import is_admission_blocked
from src.blockage_diagnostics_v1 import explain
from src.knowledge_path_v1 import spans_are_exact


def _url(path, sid, **query):
    return path + '?' + urlencode({'document': sid, **query})


def _source_excerpt(spans, blocks):
    """Display only literal, bounded slices of the verified stored source."""
    if not spans_are_exact(spans):
        return None
    located = []
    for span in spans:
        found = blocks.get(span['block_id'])
        if not found or not 0 <= span['start'] < span['end'] <= len(found[1]['text']):
            return None
        located.append((found[0], span['start'], span, found[1]))
    located.sort(key=lambda row: row[:2])
    quotes, headings = [], []
    for _, _, span, block in located:
        literal = block['text'][span['start']:span['end']]
        quotes.append({'text': literal[:480], 'truncated': len(literal) > 480})
        heading = block.get('heading') or next(reversed(block.get('section_path') or []), '')
        if heading and heading not in headings:
            headings.append(heading)
    return {'quotes': quotes, 'location': ' · '.join(headings), 'order': list(located[0][:2])}


def collect(console, *, actor_id, snapshot_id):
    from src.source_selection_v1 import authorize
    from src.source_preparation_context_v1 import stored_extraction
    from src.beslisboom_path_v1 import review_path_for_klasse
    envelope = console._envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    objects = console._read_current_objects(snapshot_id)
    bindings = console.object_review_bindings(snapshot_id, objects=objects)
    fragments = stored_extraction(envelope)
    from src.semantic_passage_v1 import semantic_source_blocks
    source_blocks = {block['block_id']: (index, block)
                     for index, block in enumerate(semantic_source_blocks(fragments or []))}
    # Share this request's already verified immutable input with the existing
    # status projection; do not reconstruct the same source a second time.
    processing = console.processing_status(snapshot_id, actor_id=actor_id,
        formation_fragments=fragments if fragments is not None else ())
    replay = envelope.get('semantic_replay') or {}
    pending = unresolved_rejections(envelope, objects=objects, bindings=bindings, fragments=fragments)
    latest = next(reversed(envelope.get('processing_attempts') or []), {})
    reference = (latest.get('diagnostic') or {}).get('validator_input_ref')
    semantic_identity = replay.get('identity') or (latest.get('diagnostic') or {}).get('semantic_identity') or {}

    if not replay and reference:
        # Pre-activation failures also remain visible. Read the verified current
        # result set and its existing observations, not only the last attempt's
        # successful calls. Never promote diagnostics to candidates.
        from src.workflows.formation_task_store_v1 import FormationTaskStore
        from src.bounded_formation_v1 import _merge_task_proposals, _durable_targets
        store = FormationTaskStore(console.workflow_document_store)
        data = store.resolve_input(reference, expected_snapshot_id=snapshot_id)
        blocks = semantic_source_blocks(data['fragments'])
        results = store.task_results(reference['context_id'])
        proposal = _merge_task_proposals([row['proposal'] for row in results])
        calls = []
        for attempt in envelope.get('processing_attempts') or []:
            if (attempt.get('diagnostic') or {}).get('validator_input_ref') == reference:
                evidence = store.diagnostic(attempt).get('provider_evidence') or {}
                calls.extend([evidence, *evidence.get('supplementary_calls', [])])
        # Provisional task results are not joint closure evidence. Only an
        # activated replay or the exact human-closure operation can close them.
        pending = pending_rejections({'task_policy': 'bounded-formation-v1', 'supplementary_calls': calls},
                                     {'objects': [], 'source_assessments': []}, blocks=blocks)
        diagnostic = store.diagnostic(latest)
        if diagnostic.get('finding'):
            pending.append({'kind': 'joint', 'reason_code': diagnostic['finding'].get('reason_code') or 'source_formation_incomplete',
                            'spans': diagnostic.get('repair_target_spans') or []})
        # Includes unstarted tasks and source gaps, even when a process died
        # before it could record a rejection checkpoint for them.
        pending.extend({'kind': 'source', 'reason_code': 'source_formation_incomplete',
                        'spans': [row['span']]} for row in _durable_targets(blocks, proposal))

    if (latest.get('state') in {'failed', 'interrupted', 'incomplete_budget'}
            and (not replay or processing.get('formation_incomplete'))):
        pending.append({'kind': 'attempt', 'reason_code': latest.get('validation_code') or
                        latest.get('error_code') or 'source_formation_incomplete', 'spans': []})
        for finding in (latest.get('diagnostic') or {}).get('page_findings') or []:
            for reason in finding.get('reasons') or []:
                pending.append({'kind': 'page', 'reason_code': reason, 'spans': [], 'page': finding.get('page')})

    usage = source_accountability(objects, review_path=review_path_for_klasse(envelope['class']),
                                  bindings=bindings, fragments=fragments)
    problems = {}
    def add(kind, reason, spans=(), obj=None, page=None):
        spans = spans if spans_are_exact(spans) else []
        spans = sorted(deepcopy(list(spans)), key=lambda row: (
            str(row.get('block_id')), row.get('start', 0), row.get('end', 0)))
        oid = obj.get('object_id') if obj else None
        identity = {'snapshot_id': snapshot_id, 'source_hash': envelope['sha256'],
                    'semantic_identity': semantic_identity.get('hash'), 'kind': kind,
                    'reason': reason, 'spans': spans, 'object_id': oid, 'page': page}
        pid = stable_json_hash(identity)
        actions = []
        if obj:
            actions.append({'label': 'Brongebruik bepalen of herstellen' if is_source_record(obj) else 'Kandidaat herstellen',
                'url': _url('/source-selection', snapshot_id, object=oid,
                            task='disposition' if is_source_record(obj) else 'repair')})
        else:
            # Source dispositions use the current materialised source register,
            # not a human-review task manufactured from a provider rejection.
            for source in objects:
                source_spans = ((source.get('metadata') or {}).get('semantic_passage') or {}).get('spans') or []
                if is_source_record(source) and any(a.get('block_id') == b.get('block_id')
                    and max(a.get('start', 0), b.get('start', 0)) < min(a.get('end', 0), b.get('end', 0))
                    for a in spans for b in source_spans):
                    actions.append({'label': 'Bronbereik bekijken en behandelen',
                        'url': _url('/source-selection', snapshot_id, object=source['object_id'], task='disposition')})
        if page is not None:
            actions.append({'label': 'Pagina-afhandeling in Vorming',
                            'url': _url('/source-selection', snapshot_id) + '#paginas'})
        elif reason == 'processing_attempt_limit_reached':
            actions.append({'label': 'Herstelvoorwaarden in Vorming',
                            'url': _url('/source-selection', snapshot_id) + '#processing-recovery'})
        actions.append({'label': 'Diagnose en herstelvoorwaarden', 'url': _url('/inzicht/document', snapshot_id)})
        problems[pid] = {'problem_id': pid, 'kind': kind, **explain(reason), 'spans': spans,
                         'object_id': oid, 'page': page, 'actions': actions,
                         'source_excerpt': _source_excerpt(spans, source_blocks)}

    for row in pending:
        add(row.get('kind') or 'formation', row.get('reason_code') or 'source_formation_incomplete', row.get('spans') or [], page=row.get('page'))
    for obj in objects:
        spans = ((obj.get('metadata') or {}).get('semantic_passage') or {}).get('spans') or []
        if is_source_record(obj):
            current = usage.get(obj['object_id']) or {}
            if current.get('closure') in {'open', 'repair_required'}:
                add('source', current.get('reason') or 'source_formation_incomplete', spans, obj)
        elif is_admission_blocked(obj):
            for reason in (obj.get('metadata') or {}).get('admission', {}).get('reason_codes') or ['candidate_admission_blocked']:
                add('admission', reason, spans, obj)

    return {'snapshot_id': snapshot_id, 'title': envelope['title'], 'version': envelope['version'],
            'source_hash': envelope['sha256'], 'processing': processing,
            'problems': sorted(problems.values(), key=lambda row: (row['kind'], row['problem_id']))}
