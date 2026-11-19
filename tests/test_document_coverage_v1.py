"""Proof through the installed review and source-disposition routes.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.review.document_coverage_v1 import assess
from src.review.review_passage_read_v1 import read_review_document
from src.vorming.source_containers_v1 import source_accountability
from tests.ko_review_fixture_support import affirmative_assessment
from tests.test_availability_repair import accounts, bind, login
from tests.test_recommendation_context_v3 import response_for
from tests.test_review_formation_problems import execute
from tests.test_source_context_review_ui_v1 import Forms, _payload

SOURCE = Path(__file__).parent / 'fixtures/smetten-documenttoets.html'
CORE = 'Controleer dagelijks de huid. Leg de waarneming vast.'
EXCEPTION = 'Sla de dagelijkse huidcontrole over als de patiënt de controle weigert.'


def _capture(console, reviewer, sid):
    account = {'account_id': reviewer, 'roles': ['reviewer']}
    with console.document_read_operation():
        inputs = read_review_document(console, account, sid)
        usage = source_accountability(inputs.objects, bindings=inputs.bindings, fragments=inputs.fragments)
        return inputs, usage, assess(inputs.envelope, inputs.objects, inputs.revision, inputs.fragments, usage)


def _receive(console, author, reviewer, data):
    return console.receive_source(actor_id=author, filename=SOURCE.name, data=data,
        content_type='text/html', ingest_kind='new', title='Synthetische Smetten-proef',
        version='1', date='2026-11-18', live_url='', class_='richtlijn', family='fixture',
        named_reviewers=[reviewer])['snapshot_id']


def _provider(selected):
    def respond(_url, _headers, payload, _timeout):
        inputs = json.loads(payload['input'][1]['content'])
        if any(selected in block['text'] for block in inputs['source_blocks']) and not inputs.get('selection_targets'):
            result = response_for(payload, selected)
        else:
            result = {'objects': [], 'relations': [], 'abstain_reason': 'uncertain'}
        return {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(result)}]}]}
    return respond


def test_missing_exception_and_passage_decision_follow_current_revision(tmp_path, production_console, monkeypatch):
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    author, reviewer = accounts(console)
    bind(console, _provider(CORE))
    sid = _receive(console, author, reviewer, SOURCE.read_bytes())
    execute(console, sid, author, 'document-coverage-test')
    candidate, = [row for row in console.snapshot_objects(sid)
                  if row.get('proposed_object_type') == 'recommendation']
    assert candidate['content']['clean_text'] == CORE
    assert candidate['metadata']['admission']['gate_result'] == 'allowed'
    console.review_object(actor_id=reviewer, snapshot_id=sid, object_id=candidate['object_id'],
        decision='approve', confirmed_object_type='recommendation', recommendation_direction='for',
        recommendation_strength_level='not_stated', assessment=affirmative_assessment(), evidence_not_applicable=True)

    before, usage, coverage = _capture(console, reviewer, sid)
    findings = {item['kind']: item for item in coverage['findings']}
    assert findings['recommendation']['status'] == 'covered'
    assert findings['condition']['status'] == findings['exception']['status'] == 'missing'
    exception = findings['exception']
    assert exception['text'] == EXCEPTION and exception['location'] == 'lines:10-10;p:3'
    assert exception['span']['end'] == len(EXCEPTION)
    source_id, = exception['source_object_ids']
    assert assess(before.envelope, before.objects, before.revision, None, usage)['status'] == 'unavailable'
    without_source_record = [row for row in before.objects if row['object_id'] != source_id]
    absent = assess(before.envelope, without_source_record, before.revision, before.fragments, usage)
    assert absent['findings'][-1]['status'] == 'missing'
    assert absent['findings'][-1]['source_object_ids'] == []

    client = TestClient(console._metis_test_application, base_url='https://console.example.test',
                        headers={'Origin': 'https://console.example.test'})
    params = {'document': sid, 'task': 'inventory'}
    login(client)  # The uploader also has a reviewer role, but isn't named here.
    denied = client.get('/review', params=params, follow_redirects=False)
    assert denied.status_code == 303
    assert 'data-document-coverage' not in denied.text
    login(client, 'reviewer')
    page = client.get('/review', params=params)
    assert page.status_code == 200
    assert 'data-coverage-kind="exception" data-coverage-status="missing"' in page.text
    assert 'Bronregel 10' in page.text
    assert EXCEPTION in page.text
    link = f'/source-selection?document={sid}&object={source_id}&task=disposition'
    assert link.replace('&', '&amp;') in page.text
    source = client.get(link)
    assert source.status_code == 200 and EXCEPTION in source.text

    def apply_role(page, role, reason):
        form = next(form for form in Forms(page.text).forms if any(
            item.get('name') == 'role' and item.get('value') == role for item in form['inputs']))
        return client.post('/review/source-context', data=_payload(form, role=role, reason=reason),
                           follow_redirects=False)

    reason = 'Bewust buiten de afbakening van deze synthetische deelproef.'
    saved = apply_role(source, 'excluded', reason)
    assert saved.status_code == 303, saved.text
    page = client.get('/review', params=params)
    assert 'data-coverage-kind="exception" data-coverage-status="excluded"' in page.text
    assert reason in page.text
    _, _, excluded = _capture(console, reviewer, sid)
    assert excluded['binding']['set_revision'] != coverage['binding']['set_revision']
    assert excluded['binding']['extraction_hash'] == coverage['binding']['extraction_hash']
    assert excluded['findings'][-1]['objects']  # Exact current disposition version.

    reset = apply_role(client.get(link), 'reset', 'Beoordeel de uitzondering opnieuw.')
    assert reset.status_code == 303, reset.text
    assert 'data-coverage-kind="exception" data-coverage-status="missing"' in client.get('/review', params=params).text
    _, _, reopened = _capture(console, reviewer, sid)
    assert reopened['binding']['set_revision'] != excluded['binding']['set_revision']
    assert reopened['findings'][-1]['objects'] == []
    assert reopened['findings'][-1]['reason'] == ''

    other = _receive(console, author, reviewer, SOURCE.read_bytes().replace(b'<title>', b'<title>Andere bron: '))
    response = client.get('/review', params={'document': other, 'task': 'inventory'})
    assert response.status_code == 200
    assert 'data-document-coverage' not in response.text


def test_partial_recommendation_does_not_cover_the_provision(tmp_path, production_console, monkeypatch):
    monkeypatch.setenv('METIS_FORMATION_TASK_STORAGE', 'v1')
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    author, reviewer = accounts(console)
    bind(console, _provider('Controleer dagelijks de huid.'))
    sid = _receive(console, author, reviewer, SOURCE.read_bytes())
    execute(console, sid, author, 'partial-coverage-test')
    _, _, coverage = _capture(console, reviewer, sid)
    recommendation = coverage['findings'][0]
    assert recommendation['status'] == 'partial'
    assert recommendation['objects']
