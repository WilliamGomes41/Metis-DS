"""Compact native workboard presentation inputs; Review rules remain owners.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest
from tests.test_d5_4_review_interaction_evidence import _system
from tests.test_insight_v1 import _login
from src.review.review_interaction_v1 import _is_decision_event
from src.review.four_eyes_v1 import is_forbidden_reviewer


def started(events, account):
    result = set()
    for event in events:
        if not (_is_decision_event(event) or event.get('event_type') == 'review_audit_evidence'):
            continue
        details = event.get('details') or {}
        reviewer = str(details.get('reviewer_id') or details.get('reviewer_account_id') or '')
        actor = str(event.get('actor') or '').strip()
        own = reviewer == account['account_id'] if reviewer else actor in {account['account_id'], account.get('username')}
        if own and not is_forbidden_reviewer(actor):
            result.add(str(details.get('snapshot_id') or ''))
    return result


@pytest.mark.parametrize('azure',[False,True])
def test_workboard_metadata_never_evaluates_full_archive(tmp_path, production_console, azure):
    console, users, sid, _ = _system(tmp_path,
        production_console=lambda **options: production_console(azure=azure,**options))
    store = console.workflow_document_store
    expected = console.review_workboard_summaries(users['reviewer_a']['account_id'],metadata_only=True)
    assert sid in expected
    assert expected[sid]['envelope']['named_reviewers']
    before = deepcopy(store.get_envelope(sid))
    with store._connect() as con:
        con.execute('ALTER TABLE workflow.documents DISABLE TRIGGER USER')
        try:
            # The old JSONB subtraction raises on scalar null. The valid compact
            # cache must supply every selected metadata field independently.
            con.execute("UPDATE workflow.documents SET envelope_payload='null'::jsonb WHERE snapshot_id=%s",(sid,))
            con.commit()
            assert console.review_workboard_summaries(users['reviewer_a']['account_id'],metadata_only=True) == expected
            # Explicit nullable compatibility path: consume existing authority
            # without silently preparing or writing a projection on GET.
            con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb,review_read_envelope=NULL '
                        'WHERE snapshot_id=%s',(json.dumps(before),sid))
            con.commit()
            assert console.review_workboard_summaries(users['reviewer_a']['account_id'],metadata_only=True) == expected
            assert con.execute('SELECT review_read_envelope FROM workflow.documents WHERE snapshot_id=%s',
                               (sid,)).fetchone()['review_read_envelope'] is None
        finally:
            con.execute('ALTER TABLE workflow.documents ENABLE TRIGGER USER')
            con.execute('UPDATE workflow.documents SET envelope_payload=%s::jsonb WHERE snapshot_id=%s',(json.dumps(before),sid))
    assert store.get_envelope(sid) == before


@pytest.mark.parametrize('history_size,azure',[(32,False),(128,True)])
def test_compact_participation_matches_existing_rules_after_restart(tmp_path, production_console, history_size, azure):
    from tests.production_support import restart_production
    console, users, sid, oid = _system(tmp_path,
        production_console=lambda **options: production_console(azure=azure,**options))
    account = users['reviewer_a']
    rows = [
        ('object_review_approve',account['username'],{'reviewer_id':account['account_id']}),
        ('second_review_approve',users['reviewer_b']['username'],{'reviewer_id':users['reviewer_b']['account_id']}),
        ('review_audit_evidence',account['username'],{'reviewer_account_id':account['account_id']}),
        ('object_review_revise',account['username'],{}),
        ('object_review_reject','Metis',{'reviewer_id':account['account_id']}),
        ('source_context_changed',account['username'],{}),
        ('object_review_approve',account['username'],{'reviewer_id':users['reviewer_b']['account_id']}),
        ('object_review_approve',account['account_id'],{}),
    ]
    for index in range(history_size):
        kind, actor, details = rows[index % len(rows)]
        console.workflow_review_store.append_event(event_type=kind,object_id=oid,object_version='1.0.0',actor=actor,
            details={**details,'snapshot_id':sid,'unused_archive':'fixture-only-'+('x'*65536)})
    console = restart_production(console)
    store = console.workflow_review_store
    old = store.read_events_for_snapshots([sid])
    compact = store.read_review_participation_events([sid])
    assert started(compact, account) == started(old,account) == {sid}
    # Compare each header separately: an earlier own decision must not hide a
    # regression in foreign/forbidden actors or the reviewer-ID precedence.
    headers = [{
        'event_type': e.get('event_type'), 'actor': e.get('actor'),
        'details': {k:(e.get('details') or {}).get(k)
                    for k in ('snapshot_id','reviewer_id','reviewer_account_id')},
    } for e in old]
    assert {json.dumps(e,sort_keys=True) for e in compact} == {json.dumps(e,sort_keys=True) for e in headers}
    for original, header in zip(old,headers):
        assert started([original],account) == started([header],account)
    assert len(json.dumps(old)) > history_size * 65536
    assert len(compact) <= len(rows)+4
    assert len(json.dumps(compact)) < 5000
    assert all(set(e)=={'event_type','actor','details'} for e in compact)
    assert all(set(e['details']) <= {'snapshot_id','reviewer_id','reviewer_account_id'} for e in compact)
    assert store.read_review_participation_events([]) == []
    with store._connect() as con:
        con.execute('SET LOCAL enable_seqscan=off')
        plan = con.execute("EXPLAIN SELECT event_payload->'actor' FROM workflow.review_events "
                           "WHERE event_payload->'details'->>'snapshot_id'=ANY(%s)",([sid],)).fetchall()
    assert 'workflow_review_events_document_history' in str(plan)


def test_native_workboard_does_not_read_review_event_archives(tmp_path, production_console, production_app, monkeypatch):
    console, users, sid, _ = _system(tmp_path,production_console=production_console)
    client = _login(console,users['reviewer_a']['username'],production_app=production_app)
    def forbidden(*a,**k):
        raise AssertionError('A personal start/continue link may not load event archives')
    monkeypatch.setattr(console.workflow_review_store,'read_events_for_snapshots',forbidden)
    page = client.get('/review')
    assert page.status_code == 200 and sid in page.text


def test_current_workboard_requires_source_bytes_even_with_retained_extraction(tmp_path, production_console):
    """Counterexample for a source-proof-only future cutover, without mocks."""
    from src.review.review_workboard_v1 import review_work_item
    console, users, sid, _ = _system(tmp_path,production_console=production_console)
    envelope = console._envelope(sid)
    assert console.immutable_source_store is None
    source = console._source_cache_path(envelope)
    original = source.read_bytes()
    metadata = console.review_workboard_summaries(users['reviewer_a']['account_id'],metadata_only=True)
    before = review_work_item(console,account=users['reviewer_a'],envelope=envelope)
    assert before['review_duties'] > 0
    try:
        source.write_bytes(b'x' * len(original))
        assert source.stat().st_size == len(original)
        assert console.review_workboard_summaries(users['reviewer_a']['account_id'],metadata_only=True) == metadata
        after = review_work_item(console,account=users['reviewer_a'],envelope=envelope)
        assert after['review_duties'] == 0
    finally:
        source.write_bytes(original)
