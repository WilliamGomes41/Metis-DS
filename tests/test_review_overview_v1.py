"""Review overview per kind: presentation over existing projections only.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import re
from copy import deepcopy

from src.knowledge_path_v1 import content_reviewable
from src.review_duty_v1 import reviewer_route_counts
from src.source_accountability_v1 import evidence_of
from src.source_containers_v1 import partition
from tests.characterization.overview_support import (LEGACY_TEXT, OPEN_TEXT, guideline_document,
                                                     install_native_summaries, native_summary, tree_document)
from tests.characterization.support import REVIEWER
from tests.semantic_fixture_support import install_fixture_history


def _room(console, account, sid, task=""):
    import src.operations_console_app as ui
    return ui._render_review_room(console, account, sid, task=task)


def _source_id(rows, text):
    return next(r["object_id"] for r in rows if (r.get("content") or {}).get("clean_text") == text and evidence_of(r))


def test_content_task_excludes_source_handling_and_preserves_duty_ground(tmp_path, *, production_console):
    console, sid, account = guideline_document(tmp_path, production_console=production_console)
    rows = console.snapshot_objects(sid)
    content = next(r for r in rows if content_reviewable(r))
    legacy_rest = deepcopy(content)
    legacy_rest["object_id"] += "-rest"
    legacy_rest["metadata"]["semantic_passage"]["selection_origin"] = "deterministic_rest"
    install_fixture_history(console, sid, rows + [legacy_rest])
    rows = console.snapshot_objects(sid)
    assert not content_reviewable(legacy_rest)
    assert len(partition(rows)["knowledge"]) == 2
    routes = reviewer_route_counts(rows, review_path="richtlijn", reviewer_id=REVIEWER,
                                   bindings=console.object_review_bindings(sid),
                                   fragments=console.review_source_fragments(sid))
    html = _room(console, account, sid)
    assert 'data-content-review-workplace' in html
    assert 'data-review-layer' not in html
    assert routes["actionable_contextual_duties"] + routes["actionable_batch_duties"] == 1
    assert legacy_rest['object_id'] not in html
    from src.publication_readiness_v1 import review_followup_queues
    open_source = len(review_followup_queues(rows, review_path="richtlijn", bindings=console.object_review_bindings(sid),
                                             fragments=console.review_source_fragments(sid))["disposition"])
    # The deterministic rest row is source handling too, so the label is not "bronpassages".
    assert open_source == 3
    assert "Bronafhandeling open" not in html
    assert 'data-open-work-ratio' not in html and 'task=history' in html


def test_workboard_counters_name_the_existing_version_and_observation_time(tmp_path, *, production_console):
    console, sid, account = guideline_document(tmp_path, production_console=production_console)
    from src.review_workboard_v1 import _workboard_page
    html = _workboard_page(console, account=account, snapshot_id=sid)
    scope = re.search(r'data-count-scope[^>]*>([^<]+)<', html)
    assert scope and "versie 1.0 · peiltijd " in scope.group(1)
    assert " UTC" in scope.group(1)


def test_knowledge_progress_and_lane_total_exclude_excluded_source_record(tmp_path, *, production_console):
    from src.operations_console_app import _lane_total
    from src.source_context_review_v1 import confirm_source_exclusions
    console, sid, account = guideline_document(tmp_path, production_console=production_console)
    rows = console.snapshot_objects(sid)
    confirm_source_exclusions(console, actor_id=REVIEWER, snapshot_id=sid,
        source_object_ids=[_source_id(rows, LEGACY_TEXT)], reason="Documentversie, geen kennis.",
        command_id="overview-exclusion", expected_revision=console.objects_revision(sid))
    rows = console.snapshot_objects(sid)
    html = _room(console, account, sid)
    from src.operations_console_app import knowledge_progress
    assert knowledge_progress(rows, review_path="richtlijn") == {"total": 1, "done": 0, "superseded": 0}
    assert 'data-knowledge-progress' not in html
    # #672: an excluded source record is source handling, never a finished knowledge review.
    assert _lane_total(rows, review_path="richtlijn", lane="contextual", open_rows=[]) == 0


def test_bulk_exclusion_only_for_v1_metadata_and_category_tiles(tmp_path, *, production_console):
    console, sid, account = guideline_document(tmp_path, production_console=production_console)
    rows = console.snapshot_objects(sid)
    legacy, unresolved = _source_id(rows, LEGACY_TEXT), _source_id(rows, OPEN_TEXT)
    from src.source_selection_ui_v1 import render_source_accountability
    owner = render_source_accountability(console, account, sid)
    form = owner[owner.index('action="/review/source-exclusions"'):owner.index('</form>', owner.index('action="/review/source-exclusions"'))]
    assert f'value="{legacy}"' in form and unresolved not in form
    for task in ("inventory", "disposition"):
        html = _room(console, account, sid, task=task)
        assert 'action="/review/source-exclusions"' not in html
        assert 'name="source_object_ids"' not in html
        assert 'Bronregels gemotiveerd uitsluiten in Vorming' in html
        assert 'data-review-filter' in html and f'task=disposition">Onbeslist' in html
        tiles = re.findall(r'data-source-category="(\w+)"[^>]*><b>(\d+)</b>', html)
        assert dict(tiles) == {"unresolved": "2", "invalid_evidence": "0", "linked_context": "0",
                               "document_information": "0", "reviewed": "0"}


def _assert_tree_overview(html):
    assert 'data-content-review-workplace' in html
    assert 'data-count="kennis"' not in html and 'data-open-work-ratio' not in html
    assert 'Kennisvoorstellen beoordelen' in html


def test_tree_document_has_no_knowledge_counter_in_room(tmp_path, *, production_console):
    console, sid, account = tree_document(tmp_path, production_console=production_console)
    _assert_tree_overview(_room(console, account, sid))


def test_tree_document_has_no_knowledge_counter_in_workboard_object_path(tmp_path, *, production_console):
    from src.review_workboard_v1 import _workboard_page
    console, sid, account = tree_document(tmp_path, production_console=production_console)
    html = _workboard_page(console, account=account, snapshot_id=sid)
    assert 'data-personal-open>3<' in html
    assert 'task=structure' in html
    assert 'data-knowledge-progress' not in html


def test_tree_document_has_no_knowledge_counter_on_native_summary_path(tmp_path, monkeypatch, *, production_console):
    import src.review_workboard_v1 as board
    console, sid, account = tree_document(tmp_path, production_console=production_console)
    calls = install_native_summaries(monkeypatch, console, sid, native_summary(
        console, sid, heading_total=1, heading_pending=1, individual_total=2, individual_pending=2,
        actionable_structure_duties=1, actionable_contextual_duties=2, contextual_review_duties=2))
    html = board._workboard_page(console, account=account, snapshot_id=sid)
    assert calls == [sid]
    assert 'data-personal-open>3<' in html
    assert 'task=structure' in html


def test_guideline_native_summary_shows_knowledge_counter_without_progress(tmp_path, monkeypatch, *, production_console):
    import src.review_workboard_v1 as board
    console, sid, account = guideline_document(tmp_path, production_console=production_console)
    calls = install_native_summaries(monkeypatch, console, sid, native_summary(
        console, sid, heading_total=1, heading_pending=1, normal_passages=1, normal_batches=1,
        closure_gap_count=2, actionable_structure_duties=1, actionable_batch_duties=1, actionable_contextual_duties=2))
    html = board._workboard_page(console, account=account, snapshot_id=sid)
    assert calls == [sid]
    assert 'data-personal-open>3<' in html
    assert 'task=contextual' in html
    assert 'data-count="bronafhandeling"' not in html
    assert 'data-knowledge-progress' not in html and 'data-count-scope' in html
