from tests.review_authority_fixture_support import materialised_row, source_fragments, approved_bindings
"""Task-oriented review navigation without new governance state."""
# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from src.operations_console_app import _render_review_index, _render_review_room


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


def test_default_review_page_is_a_clickable_task_dashboard():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("r2", "recommendation", status="approved"),
        _obj("d1", "definition"),
    ]

    html = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments())

    assert "Volgende stap" in html
    assert "Documentindeling controleren" in html
    assert "Passages afzonderlijk beoordelen" in html
    assert "Passages selecteren en bevestigen" in html
    assert "Ga verder met beoordelen" in html
    assert 'class="review-task-grid"' in html
    assert "Een onafhankelijke tweede beoordeling geven" not in html
    assert "task=repair" not in html
    assert 'href="/review?document=snap-1&amp;task=structure"' in html
    assert 'href="/review?document=snap-1&amp;task=contextual"' in html
    assert 'href="/review?document=snap-1&amp;task=batch"' in html
    assert "Passage r1." not in html
    assert "Alle passages en hun afhandeling" not in html


def test_each_task_view_only_contains_its_own_work():
    objects = [
        _obj("h1", "heading"),
        _obj("r1", "recommendation"),
        _obj("d1", "definition"),
    ]

    individual = _render_review_index("snap-1", objects, "richtlijn", task="individual", fragments=source_fragments())
    headings = _render_review_index("snap-1", objects, "richtlijn", task="headings", fragments=source_fragments())

    assert "Passage r1." in individual
    assert "Passage d1." not in individual
    assert "Passage h1." not in individual
    assert "Passage h1." in headings
    assert "Passage r1." not in headings
    assert "← Terug naar taken" in individual


def test_control_information_is_secondary_to_review_tasks():
    objects = [_obj("r1", "recommendation")]

    dashboard = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments())
    control = _render_review_index("snap-1", objects, "richtlijn", task="inventory", fragments=source_fragments())

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

    dashboard = _render_review_index("snap-1", [blocked], "richtlijn", fragments=source_fragments())

    assert "1 passage is nog niet beschikbaar voor goedkeuring." in dashboard
    assert "Passages corrigeren" in dashboard
    assert 'class="review-blocked-notice"' in dashboard
    assert '/review?document=snap-1&amp;task=repair' in dashboard



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

    dashboard = _render_review_index("snap-1", objects, "richtlijn", fragments=source_fragments())

    assert "Reviewvoortgang" in dashboard
    assert "5 van 7 bronpassages afgehandeld" in dashboard
    assert 'class="review-progress-number">71<span>%</span>' in dashboard
    assert "<dt>Nog te beoordelen</dt><dd>2</dd>" in dashboard
    assert "<dt>Goedgekeurd</dt><dd>1</dd>" in dashboard
    assert "<dt>Afgewezen</dt><dd>1</dd>" in dashboard
    assert "<dt>Niet opgenomen</dt><dd>1</dd>" in dashboard
    assert "<strong>1</strong> context" in dashboard
    assert "<strong>1</strong> onderbouwing" in dashboard
    assert "<strong>1</strong> herzien na correctie" in dashboard
    assert 'task=history' in dashboard

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
        ], fragments=source_fragments())

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
    assert "Bekijk historie" in decisions
    assert "task=history" in decisions


class _HistoryConsole:
    def __init__(self, rows: list[dict], signals: list[dict]) -> None:
        self.rows = rows
        self.signals = signals
        self.object_reads: list[tuple[str, bool]] = []

    def list_envelopes(self) -> list[dict]:
        return [
            {
                "snapshot_id": "snap-1",
                "title": "Richtlijn",
                "version": "1.0",
                "family": "test",
                "class": "richtlijn",
                "state": "captured",
            }
        ]

    def snapshot_objects_and_revision(
        self,
        snapshot_id: str,
        include_blocked: bool = False,
    ) -> tuple[list[dict], str]:
        self.object_reads.append((snapshot_id, include_blocked))
        return self.rows, "revision-1"

    def audit_review_signals(self) -> list[dict]:
        return self.signals


def test_object_history_reuses_one_document_read_and_shows_stored_version_diff() -> None:
    previous = _with_register(
        _obj("revised", "recommendation", status="revise"),
        "selected_as_candidate",
    )
    previous["object_version"] = "1.0"
    previous["object_type"] = "recommendation"
    previous["governance"].update(
        {
            "validated_by": "reviewer.bert",
            "validation_date": "2026-09-18T10:00:00+00:00",
        }
    )
    current = _with_register(
        _obj("revised", "recommendation", status="needs_review"),
        "selected_as_candidate",
    )
    current["object_version"] = "1.0.1"
    current["content"] = {"clean_text": "Passage revised met volledige bronzin."}
    current["provenance"] = {
        "previous_object_version": "1.0",
        "revision_reason": "Gebruik de volledige bronzin.",
    }
    signals = [
        {
            "event_type": "review_audit_evidence",
            "object_id": "revised",
            "object_version": "1.0.1",
            "actor": "reviewer.bert",
            "occurred_at": "2026-09-18T10:05:00+00:00",
            "details": {
                "snapshot_id": "snap-1",
                "decision": "repair",
                "comment": "Gebruik de volledige bronzin.",
            },
        },
        {
            "event_type": "review_audit_evidence",
            "object_id": "revised",
            "object_version": "1.0",
            "actor": "reviewer.bert",
            "occurred_at": "2026-09-18T10:00:00+00:00",
            "details": {
                "snapshot_id": "snap-1",
                "decision": "revise",
                "comment": "Passage mist context.",
            },
        },
    ]
    console = _HistoryConsole([previous, current], signals)

    html = _render_review_room(
        console,  # type: ignore[arg-type]
        {"display_name": "Bert", "roles": ["reviewer"]},
        "snap-1",
        "revised",
        task="decisions",
        counts={},
    )

    assert console.object_reads == [("snap-1", True)]
    assert "Objecthistorie" in html
    assert "Verschil met vorige versie" in html
    assert "Passage revised." in html
    assert "Passage revised met volledige bronzin." in html
    assert "Correctie gevraagd" in html
    assert "Te beoordelen" in html
    assert "Gebruik de volledige bronzin." in html
    assert "Passage mist context." in html
    assert "Versie 1.0" in html
    assert "Versie 1.0.1" in html
    assert "huidige versie" in html
    assert '<form class="review-decision-form"' not in html


def test_dashboard_accounts_for_every_passage_without_hiding_followup_work():
    from copy import deepcopy
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
    dashboard = _render_review_index('snap-430', rows, 'richtlijn', fragments=source_fragments())
    inventory = _render_review_index('snap-430', rows, 'richtlijn', task='inventory', fragments=source_fragments())
    followup = _render_review_index('snap-430', rows, 'richtlijn', task='disposition', fragments=source_fragments())
    assert '6 van 436 bronpassages afgehandeld' in dashboard
    assert '<dt>Nog te beoordelen</dt><dd>430</dd>' in dashboard
    assert inventory.count('data-passage-id=') == 436
    assert followup.count('data-passage-id=') == 338
    assert 'Metis heeft nog niet vastgesteld' in followup
    assert dashboard.count('/review?document=snap-430&amp;task=repair') == 1
    assert rows == before


def test_dashboard_counts_passages_without_implying_semantic_or_selected_groups():
    rows = [_obj("d1", "definition"), _obj("d2", "definition")]
    html = _render_review_index("snap-1", rows, "richtlijn", normal_review_enabled=True, fragments=source_fragments())
    assert "Passages selecteren en bevestigen" in html
    assert "2 passages" in html
    assert "1 selecties" not in html

