"""Execution/help/management boundaries at the installed HTTP surface.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.console_navigation_simplify_v1 import install_navigation_simplification
from src.operations_console_app import create_console_app
from src.publish_readiness_ui_v1 import install_publish_readiness_ui
from src.review_workboard_v1 import install_review_workboard
from tests.test_vsa_publish_readiness_ui_v1 import _console_with_document, TEST_PASSWORD

pytestmark = [pytest.mark.release_control_scope_belofte, pytest.mark.release_control_toegang,
              pytest.mark.release_control_slop, pytest.mark.release_control_releasebewijs]


class Surface(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.text = []
        self.in_script = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag in {'script', 'style'}:
            self.in_script = True

    def handle_endtag(self, tag):
        if tag in {'script', 'style'}:
            self.in_script = False

    def handle_data(self, text):
        if not self.in_script:
            self.text.append(text)


def client_for(console):
    app = create_console_app(console)
    install_publish_readiness_ui(app, console)
    install_review_workboard(app, console)
    install_navigation_simplification(app)
    return TestClient(app, base_url='https://testserver')


def login(client, username):
    response = client.post('/login', data={'username': username, 'password': TEST_PASSWORD})
    assert response.status_code == 200


def test_task_help_and_management_are_separate_readonly_destinations(tmp_path):
    console, accounts, receipt, _ = _console_with_document(tmp_path)
    sid = receipt['snapshot_id']
    before = deepcopy(console.snapshot_objects(sid)), deepcopy(console._envelope(sid))
    client = client_for(console)
    assert client.get('/help/review').status_code == 401
    assert client.get('/settings/technical/processing', params={'document': sid}).status_code == 401
    login(client, 'researcher.anne')
    for path in ['/ingest', '/review', '/tree']:
        response = client.get(path)
        assert response.status_code == 200
        surface = Surface(response.text)
        text = ' '.join(surface.text)
        assert 'Actieve verwerkingsmodus' not in text
        assert 'admission-contract' not in text
        assert not any(a.get('action') in {'/tree/reprocess', '/tree/processing-recovery'} for _, a in surface.tags)
        assert not any(a.get('href', '').startswith('/review/processing-') for _, a in surface.tags)
        assert any(a.get('href', '').startswith('/help/') for _, a in surface.tags)
    help_page = client.get('/help/review')
    assert help_page.status_code == 200
    assert 'Een definitie legt een begrip uit' in help_page.text
    management = client.get('/settings/technical')
    assert management.status_code == 200
    assert 'Actieve verwerkingsmodus' in management.text
    assert '/settings/technical/processing?document=' in management.text
    diagnostics = client.get('/settings/technical', params={'document': sid})
    assert diagnostics.status_code == 200
    assert 'Diagnostiek en brondekking' in diagnostics.text
    assert not any(a.get('method') == 'post' and a.get('action') == '/review' for _, a in Surface(diagnostics.text).tags)
    assert (console.snapshot_objects(sid), console._envelope(sid)) == before
    stranger = console.create_account(username='stranger', password=TEST_PASSWORD, roles=('reviewer',))
    login(client, stranger['username'])
    assert client.get('/settings/technical/processing', params={'document': sid}).status_code == 400
    assert client.get('/settings/technical', params={'document': sid}).status_code == 400


def test_review_exposes_source_and_explicit_choices_without_embedded_manual(tmp_path):
    console, _, receipt, _ = _console_with_document(tmp_path)
    sid = receipt['snapshot_id']
    client = client_for(console)
    login(client, 'reviewer.bert')
    dashboard = client.get('/review', params={'document': sid}).text
    assert 'review-next-step' in dashboard  # Production middleware must preserve the primary action.
    obj = next(o for o in console.snapshot_objects(sid) if o['object_type'] not in {'document', 'heading'})
    page = client.get('/review', params={'document': sid, 'object': obj['object_id']})
    assert page.status_code == 200
    surface = Surface(page.text)
    assert 'review-decision-layout' in page.text
    assert 'review-source-column' in page.text and 'review-choices-column' in page.text
    assert 'Bronpassage en context' in page.text
    assert 'Een definitie legt een begrip uit' not in page.text
    assert 'why-selected' not in page.text
    radios = [a for tag, a in surface.tags if tag == 'input' and a.get('name') in {'documentpositie_action', 'type_action'}]
    assert len(radios) == 4
    assert all('checked' not in a for a in radios)
    assert len([a for tag, a in surface.tags if tag == 'button' and 'data-submit-review' in a]) == 1
    assert '<summary>Broncontext' not in page.text


def test_blocked_processing_keeps_existing_retry_command_in_management(tmp_path, monkeypatch):
    console, accounts, receipt, _ = _console_with_document(tmp_path)
    sid = receipt['snapshot_id']
    client = client_for(console)
    login(client, 'researcher.anne')
    monkeypatch.setattr(console, 'processing_status', lambda document, actor_id=None: {
        'retry_allowed': True, 'error_code': 'pre_review_llm_provider_unavailable',
        'reason_code': 'pre_review_llm_provider_unavailable', 'retry_not_before': None})
    page = client.get('/settings/technical/processing', params={'document': sid})
    assert page.status_code == 200
    assert 'action="/tree/reprocess"' in page.text and 'name="command_id"' in page.text
    assert 'pre_review_llm_provider_unavailable' in page.text
    commands = []
    monkeypatch.setattr(console, 'retry_pre_review', lambda **kw: commands.append(kw))
    response = client.post('/tree/reprocess', data={'snapshot_id': sid, 'command_id': 'reviewable-retry'}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == f'/settings/technical/processing?document={sid}'
    assert commands == [{'actor_id': accounts['researcher']['account_id'], 'snapshot_id': sid, 'command_id': 'reviewable-retry'}]


def test_publish_keeps_review_recovery_and_hides_technical_diagnosis(tmp_path, monkeypatch):
    console, _, receipt, _ = _console_with_document(tmp_path)
    sid = receipt['snapshot_id']
    monkeypatch.setattr(console, 'consider_publish', lambda **kw: {
        'state': 'captured_not_published', 'publication_ready': False, 'technical_ready': False,
        'curation_ready': True, 'technical_blockers': ['four_eyes_required', 'private_provider_error'],
        'blockers': ['four_eyes_required', 'private_provider_error']})
    client = client_for(console)
    login(client, 'publisher.carla')
    page = client.get('/publish')
    assert page.status_code == 200
    text = ' '.join(Surface(page.text).text)
    assert 'private_provider_error' not in text and 'four_eyes_required' not in text
    assert f'/review?document={sid}' in page.text
    assert 'data-publish-form' not in page.text


@pytest.mark.parametrize(('username', 'digest'), [
    ('researcher.anne', 'ffe8730795faf00d002843a6d99cc039facca04cd634ece88a3fe682fae9efc8'),
    ('reviewer.bert', 'a4f0c2233957f479b498aaea66c8015ec0ace604ed93bd339ce8c83d3b8dcac4'),
])
def test_mijn_werk_matches_reference_render_including_shared_navigation(tmp_path, username, digest):
    console, _, _, _ = _console_with_document(tmp_path)
    client = client_for(console)
    login(client, username)
    response = client.get('/')
    assert response.status_code == 200
    # Exact reference render from main 27ea123; only asset cache version may differ.
    html = re.sub(r'/brand/console.css\?v=[a-f0-9]+', '/brand/console.css?v=ASSET', response.text)
    assert hashlib.sha256(html.encode()).hexdigest() == digest, 'Out-of-scope Mijn werk changed'
    assert sum(tag == 'a' and 'home-tile' in attrs.get('class', '').split() for tag, attrs in Surface(html).tags) == 4
    css = (Path(__file__).parents[1] / 'assets/brand/console.css').read_text()
    original = css.split('\n/* Task-only execution/evidence layout;')[0]
    assert hashlib.sha256(original.encode()).hexdigest() == '1d1c9a4ea0881394f3e22ffaf7cff8958482a401d23e98fe65a947586db98b77'
    # Added selectors must not touch the shared home layout.
    assert '.home-tiles' not in css[len(original):]
