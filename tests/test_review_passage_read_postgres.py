"""Passage GET owns only its required objects; commands keep current authority.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale
# release-control-evidence: kwaliteit
# release-control-evidence: releasebewijs
"""
from tests.test_review_render_source_reuse import review_client  # noqa: F401
import pytest


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
def test_isolated_source_window_keeps_exact_candidate_evidence(review_client, index):
    from src.vorming.source_reconstruction_v1 import review_source_window
    from src.vorming.knowledge_materialisation_v1 import validate_materialised_candidate
    console, _client, sid = review_client
    obj = [o for o in console.snapshot_objects(sid)
           if (o.get('metadata') or {}).get('semantic_passage', {}).get('spans')][index]
    fragments = console.review_source_fragments(sid)
    window = review_source_window(fragments, [obj])
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
