"""#851: readable source grouping retains every finding and all authority.

# release-control-evidence: scope/belofte toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from html import escape
import re

import pytest
from fastapi.testclient import TestClient

from src.formation_problems_v1 import _source_excerpt, collect
from src.source_selection_ui_v1 import _formation_groups, _formation_problem_html
from tests.test_review_formation_problems import received, execute, SECOND
from tests.test_availability_repair import login


@pytest.mark.parametrize('span', [
    {'block_id': 'missing', 'start': 0, 'end': 4},
    {'block_id': 'b', 'start': 0, 'end': 30},
    {'block_id': 'b', 'start': -1, 'end': 4},
])
def test_unverified_source_location_never_gets_a_quote(span):
    assert _source_excerpt([span], {'b': (0, {'text': 'Advies.'})}) is None


def test_only_identical_known_ranges_group_and_quotes_are_escaped():
    text = '<script>alert("bron")</script>'
    span = {'block_id': 'b', 'start': 0, 'end': len(text)}
    excerpt = _source_excerpt([span], {'b': (0, {'text': text})})
    def row(pid, *, ref=span, quote=excerpt):
        return {'problem_id': pid * 64, 'spans': [ref], 'source_excerpt': quote,
                'title': 'Controle nodig', 'code': 'fixture', 'expected_condition': 'Controleer de bron.',
                'actions': [{'url': '/inzicht/document?document=fixture', 'label': 'Diagnose en herstelvoorwaarden'}]}
    rows = [row('a'), row('b'), row('c', ref={**span, 'end': len(text)-1}),
            row('d', quote=None), row('e', quote=None)]
    before = deepcopy(rows)
    groups = _formation_groups(rows)
    assert sorted(map(len, groups)) == [1, 1, 1, 2]
    html = ''.join(_formation_problem_html(g, escape) for g in groups)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert set(re.findall(r'id="problem-([a-e]{64})"', html)) == {row['problem_id'] for row in rows}
    assert rows == before


def test_real_problem_page_shows_source_without_losing_findings_or_writing(tmp_path, production_console, monkeypatch):
    console, sid, author, reviewer, calls, mode, _ = received(tmp_path, production_console, monkeypatch)
    client = TestClient(console._metis_test_application)
    login(client)
    initial = client.get('/formation-problems', params={'document': sid})
    assert 'Nog geen verwerkingsresultaat' in initial.text and not calls
    execute(console, sid, author, 'clarity-initial')
    before = deepcopy(console._envelope(sid)), console.snapshot_objects(sid), console.object_review_bindings(sid)
    report = collect(console, actor_id=author, snapshot_id=sid)
    assert len(report['problems']) == 2
    assert all(row['source_excerpt']['quotes'][0]['text'] == SECOND for row in report['problems'])
    page = client.get('/formation-problems', params={'document': sid})
    assert page.status_code == 200 and '1 bronstuk · 2 meldingen' in page.text
    assert page.text.count('class="formation-item"') == 1
    assert SECOND in page.text and 'Technische details' in page.text
    assert set(re.findall(r'id="problem-([0-9a-f]{64})"', page.text)) == {row['problem_id'] for row in report['problems']}
    assert before == (console._envelope(sid), console.snapshot_objects(sid), console.object_review_bindings(sid))
    assert len(calls) == 3 and 'source_formation_incomplete' in console.publication_readiness(sid)['blockers']
