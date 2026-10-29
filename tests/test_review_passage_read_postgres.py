"""Passage GET owns only its required objects; commands keep current authority.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.test_review_render_source_reuse import review_client  # noqa: F401
import pytest


def test_incomplete_passage_prepares_the_complete_source_once(tmp_path, production_console, monkeypatch):
    """A bounded passage must not replace the full source used for closure."""
    from copy import deepcopy
    from fastapi.testclient import TestClient
    from src.operations_console_v1 import ConsoleError
    import src.vorming.knowledge_materialisation_v1 as materialisation
    import src.vorming.prepared_source_views_v1 as prepared
    from src.vorming.prepared_source_views_v1 import SourceFragments
    from src.vorming.source_preparation_context_v1 import stored_extraction
    from tests.test_review_formation_problems import received, execute
    from tests.test_availability_repair import login

    console, sid, author, _, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'passage-full-formation')
    objects = console.snapshot_objects(sid)
    obj = next(o for o in objects if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    before = (deepcopy(objects), deepcopy(console._envelope(sid)),
              console.workflow_review_store.read_events(), console.workflow_review_store.read_bindings([sid]))
    full_source = stored_extraction(before[1])
    expected_status = console.processing_status(sid)
    assert expected_status['formation_incomplete']
    original_status = console.processing_status
    original_eq = materialisation._SourceNumber.__eq__
    original_prepare = prepared.prepare
    captured, comparisons, preparations = [], [], []

    def status(*args, **kwargs):
        result = original_status(*args, **kwargs)
        captured.append((kwargs.get('formation_fragments'), result))
        return result

    def compare(self, other):
        comparisons.append(1)
        return original_eq(self, other)

    def prepare(raw):
        preparations.append(1)
        return original_prepare(raw)

    with TestClient(console._metis_test_application) as client:
        login(client, 'reviewer')
        monkeypatch.setattr(console, 'processing_status', status)
        monkeypatch.setattr(materialisation._SourceNumber, '__eq__', compare)
        monkeypatch.setattr(prepared, 'prepare', prepare)
        page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    assert 'data-formation-incomplete' in page.text
    assert not comparisons, 'full source must not be compared again for each validation'
    assert len(preparations) == 1, 'an exact complete passage carrier should not be prepared twice'
    assert len(captured) == 1
    fragments, actual_status = captured[0]
    assert isinstance(fragments, SourceFragments)
    assert list(fragments) == full_source
    with pytest.raises(ConsoleError, match='source_views_carrier_immutable'):
        fragments[0]['clean_text'] = 'not permitted'
    assert actual_status == expected_status
    assert (console.snapshot_objects(sid), console._envelope(sid),
            console.workflow_review_store.read_events(), console.workflow_review_store.read_bindings([sid])) == before


@pytest.mark.parametrize('layout', ['legacy', 'prepared'])
@pytest.mark.parametrize('case', ['missing_extraction', 'corrupt_extraction', 'corrupt_replay',
                                'missing_source', 'partial_window', 'carrier_error'])
def test_incomplete_passage_keeps_existing_fail_closed_behavior(tmp_path, production_console, monkeypatch, case, layout):
    from copy import deepcopy
    from fastapi.testclient import TestClient
    from src.operations_console_v1 import ConsoleError
    from src.vorming.source_preparation_context_v1 import KEY, stored_extraction
    import src.vorming.prepared_source_views_v1 as prepared
    from tests.test_review_formation_problems import received, execute
    from tests.test_availability_repair import login

    console, sid, author, _, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'passage-fail-closed')
    store = console.workflow_document_store
    if layout == 'legacy':
        with store._connect() as con:
            con.execute('TRUNCATE workflow.source_read_roots CASCADE')
            con.execute('UPDATE workflow.documents SET review_source_ref=NULL')
    if case not in {'missing_source', 'partial_window', 'carrier_error'}:
        envelope = store.get_envelope(sid)
        if case == 'missing_extraction':
            del envelope[KEY]
        elif case == 'corrupt_extraction':
            envelope[KEY]['fragments_hash'] = 'corrupt'
        else:
            envelope['semantic_replay']['identity']['hash'] = 'corrupt'
        store.write_bundle(envelope=envelope)
    objects = console.snapshot_objects(sid)
    obj = next(o for o in objects if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    if case in {'partial_window', 'carrier_error'}:
        import src.vorming.source_reconstruction_v1 as reconstruction
        full_source = stored_extraction(store.get_envelope(sid))
        real_window = reconstruction.review_source_window
        window = real_window(full_source, [obj])
        assert 0 < len(window) < len(full_source)
        # Exercise the existing real window selector for the requested object;
        # the status check must still use the whole source outside this window.
        monkeypatch.setattr(reconstruction, 'review_source_window',
                            lambda fragments, _objects: real_window(fragments, [obj]))
    expected = console.processing_status(sid)
    assert expected['formation_incomplete']
    before = (deepcopy(store.get_envelope(sid)), deepcopy(objects),
              console.workflow_review_store.read_events(), console.workflow_review_store.read_bindings([sid]))
    results = []
    original_status = console.processing_status
    original_prepare = prepared.prepare
    calls = []

    def status(*args, **kwargs):
        result = original_status(*args, **kwargs)
        results.append((kwargs.get('formation_fragments'), result))
        return result

    def prepare(raw):
        calls.append(1)
        # The first call is the passage view; fail only the optional full view.
        if layout == 'legacy' and case == 'carrier_error' and len(calls) == 2:
            raise ConsoleError('source_views_integrity_failed')
        return original_prepare(raw)

    with TestClient(console._metis_test_application) as client:
        login(client, 'reviewer')
        monkeypatch.setattr(console, 'processing_status', status)
        monkeypatch.setattr(prepared, 'prepare', prepare)
        if layout == 'prepared':
            def no_rebuild(*args, **kwargs):
                raise AssertionError('Prepared partial formation may not reconstruct source')
            monkeypatch.setattr('src.vorming.source_reconstruction_v1._with_status', no_rebuild)
            if case == 'carrier_error':
                original_reader = console._prepared_review_source
                def unavailable_full(envelope, *, objects=None):
                    if objects is None:
                        raise ConsoleError('source_views_integrity_failed')
                    return original_reader(envelope, objects=objects)
                monkeypatch.setattr(console, '_prepared_review_source', unavailable_full)
        if case == 'missing_source':
            def missing(*args, **kwargs):
                raise ConsoleError('source_integrity_failed')
            monkeypatch.setattr(console, '_verified_source_bytes', missing)
        page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200 and 'data-formation-incomplete' in page.text
    assert len(results) == 1 and results[0][1] == expected
    if case == 'partial_window':
        assert list(results[0][0]) == full_source
        assert len(results[0][0]) > len(window)
    if case in {'partial_window', 'carrier_error'}:
        if layout == 'legacy':
            assert len(calls) >= 2
        else:
            assert len(calls) == 1  # Existing checked carrier; no reconstruction.
    if case == 'missing_source':
        assert not calls
    assert (store.get_envelope(sid), console.snapshot_objects(sid),
            console.workflow_review_store.read_events(), console.workflow_review_store.read_bindings([sid])) == before


@pytest.mark.parametrize('layout', ['legacy', 'prepared'])
@pytest.mark.parametrize('change', ['extraction', 'source_identity'])
def test_incomplete_passage_does_not_reuse_changed_extraction(tmp_path, production_console, monkeypatch, change, layout):
    from copy import deepcopy
    from dataclasses import replace
    from src.integrity_kernel import stable_hash
    from src.operations_console_app import _review_formation_notice
    from src.review.review_passage_read_v1 import read_review_passage
    from src.vorming.source_preparation_context_v1 import KEY
    from tests.test_review_formation_problems import received, execute

    console, sid, author, reviewer, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'passage-changed-extraction')
    store = console.workflow_document_store
    if layout == 'legacy':
        with store._connect() as con:
            con.execute('TRUNCATE workflow.source_read_roots CASCADE')
            con.execute('UPDATE workflow.documents SET review_source_ref=NULL')
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    before = deepcopy(store.get_envelope(sid))
    changed = deepcopy(before)
    record = changed[KEY]
    if change == 'extraction':
        record['fragments'][-1]['test_new_extraction_marker'] = 'changed'
        record['fragments_hash'] = stable_hash(record['fragments'])
        record['record_hash'] = stable_hash({k: v for k, v in record.items() if k != 'record_hash'})
    original_status = console.processing_status
    captured = []

    def status(*args, **kwargs):
        result = original_status(*args, **kwargs)
        captured.append((kwargs.get('formation_fragments'), result))
        return result

    with console.document_read_operation(), monkeypatch.context() as changed_reads:
        inputs = read_review_passage(console, {'account_id': reviewer, 'roles': ['reviewer']}, sid, obj['object_id'])
        prior_carrier = inputs.fragments
        if change == 'source_identity':
            inputs = replace(inputs, envelope={**inputs.envelope, 'version': 'earlier-version'})
        changed_reads.setattr(store, 'get_envelope', lambda snapshot_id: deepcopy(changed))
        changed_reads.setattr(console, 'processing_status', status)
        notice = _review_formation_notice(console, sid, inputs)
        assert console._document_reads().envelopes[sid] is inputs.envelope
    assert 'data-formation-incomplete' in notice
    assert len(captured) == 1 and captured[0][1]['formation_incomplete']
    assert captured[0][0] is not prior_carrier
    if layout == 'prepared' and change == 'extraction':
        # A new extraction with the old durable pin is unavailable, never rebuilt
        # or silently treated as legacy. Its partial carrier proves no closure.
        assert captured[0][0] is None
    else:
        assert captured[0][0].root.payload['fragments_hash'] == record['fragments_hash']
    assert store.get_envelope(sid) == before


def test_passage_capture_keeps_bindings_stable_when_writer_commits(tmp_path, production_console, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from copy import deepcopy
    from src.integrity_kernel import exact_review_snapshot_hash
    from src.operations_console_app import _review_formation_notice
    from src.publication.publish_authorization_v1 import tuple_record
    from src.review.review_passage_read_v1 import read_review_passage
    from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
    from tests.test_review_formation_problems import received, execute

    console, sid, author, reviewer, _, _, _ = received(tmp_path, production_console, monkeypatch)
    execute(console, sid, author, 'passage-binding-capture')
    store = console.workflow_document_store
    other = PostgresWorkflowReviewStore(store.config)
    objects = console.snapshot_objects(sid)
    obj = next(o for o in objects if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    before = deepcopy(objects), deepcopy(store.get_envelope(sid)), console.workflow_review_store.read_events()
    existing = other.read_bindings([sid]).get(sid, [])
    # The tuple is deliberately stale for the captured candidate and cannot
    # become an approval merely because a concurrent writer commits it.
    binding = tuple_record(object_id=obj['object_id'], object_version=obj['object_version'],
        canonical_object_hash=exact_review_snapshot_hash(obj), confirmed_object_type='definition',
        reviewer='reviewer', reviewer_id=reviewer, decision='approve')
    binding['test_after_capture'] = True
    original = store.review_document_input
    writes = []

    def capture(snapshot_id):
        result = original(snapshot_id)
        if not writes:
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(other.replace_snapshot_bindings, snapshot_id, [*existing, binding]).result(timeout=10)
            writes.append(1)
        return result

    monkeypatch.setattr(store, 'review_document_input', capture)
    actor = {'account_id': reviewer, 'roles': ['reviewer']}
    with console.document_read_operation():
        inputs = read_review_passage(console, actor, sid, obj['object_id'])
        assert not any(row.get('test_after_capture') for row in inputs.bindings)
        assert 'data-formation-incomplete' in _review_formation_notice(console, sid, inputs)
    with console.document_read_operation():
        fresh = read_review_passage(console, actor, sid, obj['object_id'])
    found = [row for row in fresh.bindings if row.get('test_after_capture')]
    assert len(found) == 1 and found[0]['valid'] is False
    assert writes == [1]
    assert (console.snapshot_objects(sid), store.get_envelope(sid),
            console.workflow_review_store.read_events()) == before
    assert len(other.read_bindings([sid])[sid]) == len(existing) + 1


@pytest.mark.parametrize('review_client', [300], indirect=True)
def test_prepared_source_comparisons_do_not_grow_with_candidates(review_client, monkeypatch):
    import src.vorming.knowledge_materialisation_v1 as materialisation
    from src.review.review_duty_v1 import review_work_projection
    from src.vorming.prepared_source_views_v1 import prepare

    console, _client, sid = review_client
    envelope = console._envelope(sid)
    fragments = prepare(console.review_source_fragments(sid, envelope=envelope)).fragments
    candidates = [obj for obj in console.snapshot_objects(sid)
                  if (obj.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    assert len(candidates) >= 100
    comparisons = []
    original = materialisation._SourceNumber.__eq__

    def compare(self, other):
        comparisons.append(1)
        return original(self, other)

    monkeypatch.setattr(materialisation._SourceNumber, '__eq__', compare)
    for count in (1, 50, len(candidates)):
        comparisons.clear()
        duties, _, _ = review_work_projection(candidates[:count], review_path='richtlijn',
            reviewer_id=envelope['named_reviewers'][0], bindings=[], fragments=fragments)
        assert len(duties) == count
        assert not comparisons


def test_passage_get_does_not_load_document_object_payloads(review_client, monkeypatch):
    console, client, sid = review_client
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))

    def forbidden(*args, **kwargs):
        raise AssertionError('One passage may not load all document object payloads')

    monkeypatch.setattr(console.workflow_document_store, 'list_document_objects', forbidden)
    monkeypatch.setattr(console, 'snapshot_objects_and_revision', forbidden)
    response = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert response.status_code == 200
    assert obj['content']['clean_text'] in response.text
    assert 'name="snapshot_revision"' in response.text
    assert 'Review' in response.text


def test_passage_revision_is_rejected_after_another_object_changes(review_client):
    import re
    from copy import deepcopy
    from src.review.review_passage_read_v1 import resolve_review_revision
    from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
    import pytest

    console, client, sid = review_client
    rows = console.snapshot_objects(sid)
    candidates = [o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    response = client.get('/review', params={'document': sid, 'object': candidates[0]['object_id']})
    assert response.status_code == 200
    token = re.search(r'name="snapshot_revision" value="([^"]+)"', response.text).group(1)
    assert resolve_review_revision(console, sid, token) == console.objects_revision(sid)
    changed = deepcopy(console._load_objects(sid))
    next(o for o in changed if o['object_id'] == candidates[1]['object_id'])['review_test_marker'] = 'changed'
    console._save_objects(sid, changed)
    with pytest.raises(ConsoleError) as error:
        resolve_review_revision(console, sid, token)
    assert error.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT


@pytest.mark.parametrize('index', [0, 10, 19])
@pytest.mark.parametrize('review_client', [None, 'raw'], indirect=True)
def test_isolated_source_window_keeps_exact_candidate_evidence(review_client, index):
    from src.vorming.source_reconstruction_v1 import review_source_window
    from src.vorming.knowledge_materialisation_v1 import validate_materialised_candidate
    console, _client, sid = review_client
    obj = [o for o in console.snapshot_objects(sid)
           if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')][index]
    fragments = console.review_source_fragments(sid)
    # Indexed source windows are selected by the existing store owner; raw
    # legacy sources use the independently closed-block selector. A full
    # immutable carrier deliberately retains its originally requested scope.
    selected = console.review_source_fragments(sid, objects=[obj])
    window = review_source_window(selected, [obj])
    assert len(window) == 1
    assert validate_materialised_candidate(obj, fragments=window) == validate_materialised_candidate(obj, fragments=fragments)


@pytest.mark.parametrize('review_client', ['large'], indirect=True)
def test_context_picker_pages_preserve_access_without_loading_all_payloads(review_client, monkeypatch):
    console, client, sid = review_client
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    original = console.workflow_document_store.review_object_histories
    loaded = []

    def selected(snapshot_id, ids):
        loaded.extend(ids)
        return original(snapshot_id, ids)

    monkeypatch.setattr(console.workflow_document_store, 'review_object_histories', selected)
    page = client.get('/source-selection', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200 and len(set(loaded)) <= 26
    assert '59 teksten' in page.text and 'Volgende' in page.text
    assert 'Begrip 59 is' not in page.text
    loaded.clear()
    last = client.get('/source-selection', params={'document': sid, 'object': obj['object_id'], 'context_page': 3})
    assert last.status_code == 200 and 'Begrip 59 is' in last.text
    assert len(set(loaded)) <= 26
    choices, total = console.workflow_document_store.review_choice_ids(
        sid, obj['object_id'], query='', page=999)
    assert choices == [] and total == 59


@pytest.mark.parametrize('case', [
    'current', 'stale', 'wrong_document', 'malformed', 'role_removed',
    'empty_generation', 'missing_separator', 'empty_document_revision',
    'empty_object_generation', 'extra_separator', 'non_decimal_generation',
    'trailing_newline', 'non_string_generation', 'oversized_token',
])
def test_compact_form_uses_the_real_review_command_and_refuses_invalid_context(review_client, case):
    import base64
    import json
    import re
    from copy import deepcopy
    console, client, sid = review_client
    rows = console.snapshot_objects(sid)
    candidates = [o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    obj = candidates[0]
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    revision = re.search(r'name="snapshot_revision" value="([^"]+)"', page.text).group(1)
    assert revision.startswith('review-generation-v1:')
    if case == 'stale':
        changed = deepcopy(console._load_objects(sid))
        next(o for o in changed if o['object_id'] == candidates[1]['object_id'])['review_test_marker'] = 'concurrent'
        console._save_objects(sid, changed)
    elif case == 'wrong_document':
        payload = json.loads(base64.urlsafe_b64decode(revision.partition(':')[2]))
        payload[0] = 'another-document'
        revision = 'review-generation-v1:' + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    elif case == 'malformed':
        revision = 'review-generation-v1:not-json'
    elif case in {
        'empty_generation', 'missing_separator', 'empty_document_revision',
        'empty_object_generation', 'extra_separator', 'non_decimal_generation',
        'trailing_newline', 'non_string_generation', 'oversized_token',
    }:
        generation = {
            'empty_generation': '', 'missing_separator': '0' * 160,
            'empty_document_revision': ':1', 'empty_object_generation': '1:',
            'extra_separator': '1:2:3',
            'non_decimal_generation': '0' * 160 + ':0' + '0' * 80 + '!',
            'trailing_newline': '1:2\n', 'non_string_generation': 12,
            'oversized_token': '0' * 600 + ':1',
        }[case]
        revision = 'review-generation-v1:' + base64.urlsafe_b64encode(
            json.dumps([sid, generation]).encode()).decode()
    elif case == 'role_removed':
        reviewer_id = console._envelope(sid)['named_reviewers'][0]
        console.workflow_identity_store.update_roles(reviewer_id, ['researcher'])
    before = deepcopy(console.snapshot_objects(sid))
    events = console.workflow_review_store.read_events()
    result = client.post('/review', data={
        'snapshot_id': sid, 'object_id': obj['object_id'], 'snapshot_revision': revision,
        'suitability': 'ja', 'documentpositie_action': 'dit_klopt', 'type_action': 'dit_klopt',
        'confirmed_object_type': 'definition', 'eindoordeel': 'goedkeuren', 'decision': 'approve',
        'relation_review_ack': '1'}, follow_redirects=False)
    if case == 'current':
        assert result.status_code == 303
        current = next(o for o in console.snapshot_objects(sid) if o['object_id'] == obj['object_id'])
        assert current['governance']['validation_status'] == 'approved'
        assert any(row['valid'] and row['object_id'] == obj['object_id']
                   for row in console.object_review_bindings(sid))
    else:
        assert result.status_code == (403 if case == 'role_removed' else 409)
        assert console.snapshot_objects(sid) == before
        assert console.workflow_review_store.read_events() == events


@pytest.mark.parametrize('review_client', ['large'], indirect=True)
@pytest.mark.parametrize('many_targets', [False, True])
def test_linked_context_outside_picker_page_keeps_full_projection(review_client, many_targets):
    from src.review.review_passage_read_v1 import read_review_passage
    from src.vorming.source_containers_v1 import source_accountability
    console, _client, sid = review_client
    candidates = [o for o in console.snapshot_objects(sid)
                  if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    target, source = candidates[0], candidates[50]
    targets = [target] + ([o for o in candidates[30:] if o['object_id'] != source['object_id']]
                          if many_targets else [])
    reviewer_id = console._envelope(sid)['named_reviewers'][0]
    console.confirm_source_context(actor_id=reviewer_id, snapshot_id=sid,
        source_object_id=source['object_id'], role='context',
        target_object_ids=[o['object_id'] for o in targets], reason='Deze bronpassage hoort bij het doel.',
        command_id='outside-picker-context', expected_revision=console.objects_revision(sid))
    package = read_review_passage(console, {'account_id': reviewer_id, 'roles': ['reviewer']},
                                  sid, target['object_id'])
    assert source['object_id'] in {o['object_id'] for o in package.objects}
    assert len(package.objects) < len(candidates)
    if many_targets:
        assert len(package.objects) > 26  # Paging never truncates required context.
    full = source_accountability(console.snapshot_objects(sid), bindings=console.object_review_bindings(sid),
                                  fragments=console.review_source_fragments(sid))
    selected = source_accountability(package.objects, bindings=package.bindings, fragments=package.fragments)
    for oid in [source['object_id'], *(o['object_id'] for o in targets)]:
        assert selected[oid] == full[oid]


def test_unknown_snapshot_and_database_failure_remain_distinct(review_client, monkeypatch):
    from src.operations_console_v1 import ConsoleError
    from src.review.review_passage_read_v1 import read_review_passage
    from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
    console, client, sid = review_client
    obj = next(o for o in console.snapshot_objects(sid)
               if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans'))
    response = client.get('/review', params={'document': 'missing', 'object': obj['object_id']})
    assert response.status_code == 400 and 'niet meer beschikbaar' in response.text
    def unavailable(*args, **kwargs):
        raise WorkflowDocumentStoreError('workflow_document_read_failed')
    monkeypatch.setattr(console.workflow_document_store, 'review_document_input', unavailable)
    reviewer_id = console._envelope(sid)['named_reviewers'][0]
    with pytest.raises(ConsoleError) as error:
        read_review_passage(console, {'account_id': reviewer_id, 'roles': ['reviewer']}, sid, obj['object_id'])
    assert error.value.code == 'workflow_document_unavailable'


@pytest.mark.parametrize('review_client', ['large'], indirect=True)
def test_dependencies_include_incoming_and_outgoing_relations_beyond_picker(review_client):
    from copy import deepcopy
    from src.review.revision_workflow import bump_patch, revise_object
    from src.knowledge_relations_v1 import build_knowledge_relation
    from src.review.review_passage_read_v1 import read_review_passage
    console, _client, sid = review_client
    rows = deepcopy(console._load_objects(sid))
    candidates = [o for o in rows if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')]
    selected, incoming, outgoing = (deepcopy(candidates[i]) for i in (40, 55, 59))
    for obj in (selected, incoming):
        previous = obj['object_version']
        obj['object_version'] = bump_patch(previous)
        obj['provenance']['previous_object_version'] = previous
    for source, target in ((incoming, selected), (selected, outgoing)):
        source['proposed_knowledge_relations'] = [build_knowledge_relation(
            source_object_id=source['object_id'], source_object_version=source['object_version'],
            relation_type='supported_by', target_object_id=target['object_id'],
            target_object_version=target['object_version'])]
    reviewer_id = console._envelope(sid)['named_reviewers'][0]
    selected, incoming = (revise_object(before, after, snapshot_id=sid,
        reason='Relation dependency fixture', actor=reviewer_id, force=True)
        for before, after in ((candidates[40], selected), (candidates[55], incoming)))
    console._save_objects(sid, [*rows, selected, incoming])
    package = read_review_passage(console, {'account_id': reviewer_id, 'roles': ['reviewer']},
                                  sid, selected['object_id'])
    by_id = {o['object_id']: o for o in package.objects}
    for obj in (selected, incoming, outgoing):
        assert by_id[obj['object_id']] == obj
    assert len(by_id) < len(candidates)
