"""Integrated workplace boundaries and historical navigation on native PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from tests.content_review_fixture_support import bind, prepare, snapshot
from tests.test_content_review_workplace import login
from tests.test_insight_diagnostics_navigation_v1 import Links


@pytest.mark.parametrize('kind', ['context', 'classification'])
def test_historical_editor_preserves_passage_and_review_origin(tmp_path, production_console, production_app, kind):
    console = production_console(root=tmp_path, processing_binder=bind)
    actors, docs = prepare(console)
    doc = docs[0]
    sid, oid = doc['snapshot_id'], doc['batch'][0]
    browser = login(console, production_app, actors['a'])
    revision = console.objects_revision(sid)
    params = dict(document=sid, object=oid, review_revision=revision)
    if kind == 'context':
        params.update(context_mode='source', context_q='waarneming')
    else:
        params.update(task='repair', repair_kind='classification')
    before = deepcopy(snapshot(console, docs))
    old = browser.get('/review', params=params, follow_redirects=False)
    assert old.status_code == 303
    owner = urlsplit(old.headers['location'])
    assert owner.path == '/source-selection'
    query = parse_qs(owner.query)
    assert query['document'] == [sid] and query['object'] == [oid]
    assert query.get('review_revision') == [revision]
    if kind == 'context':
        assert query['context_mode'] == ['source'] and query['context_q'] == ['waarneming']
        assert owner.fragment == 'passage-context'
    else:
        assert query.get('repair_kind') == ['classification']
    opened = browser.get(old.headers['location'])
    assert opened.status_code == 200
    back = [parse_qs(urlsplit(href).query) for href in Links(opened.text).hrefs
        if urlsplit(href).path == '/review']
    assert any(row.get('object') == [oid] and row.get('review_revision') == [revision] for row in back)
    assert snapshot(console, docs) == before


def test_mutation_routes_have_one_installed_owner(tmp_path, production_console):
    console = production_console(root=tmp_path, processing_binder=bind)
    app = console._metis_test_application
    commands = ('/source-selection/start', '/review/resolve', '/review/source-context',
                '/review/source-exclusions', '/review/headings/batch-confirm',
                '/tree/processing-recovery', '/inzicht/document/pagina-verantwoorden',
                '/review', '/review/normal-risk/batch-confirm', '/review/second-review',
                '/review/decision-graph', '/review/decision-passage',
                '/review/context/accept', '/review/relations')
    inventory = {}
    for command in commands:
        owners = [route for route in app.routes if getattr(route, 'path', None) == command
                  and 'POST' in (getattr(route, 'methods', None) or ())]
        assert len(owners) == 1, command
        endpoint = owners[0].endpoint
        inventory[command] = endpoint.__module__ + ':' + endpoint.__qualname__
    if output := os.environ.get('WORKPLACE_INSTALLED_ROUTES_OUTPUT'):
        Path(output).write_text(json.dumps(inventory, indent=2) + '\n')
