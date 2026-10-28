"""Review preparation must be visible without exporting source contents."""
import pytest

from src.extract_html_v1 import extract
from src.prepared_source_views_v1 import prepare
from src.request_diagnostics_v1 import RequestEvidence, _CURRENT, diagnostic_phase


def test_preparation_is_a_nested_phase_and_does_not_change_source(tmp_path):
    source = tmp_path / 'source.html'
    source.write_text('<html><body><p>Vertrouwelijke brontekst.</p></body></html>')
    fragments = extract(source, document_id='fixture', source_id='fixture')
    expected = prepare(fragments).payload
    events = []
    evidence = RequestEvidence('test', '/review', events.append)
    token = _CURRENT.set(evidence)
    try:
        with diagnostic_phase('review_render'):
            result = prepare(fragments)
    finally:
        _CURRENT.reset(token)
    assert result.payload == expected
    assert evidence.tree['review_render/source_prepare']['calls'] == 1
    assert evidence.tree['review_render']['exclusive_ms'] >= 0
    assert evidence.tree['review_render']['inclusive_ms'] >= evidence.tree['review_render/source_prepare']['inclusive_ms']
    assert 'Vertrouwelijke' not in str(events)


def test_preparation_failure_still_finishes_timing(monkeypatch):
    import src.pre_review_semantic_v1 as semantic
    def fail(_rows):
        raise ValueError('private content')
    monkeypatch.setattr(semantic, '_content_fragments', fail)
    evidence = RequestEvidence('test', '/review', lambda _event: None)
    token = _CURRENT.set(evidence)
    try:
        with pytest.raises(ValueError, match='private content'):
            prepare([])
    finally:
        _CURRENT.reset(token)
    assert evidence.totals['source_prepare']['calls'] == 1
    assert evidence.stack == ()
