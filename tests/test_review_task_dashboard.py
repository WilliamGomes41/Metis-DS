from tests.review_authority_fixture_support import materialised_row, source_fragments, approved_bindings
"""Task-oriented review navigation without new governance state."""
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from src.operations_console_app import _render_review_index


def _obj(object_id: str, proposed: str, *, status: str = "needs_review", section: str = "Inhoud") -> dict:
    row = {
        "object_id": object_id,
        "object_type": "unclassified",
        "proposed_object_type": proposed,
        "content": {"clean_text": f"Passage {object_id}."},
        "structure": {"section_path": [section]},
        "metadata": {"semantic_passage": {"selection_origin": "proposal_selected",
                     "spans": [{"block_id": f"block-{object_id}", "start": 0, "end": 1}]}, "admission": {"gate_result": "allowed", "section_path": [section]}},
        "governance": {"validation_status": status},
        "risk": {"level": "normal", "requires_second_review": False},
    }
    return materialised_row(row)


def test_default_review_index_is_one_content_task_without_category_choices():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("r2", "recommendation", status="approved"),
        _obj("d1", "definition"),
    ]

    html = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments(), bindings=approved_bindings(objects))

    assert "Kennisvoorstellen beoordelen" in html
    assert 'data-content-review-workplace' in html
    assert 'review-task-grid' not in html
    assert "Passage r1." in html
    assert "Passage h1." not in html
    assert 'task=inventory' in html and 'task=history' not in html
    assert 'task=repair' not in html


def test_each_task_view_only_contains_its_own_work():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("d1", "definition"),
    ]

    individual = _render_review_index("snap-1", objects, "richtlijn", task="individual", fragments=source_fragments(), bindings=approved_bindings(objects))
    headings = _render_review_index("snap-1", objects, "richtlijn", task="headings", fragments=source_fragments(), bindings=approved_bindings(objects))

    assert "Passage r1." in individual
    assert "Passage d1." not in individual
    assert "Passage h1." not in individual
    assert "Passage h1." in headings
    assert "Passage r1." not in headings
    assert "← Terug naar werkvoorraad" in individual


def test_control_information_is_secondary_to_review_tasks():
    objects = [_obj("r1", "recommendation")]

    dashboard = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments(), bindings=approved_bindings(objects))
    control = _render_review_index("snap-1", objects, "richtlijn", task="inventory", fragments=source_fragments(), bindings=approved_bindings(objects))

    assert "Controle en uitzonderingen" not in dashboard
    assert "Passages herstellen" not in dashboard
    assert 'class="review-management"' not in dashboard
    assert 'class="review-blocked-notice"' not in dashboard
    assert "Alle passages en hun afhandeling" not in dashboard
    assert "Alle passages en hun afhandeling" in control
    assert "Alle passages en hun afhandeling" in control


def test_control_card_highlights_blocked_passages_as_work():
    blocked = _obj("b1", "definition")
    blocked["metadata"] = {
        "admission": {"gate_result": "blocked", "section_path": ["Inhoud"]}
    }

    dashboard = _render_review_index("snap-1", [blocked], "richtlijn", fragments=source_fragments(), bindings=approved_bindings([blocked]))

    assert "Geen inhoudelijke beoordeling voor jou beschikbaar" in dashboard
    assert "Passage b1." not in dashboard
    assert 'task=inventory' in dashboard
    assert 'review-blocked-notice' not in dashboard



def _with_register(
    obj: dict,
    status: str,
    *,
    source: str = "review",
    reason_codes: list[str] | None = None,
) -> dict:
    row = dict(obj)
    row["metadata"] = {
        **(obj.get("metadata") or {}),
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
        **revised["provenance"],
        "previous_object_version": "1.0",
        "revision_reason": "Gebruik de volledige bronzin.",
    }
    pending = _with_register(
        _obj("pending", "recommendation"),
        "selected_as_candidate",
    )
    objects = [approved, rejected, context, support, excluded, revised, pending]

    dashboard = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments(), bindings=approved_bindings(objects))

    assert 'Kennisvoorstellen beoordelen' in dashboard
    assert 'Passage pending.' in dashboard and 'Passage revised.' in dashboard
    assert 'bronpassages afgehandeld' not in dashboard
    assert 'task=history' not in dashboard


def test_dashboard_accounts_for_every_passage_without_hiding_followup_work():
    from copy import deepcopy
    import re
    rows = [_obj(f'h{i}', 'heading') for i in range(56)]
    rows += [_obj(f'r{i}', 'recommendation') for i in range(5)]
    rows += [_obj(f'd{i}', 'definition') for i in range(8)]
    for i in range(338):
        obj = _obj(f'u{i}', 'unclassified')
        obj['metadata'] = {'passage_register': {'status': 'not_yet_assessed'}}
        rows.append(obj)
    for i in range(23):
        obj = _obj(f'b{i}', 'definition')
        obj['metadata']['admission']['gate_result'] = 'blocked'
        rows.append(obj)
    rows += [_with_register(_obj(f'c{i}', 'explanation', status='approved'), 'used_as_context') for i in range(6)]
    before = deepcopy(rows)
    from src.vorming.prepared_source_views_v1 import prepare
    fragments = prepare(source_fragments()).fragments
    dashboard = _render_review_index('snap-430', rows, 'richtlijn', fragments=fragments, bindings=approved_bindings(rows))
    inventory = _render_review_index('snap-430', rows, 'richtlijn', task='inventory', fragments=fragments, bindings=approved_bindings(rows))
    followup = _render_review_index('snap-430', rows, 'richtlijn', task='disposition', fragments=fragments, bindings=approved_bindings(rows))
    assert 'bronpassages afgehandeld' not in dashboard
    assert 'Kennisvoorstellen beoordelen' in dashboard
    assert inventory.count('data-passage-id=') == 25
    assert followup.count('data-passage-id=') == 25
    for task, expected in (('inventory', {row['object_id'] for row in rows}),
                           ('disposition', {f'u{i}' for i in range(338)})):
        seen = set()
        for page in range(1, (len(expected) + 24) // 25 + 1):
            body = _render_review_index('snap-430', rows, 'richtlijn', task=task, page=page,
                fragments=fragments, bindings=approved_bindings(rows))
            ids = set(re.findall(r'data-passage-id="([^"]+)"', body))
            assert 0 < len(ids) <= 25 and not seen & ids
            seen.update(ids)
        assert seen == expected
    assert 'Metis heeft nog niet vastgesteld' in followup
    assert 'task=inventory' in dashboard
    assert 'task=repair' not in dashboard
    assert rows == before


def test_dashboard_counts_passages_without_implying_semantic_or_selected_groups():
    rows = [_obj("d1", "definition"), _obj("d2", "definition")]
    html = _render_review_index("snap-1", rows, "richtlijn", fragments=source_fragments(), bindings=approved_bindings(rows))
    assert "Kennisvoorstellen beoordelen" in html
    assert "review-task-grid" not in html
    assert "1 selecties" not in html

