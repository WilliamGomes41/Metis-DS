"""Task-oriented review navigation without new governance state."""
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from src.operations_console_app import _render_review_index


def _obj(object_id: str, proposed: str, *, status: str = "needs_review", section: str = "Inhoud") -> dict:
    return {
        "object_id": object_id,
        "object_type": "unclassified",
        "proposed_object_type": proposed,
        "content": {"clean_text": f"Passage {object_id}."},
        "structure": {"section_path": [section]},
        "admission": {"gate_result": "allowed", "section_path": [section]},
        "governance": {"validation_status": status},
        "risk": {"level": "normal", "requires_second_review": False},
    }


def test_default_review_page_is_a_clickable_task_dashboard():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("r2", "recommendation", status="approved"),
        _obj("d1", "definition"),
    ]

    html = _render_review_index("snap-1", objects, "richtlijn")

    assert "Volgende stap" in html
    assert "Koppen controleren" in html
    assert "Belangrijke passages beoordelen" in html
    assert "Vergelijkbare passages samen beoordelen" in html
    assert "1 te beoordelen · 1 afgerond" in html
    assert 'href="/review?document=snap-1&amp;task=headings"' in html
    assert 'href="/review?document=snap-1&amp;task=individual"' in html
    assert 'href="/review?document=snap-1&amp;task=together"' in html
    assert "Passage r1." not in html
    assert "Controleoverzicht per kop" not in html


def test_each_task_view_only_contains_its_own_work():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("d1", "definition"),
    ]

    individual = _render_review_index("snap-1", objects, "richtlijn", task="individual")
    headings = _render_review_index("snap-1", objects, "richtlijn", task="headings")

    assert "Passage r1." in individual
    assert "Passage d1." not in individual
    assert "Passage h1." not in individual
    assert "Passage h1." in headings
    assert "Passage r1." not in headings
    assert "← Terug naar taken" in individual


def test_control_information_is_secondary_to_review_tasks():
    objects = [_obj("r1", "recommendation")]

    dashboard = _render_review_index("snap-1", objects, "richtlijn")
    control = _render_review_index("snap-1", objects, "richtlijn", task="control")

    assert "Controle en uitzonderingen" in dashboard
    assert "Dekking en technische controle" in dashboard
    assert "Geen technische blokkades" in dashboard
    assert "Open technische controle" in dashboard
    assert "review-control-card-clear" in dashboard
    assert 'href="/review?document=snap-1&amp;task=control"' in dashboard
    assert "Controleoverzicht per kop" not in dashboard
    assert "Dekking en technische controle" in control
    assert "Controleoverzicht per kop" in control


def test_control_card_highlights_blocked_passages_as_work():
    blocked = _obj("b1", "definition")
    blocked["metadata"] = {
        "admission": {"gate_result": "blocked", "section_path": ["Inhoud"]}
    }

    dashboard = _render_review_index("snap-1", [blocked], "richtlijn")

    assert "1 passage vereist technisch herstel" in dashboard
    assert "Metis kon deze passages niet veilig verwerken" in dashboard
    assert "review-control-card-alert" in dashboard
