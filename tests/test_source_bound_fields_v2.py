"""Source -> proposal -> persisted object -> admission -> review/export.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json
from copy import deepcopy

import pytest

from src.source_bound_fields_v2 import FIELDS, KEY, MODE
from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.operations_console_app import _source_bound_fields_html
from src.processing_evidence_export_v1 import processing_evidence_tables

TEXT = "Screening van ouderen is niet zinvol."


def fragment():
    return {"fragment_id": "f1", "raw_text": TEXT, "clean_text": TEXT,
            "fragment_hash": "h1", "section_path": ["Screening"],
            "source_locator": {"locator_type": "web_line_range", "locator_value": "lines:1-1"}}


def proposal(payload):
    block = json.loads(payload["input"][1]["content"])["source_blocks"][0]
    def span(text):
        start = block["text"].index(text)
        return {"block_id": block["block_id"], "start": start, "end": start+len(text)}
    fields = {field: {"span": None, "missing_reason": "not_applicable"} for field in FIELDS}
    for name, text in {"subject_span": "Screening van ouderen", "predicate_span": "is",
                       "type_evidence_spans": "niet zinvol", "actor_of_scope": "ouderen",
                       "recommended_action": "Screening", "action_object_or_goal": "ouderen",
                       "recommendation_evidence_span": TEXT}.items():
        fields[name] = {"span": span(text), "missing_reason": None}
    return {"objects": [{"spans": [span(TEXT)], "proposed_object_type": "recommendation",
                         "field_evidence": fields, "context_evidence": [],
                         "recommendation_semantics": {"direction": "against", "direction_evidence": span("niet zinvol"),
                         "strength": None, "strength_status": "not_stated", "strength_evidence": None}}],
            "relations": [], "abstain_reason": None}


def prepare(mutate=None):
    captured = {}
    def post(url, headers, payload, timeout):
        captured.update(payload)
        prop = proposal(payload)
        if mutate:
            mutate(prop)
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(prop)}]}]}
    fragments = [fragment()]
    spec = semantic_spec_from_fragments(document_id="doc", title="Test", family="test", class_="richtlijn",
          fragments=fragments, content_kind="html", api_key="test", model="test", post_json=post,
          formation_context={"snapshot_id": "snap", "source_sha256": "a"*64}, field_contract_v2=True)
    manifest = {"canonical_source": {"source_id": "s1", "title": "Test", "source_type": "html", "source_url": "test", "source_level": "national", "canonicality": "canonical", "integrity_status": "verified", "source_checksum": "a"*64}}
    rows = transform(spec, manifest, fragments)
    gated = apply_admission_gate(rows, klasse="richtlijn", fragments=fragments, document_version="1", source_hash="a"*64)
    return spec, gated, captured


def test_negative_recommendation_has_exact_fields_without_regex_reinterpretation():
    spec, rows, request = prepare()
    obj = rows[1]
    assert obj["content"]["clean_text"] == TEXT
    assert obj["metadata"]["semantic_passage"]["formation_mode"] == MODE
    assert obj["metadata"]["admission"]["gate_result"] == "allowed"
    assert obj["metadata"]["admission"]["recommended_action"] == "Screening"
    assert not obj.get("confirmed_object_type")
    assert 'field_evidence' in request["text"]["format"]["schema"]["properties"]["objects"]["items"]["required"]
    html = _source_bound_fields_html(obj)
    assert 'Voorgestelde betekenisvelden' in html and 'niet zinvol' in html
    tables, _ = processing_evidence_tables(snapshot_id="snap", revision="r1", envelope={}, objects=rows)
    field = next(r for r in tables["proposal_fields"] if r['field']=='recommended_action' and r['object_id']==obj['object_id'])
    assert field["source_span"]["start"] == 0 and field["value"] == "Screening"
    assert field['contract_version'] == 'source-bound-fields-v2'


def test_missing_field_is_not_filled_by_heuristics():
    def missing(p):
        p['objects'][0]['field_evidence']['recommended_action'] = {'span': None, 'missing_reason': 'uncertain'}
    _, rows, _ = prepare(missing)
    a=rows[1]['metadata']['admission']
    assert a['gate_result']=='blocked' and a['recommended_action']==''


@pytest.mark.parametrize('mutation', ['text', 'bounds', 'unknown', 'extra', 'reason'])
def test_invalid_model_evidence_fails_before_object_commit(mutation):
    def corrupt(p):
        o=p['objects'][0]
        if mutation=='text': o['candidate_text']='Nieuwe tekst.'
        if mutation=='bounds': o['field_evidence']['recommended_action']['span']['end']=10000
        if mutation=='unknown': o['field_evidence']['recommended_action']['span']['block_id']='unknown'
        if mutation=='extra': o['field_evidence']['recommended_action']['text']='Nieuwe tekst'
        if mutation=='reason': o['field_evidence']['recommended_action']['missing_reason']='uncertain'
    with pytest.raises(ValueError, match="semantic_object_contains_untrusted_fields|source_bound_field") as error:
        prepare(corrupt)
    assert error.value.code == "pre_review_llm_proposal_rejected"


@pytest.mark.parametrize('change', ['text', 'type', 'missing'])
def test_correction_cannot_reuse_stale_or_missing_v2_evidence(change):
    _, rows, _ = prepare()
    changed=deepcopy(rows)
    if change=='text': changed[1]['content']['clean_text']='Screening van ouderen is zinvol.'
    if change=='type': changed[1]['proposed_object_type']='definition'
    if change=='missing': del changed[1]['metadata'][KEY]
    result=apply_admission_gate(changed, klasse='richtlijn', fragments=[fragment()], document_version='1', source_hash='a'*64)
    assert result[1]['metadata']['admission']['gate_result']=='blocked'
    assert any(code.startswith('source_bound_') for code in result[1]['metadata']['admission']['reason_codes'])


def test_console_opt_in_persists_evidence_replays_and_survives_restart(tmp_path):
    from src.operations_console_v1 import OperationsConsole
    from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing, PASSAGE_FORMATION_MODE_ENV
    from src.llm_provider_v1 import LLM_API_KEY_ENV, LLM_MODEL_ENV
    calls=[]
    response_status = ['completed']
    def post(url, headers, payload, timeout):
        calls.append(payload)
        return {"id": "response-origin", "status": response_status[0], "usage": {"input_tokens": 123, "output_tokens": 45},
                "private_provider_metadata": "must-not-persist",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": ' '+json.dumps(proposal(payload))+'\n'}]}]}
    console=OperationsConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    env={PASSAGE_FORMATION_MODE_ENV: MODE, LLM_API_KEY_ENV: 'test', LLM_MODEL_ENV: 'test-model'}
    bind_pre_review_semantic_processing(console, environ=env, post_json=post)
    author=console.create_account(username='author', password='strong-test-password', roles=('researcher',))
    reviewer=console.create_account(username='reviewer', password='strong-test-password', roles=('reviewer',))
    receipt=console.ingest(actor_id=author['account_id'], filename='test.html',
        data=f'<html><body><h1>Screening</h1><p>{TEXT}</p></body></html>'.encode(),
        content_type='text/html', ingest_kind='new', title='Test', version='1.0', date='2026-09-29',
        live_url='', class_='richtlijn', family='test', named_reviewers=[reviewer['account_id']])
    sid=receipt['snapshot_id']
    persisted=console.snapshot_objects(sid, include_blocked=True)
    target=next(o for o in persisted if KEY in (o.get('metadata') or {}))
    assert target['metadata']['admission']['gate_result']=='allowed'
    assert len(calls)==1
    from copy import deepcopy
    evidence = deepcopy(console._envelope(sid)['semantic_replay']['provider_evidence'])
    assert evidence['request'] == calls[0]
    assert evidence['response']['id'] == 'response-origin'
    assert evidence['response']['input_tokens'] == 123
    assert evidence['response']['output_text'] == ' '+json.dumps(proposal(calls[0]))+'\n'
    assert 'Authorization' not in json.dumps(evidence)
    assert 'must-not-persist' not in json.dumps(evidence)
    restarted=OperationsConsole(root=tmp_path, source_store=tmp_path/'sources', runtime=tmp_path/'runtime')
    bind_pre_review_semantic_processing(restarted, environ=env, post_json=post)
    assert restarted._envelope(sid)['semantic_replay']['provider_evidence'] == evidence
    assert any(KEY in (o.get('metadata') or {}) for o in restarted.snapshot_objects(sid, include_blocked=True))
    restarted.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert len(calls)==1  # exact v2 identity reuses only validated v2 proposal
    assert restarted._envelope(sid)['semantic_replay']['provider_evidence'] == evidence
    # The authorized HTTP download resolves its compact revision and contains the
    # origin call, without mutating the current document or inventing a new call.
    import csv, io
    from zipfile import ZipFile
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app, COOKIE
    client = TestClient(create_console_app(restarted))
    session = restarted.authenticate('reviewer', 'strong-test-password')
    client.cookies.set(COOKIE, session['token'])
    before = deepcopy(restarted._envelope(sid)), restarted.objects_revision(sid)
    response = client.get('/review/processing-evidence-export', params={'document': sid})
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        def rows(name):
            return list(csv.DictReader(io.StringIO(archive.read(name+'.csv').decode('utf-8-sig'))))
        call = rows('model_calls')[0]
        assert json.loads(call['request']) == calls[0]
        assert call['output_text'] == evidence['response']['output_text']
        assert call['call_id'] == 'response-origin' and call['response_status'] == 'completed'
        assert call['run_id'] == '' and call['raw_response'] == ''
        revision = rows('revision')[0]
        assert revision['objects_revision'] == before[1]
        assert all(r['revision_id'] == revision['revision_id'] for r in rows('source_stages'))
        assert 'objects_revision' not in call
        assert 'processing-evidence-export-v5' in archive.read('README.txt').decode()
    assert before == (restarted._envelope(sid), restarted.objects_revision(sid))
    # Even valid JSON from an explicitly incomplete response cannot replace work.
    from src.operations_console_v1 import ConsoleError
    response_status[0] = 'incomplete'
    env[LLM_MODEL_ENV] = 'test-model-next'  # Force a new call, not exact replay.
    with pytest.raises(ConsoleError, match='pre_review_llm_response_not_completed'):
        restarted.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert before == (restarted._envelope(sid), restarted.objects_revision(sid))
    response_status[0] = 'completed'
    # Changing only the contract mode cannot replay v2 as v1.
    from src.pre_review_semantic_v1 import SEMANTIC_MODE
    env[PASSAGE_FORMATION_MODE_ENV]=SEMANTIC_MODE
    with pytest.raises(ValueError, match='semantic_object_contains_untrusted_fields'):
        restarted.reextract_unpublished(actor_id=author['account_id'], snapshot_id=sid)
    assert len(calls)==3
    assert any(KEY in (o.get('metadata') or {}) for o in restarted.snapshot_objects(sid, include_blocked=True))


def test_v2_admission_never_calls_legacy_enricher(monkeypatch):
    import src.admission_gate_v1 as gate
    def forbidden(*args):
        raise AssertionError('v2 called legacy enrichment')
    monkeypatch.setattr(gate, '_enrich_from_text', forbidden)
    assert prepare()[1][1]['metadata']['admission']['gate_result']=='allowed'


@pytest.mark.parametrize('corruption', ['text', 'bounds'])
def test_transform_rechecks_source_instead_of_trusting_derived_metadata(corruption):
    from src.semantic_replay_v1 import stable_json_hash
    spec, _, _ = prepare()
    changed=deepcopy(spec)
    item=changed['objects'][1]
    if corruption == 'text':
        item['text']=item['clean_text']=TEXT+' Nieuwe kennis.'
    else:
        item['semantic_passage']['spans'][0]['end'] = 10000
    record=item[KEY]
    record['candidate_text']=item['text']
    record['binding_hash']=stable_json_hash({k:v for k,v in record.items() if k!='binding_hash'})
    manifest={'canonical_source': {'source_id':'s','title':'t','source_url':'u','source_type':'html',
                                  'source_level':'national','canonicality':'canonical','integrity_status':'verified'}}
    with pytest.raises(ValueError, match='source_bound_candidate_text_mismatch|source_bound_field_bounds_invalid'):
        transform(changed, manifest, [fragment()])


def test_unclassified_v2_preserves_bound_type_and_evidence():
    def unclassified(p):
        p['objects'][0]['proposed_object_type'] = 'unclassified'
        p['objects'][0]['recommendation_semantics'] = None
    _, rows, _ = prepare(unclassified)
    obj = rows[1]
    assert obj['proposed_object_type'] == 'unclassified'
    admission = obj['metadata']['admission']
    assert admission['proposed_type'] == 'unclassified'
    assert 'source_bound_fields_stale' not in admission['reason_codes']
    assert admission['subject_span'] == 'Screening van ouderen'
    assert not obj.get('confirmed_object_type')  # human classification remains pending


@pytest.mark.parametrize('corruption', ['text', 'type', 'hash'])
def test_export_marks_stale_or_invalid_evidence(corruption):
    _, rows, _ = prepare()
    obj = rows[1]
    if corruption == 'text':
        obj['content']['clean_text'] = 'Screening is zinvol.'
    elif corruption == 'type':
        obj['proposed_object_type'] = 'definition'
    else:
        obj['metadata'][KEY]['binding_hash'] = 'invalid'
    rows = apply_admission_gate(rows, klasse='richtlijn', fragments=[fragment()], document_version='1', source_hash='a'*64)
    tables, _ = processing_evidence_tables(snapshot_id='snap', revision='r2', envelope={}, objects=rows)
    field = next(r for r in tables['proposal_fields'] if r['field']=='recommended_action' and r['object_id']==obj['object_id'])
    assert field['value'] == ''
    assert field['producer_status'] == ('invalid_source_bound_proposal' if corruption == 'hash' else 'stale_source_bound_proposal')
