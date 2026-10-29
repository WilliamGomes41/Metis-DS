"""Bounded Review retains the existing processing-to-review quality evidence.

# release-control-evidence: scope/belofte opslag stale recovery
# release-control-evidence: kwaliteit metrics slop releasebewijs
"""
from copy import deepcopy

from fastapi.testclient import TestClient

from src.settings.quality_evidence_v1 import RUNS, review_evidence
from tests.production_support import restart_production
from tests.test_review_command_bounded_http_v1 import bounded_post_only, submission
from tests.test_review_formation_problems import FIRST, execute, received


def test_bounded_http_quality_audit_matches_full_authoritative_envelope(
    tmp_path, production_console, production_app, monkeypatch,
):
    console, sid, author, _reviewer, _calls, mode, _provider = received(
        tmp_path, production_console, monkeypatch)
    mode['broken'] = False
    execute(console, sid, author, 'bounded-quality-audit')
    documents = console.workflow_document_store
    focal = next(obj for obj in console.snapshot_objects(sid)
                 if obj.get('proposed_object_type') == 'recommendation'
                 and obj['content']['clean_text'] == FIRST)
    envelope = documents.get_envelope(sid)
    latest = deepcopy(envelope[RUNS][-1])
    first = next(row for row in latest['candidates'] if row['object_id'] == focal['object_id'])
    assert first['origin']['route'] != 'unknown'
    # The established oracle uses the latest run and first matching candidate.
    # A later duplicate must not replace that original evidence.
    duplicate = deepcopy(first)
    duplicate['origin'] = {'route': 'unknown'}
    duplicate['fingerprint']['text'] = 'later-duplicate-is-not-the-baseline'
    latest['candidates'].append(duplicate)
    old = deepcopy(latest)
    old['run_id'] = 'obsolete-run-must-not-be-used'
    envelope[RUNS] = [old, latest]
    documents.write_bundle(envelope=envelope, objects=documents.list_document_objects(sid))
    authoritative = documents.get_envelope(sid)

    projected = documents.review_command_quality_input(sid, [focal['object_id']])
    assert projected == [{'run_id': latest['run_id'], 'candidates': [first, duplicate]}]
    assert 'source_fragments' not in projected[0]
    assert 'document_extraction' not in projected[0]

    with TestClient(production_app(console), base_url='https://testserver') as client:
        assert client.post('/login', data={'username': 'reviewer', 'password': 'fixture-only'},
                           follow_redirects=False).status_code == 303
        page = client.get('/review', params={'document': sid, 'object': focal['object_id']})
        assert page.status_code == 200
        with bounded_post_only(console, sid, monkeypatch):
            saved = client.post('/review', data=submission(page, sid, focal), follow_redirects=False)
        assert saved.status_code == 303

    after = next(obj for obj in console.snapshot_objects(sid) if obj['object_id'] == focal['object_id'])
    expected = review_evidence(authoritative, focal, after)
    assert expected['run_id'] == latest['run_id']
    assert expected['origin'] == first['origin']
    assert expected['origin']['route'] != 'unknown'

    def quality_events(owner):
        return [event['details']['quality_evidence']
                for event in owner.workflow_review_store.read_events()
                if event.get('object_id') == focal['object_id']
                and (event.get('details') or {}).get('quality_evidence')]

    assert quality_events(console) == [expected]
    assert documents.get_envelope(sid)[RUNS] == authoritative[RUNS]
    assert quality_events(restart_production(console)) == [expected]
