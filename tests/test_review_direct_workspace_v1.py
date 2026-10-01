"""Direct workspace navigation stays scoped and never writes review state.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.review_workboard_v1 import install_review_workboard


class Console:
    _ledger_path = None

    def __init__(self, *, roles=('reviewer',), documents=()):
        self.roles = roles
        self.documents = dict(documents)

    def list_envelopes(self):
        return [{**d['envelope'], 'snapshot_id': sid} for sid, d in self.documents.items()]

    def list_accounts(self):
        return [{'account_id': i, 'display_name': i} for i in {i for d in self.documents.values() for i in d['envelope']['named_reviewers']}]

    def session_account(self, token):
        if not token:
            raise ConsoleError('not_authenticated')
        return {'account_id': token, 'roles': self.roles}

    def waiting_task_counts(self, account):
        return {}

    def document_lifecycle_status(self, snapshot):
        return self.documents[snapshot].get('lifecycle', {
            'workflow_status': 'processing', 'release_status': 'none',
            'serving_status': 'inactive', 'presentation_status': 'in_review',
        })

    def review_workboard_summaries(self, account, snapshot=None):
        return {key: value for key, value in self.documents.items()
                if account in value['envelope']['named_reviewers']
                and (snapshot is None or snapshot == key)}


def document(title, *, reviewers=('reviewer',), waiting=False, closed=False):
    result = {
        'envelope': {'title': title, 'version': '1.0', 'class': 'richtlijn',
                     'family': 'Test', 'state': 'in_review', 'named_reviewers': reviewers},
        'progress_total': 10, 'progress_done': 2,
        'heading_total': 10, 'heading_pending': 8, 'review_duties': 8,
        'structure_review_duties': 8,
        'actionable_review_duties': 0 if waiting else 8,
        'actionable_structure_duties': 0 if waiting else 8,
        'waiting_for_reviewer_duties': 8 if waiting else 0,
    }
    if closed:
        result['lifecycle'] = {'workflow_status': 'closed', 'release_status': 'published',
                               'serving_status': 'inactive', 'presentation_status': 'withdrawn'}
    return result


def client(console, *, login=True):
    from src.operations_console_app import COOKIE
    app = FastAPI()

    @app.exception_handler(ConsoleError)
    async def error(request, exc):
        return JSONResponse({'error': str(exc)}, status_code=403)

    @app.get('/review')
    def old_review():
        raise AssertionError('replaced route')

    @app.post('/review/headings/batch-confirm')
    def headings():
        raise AssertionError('not used')

    install_review_workboard(app, console)
    result = TestClient(app)
    if login:
        result.cookies.set(COOKIE, 'reviewer')
    return result


def test_single_document_contains_collapsed_work_and_is_read_only():
    console = Console(documents=[('one', document('Document A'))])
    before = deepcopy(console.documents)
    response = client(console).get('/review')
    assert response.status_code == 200
    assert 'Jouw open werk' in response.text
    assert 'Document A' in response.text
    assert 'Ga verder' in response.text
    assert '8 te controleren · 2 afgerond' in response.text
    assert 'data-review-workboard' not in response.text
    assert '<details class="review-document-picker">' not in response.text
    assert console.documents == before


def test_multiple_documents_expand_without_leaking_assignments():
    console = Console(documents=[('wait', document('Waiting', waiting=True)),
                                 ('active', document('Active <safe>')),
                                 ('private', document('Private', reviewers=('other',)))])
    browser = client(console)
    response = browser.get('/review')
    assert response.status_code == 200
    assert response.text.count('<details class="doc-card document-disclosure review-document-card"') == 2
    assert 'Active &lt;safe&gt;' in response.text
    assert 'review-document-card" open' not in response.text
    assert 'wacht op een andere onafhankelijke reviewer' in response.text
    assert 'Private' not in response.text
    waiting = browser.get('/review?document=wait')
    assert waiting.status_code == 200
    assert '8 wachten op een andere beoordelaar' in waiting.text
    selected = waiting.text.split('review-document-card" open>', 1)[1].split('</details>', 1)[0]
    assert 'class="review-task-card"' not in selected
    assert 'task=waiting' in waiting.text
    readonly = browser.get('/review?document=private', follow_redirects=False)
    assert readonly.status_code == 303
    assert readonly.headers['location'] == '/review/trajectory?document=private'


def test_closed_document_with_stale_duties_has_history_not_continuation():
    response = client(Console(documents=[('old', document('Old', closed=True))])).get('/review')
    assert response.status_code == 200
    assert 'ingetrokken' in response.text
    assert 'task=history' in response.text
    assert 'Ga verder' not in response.text
    assert 'task=structure' not in response.text


def test_empty_and_access_boundaries():
    assert 'Geen aan jou toegewezen reviewdocumenten' in client(Console()).get('/review').text
    assert client(Console(), login=False).get('/review').status_code == 403
    assert client(Console(roles=('researcher',))).get('/review').status_code == 403


def test_waiting_duties_are_not_counted_as_completed_work():
    value = document('Mixed')
    value.update(actionable_structure_duties=3, actionable_review_duties=3,
                 waiting_for_reviewer_duties=5)
    response = client(Console(documents=[('mixed', value)])).get('/review')
    assert '3 te controleren · 2 afgerond' in response.text
    assert '3 te controleren · 7 afgerond' not in response.text
    assert '5 wachten op een andere beoordelaar' in response.text


def test_task_page_returns_to_selected_document(monkeypatch):
    def render(console, account, document, object='', *, task='', counts=None):
        assert document == 'two' and task == 'structure'
        return '<h1>Koppen controleren</h1><a class="btn-secondary" href="/review">Ander document kiezen</a>'
    monkeypatch.setattr('src.review_workboard_v1._render_review_room', render)
    console = Console(documents=[('one', document('One')), ('two', document('Two'))])
    response = client(console).get('/review?document=two&task=structure')
    assert response.status_code == 200
    assert 'Koppen controleren' in response.text
    assert 'href="/review?document=two&amp;q=&amp;page=1"' in response.text
    assert "Terug naar documenten" in response.text


def test_hundreds_of_documents_are_paged_searchable_and_have_unique_workspace_ids():
    import re
    docs = [(f'snap-{i}', document(f'Document {i:03}')) for i in range(103)]
    docs.append(('private', document('Private', reviewers=('other',))))
    console = Console(documents=docs)
    browser = client(console)
    response = browser.get('/review?page=2')
    assert response.status_code == 200
    assert response.text.count('class="doc-card document-disclosure review-document-card"') == 25
    assert '103 documenten' in response.text and 'pagina 2 van 5' in response.text
    assert 'Document 025' in response.text and 'Document 000' not in response.text
    ids = re.findall(r'\bid="([^"]+)"', response.text)
    assert len(ids) == len(set(ids))
    found = browser.get('/review?q=Document+102')
    assert 'Document 102' in found.text and 'Document 025' not in found.text
    assert 'Private' not in response.text and 'Private' not in found.text
    assert not hasattr(console, 'snapshot_objects')  # Projection-only rendering.


def test_projected_legacy_human_review_stamp_starts_review_but_context_count_does_not():
    value = document('Legacy')
    value['progress_context'] = 2
    console = Console(documents=[('legacy', value)])
    browser = client(console)
    assert 'Review: Nog niet gestart' in browser.get('/review').text
    value['has_review_decision'] = True
    assert 'Review: Gestart' in browser.get('/review').text
