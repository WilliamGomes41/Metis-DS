"""#860: personal actionability, unchanged authority, bounded reads and GET state.

# release-control-evidence: scope/belofte toegang kwaliteit slop releasebewijs
# release-control-evidence: opslag durable recovery stale
"""
from collections import Counter
from copy import deepcopy
import re

import pytest
from fastapi.testclient import TestClient

from src.review.review_duty_v1 import reviewer_route_for
from src.review.review_workboard_v1 import _workboard_page, review_work_item
from tests.personal_review_fixture_support import PASSWORD, bind, prepare, snapshot
from tests.production_support import restart_production


def card(html, sid):
    return re.search(r'<article[^>]*data-workboard-document="'+sid+r'".*?</article>', html, re.S).group()


@pytest.fixture
def mixed(tmp_path, production_console):
    console = production_console(root=tmp_path, processing_binder=bind)
    accounts, docs = prepare(console)
    return console, accounts, docs


def test_native_mixed_personal_populations_parity_and_read_only_restart(mixed):
    console, accounts, docs = mixed
    before = snapshot(console, docs)
    expected = {'a': {'Gemengd': ({docs['Gemengd']['context'], docs['Gemengd']['batch']}, 0),
                      'Wachten': (set(), 0), 'Klaar': (set(), 0), 'Bronwerk': (set(), 0),
                      'Vergelijkbaar': ({docs['Vergelijkbaar']['batch']}, 0)},
                'b': {'Gemengd': (set(), 0),
                      'Wachten': ({docs['Wachten']['context'], docs['Wachten']['batch']}, 2),
                      'Klaar': (set(), 0), 'Bronwerk': (set(), 0), 'Vergelijkbaar': (set(), 0)}}
    for who in ('a', 'b'):
        actor = accounts[who]
        summaries = console.review_workboard_summaries(actor['account_id'])
        html = _workboard_page(console, account=actor)
        for name, (ids, second) in expected[who].items():
            sid = docs[name]['snapshot_id']
            objects = console.snapshot_objects(sid)
            bindings = console.object_review_bindings(sid)
            fragments = console.review_source_fragments(sid)
            actual = {row['object_id'] for row in objects if (route := reviewer_route_for(row,
                review_path='richtlijn', reviewer_id=actor['account_id'], bindings=bindings,
                fragments=fragments)) and route['actionable']}
            assert actual == ids  # Exact candidate sets, not screenshot totals.
            obj_item = review_work_item(console, account=actor, envelope=console._envelope(sid))
            native = summaries[sid]['work_item']
            for field in ('actionable_review_duties', 'actionable_second_review_duties', 'review_duties', 'next_href'):
                assert native[field] == obj_item[field]
            rendered = card(html, sid)
            assert rendered.count('data-personal-review-action') == bool(ids)
            if ids:
                assert f'data-personal-open>{len(ids)}<' in rendered
                assert f'data-personal-first>{len(ids)-second}<' in rendered
                assert f'data-personal-second>{second}<' in rendered
            elif name in ('Gemengd', 'Wachten', 'Vergelijkbaar'):
                assert 'data-personal-state="waiting"' in rendered
            else:
                assert 'data-personal-state="complete"' in rendered
            if name == 'Vergelijkbaar' and who == 'a':
                assert 'task=batch' in rendered
            assert 'data-open-work-ratio' not in rendered and '<details' not in rendered
        for old in ('data-review-work-queues', 'data-review-task-dashboard', 'data-review-participants', 'data-source-category'):
            assert old not in html
    assert snapshot(console, docs) == before
    fresh = restart_production(console)
    assert snapshot(fresh, docs) == before
    assert card(_workboard_page(fresh, account=accounts['a']), docs['Gemengd']['snapshot_id']).count('data-personal-review-action') == 1
    assert 'data-workboard-document' not in _workboard_page(fresh, account=accounts['outsider'])


def test_real_review_changes_only_own_current_work_and_label(mixed, production_app):
    console, accounts, docs = mixed
    client = TestClient(production_app(console), base_url='https://testserver')
    assert client.post('/login', data={'username': accounts['a']['username'], 'password': PASSWORD}, follow_redirects=False).status_code == 303
    sid = docs['Gemengd']['snapshot_id']
    # The reject was this actor's real decision; other actors' approvals on other documents do not start this one.
    assert '>Verder beoordelen</a>' in card(client.get('/review').text, sid)
    waiting = docs['Wachten']['snapshot_id']
    page_b = _workboard_page(console, account=accounts['b'])
    assert '>Beginnen</a>' in card(page_b, waiting)
    console.review_object(actor_id=accounts['a']['account_id'], snapshot_id=sid, object_id=docs['Gemengd']['context'],
                          decision='approve', confirmed_object_type='recommendation', recommendation_direction='for',
                          recommendation_strength_level='not_stated')
    after = client.get('/review').text
    assert 'data-personal-open>1<' in card(after, sid)
    assert 'task=contextual' in card(after, sid)
    assert 'data-personal-second>1<' in card(_workboard_page(console, account=accounts['b']), sid)
    assert '>Beginnen</a>' in card(_workboard_page(console, account=accounts['b']), sid)
    # The existing exact binding authority is invalidated, not a separate progress cursor.
    rows = console.workflow_review_store.read_bindings([sid])[sid]
    for row in rows:
        row['valid'] = False
    console.workflow_review_store.replace_snapshot_bindings(sid, rows)
    fresh = restart_production(console)
    assert 'data-personal-open>2<' in card(_workboard_page(fresh, account=accounts['a']), sid)
    assert 'data-personal-state="waiting"' in card(_workboard_page(fresh, account=accounts['b']), sid)


def test_metadata_page_bounds_existing_enrichment_and_history_reads(mixed, monkeypatch):
    console, accounts, docs = mixed
    actor = accounts['a']
    real = console.review_workboard_summaries(actor['account_id'], metadata_only=True)
    # 25 no-current-work cards followed by an open card; never infer global empty from page one.
    source = real[docs['Bronwerk']['snapshot_id']]
    metadata = {f'page-{i}': {**deepcopy(source), 'envelope': {**deepcopy(source['envelope']),
        'snapshot_id': f'page-{i}', 'title': f'Bron {i}'}} for i in range(25)}
    open_sid = docs['Gemengd']['snapshot_id']
    metadata[open_sid] = real[open_sid]
    calls = Counter()
    monkeypatch.setattr(console, 'review_workboard_summaries', lambda *args, **kwargs: deepcopy(metadata))
    real_enrich = console._enrich_review_workboard_summaries
    base_item = review_work_item(console, account=actor, envelope=source['envelope'])
    def enrich(account_id, selected):
        calls['enrich'] += 1
        calls['visible'] += len(selected)
        for sid, summary in selected.items():
            if sid.startswith('page-'):
                summary['work_item'] = {**deepcopy(base_item), 'snapshot_id': sid, 'envelope': summary['envelope']}
            else:
                real_enrich(account_id, {sid: summary})
    monkeypatch.setattr(console, '_enrich_review_workboard_summaries', enrich)
    reader = console.workflow_review_store.read_review_participation_events
    history_pages = []
    def history(ids):
        calls['history'] += 1
        assert len(ids) <= 25
        history_pages.append(list(ids))
        return reader(ids)
    monkeypatch.setattr(console.workflow_review_store, 'read_review_participation_events', history)
    monkeypatch.setattr(console.workflow_review_store, 'read_events_for_snapshots',
        lambda *args, **kwargs: pytest.fail('Personal participation must not read full audit archives'))
    monkeypatch.setattr(console, 'list_accounts', lambda: pytest.fail('No participant roster reader on personal landing'))
    first = _workboard_page(console, account=actor, theme='personal')
    assert calls == Counter(enrich=1, visible=25, history=1)
    assert history_pages == [[f'page-{i}' for i in range(25)]]
    assert 'Op deze pagina heb je geen uitvoerbare beoordelingen.' in first
    assert open_sid not in first
    assert 'theme=personal' in first and 'page=2' in first
    second = _workboard_page(console, account=actor, page=2)
    assert calls == Counter(enrich=2, visible=26, history=2)
    assert history_pages[1] == [open_sid]
    assert 'data-personal-open>2<' in card(second, open_sid)
