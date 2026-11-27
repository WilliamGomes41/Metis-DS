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


from tests.content_review_fixture_support import bind, prepare, snapshot
from tests.test_content_review_workplace import login


def test_removed_editors_leave_review_evidence_intact(tmp_path, production_console, production_app):
    console = production_console(root=tmp_path, processing_binder=bind)
    actors, docs = prepare(console)
    doc = docs[0]
    sid, oid = doc['snapshot_id'], doc['batch'][0]
    browser = login(console, production_app, actors['a'])
    revision = console.objects_revision(sid)
    before = deepcopy(snapshot(console, docs))
    for route, query in (
        ('/source-selection', {'task': 'structure'}),
        ('/source-selection', {'task': 'repair'}),
        ('/source-selection', {'task': 'repair', 'object': oid, 'repair_kind': 'classification'}),
        ('/source-selection', {'task': 'continuation', 'object': oid}),
        ('/source-selection', {'object': oid}),
        ('/source-selection', {'selected_document': sid, 'object': oid, 'context_mode': 'source'}),
        ('/review', {'task': 'structure'}),
        ('/review', {'task': 'repair', 'object': oid, 'repair_kind': 'classification'}),
        ('/review', {'object': oid, 'context_mode': 'source', 'context_q': 'waarneming'}),
    ):
        params = {'document': sid, 'review_revision': revision, **query}
        response = browser.get(route, params=params, follow_redirects=False)
        assert response.status_code == 404, (route, query)
        assert 'location' not in response.headers
    assert browser.post("/review/source-context", data={"snapshot_id": sid, "source_object_id": oid}).status_code == 404
    assert snapshot(console, docs) == before


def test_mutation_routes_have_one_installed_owner(tmp_path, production_console):
    console = production_console(root=tmp_path, processing_binder=bind)
    app = console._metis_test_application
    commands = ('/source-selection/start', '/review/resolve',
                '/review/source-exclusions', '/review/headings/batch-confirm',
                '/tree/processing-recovery', '/inzicht/document/pagina-verantwoorden',
                '/review', '/review/normal-risk/batch-confirm', '/review/second-review',
                '/review/decision-graph', '/review/decision-passage',
                '/review/relations')
    inventory = {}
    for command in commands:
        owners = [route for route in app.routes if getattr(route, 'path', None) == command
                  and 'POST' in (getattr(route, 'methods', None) or ())]
        assert len(owners) == 1, command
        endpoint = owners[0].endpoint
        inventory[command] = endpoint.__module__ + ':' + endpoint.__qualname__
    if output := os.environ.get('WORKPLACE_INSTALLED_ROUTES_OUTPUT'):
        Path(output).write_text(json.dumps(inventory, indent=2) + '\n')
