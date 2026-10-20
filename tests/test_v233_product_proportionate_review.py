from __future__ import annotations

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from test_t4_single_knowledge_path_invariants import _allowed_source
from copy import deepcopy
from pathlib import Path

import pytest

from src.passage_register_v1 import apply_passage_register, passage_register_of
from src.proportionate_review_v1 import (
    NORMAL_RISK_BATCH_MAX,
    ProportionateReviewConsole,
    normal_risk_batch_eligible,
    normal_risk_batch_queue,
    regular_review_queue,
    render_normal_risk_batch_panel,
)
from src.operations_console_v1 import ConsoleError


def _obj(
    object_id: str,
    proposed_type: str,
    *,
    gate: str = "allowed",
    high: bool = False,
    second: bool = False,
    uncertain: bool = False,
    section: tuple[str, ...] = ("1 Achtergrond",),
) -> dict:
    row = {
        "object_id": object_id,
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": proposed_type,
        "content": {"clean_text": f"Inhoud {object_id}."},
        "structure": {"section_path": list(section)},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "proposed_type": proposed_type,
                "section_path": list(section),
                "reason_codes": ["machine_reason"] if gate == "blocked" else [],
            },
            **(
                {}
                if gate != "allowed" or proposed_type == "heading"
                else {
                    "semantic_passage": {
                        "selection_origin": "proposal_selected",
                        "spans": [{
                            "block_id": f"block-{object_id}",
                            "start": 0,
                            "end": len(f"Inhoud {object_id}."),
                        }],
                    }
                }
            ),
        },
        "risk": {
            "level": "high" if high else "standard",
            "requires_second_review": second,
        },
        "uncertainty": {
            "has_uncertainty": uncertain,
            "items": ["onduidelijk"] if uncertain else [],
        },
        "governance": {
            "validation_status": "needs_review",
            "review_track": "clinical",
        },
    }

    from copy import deepcopy
    from test_t4_single_knowledge_path_invariants import _allowed_candidate
    from src.integrity_kernel import stamp_canonical_hashes
    fixture = _allowed_candidate()
    for key in ("content", "source", "provenance"):
        row[key] = deepcopy(fixture[key])
    row["metadata"]["semantic_passage"] = deepcopy(fixture["metadata"]["semantic_passage"])
    stamp_canonical_hashes(row)
    return row


def test_admission_blocked_is_open_work_not_substantive_exclusion() -> None:
    row = apply_passage_register([_obj("blocked", "recommendation", gate="blocked")])[0]
    register = passage_register_of(row)
    assert register["status"] == "not_yet_assessed"
    assert register["source"] == "extract"
    assert register["reason_codes"] == ["machine_reason"]


def test_human_exclusion_remains_authoritative_after_register_refresh() -> None:
    row = _obj("blocked", "recommendation", gate="blocked")
    row["metadata"]["passage_register"] = {
        "status": "excluded_with_reason",
        "reason_codes": ["geen_kenniseenheid"],
        "suitability": "geen_kenniseenheid",
        "source": "review",
        "linked_object_id": "",
        "section_path": ["1 Achtergrond"],
    }
    refreshed = apply_passage_register([row])[0]
    assert passage_register_of(refreshed)["status"] == "excluded_with_reason"
    assert passage_register_of(refreshed)["source"] == "review"


def test_regular_review_queue_is_broader_than_priority_duty_but_still_fail_closed() -> None:
    definition = _obj("definition", "definition")
    explanation = _obj("explanation", "explanation")
    recommendation = _obj("recommendation", "recommendation")
    blocked = _obj("blocked", "definition", gate="blocked")
    heading = _obj("heading", "heading")
    ids = {
        row["object_id"]
        for row in regular_review_queue(
            [definition, explanation, recommendation, blocked, heading],
            review_path="richtlijn", fragments=_allowed_source())
    }
    assert ids == {"definition", "explanation", "recommendation"}


def test_normal_risk_batch_excludes_action_high_risk_second_review_blocked_and_uncertain() -> None:
    eligible = _obj("definition", "definition")
    explanation = _obj("explanation", "explanation")
    recommendation = _obj("recommendation", "recommendation")
    high = _obj("high", "definition", high=True)
    second = _obj("second", "definition", second=True)
    blocked = _obj("blocked", "definition", gate="blocked")
    uncertain = _obj("uncertain", "definition", uncertain=True)
    rows = [eligible, explanation, recommendation, high, second, blocked, uncertain]
    assert normal_risk_batch_eligible(eligible, review_path="richtlijn", fragments=_allowed_source()) is True
    assert normal_risk_batch_eligible(explanation, review_path="richtlijn", fragments=_allowed_source()) is True
    assert normal_risk_batch_eligible(uncertain, review_path="richtlijn", fragments=_allowed_source()) is False
    assert [row["object_id"] for row in normal_risk_batch_queue(rows, review_path="richtlijn", fragments=_allowed_source())] == [
        "definition",
        "explanation",
    ]


@pytest.fixture
def batch_console(production_console, tmp_path, monkeypatch):
    """Real PG commands; spies observe delegation without replacing authority."""
    from src.integrity_kernel import stamp_canonical_hashes
    from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history
    from tests.test_t4_single_knowledge_path_invariants import _project_policy

    def make(requested):
        console = production_console(root=tmp_path, processing_binder=lambda console: None, isolated=True)
        bind_fixture_selections(console, [("Oedeem is een ophoping van vocht.", "definition")])
        author = console.create_account('author', 'fixture-password', ['researcher'])
        reviewer = console.create_account('reviewer', 'fixture-password', ['reviewer'])
        receipt = console.ingest(actor_id=author['account_id'], filename='batch.html',
            content_type='text/html', data=b'<html><h1>Begrippen</h1><h2>1 Achtergrond</h2><p>Oedeem is een ophoping van vocht.</p></html>',
            ingest_kind='new', title='Batch', version='1', date='2026-10-20', live_url='',
            class_='richtlijn', family='batch', named_reviewers=[reviewer['account_id']])
        sid = receipt['snapshot_id']
        base = next(o for o in console.snapshot_objects(sid) if o.get('proposed_object_type')=='definition')
        rows = []
        for requested_row in requested:
            row = deepcopy(base)
            for key in ['object_id','object_type','proposed_object_type','confirmed_object_type',
                        'uncertainty']:
                if key in requested_row:
                    row[key] = deepcopy(requested_row[key])
            row['structure'].update(requested_row['structure'])
            row['governance'].update(requested_row['governance'])
            row['risk'].update({('risk_level' if key=='level' else key): value
                                for key,value in requested_row['risk'].items()})
            row['metadata']['admission'] = deepcopy(requested_row['metadata']['admission'])
            _project_policy(console, sid, row)
            stamp_canonical_hashes(row)
            rows.append(row)
        install_fixture_history(console, sid, rows)
        console.test_snapshot_id, console.test_reviewer_id = sid, reviewer['account_id']
        console.initial_revision = console.objects_revision(sid)
        console.calls, console.opened, console.review_revisions = [], [], []
        review, open_original = console.review_object, console._require_open_original
        def observe_review(**command):
            if not console.calls:
                console.preflight_open_count = len(console.opened)
            console.calls.append(dict(command))
            result = review(**command)
            console.review_revisions.append(console.objects_revision(sid))
            return result
        def observe_source(snapshot_id, object_id):
            console.opened.append(object_id)
            return open_original(snapshot_id, object_id)
        monkeypatch.setattr(console, 'review_object', observe_review)
        monkeypatch.setattr(console, '_require_open_original', observe_source)
        return console
    return make


def test_one_batch_interaction_delegates_to_individual_object_reviews(batch_console) -> None:
    console = batch_console([
        _obj("d1", "definition"),
        _obj("d2", "definition"),
    ])
    updated = console.batch_review_normal_risk(
        actor_id=console.test_reviewer_id,
        snapshot_id=console.test_snapshot_id,
        object_ids=["d1", "d2"],
        expected_revision=console.initial_revision,
    )
    assert console.preflight_open_count == 2
    assert console.opened == ["d1", "d2", "d1", "d2"]
    assert [call["object_id"] for call in console.calls] == ["d1", "d2"]
    assert [call["decision"] for call in console.calls] == ["approve", "approve"]
    assert [call["confirmed_object_type"] for call in console.calls] == ["definition", "definition"]
    assert all(call["suitability"] == "ja" for call in console.calls)
    assert [call["expected_revision"] for call in console.calls] == [console.initial_revision, console.review_revisions[0]]
    assert {row["object_id"] for row in updated} == {"d1", "d2"}


def test_batch_preflights_all_objects_before_writing(batch_console) -> None:
    console = batch_console([
        _obj("d1", "definition"),
        _obj("high", "definition", high=True),
    ])
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(
            actor_id=console.test_reviewer_id,
            snapshot_id=console.test_snapshot_id,
            object_ids=["d1", "high"],
        )
    assert console.calls == []
    assert console.opened == []


def test_batch_cannot_cross_sections(batch_console) -> None:
    console = batch_console([
        _obj("d1", "definition", section=("1 Achtergrond",)),
        _obj("d2", "definition", section=("2 Uitwerking",)),
    ])
    with pytest.raises(ConsoleError, match="normal_risk_batch_mixed_section"):
        console.batch_review_normal_risk(
            actor_id=console.test_reviewer_id,
            snapshot_id=console.test_snapshot_id,
            object_ids=["d1", "d2"],
        )
    assert console.calls == []


def test_batch_cannot_mix_definition_and_explanation(batch_console) -> None:
    console = batch_console([
        _obj("d1", "definition"),
        _obj("e1", "explanation"),
    ])
    with pytest.raises(ConsoleError, match="normal_risk_batch_mixed_type"):
        console.batch_review_normal_risk(
            actor_id=console.test_reviewer_id,
            snapshot_id=console.test_snapshot_id,
            object_ids=["d1", "e1"],
        )
    assert console.calls == []
    assert console.opened == []


def test_batch_has_hard_maximum_of_twenty_objects(batch_console) -> None:
    rows = [_obj(f"d{index}", "definition") for index in range(NORMAL_RISK_BATCH_MAX + 1)]
    console = batch_console(rows)
    with pytest.raises(ConsoleError, match="normal_risk_batch_too_large"):
        console.batch_review_normal_risk(
            actor_id=console.test_reviewer_id,
            snapshot_id=console.test_snapshot_id,
            object_ids=[row["object_id"] for row in rows],
        )
    assert console.calls == []
    assert console.opened == []


def test_rendered_batch_panel_splits_large_groups_by_type_and_maximum(batch_console) -> None:
    rows = [_obj(f"d{index}", "definition") for index in range(NORMAL_RISK_BATCH_MAX + 1)]
    rows += [_obj("e1", "explanation"), _obj("r1", "recommendation"), _obj("u1", "definition", uncertain=True)]
    console = batch_console(rows)
    html = render_normal_risk_batch_panel(console, console.test_snapshot_id)
    assert html.count('action="/review/normal-risk/batch-confirm"') == 1
    assert html.count('class="normal-risk-single"') == 2
    assert f"Maximaal {NORMAL_RISK_BATCH_MAX} passages per bevestiging" in html
    assert f"Definitie ({NORMAL_RISK_BATCH_MAX})" in html
    assert "Voorstel van Metis: Definitie" in html
    assert "Voorstel van Metis: Toelichting" in html
    assert 'value="r1"' not in html
    assert 'value="u1"' not in html


@pytest.mark.parametrize("human_type", ["recommendation", "condition", "exception"])
@pytest.mark.parametrize("field", ["confirmed_object_type", "object_type"])
def test_batch_never_overwrites_authoritative_action_type(human_type: str, field: str, batch_console) -> None:
    row = _obj("d1", "definition")
    row[field] = human_type
    console = batch_console([row])
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(actor_id=console.test_reviewer_id, snapshot_id=console.test_snapshot_id, object_ids=["d1"])
    assert console.calls == []


def test_sectionless_single_object_is_not_batchable(batch_console) -> None:
    console = batch_console([_obj("d1", "definition", section=())])
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(actor_id=console.test_reviewer_id, snapshot_id=console.test_snapshot_id, object_ids=["d1"])
    assert console.calls == []


def test_nonbatch_content_and_batch_members_have_individual_routes(batch_console) -> None:
    rows = [_obj("d1", "definition"), _obj("u1", "definition", uncertain=True),
            _obj("s1", "definition", section=())]
    console = batch_console(rows)
    panel = render_normal_risk_batch_panel(console, console.test_snapshot_id)
    for row in rows:
        assert f'&amp;object={row["object_id"]}' in panel
    assert 'value="u1"' not in panel
    assert 'value="s1"' not in panel


def test_stale_batch_fails_before_any_review_or_source_open(batch_console) -> None:
    console = batch_console([_obj("d1", "definition")])
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.batch_review_normal_risk(actor_id=console.test_reviewer_id, snapshot_id=console.test_snapshot_id, object_ids=["d1"], expected_revision="old")
    assert console.calls == []
    assert console.opened == []


def test_source_contains_no_new_store_or_review_tier() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "proportionate_review_v1.py").read_text(encoding="utf-8")
    assert "light/standard/strict" not in source
    assert "use_scope" not in source
    assert "new database" not in source.lower()


def test_batch_type_is_a_proposal_and_correction_does_not_confirm_it(batch_console) -> None:
    row = _obj('definition', 'definition')
    before = deepcopy(row)
    console = batch_console([row])
    html = render_normal_risk_batch_panel(console, console.test_snapshot_id,
        snapshot=(console.snapshot_objects(console.test_snapshot_id), console.initial_revision))
    assert 'Voorstel van Metis: Definitie' in html
    assert '#classification-definition' in html
    assert 'Type of gebruik controleren' in html
    assert row == before
    row['confirmed_object_type'] = 'explanation'
    console = batch_console([row])
    html = render_normal_risk_batch_panel(console, console.test_snapshot_id,
        snapshot=(console.snapshot_objects(console.test_snapshot_id), console.initial_revision))
    assert 'Bevestigd type: Toelichting' in html
    assert 'Voorstel van Metis: Definitie' not in html


def test_singleton_has_individual_review_without_batch_controls(batch_console):
    console = batch_console([_obj("single", "definition")])
    html = render_normal_risk_batch_panel(console, console.test_snapshot_id)
    assert "Passage beoordelen" in html
    assert 'name="object_ids"' not in html
    assert "data-select-review-batch" not in html
    assert 'action="/review/normal-risk/batch-confirm"' not in html
