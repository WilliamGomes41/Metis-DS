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



def _with_register(
    obj: dict,
    status: str,
    *,
    source: str = "review",
    reason_codes: list[str] | None = None,
) -> dict:
    row = dict(obj)
    row["metadata"] = {
        "passage_register": {
            "status": status,
            "reason_codes": list(reason_codes or []),
            "suitability": "",
            "source": source,
            "linked_object_id": "",
            "section_path": ["Inhoud"],
        }
    }
    return row


def test_review_dashboard_projects_distinct_final_dispositions_and_revision_work() -> None:
    approved = _with_register(
        _obj("approved", "recommendation", status="approved"),
        "selected_as_candidate",
    )
    rejected = _with_register(
        _obj("rejected", "recommendation", status="rejected"),
        "excluded_with_reason",
        reason_codes=["geen_kenniseenheid"],
    )
    context = _with_register(
        _obj("context", "explanation", status="approved"),
        "used_as_context",
    )
    support = _with_register(
        _obj("support", "explanation", status="approved"),
        "linked_as_support",
    )
    excluded = _with_register(
        _obj("excluded", "explanation", status="approved"),
        "excluded_with_reason",
        reason_codes=["geen_kenniseenheid"],
    )
    revised = _with_register(
        _obj("revised", "recommendation"),
        "selected_as_candidate",
    )
    revised["object_version"] = "1.0.1"
    revised["provenance"] = {
        "previous_object_version": "1.0",
        "revision_reason": "Gebruik de volledige bronzin.",
    }
    pending = _with_register(
        _obj("pending", "recommendation"),
        "selected_as_candidate",
    )
    objects = [approved, rejected, context, support, excluded, revised, pending]

    dashboard = _render_review_index("snap-1", objects, "richtlijn")

    assert "Reviewvoortgang" in dashboard
    assert "5 van 7 bronpassages afgehandeld (71%)" in dashboard
    assert "<strong>2</strong> nog te beoordelen" in dashboard
    assert "<strong>1</strong> goedgekeurd" in dashboard
    assert "<strong>1</strong> afgewezen" in dashboard
    assert "<strong>1</strong> niet opgenomen" in dashboard
    assert "<strong>1</strong> context" in dashboard
    assert "<strong>1</strong> onderbouwing" in dashboard
    assert "<strong>1</strong> herzien na correctie" in dashboard
    assert 'task=decisions' in dashboard

    decisions = _render_review_index(
        "snap-1",
        objects,
        "richtlijn",
        task="decisions",
        audit_signals=[
            {
                "event_type": "review_audit_evidence",
                "object_id": "rejected",
                "actor": "reviewer.bert",
                "occurred_at": "2026-09-18T10:00:00+00:00",
                "details": {
                    "snapshot_id": "snap-1",
                    "decision": "reject",
                    "comment": "Dit is geen zelfstandig kennisobject.",
                },
            },
            {
                "event_type": "review_audit_evidence",
                "object_id": "revised",
                "actor": "reviewer.bert",
                "occurred_at": "2026-09-18T10:05:00+00:00",
                "details": {
                    "snapshot_id": "snap-1",
                    "decision": "repair",
                    "comment": "Gebruik de volledige bronzin.",
                },
            },
        ],
    )

    assert "Besluiten en historie" in decisions
    assert "Goedgekeurd" in decisions
    assert "Afgewezen" in decisions
    assert "Context" in decisions
    assert "Alleen onderbouwing" in decisions
    assert "Niet opgenomen" in decisions
    assert "Herzien na correctie" in decisions
    assert "Dit is geen zelfstandig kennisobject." in decisions
    assert "Gebruik de volledige bronzin." in decisions
    assert "vorige versie 1.0" in decisions
    assert "versie 1.0.1" in decisions
    assert "Passage pending." not in decisions
    assert "data-review-form" not in decisions
    assert "task=decisions" in decisions
