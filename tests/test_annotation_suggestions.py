"""Meaning proposals cannot invent source bindings or mutate persisted truth.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_v1 as annotation
from src.vorming import human_annotation_suggestion_v1 as suggestions
from src.vorming.source_bound_fields_v3 import FIELDS
from tests.test_human_annotation_postgres import source, anchor, command
from tests.production_support import restart_production


def proposal(**quotes):
    fields = {field: {'quote': None, 'missing_reason': 'not_applicable'} for field in FIELDS}
    for field, quote in quotes.items():
        fields[field] = {'quote': quote, 'missing_reason': None}
    return {'object_type': 'recommendation', 'fields': fields, 'semantics': {
        'direction': 'for', 'direction_quote': 'Controleer', 'strength_status': 'not_stated',
        'strength': None, 'strength_quote': None}}


def provider(raw):
    return {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': json.dumps(raw)}]}]}


def test_literal_binding_unicode_and_ambiguous_words():
    rows = [{'block_id': 'b', 'start': 10, 'end': 38, 'text': '👩🏽‍⚕️ huid huid café.'}]
    result = suggestions.bind_proposal(proposal(subject_span='👩🏽‍⚕️', predicate_span='huid',
                                                recommended_action='café', actor_span='verpleegkundige'), rows)
    assert result['field_evidence']['subject_span'] == {'span': {'block_id': 'b', 'start': 10, 'end': 15}, 'missing_reason': None}
    assert result['field_evidence']['recommended_action']['span'] == {'block_id': 'b', 'start': 26, 'end': 31}
    for field in ('predicate_span', 'actor_span'):
        assert result['field_evidence'][field] == {'span': None, 'missing_reason': 'uncertain'}
    assert result['recommendation_semantics']['direction'] is None  # absent cue cannot support direction
    assert suggestions.bind_quote('huid', [{'block_id': 'a','start': 0,'text': 'huid'},
                                         {'block_id': 'b','start': 0,'text': 'huid'}]) is None
    assert suggestions.bind_quote('cafe', rows) is None  # no Unicode/quote normalization guessing


@pytest.mark.parametrize('corruption', ['extra', 'type', 'free_text', 'missing', 'semantics'])
def test_closed_provider_contract(corruption):
    raw = proposal()
    if corruption == 'extra': raw['candidate_text'] = 'A replacement statement'
    if corruption == 'type': raw['object_type'] = 'unknown'
    if corruption == 'free_text': raw['fields']['subject_span'] = {'text': 'invented'}
    if corruption == 'missing': raw['fields']['subject_span'] = {'quote': None, 'missing_reason': None}
    if corruption == 'semantics': raw['semantics']['direction'] = 'always'
    with pytest.raises(ConsoleError, match='annotation_suggestion_invalid'):
        suggestions.bind_proposal(raw, [{'block_id':'b','start':0,'text':'Controleer de huid.'}])


def setup(production_console, tmp_path):
    console, actor, reviewer, sid, view, _ = source(production_console, tmp_path)
    cmd = command(view, ranges=[anchor(view, 'Controleer')])
    cmd['selection']['object_type'] = None
    annotation.save(console, actor_id=actor, **cmd)
    view = annotation.overview(console, actor_id=actor, snapshot_id=sid)
    request = {'snapshot_id': sid, 'annotation_id': cmd['annotation_id'], 'revision': 1,
        'basis': {key: view[key] for key in ('snapshot_id','working_revision_id','extraction_hash',
                                           'normalization','generation','objects_revision')}}
    return console, actor, reviewer, sid, view, cmd, request


def configure(monkeypatch):
    monkeypatch.setenv('METIS_LLM_API_KEY', 'synthetic-test-key')
    monkeypatch.setenv('METIS_LLM_MODEL', 'synthetic-model')


def test_http_suggestion_readonly_then_draft_save_resume_and_correct(production_console, production_app, tmp_path, monkeypatch):
    console, actor, _, sid, view, cmd, request = setup(production_console, tmp_path)
    configure(monkeypatch)
    calls = []
    def transport(url, headers, body, limits):
        calls.append(body)
        assert limits.total == 45 and limits.max_attempts == 1
        return provider(proposal(subject_span='de huid', predicate_span='Controleer',
            type_evidence_spans=view['entries'][0]['ranges'][0]['quote'],
            recommendation_evidence_span=view['entries'][0]['ranges'][0]['quote'],
            recommended_action='Controleer', action_object_or_goal='de huid'))
    monkeypatch.setattr(suggestions, 'logged_post_json', transport)
    client = TestClient(production_app(console), base_url='https://testserver')
    client.post('/login', data={'username':'annotator','password':'annotation-secret'})
    response = client.post('/annotations/suggest', json=request)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['basis'] == request['basis'] and result['revision'] == 1
    assert len(calls) == 1 and calls[0]['store'] is False
    sent = json.loads(calls[0]['input'][1]['content'])
    assert len(sent['selected']) == 1 and 'Alleen bij klachten' not in json.dumps(sent)
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid) == view  # query cannot write
    assert 'candidate_text' not in result and 'object_id' not in result
    selection = {**cmd['selection'], **{k:result[k] for k in ('object_type','field_evidence','recommendation_semantics')}}
    for field in selection['field_evidence'].values():
        if field['span']:
            block = next(b for b in view['blocks'] if b['block_id'] == field['span']['block_id'])
            field['quote'] = block['text'][field['span']['start']:field['span']['end']]
    selection['recommendation_semantics'] = {**selection['recommendation_semantics'],
        'direction_evidence': {'span':result['recommendation_semantics']['direction_evidence'],'quote':'Controleer'}}
    cmd.update(command_id=str(uuid4()), expected_revision=1, expected_generation=view['generation'], selection=selection)
    annotation.save(console, actor_id=actor, **cmd)
    resumed = restart_production(console)
    saved = annotation.overview(resumed, actor_id=actor, snapshot_id=sid)
    assert saved['entries'][0]['status'] == 'draft'
    assert saved['entries'][0]['object_type'] == 'recommendation'
    assert saved['entries'][0]['field_evidence']['subject_span']['span']['start'] == 17
    assert saved['entries'][0]['evidence_not_applicable'] is False
    assert resumed.snapshot_objects(sid, include_blocked=True) == []
    # Existing human correction save, not a second meaning authority.
    selection = deepcopy(selection)
    selection['field_evidence']['actor_span'] = {'span':None,'missing_reason':'not_stated'}
    cmd.update(command_id=str(uuid4()), expected_revision=2, expected_generation=saved['generation'], selection=selection)
    annotation.save(resumed, actor_id=actor, **cmd)
    assert annotation.overview(resumed, actor_id=actor, snapshot_id=sid)['entries'][0]['field_evidence']['actor_span']['missing_reason'] == 'not_stated'


@pytest.mark.parametrize('change', ['before', 'during', 'rights'])
def test_stale_or_unauthorized_answer_never_changes_work(production_console, tmp_path, monkeypatch, change):
    console, actor, reviewer, sid, view, cmd, request = setup(production_console, tmp_path)
    configure(monkeypatch)
    outsider = console.create_account(username='outsider',password='test-secret',roles=('reviewer',))
    calls = []
    def mutate():
        cmd.update(command_id=str(uuid4()), expected_revision=1, expected_generation=view['generation'])
        annotation.save(console, actor_id=actor, **cmd)
    def transport(*args):
        calls.append(True)
        if change == 'during': mutate()
        return provider(proposal())
    if change == 'before': mutate()
    with pytest.raises(ConsoleError):
        suggestions.suggest(console, actor_id=outsider['account_id'] if change == 'rights' else actor,
                            request=request, post_json=transport)
    assert len(calls) == (1 if change == 'during' else 0)
    saved = annotation.overview(console, actor_id=actor, snapshot_id=sid)['entries'][0]
    assert saved['revision'] == (1 if change == 'rights' else 2)
    assert saved['object_type'] is None and not saved.get('field_evidence')


@pytest.mark.parametrize('failure', ['provider', 'malformed', 'unconfigured'])
def test_failed_suggestion_keeps_existing_work(production_console, production_app, tmp_path, monkeypatch, failure):
    console, actor, _, sid, view, cmd, request = setup(production_console, tmp_path)
    configure(monkeypatch)
    if failure == 'unconfigured': monkeypatch.delenv('METIS_LLM_API_KEY')
    def transport(*args):
        if failure == 'provider': raise ConsoleError('pre_review_llm_timeout')
        return provider({'unexpected':'prose'})
    monkeypatch.setattr(suggestions, 'logged_post_json', transport)
    client = TestClient(production_app(console), base_url='https://testserver')
    client.post('/login', data={'username':'annotator','password':'annotation-secret'})
    response = client.post('/annotations/suggest', json=request)
    assert response.status_code == (422 if failure == 'malformed' else 503)
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid) == view


@pytest.mark.parametrize('key', ['snapshot_id','working_revision_id','extraction_hash','normalization','generation','objects_revision'])
def test_each_basis_component_refuses_before_external_io(production_console, tmp_path, monkeypatch, key):
    console, actor, _, sid, view, cmd, request = setup(production_console, tmp_path)
    configure(monkeypatch)
    request['basis'][key] = 'another-value'
    def forbidden(*args):
        pytest.fail('A stale input must not start an external modelcall')
    with pytest.raises(ConsoleError, match='annotation_suggestion_stale'):
        suggestions.suggest(console, actor_id=actor, request=request, post_json=forbidden)
    assert annotation.overview(console, actor_id=actor, snapshot_id=sid) == view


def test_selected_type_cannot_be_changed_by_provider():
    with pytest.raises(ConsoleError, match='annotation_suggestion_invalid'):
        suggestions.bind_proposal(proposal(), [{'block_id':'b','start':0,'text':'Controleer.'}], 'definition')
