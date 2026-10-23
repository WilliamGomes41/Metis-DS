"""Bronselectie: a real picker button, readable size and estimate, one action row."""
from __future__ import annotations

import re

import pytest

from src.source_selection_ui_v1 import _estimate, _size

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


@pytest.mark.pure_function
def test_size_uses_dutch_units() -> None:
    assert _size(512) == "512\u00a0bytes"
    assert _size(2005) == "2,0\u00a0kB"
    assert _size(3_450_000) == "3,5\u00a0MB"


@pytest.mark.pure_function
def test_estimate_is_one_sentence_without_repeating_insufficient() -> None:
    none = _estimate({"range_seconds": None, "sample_count": 0, "basis": "Onvoldoende vergelijkbare metingen."})
    assert none == "Geschatte verwerkingstijd: nog geen schatting. Onvoldoende vergelijkbare metingen (0)."
    assert none.count("Onvoldoende") == 1
    some = _estimate({"range_seconds": (120, 600), "sample_count": 4, "basis": "Grove bandbreedte."})
    assert some.startswith("Geschatte verwerkingstijd: ongeveer 2 min–10 min (onzeker).")
    assert some.endswith("Op basis van 4 metingen.")


def test_page_has_picker_button_and_one_action_row(tmp_path, *, production_app, production_console) -> None:
    from fastapi.testclient import TestClient
    from src.operations_console_app import COOKIE
    from tests.test_recoverable_formation_v1 import system
    console, sid, *_ = system(tmp_path, production_console=production_console)
    client = TestClient(production_app(console))
    client.cookies.set(COOKIE, console.authenticate('author', 'strong-test-password')['token'])
    html = client.get('/source-selection', params={'document': sid}).text
    assert '<label for="source-document">Document</label>' in html
    assert '<button class="btn-secondary" type="submit">Document selecteren</button>' in html
    card = html.split(f'id="source-{sid}"', 1)[1].split('</article>', 1)[0]
    meta = card.split('<p class="source-meta">', 1)[1].split('</p>', 1)[0]
    assert ' · Bronversie ' in meta
    assert not re.search(r'\d,\d{3}\s?bytes', meta)  # no English thousands separator
    actions = card.split('<div class="source-actions">', 1)[1]
    assert 'Bekijk diagnose in Inzicht</a></div>' in actions
