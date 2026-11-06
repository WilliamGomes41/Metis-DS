"""New review pages preserve captured context without writing during display.

# release-control-evidence: scope/belofte opslag concurrent stale recovery
# release-control-evidence: toegang slop releasebewijs
"""
from copy import deepcopy
import re

from fastapi.testclient import TestClient

from src.integrity_kernel import stamp_canonical_hashes
from src.review.ko_review_page_v1 import _context_evidence
from src.review.source_context_review_v1 import LINKS_KEY
from tests.semantic_fixture_support import install_fixture_history
from tests.test_review_command_bounded_http_v1 import physical_state
from tests.test_source_context_review_v1 import _system


def test_generic_context_is_visible_and_invalid_context_gets_a_readonly_warning(tmp_path, production_console):
    console, _, _, source, target, command = _system(tmp_path, production_console=production_console)
    console.confirm_source_context(**command)
    sid = command['snapshot_id']
    client = TestClient(console._metis_test_application)
    client.post('/login', data={'username': 'bert', 'password': 'bert-secret'})
    before = physical_state(console, sid)
    page = client.get('/review', params={'document': sid, 'object': target['object_id']})
    assert '<details class="ko-evidence" open>' in page.text
    assert 'Context die bij deze passage is vastgelegd' in page.text
    assert '<p class="context-literal">DOEN</p>' in page.text
    assert command['reason'] in page.text
    assert 'Broncontext vastleggen of aanpassen in Vorming' in page.text
    assert physical_state(console, sid) == before
    rows = console.snapshot_objects(sid)
    changed = next(row for row in rows if row['object_id'] == target['object_id'])
    changed['metadata'][LINKS_KEY][0]['source_object_version'] = '99.0.0'
    stamp_canonical_hashes(changed)
    install_fixture_history(console, sid, rows)
    corrupted = physical_state(console, sid)
    warning, opened = _context_evidence(changed, rows, sid, 'origin', set())
    assert opened
    assert 'Een koppeling verwijst naar gewijzigde of ontbrekende tekst.' in warning
    assert 'deze telt nu niet als geldig contextbewijs' in warning
    invalid = client.get('/review', params={'document': sid, 'object': target['object_id']})
    assert invalid.status_code == 400
    assert 'data-review-receipt' not in invalid.text
    assert physical_state(console, sid) == corrupted


def test_already_displayed_context_stays_collapsed_and_missing_source_has_no_pair_link(tmp_path, production_console):
    console, _, _, source, target, command = _system(tmp_path, production_console=production_console)
    console.confirm_source_context(**command)
    rows = console.snapshot_objects(command['snapshot_id'])
    focal = next(row for row in rows if row['object_id'] == target['object_id'])
    html, opened = _context_evidence(focal, rows, command['snapshot_id'], 'origin', {'DOEN'})
    assert not opened
    assert '<p class="context-literal">DOEN</p>' not in html
    assert command['reason'] in html and 'Koppeling aanpassen of verwijderen' in html
    missing = [deepcopy(row) for row in rows if row['object_id'] != source['object_id']]
    html, opened = _context_evidence(focal, missing, command['snapshot_id'], 'origin', set())
    assert opened
    assert 'De contextbron ontbreekt.' in html
    assert 'Koppeling aanpassen of verwijderen' not in html
    assert 'Broncontext vastleggen of aanpassen in Vorming' in html
    assert not re.search(r'href="[^"]*context_target=', html)
