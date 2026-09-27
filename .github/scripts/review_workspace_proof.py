from pathlib import Path
import functools
import http.server
import threading
from playwright.sync_api import sync_playwright
from src.review_workboard_v1 import _projected_document_dashboard
from src.operations_console_app import _page, _nav, _review_task_header, _review_index_item
from src.console_navigation_simplify_v1 import simplify_console_html

out = Path('layout-proof')
out.mkdir(exist_ok=True)
class Console:
    _ledger_path = None
    def review_workboard_summaries(self, account, snapshot):
        return {snapshot: {'envelope': {'title': 'Eenzaamheid bij ouderen', 'version': '1.3', 'family': 'Eenzaamheid', 'class': 'richtlijn', 'state': 'in_review'}, 'progress_total': 430, 'progress_done': 6, 'progress_context': 6, 'actionable_structure_duties': 56, 'heading_total': 56, 'actionable_contextual_duties': 5, 'actionable_batch_duties': 8, 'closure_gap_count': 338, 'blocked_count': 23}}
account = {'account_id': 'preview', 'display_name': 'Voorbeeldgebruiker', 'roles': ['researcher', 'reviewer']}
html = _projected_document_dashboard(Console(), account=account, snapshot_id='preview', counts={'review': 1})
html = simplify_console_html('/review', html).replace('/brand/', '/assets/brand/')
(out / 'index.html').write_text(html)
items = [{'object_id': str(n), 'object_type': 'heading', 'content': {'heading': t}, 'governance': {'validation_status': 'needs_review'}} for n,t in enumerate(['Inhoud', 'Aanleiding en doel', 'Een lange kop met meerdere woorden die ook op een klein scherm volledig leesbaar moet zijn'])]
headings = _page(_nav(account, 'review') + '<section class="room review-room">' + _review_task_header('preview', 'Koppen controleren', 'Controleer de koppen en hun plaats in de bron.') + '<section class="review-lane-fast"><form><div class="review-batch-tools"><button type="button" data-select-review-batch>Selecteer alles</button><button type="button" data-clear-review-batch>Selectie wissen</button></div><ol class="object-index review-heading-list">' + ''.join(_review_index_item(o, 'preview', checkbox=True, task='structure') for o in items) + '</ol></form></section></section>')
(out / 'headings.html').write_text(simplify_console_html('/review', headings).replace('/brand/', '/assets/brand/'))
server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), functools.partial(http.server.SimpleHTTPRequestHandler, directory='.'))
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
        assert page.locator('.review-sidebar .review-burden').count() == 1
        assert page.locator('.review-next-step').count() == 0
        for theme in ('light','dark'):
            if theme == 'dark':
                page.locator('[data-theme-toggle]').click()
                page.reload()
            assert page.locator('html').get_attribute('data-theme') == theme
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), name
            page.screenshot(path=str(out / f'{name}-{theme}.png'), full_page=True)
        page.goto('http://127.0.0.1:8765/layout-proof/headings.html')
        page.get_by_role('button',name='Selecteer alles',exact=True).click()
        assert page.locator('[name="object_ids"]:checked').count() == 3
        page.get_by_role('button',name='Selectie wissen',exact=True).click()
        assert page.locator('[name="object_ids"]:checked').count() == 0
        box=page.locator('.review-select-target').first.bounding_box()
        assert box['width'] >= 44 and box['height'] >= 44
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        page.screenshot(path=str(out / f'{name}-headings.png'), full_page=True)
        page.close()
    browser.close()
server.shutdown()
print('PASS: desktop/mobile, light/dark, theme persistence, headings selection, click targets, overflow, no JS errors')
