from pathlib import Path
import http.server
import threading
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright
from src.review_workboard_v1 import _workboard_page
from src.console_navigation_simplify_v1 import simplify_console_html

out = Path('layout-proof')
out.mkdir(exist_ok=True)
class Console:
    _ledger_path = None
    def waiting_task_counts(self, account):
        return {'review': 2}
    def document_lifecycle_status(self, snapshot):
        return {'workflow_status': 'processing', 'release_status': 'none', 'serving_status': 'inactive', 'presentation_status': 'in_review'}
    def review_workboard_summaries(self, account, snapshot=None):
        docs = {
            'one': {'envelope': {'title': 'Eenzaamheid bij ouderen', 'version': '1.3', 'family': 'Eenzaamheid', 'class': 'richtlijn', 'state': 'in_review'}, 'progress_total': 430, 'progress_done': 6, 'progress_context': 6, 'actionable_review_duties': 69, 'review_duties': 69, 'actionable_structure_duties': 56, 'heading_total': 56, 'heading_pending': 56, 'actionable_contextual_duties': 5, 'individual_total': 5, 'individual_pending': 5, 'actionable_batch_duties': 8, 'closure_gap_count': 338, 'blocked_count': 23},
            'two': {'envelope': {'title': 'Zorg bij depressie', 'version': '2.0', 'family': 'GGZ', 'class': 'richtlijn', 'state': 'in_review'}, 'progress_total': 20, 'progress_done': 12, 'progress_approved': 12, 'review_duties': 8, 'actionable_review_duties': 0, 'actionable_structure_duties': 0, 'waiting_for_reviewer_duties': 8},
        }
        return {key: value for key,value in docs.items() if snapshot is None or snapshot == key}
account = {'account_id': 'preview', 'display_name': 'Voorbeeldgebruiker', 'roles': ['researcher', 'reviewer']}
for snapshot, name in [('', 'index'), ('one', 'one'), ('two', 'two')]:
    html = _workboard_page(Console(), account=account, snapshot_id=snapshot)
    (out / (name + '.html')).write_text(simplify_console_html('/review', html).replace('/brand/', '/assets/brand/'))
class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/review':
            document = parse_qs(parsed.query).get('document', ['one'])[0]
            self.path = '/layout-proof/' + ('two' if document == 'two' else 'one') + '.html'
        return super().do_GET()
server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width, name in [(1440, 'desktop'), (390, 'mobile')]:
        page = browser.new_page(viewport={'width': width, 'height': 1000}, color_scheme='light')
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:8765/layout-proof/index.html')
        assert page.locator('.doc-title').count() == 1
        assert page.locator('.review-task-card').count() == 4
        assert page.locator('.review-task-card-action').first.inner_text().startswith('Ga verder')
        assert page.locator('[data-review-workboard]').count() == 0
        for theme in ('light','dark'):
            if theme == 'dark':
                page.locator('[data-theme-toggle]').click()
                page.reload()
            assert page.locator('html').get_attribute('data-theme') == theme
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(out / f'{name}-{theme}.png'), full_page=True)
            page.locator('.review-document-picker summary').click()
            assert page.get_by_role('navigation',name='Jouw reviewdocumenten').is_visible()
            assert page.locator('.review-document-picker [aria-current="page"]').count() == 1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(out / f'{name}-{theme}-picker.png'), full_page=True)
            page.get_by_role('link',name='Zorg bij depressie',exact=False).click()
            assert 'Zorg bij depressie' in page.locator('.doc-title').inner_text()
            assert page.locator('.review-task-card').count() == 0
            assert '8 wachten op een andere beoordelaar' in page.locator('.review-work-main').inner_text()
            assert page.locator('html').get_attribute('data-theme') == theme
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(out / f'{name}-{theme}-waiting.png'), full_page=True)
            page.locator('.review-document-picker summary').click()
            page.get_by_role('link',name='Eenzaamheid bij ouderen',exact=False).click()
        assert not errors, errors
        page.close()
    browser.close()
server.shutdown()
print('PASS: direct workspace, document choice, waiting-only, 1440/390px, light/dark and preference persistence, no overflow or JS errors')
