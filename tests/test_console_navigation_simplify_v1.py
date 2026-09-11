from __future__ import annotations

from src.console_navigation_simplify_v1 import simplify_console_html


def test_home_keeps_audit_but_removes_duplicate_workflow_nav() -> None:
    html = '''
    <nav class="rooms">
      <a href="/">Mijn werk</a>
      <a href="/ingest">Inleveren</a>
      <a href="/review">Review</a>
      <a href="/publish">Publiceren</a>
      <a href="/tree">Documenten</a>
      <a href="/audit">Audit</a>
      <a href="/accounts">Accounts</a>
    </nav>
    <a class="home-tile" href="/ingest">Inleveren</a>
    <a class="review-control-card" href="/audit">Audit</a>
    '''
    result = simplify_console_html("/", html)
    assert '>Mijn werk<' not in result
    assert '<a href="/ingest">Inleveren</a>' not in result
    assert '<a href="/review">Review</a>' not in result
    assert '<a href="/publish">Publiceren</a>' not in result
    assert '<a href="/tree">Documenten</a>' not in result
    assert '<a href="/audit">Audit</a>' in result
    assert 'class="home-tile" href="/ingest"' in result
    assert 'class="review-control-card" href="/audit"' in result


def test_review_removes_recommended_duplicate_and_batch_source_shortcut() -> None:
    html = '''
    <a href="/">Mijn werk</a>
    <section class="review-next-step" aria-labelledby="review-next-title">
      <a class="btn-primary" href="/review?document=s1&amp;task=individual">Ga verder</a>
    </section>
    <a class="review-task-card" href="/review?document=s1&amp;task=individual">Belangrijke passages beoordelen</a>
    <a href="/review?document=s1&amp;object=o1&amp;task=together">Afzonderlijk beoordelen</a>
    <a href="/review/bronpassage?document=s1&amp;object=o1">Bronpassage</a>
    '''
    result = simplify_console_html("/review", html)
    assert "review-next-step" not in result
    assert "Ga verder" not in result
    assert "review-task-card" in result
    assert "Afzonderlijk beoordelen" in result
    assert ">Bronpassage<" not in result


def test_parent_chooser_is_selection_not_navigation() -> None:
    html = '''
    <div data-parent-choice-list>
      <ol><li><a href="/review?document=s1&object=h1">1. Inleiding</a>
      <label><input type="radio" name="parent_choice" value="h1"> Kies</label></li></ol>
    </div>
    '''
    result = simplify_console_html("/review", html)
    assert "1. Inleiding" in result
    assert 'href="/review?document=s1&object=h1"' not in result
    assert 'name="parent_choice" value="h1"' in result


def test_ingest_success_keeps_next_step_and_removes_documents_shortcut() -> None:
    html = '''
    <a class="btn-secondary" href="/review">Naar review</a>
    <a class="btn-secondary" href="/tree">Naar Documenten</a>
    '''
    result = simplify_console_html("/ingest", html)
    assert "Naar review" in result
    assert "Naar Documenten" not in result


def test_audit_page_is_not_simplified_beyond_global_home_duplicate() -> None:
    html = '''
    <a href="/">Mijn werk</a>
    <a href="/audit">Audit</a>
    <a class="btn-primary" href="/audit/new">Nieuwe audit</a>
    <a class="btn-primary" href="/audit/new?type=experiment">Kies dit type</a>
    '''
    result = simplify_console_html("/audit", html)
    assert '>Mijn werk<' not in result
    assert '<a href="/audit">Audit</a>' in result
    assert 'href="/audit/new"' in result
    assert 'href="/audit/new?type=experiment"' in result
