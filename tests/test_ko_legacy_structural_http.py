# release-control-evidence: scope/belofte opslag toegang slop releasebewijs
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review.review_duty_v1 import authoritative_review_type
from tests.test_explicit_review_policy import policy
from tests.test_formation_repair_workplace import form_data
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_source_context_review_ui_v1 import Forms
from tests.test_v225_beslisboom_path import _console, _accounts, _ingest_boom


def _setup(tmp_path, production_console, production_app, *, required=False):
    console = _console(tmp_path, production_console=production_console)
    people = _accounts(console)
    extra = dict(named_reviewers=[], review_policy=policy(people, 'required')) if required else {}
    sid = _ingest_boom(console, people, **extra)['snapshot_id']
    client = TestClient(production_app(console))
    username = 'researcher.anne' if required else 'reviewer.bert'
    password = 'anne-secret' if required else 'bert-secret'
    assert client.post('/login', data={'username': username, 'password': password}, follow_redirects=False).status_code == 303
    return console, people, sid, client


def _first_form(client, sid, obj):
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    data = form_data(page, '/review')
    data.pop('review_ui', None)
    data.update(suitability='ja', eindoordeel='goedkeuren', decision='approve', type_action='dit_klopt',
                confirmed_object_type=authoritative_review_type(obj), documentpositie_action='dit_klopt')
    return page, data


@pytest.mark.parametrize('mode', ['path', 'ko_missing', 'conversion_missing', 'partial_yes', 'partial_blank', 'negative'])
def test_legacy_first_form_distinguishes_absent_from_supplied_answers(
        tmp_path, production_console, production_app, monkeypatch, mode):
    console, _, sid, client = _setup(tmp_path, production_console, production_app)
    kind = 'node' if mode == 'ko_missing' else 'path'
    obj = next(row for row in console.snapshot_objects(sid) if authoritative_review_type(row) == kind)
    page, data = _first_form(client, sid, obj)
    if kind == 'path':
        form = next(form for form in Forms(page.text).forms if form['attrs'].get('action') == '/review')
        assert not any(item.get('name') in {'applicable', 'complete', 'placed_correctly'} for item in form['inputs'])
    if mode == 'conversion_missing':
        data.update(confirmed_object_type='node', type_action='type_wijzigen')
    if mode == 'partial_yes':
        data['applicable'] = 'yes'
    if mode == 'partial_blank':
        data['applicable'] = ''
    if mode == 'negative':
        data.update(applicable='yes', complete='adjust', placed_correctly='yes')
    original = console.review_object
    failures = []
    def observe(**kwargs):
        try:
            return original(**kwargs)
        except ConsoleError as error:
            failures.append(error.code)
            raise
    monkeypatch.setattr(console, 'review_object', observe)
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    saved = client.post('/review', data=data, follow_redirects=False)
    if mode == 'path':
        assert saved.status_code == 303, saved.text
        binding = next(row for row in console.object_review_bindings(sid) if row['object_id'] == obj['object_id'])
        assert binding.get('valid') and binding['confirmed_object_type'] == 'path'
        assert 'assessment' not in binding and 'supporting_evidence' not in binding
    else:
        assert saved.status_code == 400, saved.text
        expected = 'review_assessment_required' if mode in {'ko_missing', 'conversion_missing'} else 'review_assessment_requires_three_yes'
        assert failures and set(failures) == {expected}
        assert physical_state(console, sid) == before
        assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


@pytest.mark.parametrize('answers', [{}, {'applicable': ''}, {'applicable': 'adjust'}])
@pytest.mark.parametrize('endpoint', ['/review/second-review', '/review/decision-passage'])
def test_legacy_required_second_path_form_keeps_structural_exemption_strict(
        tmp_path, production_console, production_app, answers, endpoint):
    console, people, sid, client = _setup(tmp_path, production_console, production_app, required=True)
    obj = next(row for row in console.snapshot_objects(sid) if authoritative_review_type(row) == 'path')
    console.review_object(actor_id=people['researcher']['account_id'], snapshot_id=sid, object_id=obj['object_id'],
        decision='approve', confirmed_object_type='path', suitability='ja', eindoordeel='goedkeuren', type_action='dit_klopt',
        expected_revision=console.objects_revision(sid))
    assert client.post('/login', data={'username': 'reviewer.bert', 'password': 'bert-secret'}, follow_redirects=False).status_code == 303
    page = client.get('/review', params={'document': sid, 'object': obj['object_id'], 'task': 'second_review'})
    assert page.status_code == 200
    data = form_data(page, '/review/second-review')
    assert not {'applicable', 'complete', 'placed_correctly'} & data.keys()
    data.update(action='approve', **answers)
    if endpoint == '/review/decision-passage':
        data.update(document=sid, expected_revision=console.objects_revision(sid))
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    saved = client.post(endpoint, data=data, follow_redirects=False)
    if not answers:
        assert saved.status_code == 303, saved.text
        own = [row for row in console.object_review_bindings(sid)
               if row['object_id'] == obj['object_id'] and row.get('valid')]
        assert {row['reviewer_id'] for row in own} == {people[key]['account_id'] for key in ('researcher', 'reviewer')}
        assert all('assessment' not in row and 'supporting_evidence' not in row for row in own)
    else:
        assert saved.status_code == 400
        assert physical_state(console, sid) == before
        assert console.workflow_review_store.read_events_for_snapshots([sid]) == events


@pytest.mark.parametrize('decision', ['later', 'reject'])
def test_legacy_path_nonapproval_does_not_require_clinical_answers(tmp_path, production_console, production_app, decision):
    console, _, sid, client = _setup(tmp_path, production_console, production_app)
    obj = next(row for row in console.snapshot_objects(sid) if authoritative_review_type(row) == 'path')
    _, data = _first_form(client, sid, obj)
    data.update(decision=decision, eindoordeel='later_beoordelen' if decision == 'later' else 'afwijzen', comment='Deze bron later beoordelen.')
    saved = client.post('/review', data=data, follow_redirects=False)
    assert saved.status_code == 303, saved.text
    assert not any(row.get('valid') and row['decision'] == 'approve'
                   for row in console.object_review_bindings(sid) if row['object_id'] == obj['object_id'])


def test_decision_passage_clinical_second_still_requires_answers(tmp_path, production_console, production_app, monkeypatch):
    from tests.test_explicit_review_policy import _assemble_score_graph
    from tests.ko_review_fixture_support import affirmative_assessment
    console, people, sid, client = _setup(tmp_path, production_console, production_app, required=True)
    obj = next(row for row in console.snapshot_objects(sid) if authoritative_review_type(row) == 'node')
    obj = _assemble_score_graph(console, people, sid, obj['object_id'])
    console.review_object(actor_id=people['researcher']['account_id'], snapshot_id=sid, object_id=obj['object_id'],
        decision='approve', confirmed_object_type='node', suitability='ja', eindoordeel='goedkeuren',
        assessment=affirmative_assessment(), evidence_not_applicable=True, expected_revision=console.objects_revision(sid))
    assert client.post('/login', data={'username': 'reviewer.bert', 'password': 'bert-secret'}, follow_redirects=False).status_code == 303
    original = console.approve_second_review
    failures = []
    def observe(**kwargs):
        try:
            return original(**kwargs)
        except ConsoleError as error:
            failures.append(error.code)
            raise
    monkeypatch.setattr(console, 'approve_second_review', observe)
    before = deepcopy(physical_state(console, sid))
    events = console.workflow_review_store.read_events_for_snapshots([sid])
    response = client.post('/review/decision-passage', data={'document': sid, 'object_id': obj['object_id'],
        'expected_revision': console.objects_revision(sid)}, follow_redirects=False)
    assert response.status_code == 400
    assert failures and set(failures) == {'review_assessment_required'}
    assert physical_state(console, sid) == before
    assert console.workflow_review_store.read_events_for_snapshots([sid]) == events
    accepted = client.post('/review/decision-passage', data={'document': sid, 'object_id': obj['object_id'],
        'expected_revision': console.objects_revision(sid), 'applicable': 'yes', 'complete': 'yes',
        'placed_correctly': 'yes', 'evidence_not_applicable': 'yes'}, follow_redirects=False)
    assert accepted.status_code == 303, accepted.text
    binding = next(row for row in console.object_review_bindings(sid)
                   if row['object_id'] == obj['object_id'] and row['reviewer_id'] == people['reviewer']['account_id'])
    assert binding.get('valid') and binding['assessment'] == affirmative_assessment()
    assert binding['supporting_evidence']['applicability'] == 'not_applicable'
