"""Regression for graph evidence/canonical coherence and source-bound unit repair.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: beschikbaarheid
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.admission_gate_v1 import admission_of
from src.decision_graph_v1 import read_active_graph
from src.decision_unit_construction_v1 import KEY, unit_issues
from src.durable_publication_console_v1 import DurablePublicationConsole
from src.operations_console_v1 import ConsoleError
from tests.test_decision_unit_construction import pdf_data, ingest, complete_graph
from tests.test_decision_graph_chain import _console, _accounts, command
from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, MemorySourceStore


class GraphStore(MemoryCanonicalStore):
    def release_for_snapshot(self, sid):
        release = super().release_for_snapshot(sid)
        if release:
            release['decision_graph_release'] = deepcopy(self.releases[release['release_id']]['decision_graph_release'])
        return release


def finish(console, accounts, sid):
    console.update_decision_graph(**command(console, accounts, sid, 'graph', graph=complete_graph(console, sid)))
    for obj in console.snapshot_objects(sid):
        if obj['object_type'] != 'document' and obj['content']['clean_text'] not in {'Ja', 'Nee'}:
            console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                                  object_id=obj['object_id'], decision='approve', confirmed_object_type='node')
    console.update_decision_graph(**command(console, accounts, sid, 'endpoints', graph=complete_graph(console, sid)))
    console.confirm_decision_graph(**command(console, accounts, sid, 'confirm'))


def test_constructed_labels_publish_read_restart(tmp_path):
    store, source = GraphStore(), MemorySourceStore()
    def state():
        return DurablePublicationConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime',
                                         canonical_publication_store=store, immutable_source_store=source)
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    finish(console, accounts, sid)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS'
    payload = read_active_graph(store, source, sid)
    assert len(payload['graph']['edges']) == 2
    assert len(payload['objects']) == 6  # graph retains document + all source units
    assert len(store.active_publication_rows()) == 3  # labels are evidence, not knowledge
    restarted = state()
    restarted.reconcile_durable_publications()
    assert read_active_graph(store, source, sid) == payload


def repair_setup(tmp_path):
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data(['Is er sprake van een', 'Mantelzorger?']))
    objects = console.snapshot_objects(sid)
    target = next(o for o in objects if o['content']['clean_text'] == 'Is er sprake van een')
    other = next(o for o in objects if o['content']['clean_text'] == 'Mantelzorger?')
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=target['object_id'], decision='revise', comment='Voeg letterlijke bron samen.')
    return console, accounts, sid, target, other


def patch(text):
    return {'reason':'Letterlijke broncorrectie', 'operations':[
        {'op':'set','path':'content.clean_text','value':text},
        {'op':'set','path':'content.raw_text','value':text}]}


def test_merge_rebuilds_fidelity_then_graph_review_readiness(tmp_path):
    console, accounts, sid, target, other = repair_setup(tmp_path)
    revised = console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=target['object_id'], patch=patch('Is er sprake van een\nMantelzorger?'),
        additional_source_fragments=other['provenance']['source_fragments'], expected_revision=console.objects_revision(sid))
    assert unit_issues(revised) == []
    assert revised['metadata'][KEY]['literal_hash'] != target['metadata'][KEY]['literal_hash']
    graph = complete_graph(console, sid)
    next(n for n in graph['nodes'] if n['object_id'] == other['object_id'])['mode'] = 'context'
    graph['nodes'] = [{**n, 'evidence_ids':[r['raw_object_id'] for r in revised['provenance']['source_fragments']]}
                      if n['object_id'] == revised['object_id'] else n for n in graph['nodes']]
    console.update_decision_graph(**command(console, accounts, sid, 'repaired-graph', graph=graph))
    current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == target['object_id'])
    assert admission_of(current)['gate_result'] == 'allowed'
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=current['object_id'], decision='approve', confirmed_object_type='node')
    assert unit_issues(next(o for o in _console(tmp_path).snapshot_objects(sid) if o['object_id'] == target['object_id'])) == []


@pytest.fixture(params=["file", "postgres"])
def structured_repair_state(request, tmp_path):
    if request.param == "postgres":
        from tests.decision_graph_native_support import native_state
        state, _store, _source = native_state(tmp_path)
        return state
    from src.review_closure_v1 import ReviewClosureConsole
    return lambda node="default": ReviewClosureConsole(root=tmp_path,
        source_store=tmp_path/"sources", runtime=tmp_path/"runtime")


@pytest.mark.parametrize('later_primary', [False, True])
def test_native_merge_resolution_preserves_immutable_source_order(tmp_path, later_primary, structured_repair_state):
    from src.deterministic_review_repair_v1 import REPAIR_MERGE_OBJECTS
    state = structured_repair_state
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data(['Is er sprake van een', 'Mantelzorger?']))
    objects = console.snapshot_objects(sid)
    first = next(o for o in objects if o['content']['clean_text'] == 'Is er sprake van een')
    second = next(o for o in objects if o['content']['clean_text'] == 'Mantelzorger?')
    primary, absorbed = (second, first) if later_primary else (first, second)
    revised = console.submit_review_resolution(
        actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=primary['object_id'], expected_revision=console.objects_revision(sid),
        suitability='samenvoegen', comment='Samenvoegen in bronvolgorde.',
        repair_kind=REPAIR_MERGE_OBJECTS, merge_object_ids=[absorbed['object_id']])
    assert revised['content']['clean_text'] == 'Is er sprake van een\nMantelzorger?'
    assert unit_issues(revised) == []
    assert [r['raw_object_id'] for r in revised['provenance']['source_fragments']] == [
        first['provenance']['source_fragments'][0]['raw_object_id'],
        second['provenance']['source_fragments'][0]['raw_object_id']]
    restarted = state('source-order-restart')
    assert unit_issues(restarted._current_object(sid, primary['object_id'])) == []
    assert restarted._current_object(sid, absorbed['object_id'])['governance']['validation_status'] == 'superseded'


def test_merge_rejects_text_in_reversed_source_order(tmp_path):
    console, accounts, sid, first, second = repair_setup(tmp_path)
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=second['object_id'], decision='revise', comment='Samenvoegen uit bron.')
    before = deepcopy(console.snapshot_objects(sid))
    with pytest.raises(ConsoleError, match='source_fidelity'):
        console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
            object_id=second['object_id'], patch=patch('Mantelzorger? Is er sprake van een'),
            additional_source_fragments=first['provenance']['source_fragments'])
    assert console.snapshot_objects(sid) == before


def test_unchanged_grouped_selection_retains_verified_layout_order(tmp_path):
    import fitz
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 45, 235, 150))
        page.insert_text((75, 88), 'mantelzorger?', fontsize=11)
        page.insert_text((75, 70), 'Is er sprake van een', fontsize=11)
        data = doc.tobytes()
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, data)
    target = next(o for o in console.snapshot_objects(sid) if o['object_type'] != 'document')
    assert target['content']['clean_text'] == 'Is er sprake van een\nmantelzorger?'
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=target['object_id'], decision='revise', comment='Controleer bron.')
    revised = console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=target['object_id'], patch=patch(target['content']['clean_text']))
    assert unit_issues(revised) == []
    assert revised['provenance']['source_fragments'] == target['provenance']['source_fragments']


@pytest.mark.parametrize('tamper', ['literal', 'span', 'locator', 'mode', 'review', 'markerless'])
def test_released_label_tampering_is_not_a_canonical_exemption(tmp_path, tamper):
    store, source = GraphStore(), MemorySourceStore()
    console = DurablePublicationConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime',
                                        canonical_publication_store=store, immutable_source_store=source)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    finish(console, accounts, sid)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    payload = store.releases[result['release_id']]['decision_graph_release']
    label = next(o for o in payload['objects'] if o['content']['clean_text'] == 'Ja')
    if tamper == 'literal':
        label['content']['clean_text'] = 'Nee'
    elif tamper == 'span':
        label['metadata'][KEY]['spans'][0]['end'] += 1
    elif tamper == 'locator':
        label['provenance']['source_fragments'][0]['source_locator'] = {}
    elif tamper == 'mode':
        next(n for n in payload['graph']['nodes'] if n['object_id'] == label['object_id'])['mode'] = 'terminal'
    elif tamper == 'review':
        payload['reviews'] = []
    else:
        label['metadata'].pop(KEY)
    with pytest.raises(ValueError, match='decision_graph_release_invalid|decision_graph_release_mismatch'):
        read_active_graph(store, source, sid)


@pytest.mark.parametrize('bad', ['nonliteral', 'unknown', 'hash', 'locator', 'stale'])
def test_invalid_source_correction_leaves_durable_work_unchanged(tmp_path, bad):
    console, accounts, sid, target, other = repair_setup(tmp_path)
    before = deepcopy(console.snapshot_objects(sid))
    revision = console.objects_revision(sid)
    refs = deepcopy(other['provenance']['source_fragments'])
    text = 'Is er sprake van een\nMantelzorger?'
    if bad == 'nonliteral':
        text += ' Verwijs altijd.'
    elif bad == 'unknown':
        refs[0]['raw_object_id'] = 'unknown-source'
    elif bad == 'hash':
        refs[0]['raw_content_hash'] = '0'*64
    elif bad == 'locator':
        refs[0]['source_locator']['locator_value'] = 'changed-locator'
    with pytest.raises(ConsoleError, match='source_fidelity|snapshot_object_write_conflict'):
        console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
            object_id=target['object_id'], patch=patch(text), additional_source_fragments=refs,
            expected_revision='stale' if bad == 'stale' else revision)
    assert console.snapshot_objects(sid) == before
    assert _console(tmp_path).snapshot_objects(sid) == before


def test_single_literal_selection_rebuilds_spans_and_rejects_stale_evidence(tmp_path):
    from src.decision_graph_v1 import pdf_fragments
    from src.decision_unit_construction_v1 import rebuild_for_revision, reconstruct
    console = _console(tmp_path)
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    target = next(o for o in console.snapshot_objects(sid) if o['content']['clean_text'] == 'Bespreek de situatie.')
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=target['object_id'], decision='revise', comment='Bronselectie verkorten.')
    revised = console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                                     object_id=target['object_id'], patch=patch('Bespreek'))
    path, _ = console._verified_source_bytes(console._envelope(sid))
    env = console._envelope(sid)
    fragments = pdf_fragments(path, document_id=env['document_id'], source_id=env['source_id'])
    assert reconstruct(revised['metadata'][KEY], fragments) == 'Bespreek'
    assert unit_issues(revised) == []
    broken = deepcopy(revised)
    broken['metadata'][KEY]['spans'][0]['end'] = 10000
    with pytest.raises(ValueError, match='decision_unit_source_fidelity_failure'):
        rebuild_for_revision(broken, deepcopy(revised), fragments)


def test_merge_failed_commit_and_duplicate_preserve_revision_contract(tmp_path, monkeypatch):
    console, accounts, sid, target, other = repair_setup(tmp_path)
    before = deepcopy(console.snapshot_objects(sid))
    revision = console.objects_revision(sid)
    kwargs = dict(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                  object_id=target['object_id'], patch=patch('Is er sprake van een Mantelzorger?'),
                  additional_source_fragments=other['provenance']['source_fragments'], expected_revision=revision)
    commit = console._commit_prepared_store
    def fail(**_):
        raise OSError('injected_precommit')
    monkeypatch.setattr(console, '_commit_prepared_store', fail)
    with pytest.raises(OSError, match='injected_precommit'):
        console.correct_object(**kwargs)
    assert _console(tmp_path).snapshot_objects(sid) == before
    monkeypatch.setattr(console, '_commit_prepared_store', commit)
    revised = console.correct_object(**kwargs)
    assert revised['content']['clean_text'] == 'Is er sprake van een\nMantelzorger?'
    with pytest.raises(ConsoleError, match='snapshot_object_write_conflict'):
        console.correct_object(**kwargs)
    assert len([o for o in console._load_objects(sid) if o['object_id'] == target['object_id']
                and o['object_version'] == revised['object_version']]) == 1


def test_native_constructed_graph_release_and_corrected_unit_restart(tmp_path, monkeypatch):
    from tests.decision_graph_native_support import native_state
    state, store, source = native_state(tmp_path)
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts, pdf_data())
    finish(console, accounts, sid)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS'
    payload = read_active_graph(store, source, sid)
    restarted = state('restarted')
    restarted.reconcile_durable_publications()
    assert read_active_graph(store, source, sid) == payload
    # Existing durable correction transaction retains rebuilt evidence.
    repair_sid = ingest(restarted, accounts, pdf_data(['Is er sprake van een', 'Mantelzorger?']))
    objects = restarted.snapshot_objects(repair_sid)
    target = next(o for o in objects if o['content']['clean_text'] == 'Is er sprake van een')
    other = next(o for o in objects if o['content']['clean_text'] == 'Mantelzorger?')
    restarted.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=repair_sid,
                            object_id=target['object_id'], decision='revise', comment='Samenvoegen uit bron.')
    before = deepcopy(restarted.snapshot_objects(repair_sid))
    correction = dict(actor_id=accounts['researcher']['account_id'], snapshot_id=repair_sid,
        object_id=target['object_id'], patch=patch('Is er sprake van een\nMantelzorger?'),
        additional_source_fragments=other['provenance']['source_fragments'])
    commit = restarted._commit_prepared_store
    def fail_after_sql_writes(**kwargs):
        commit(**kwargs)
        raise RuntimeError('injected_after_sql_writes')
    monkeypatch.setattr(restarted, '_commit_prepared_store', fail_after_sql_writes)
    with pytest.raises(RuntimeError, match='injected_after_sql_writes'):
        restarted.correct_object(**correction)
    assert state('after-rollback').snapshot_objects(repair_sid) == before
    monkeypatch.setattr(restarted, '_commit_prepared_store', commit)
    revised = restarted.correct_object(**correction)
    after = next(o for o in state('after-correction').snapshot_objects(repair_sid) if o['object_id'] == target['object_id'])
    assert after == json.loads(json.dumps(revised))
    assert unit_issues(after) == []


def test_overlapping_literal_selection_is_ambiguous():
    from src.decision_unit_construction_v1 import record, rebuild_for_revision
    from src.integrity_kernel import stable_hash
    fragment = {'fragment_id':'repeat', 'clean_text':'Ja Ja Ja', 'fragment_hash':stable_hash('source'),
                'source_locator':{'locator_type':'page_bbox','locator_value':'p1'}}
    original = {'content':{'clean_text':'Ja Ja Ja'}, 'metadata':{KEY:record([fragment])},
                'provenance':{'source_fragments':[{'raw_object_id':'repeat',
                    'raw_content_hash':fragment['fragment_hash'], 'source_locator':fragment['source_locator']}]}}
    revised = deepcopy(original)
    revised['content']['clean_text'] = 'Ja Ja'
    with pytest.raises(ValueError, match='decision_unit_source_fidelity_failure'):
        rebuild_for_revision(original, revised, [fragment])


def test_markerless_correction_keeps_legacy_contract(tmp_path, monkeypatch):
    from src.beslisboom_path_v1 import boom_spec_from_fragments
    from src.decision_graph_v1 import pdf_fragments
    console = _console(tmp_path)
    accounts = _accounts(console)
    def legacy(kind, path, **kwargs):
        fragments = pdf_fragments(path, document_id=kwargs['document_id'], source_id=kwargs['source_id'], construct_units=False)
        return fragments, boom_spec_from_fragments(document_id=kwargs['document_id'], title=kwargs['title'],
            family=kwargs['family'], class_=kwargs['class_'], fragments=fragments)
    monkeypatch.setattr(console, '_fragments_and_spec', legacy)
    sid = ingest(console, accounts, pdf_data())
    target = next(o for o in console.snapshot_objects(sid) if o['content']['clean_text'].startswith('Bespreek de situatie.'))
    assert KEY not in target.get('metadata', {})
    console.review_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                          object_id=target['object_id'], decision='revise', comment='Legacy broncorrectie.')
    revised = console.correct_object(actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
                                     object_id=target['object_id'], patch=patch('Bespreek'))
    assert KEY not in revised.get('metadata', {})
    assert revised['content']['clean_text'] == 'Bespreek'


def test_native_interleaved_repeated_text_merge_preserves_kernel_proof(tmp_path, monkeypatch, structured_repair_state):
    """Equal literal text must not hide reordered provenance during finalization."""
    import fitz
    from src.deterministic_review_repair_v1 import REPAIR_MERGE_OBJECTS
    state = structured_repair_state
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 45, 235, 150))
        page.insert_text((75, 70), 'van een', fontsize=11)
        page.insert_text((295, 250), 'van een', fontsize=11)
        page.insert_text((75, 88), 'van een', fontsize=11)
        data = doc.tobytes()
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts, data)
    units = [o for o in console.snapshot_objects(sid) if o['object_type'] != 'document']
    primary = next(o for o in units if len(o['provenance']['source_fragments']) == 2)
    absorbed = next(o for o in units if len(o['provenance']['source_fragments']) == 1)
    assert primary['content']['clean_text'] == 'van een\nvan een'
    from src.decision_graph_v1 import pdf_fragments
    envelope = console._envelope(sid)
    source_path, _ = console._verified_source_bytes(envelope)
    immutable_fragments = pdf_fragments(source_path, document_id=envelope['document_id'],
                                       source_id=envelope['source_id'])
    source_positions = {f['fragment_id']: index for index, f in enumerate(immutable_fragments)}
    blocks = [[ref['raw_object_id'] for ref in obj['provenance']['source_fragments']]
              for obj in (primary, absorbed)]
    blocks.sort(key=lambda ids: min(source_positions[fid] for fid in ids))
    expected_ids = [fid for block in blocks for fid in block]
    revised = console.submit_review_resolution(
        actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=primary['object_id'], expected_revision=console.objects_revision(sid),
        suitability='samenvoegen', comment='Letterlijke fragmenten samenvoegen.',
        repair_kind=REPAIR_MERGE_OBJECTS, merge_object_ids=[absorbed['object_id']])
    assert revised['content']['clean_text'] == 'van een\nvan een\nvan een'
    assert [r['raw_object_id'] for r in revised['provenance']['source_fragments']] == expected_ids
    assert [s['fragment_id'] for s in revised['metadata'][KEY]['spans']] == expected_ids
    # The fragment remains incomplete; successful repair must not invent completeness.
    assert unit_issues(revised) == ['decision_unit_incomplete']
    # Exercise the finalization boundary independently of the planner's ordering.
    # Previously this overwrote verified refs, leaving them inconsistent with spans.
    revised = console._finalize_source_provenance(
        snapshot_id=sid, object_id=primary['object_id'],
        source_refs=list(reversed(deepcopy(revised['provenance']['source_fragments']))),
        repair_spec={'repair_kind': REPAIR_MERGE_OBJECTS,
                     'merge_object_ids': [absorbed['object_id']],
                     'merged_text': revised['content']['clean_text']})
    assert [r['raw_object_id'] for r in revised['provenance']['source_fragments']] == expected_ids
    assert unit_issues(revised) == ['decision_unit_incomplete']
    from src.decision_unit_construction_v1 import finalized_source_refs
    malformed = deepcopy(revised)
    malformed['metadata'][KEY]['contract'] = 'invalid-contract'
    with pytest.raises(ValueError, match='decision_unit_source_fidelity_failure'):
        finalized_source_refs(malformed, revised['provenance']['source_fragments'])
    before = deepcopy(console.snapshot_objects(sid))
    revision_before = console.objects_revision(sid)
    for mutation in ('duplicate', 'missing', 'hash', 'locator'):
        invalid_refs = deepcopy(revised['provenance']['source_fragments'])
        if mutation == 'duplicate':
            invalid_refs[1] = deepcopy(invalid_refs[0])
        elif mutation == 'missing':
            invalid_refs.pop()
        elif mutation == 'hash':
            invalid_refs[0]['raw_content_hash'] = '0' * 64
        else:
            invalid_refs[0]['source_locator']['locator_value'] = 'invalid-source-locator'
        with pytest.raises(ConsoleError, match='decision_unit_source_fidelity_failure'):
            console._finalize_source_provenance(
                snapshot_id=sid, object_id=primary['object_id'], source_refs=invalid_refs,
                repair_spec={'repair_kind': REPAIR_MERGE_OBJECTS})
        assert console.snapshot_objects(sid) == before
        assert console.objects_revision(sid) == revision_before
    from src.deterministic_review_repair_v1 import DeterministicRepairReviewConsole
    load = console._load_objects
    for field in ('end', 'fragment_text_hash', 'text_sha256', 'separator', 'parent'):
        def corrupted_rows(*args, **kwargs):
            rows = deepcopy(load(*args, **kwargs))
            row = next(r for r in reversed(rows) if r['object_id'] == primary['object_id'])
            proof = row['metadata'][KEY]
            if field == 'separator':
                proof[field] = ' '
            elif field == 'end':
                proof['spans'][0][field] += 1
            elif field == 'parent':
                proof['spans'][0][field] = {'fragment_id': 'forged-parent'}
            else:
                proof['spans'][0][field] = '0' * 64
            return rows
        with monkeypatch.context() as context:
            context.setattr(console, '_load_objects', corrupted_rows)
            for finalize in (console._finalize_source_provenance,
                             lambda **kw: DeterministicRepairReviewConsole._finalize_source_provenance(console, **kw)):
                with pytest.raises(ConsoleError, match='source_fidelity|evidence_invalid'):
                    finalize(snapshot_id=sid, object_id=primary['object_id'],
                             source_refs=revised['provenance']['source_fragments'],
                             repair_spec={'repair_kind': REPAIR_MERGE_OBJECTS})
        assert console.snapshot_objects(sid) == before
        assert console.objects_revision(sid) == revision_before
    restarted = state('interleaved-merge-restart')
    assert restarted._current_object(sid, primary['object_id']) == revised
    assert restarted._current_object(sid, absorbed['object_id'])['governance']['validation_status'] == 'superseded'


@pytest.mark.parametrize('action_primary', [False, True])
def test_native_reverse_insertion_group_extension_preserves_verified_unit_order(tmp_path, action_primary, structured_repair_state):
    import fitz
    from src.deterministic_review_repair_v1 import REPAIR_MERGE_OBJECTS
    state = structured_repair_state
    with fitz.open() as doc:
        page = doc.new_page()
        page.draw_rect(fitz.Rect(60, 45, 235, 150))
        page.insert_text((75, 88), 'mantelzorger?', fontsize=11)
        page.insert_text((75, 70), 'Is er sprake van een', fontsize=11)
        page.insert_text((75, 250), 'Bespreek de situatie.', fontsize=11)
        data = doc.tobytes()
    console = state()
    accounts = _accounts(console)
    sid = ingest(console, accounts, data)
    units = [o for o in console.snapshot_objects(sid) if o['object_type'] != 'document']
    question = next(o for o in units if o['content']['clean_text'].startswith('Is er sprake'))
    action = next(o for o in units if o['content']['clean_text'] == 'Bespreek de situatie.')
    primary, absorbed = (action, question) if action_primary else (question, action)
    expected_ids = [r['raw_object_id'] for obj in (question, action)
                    for r in obj['provenance']['source_fragments']]
    revised = console.submit_review_resolution(
        actor_id=accounts['researcher']['account_id'], snapshot_id=sid,
        object_id=primary['object_id'], expected_revision=console.objects_revision(sid),
        suitability='samenvoegen', comment='Gecontroleerde bronunits samenvoegen.',
        repair_kind=REPAIR_MERGE_OBJECTS, merge_object_ids=[absorbed['object_id']])
    assert revised['content']['clean_text'] == 'Is er sprake van een\nmantelzorger?\nBespreek de situatie.'
    assert unit_issues(revised) == []
    assert [r['raw_object_id'] for r in revised['provenance']['source_fragments']] == expected_ids
    assert [s['fragment_id'] for s in revised['metadata'][KEY]['spans']] == expected_ids
    restarted = state('group-extension-restart')
    assert restarted._current_object(sid, primary['object_id']) == revised
    assert restarted._current_object(sid, absorbed['object_id'])['governance']['validation_status'] == 'superseded'
