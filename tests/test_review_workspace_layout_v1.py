"""Personal landing preserves escaped document identity and review access."""
# release-control-evidence: scope/belofte toegang slop releasebewijs
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from src.console_navigation_simplify_v1 import simplify_console_html
from src.operations_console_v1 import ConsoleError
from src.review_workboard_v1 import _workboard_card, _workboard_page
from tests.test_review_workboard_queue_links_v1 import _item


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href'))


def test_personal_card_escapes_document_and_search_without_an_extra_workplace():
    item = _item()
    item['snapshot_id'] = 'snapshot&1'
    item['envelope']['title'] = 'Document <voorbeeld>'
    html = simplify_console_html('/review', _workboard_card(item, q='"><script>bad</script>', page=2))
    hrefs = Links(html).hrefs
    assert len(hrefs) == 1
    assert 'Document &lt;voorbeeld&gt;' in html and '<script>bad</script>' not in html
    target = urlsplit(hrefs[0])
    assert target.path == '/review'
    assert parse_qs(target.query) == {'document': ['snapshot&1'], 'task': ['contextual'],
                                     'q': ['"><script>bad</script>'], 'page': ['2']}
    assert 'data-open-work-ratio' not in html


def test_no_current_personal_work_does_not_imply_publication_readiness():
    item = _item()
    item['actionable_review_duties'] = item['review_duties'] = 0
    html = _workboard_card(item)
    assert 'Geen open beoordeling voor jou.' in html
    assert 'Klaar voor publicatie' not in html
    assert 'data-personal-review-action' not in html
    assert 'task=history' in html


def test_workboard_still_requires_reviewer_role():
    with pytest.raises(ConsoleError, match='reviewer_role_required'):
        _workboard_page(object(), account={'account_id': 'researcher-1', 'roles': ['researcher']})
