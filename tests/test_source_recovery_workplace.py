"""C: one editable workplace, unchanged native accounting/grant owners.

# release-control-evidence: scope/belofte opslag concurrent stale interrupt retry version-compat recovery
# release-control-evidence: toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
from html import escape

from fastapi.testclient import TestClient

from tests.source_recovery_workplace_support import blocked_source
from tests.test_availability_repair import accounts, login
from tests.production_support import restart_production


def client(console, production_app, username='author'):
    result = TestClient(production_app(console), base_url='https://testserver')
    login(result, username)
    return result


def test_page_accounting_owner_errors_and_native_restart(tmp_path, *, production_console, production_app):
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    author, reviewer = accounts(console)
    console.create_account(username='outsider', password='fixture-only', roles=('reviewer',))
    sid = blocked_source(console, author, reviewer, 'page-accounting', pages=True)
    browser = client(console, production_app)
    before = deepcopy(console._envelope(sid))
    for url in ('/inzicht/document?document=' + sid, '/source-selection?document=' + sid):
        response = browser.get(url)
        assert response.status_code == 200
        assert ('action="/inzicht/document/pagina-verantwoorden"' in response.text) is url.startswith('/source-selection')
    assert console._envelope(sid) == before
    command = dict(snapshot_id=sid, page=2, category='colofon_of_copyright',
                   note='Alleen copyright, geen kennis: <test> & controle.')
    for bad in (dict(command, category='invalid'), dict(command, note='kort'), dict(command, page=99)):
        response = browser.post('/inzicht/document/pagina-verantwoorden', data=bad)
        assert response.status_code == 400 and '<h1>Vorming</h1>' in response.text
        assert console._envelope(sid) == before
    response = browser.post('/inzicht/document/pagina-verantwoorden', data=dict(command, category='invalid'))
    assert escape(command['note'], quote=True) in response.text
    outsider = client(console, production_app, 'outsider')
    assert outsider.post('/inzicht/document/pagina-verantwoorden', data=command).status_code == 400
    assert console._envelope(sid) == before
    response = browser.post('/inzicht/document/pagina-verantwoorden', data=command, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers['location'] == '/source-selection?document=' + sid + '#paginas'
    saved = restart_production(console)._envelope(sid)
    row, = saved['source_page_accountings']
    assert row['page'] == 2 and row['reasons'] == ['docling_page_text_unverified']
    assert row['source_sha256'] == before['sha256'] and row['attempt_id'] == before['processing_attempts'][-1]['attempt_id']
    assert row['note'] == command['note'] and row['actor_id'] == author
    assert saved['processing_attempts'] == before['processing_attempts']
    assert not console.snapshot_objects(sid)
    assert browser.post('/inzicht/document/pagina-verantwoorden', data=command).status_code == 400
    assert restart_production(console)._envelope(sid) == saved
    assert 'Verantwoord; start de verwerking opnieuw.' in browser.get(response.headers['location']).text


def test_grant_only_authorizes_and_publisher_only_caller_is_preserved(tmp_path, *, production_console, production_app):
    console = production_console(root=tmp_path, processing_binder=lambda console: None)
    author, reviewer = accounts(console)
    sid = blocked_source(console, author, reviewer, 'recovery-grant')
    browser = client(console, production_app)
    before = deepcopy(console._envelope(sid))
    owner = browser.get('/source-selection?document=' + sid)
    assert owner.status_code == 200 and 'action="/tree/processing-recovery"' in owner.text
    assert 'action="/tree/processing-recovery"' not in browser.get('/inzicht/document?document=' + sid).text
    assert console._envelope(sid) == before
    response = browser.post('/tree/processing-recovery', data={'snapshot_id': sid, 'reason': '   '})
    assert response.status_code == 400 and '<h1>Vorming</h1>' in response.text
    assert console._envelope(sid) == before
    assert client(console, production_app, 'reviewer').post('/tree/processing-recovery',
        data={'snapshot_id': sid, 'reason': 'Dit account is geen publisher.'}).status_code == 403
    response = browser.post('/tree/processing-recovery', data={'snapshot_id': sid, 'reason': 'Controleer exact deze bron.'}, follow_redirects=False)
    assert response.status_code == 303 and response.headers['location'].endswith('#processing-recovery')
    after = restart_production(console)._envelope(sid)
    grant = after['processing_recovery']
    assert grant['consumed_by'] is None and grant['source_hash'] == before['sha256']
    assert grant['source_version'] == before['version']
    assert after['processing_attempts'] == before['processing_attempts']
    assert browser.post('/tree/processing-recovery', data={'snapshot_id': sid, 'reason': 'Dubbel'}).status_code == 400
    for url in (response.headers['location'], '/inzicht/document?document=' + sid):
        assert browser.get(url).status_code == 200
    assert restart_production(console)._envelope(sid) == after
    # This supported non-UI publisher has no source-selection/read/start authority.
    publisher = console.create_account(username='publisher-only', password='fixture-only', roles=('publisher', 'reviewer'))['account_id']
    other = blocked_source(console, author, publisher, 'publisher-only-grant')
    console.assign_roles(actor_id=author, account_id=publisher, roles=('publisher',))
    direct = client(console, production_app, 'publisher-only')
    result = direct.post('/tree/processing-recovery', data={'snapshot_id': other, 'reason': 'Bestaande directe publisher-opdracht.'}, follow_redirects=False)
    assert result.status_code == 303 and result.headers['location'].startswith('/inzicht/document?')
    assert direct.get(result.headers['location']).status_code == 200
    assert direct.get('/source-selection?document=' + other).status_code == 403
    assert restart_production(console)._envelope(other)['processing_recovery']['consumed_by'] is None


def test_accounting_cannot_rewrite_a_formed_source(tmp_path, *, production_console, production_app):
    from tests.test_vsa_publish_readiness_ui_v1 import _console_with_document, TEST_PASSWORD
    console, _, receipt, _ = _console_with_document(tmp_path, production_console=production_console)
    sid = receipt['snapshot_id']
    before = deepcopy((console._envelope(sid), console.snapshot_objects(sid), console.object_review_bindings(sid)))
    assert before[1]
    browser = TestClient(production_app(console), base_url='https://testserver')
    browser.post('/login', data={'username': 'researcher.anne', 'password': TEST_PASSWORD})
    result = browser.post('/inzicht/document/pagina-verantwoorden', data=dict(snapshot_id=sid, page=2,
        category='colofon_of_copyright', note='Dit mag de al gevormde bron niet wijzigen.'))
    assert result.status_code == 400
    restarted = restart_production(console)
    assert (restarted._envelope(sid), restarted.snapshot_objects(sid), restarted.object_review_bindings(sid)) == before
