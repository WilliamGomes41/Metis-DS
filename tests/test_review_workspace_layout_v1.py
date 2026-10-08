"""Review workspace preserves available work, counts, and access boundaries."""
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# Evidence: render the real projected dashboard and navigation transform;
# retain the existing reviewer-only workboard and existing task destinations.
from html.parser import HTMLParser

import pytest

from src.console_navigation_simplify_v1 import simplify_console_html
from src.operations_console_v1 import ConsoleError
from src.review_workboard_v1 import _projected_document_dashboard, _workboard_page


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href'))


class Projection:
    _ledger_path = None

    def __init__(self, *, empty=False):
        self.calls = []
        self.empty = empty

    def review_workboard_summaries(self, account, snapshot):
        self.calls.append((account, snapshot))
        return {snapshot: {
            'envelope': {'title': 'Document <voorbeeld>', 'version': '1.3',
                         'family': 'Test', 'class': 'richtlijn', 'state': 'in_review'},
            'progress_total': 430, 'progress_done': 6, 'progress_context': 6,
            'actionable_structure_duties': 0 if self.empty else 56,
            'heading_total': 56,
            'actionable_contextual_duties': 0 if self.empty else 5,
            'actionable_batch_duties': 0 if self.empty else 8,
            'closure_gap_count': 0 if self.empty else 338,
            'blocked_count': 23,
        }}


def render(projection):
    html = _projected_document_dashboard(
        projection, account={'account_id': 'reviewer-1', 'roles': ['reviewer']},
        snapshot_id='snapshot-1',
    )
    return simplify_console_html('/review', html)


def test_workspace_preserves_task_destinations_and_passage_progress():
    projection = Projection()
    html = render(projection)
    hrefs = Links(html).hrefs
    for task in ('structure', 'contextual', 'batch', 'disposition', 'history', 'inventory'):
        assert f'/review?document=snapshot-1&task={task}' in hrefs
    assert projection.calls == [('reviewer-1', 'snapshot-1')]
    assert html.count('Document &lt;voorbeeld&gt;') == 1
    assert '6 van 430 bronpassages afgehandeld' in html
    assert '56 te controleren' in html and '338 af te handelen' in html
    assert html.index('Jouw open werk') < html.index('Reviewvoortgang')
    assert 'review-burden' not in html
    assert '/review?document=snapshot-1&task=repair' in hrefs


def test_workspace_empty_work_does_not_imply_publication_readiness():
    html = render(Projection(empty=True))
    assert 'Geen inhoudelijke beoordeling voor jou beschikbaar.' in html
    assert 'Klaar voor publicatie' not in html
    assert '/review?document=snapshot-1&task=structure' not in Links(html).hrefs
    assert '/review?document=snapshot-1&task=repair' in Links(html).hrefs


def test_workboard_still_requires_reviewer_role():
    with pytest.raises(ConsoleError, match='reviewer_role_required'):
        _workboard_page(Projection(), account={'account_id': 'researcher-1', 'roles': ['researcher']})
