"""Full HTML snapshots of the review overview paths before the per-kind presentation.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import pytest

from .overview_support import (guideline_document, install_native_summaries, native_summary,
                               tree_document)

CASES = ["guideline_index", "guideline_inventory", "guideline_disposition", "guideline_workboard",
         "guideline_workboard_native", "tree_index", "tree_workboard", "tree_workboard_native"]


@pytest.mark.parametrize("case", CASES)
def test_review_overview_golden(case, tmp_path, monkeypatch, golden, production_console):
    import src.operations_console_app as ui
    import src.review_workboard_v1 as board

    console, sid, account = (tree_document if case.startswith("tree") else guideline_document)(tmp_path, production_console=production_console)
    before = console._envelopes.copy()
    calls = []
    if case.endswith("_native"):
        counts = (dict(heading_total=1, heading_pending=1, individual_total=2, individual_pending=2,
                       actionable_structure_duties=1, actionable_contextual_duties=2, contextual_review_duties=2)
                  if case.startswith("tree") else
                  dict(heading_total=1, heading_pending=1, normal_passages=1, normal_batches=1,
                       closure_gap_count=2, actionable_structure_duties=1, actionable_batch_duties=1))
        calls = install_native_summaries(monkeypatch, console, sid, native_summary(console, sid, **counts))
    if case.endswith(("_workboard", "_workboard_native")):
        html = board._workboard_page(console, account=account, snapshot_id=sid)
    else:
        task = {"guideline_inventory": "inventory", "guideline_disposition": "disposition"}.get(case, "")
        html = ui._render_review_room(console, account, sid, task=task)
    if case.endswith("_native"):
        assert calls == [sid], "Native branch must enrich the visible document"
        assert f'data-workboard-document="{sid}"' in html
    assert console._envelopes == before, "Rendering must not mutate envelope state"
    golden("review_overview", case, {"html": html})


def test_review_route_table_golden(tmp_path, golden, production_console, production_app):
    """Freeze production routes, including the four scoped view-check endpoints."""
    from src.operations_console_app import create_console_app
    from src.proportionate_review_v1 import ProportionateReviewConsole, install_proportionate_review_routes
    from src.review_workboard_v1 import install_review_workboard
    from .support import console_at
    console = console_at(tmp_path, production_console=production_console)
    app = production_app(console)
    routes = sorted([getattr(r, "path", ""), sorted(getattr(r, "methods", None) or [])] for r in app.router.routes)
    golden("review_overview", "routes", {"routes": routes})
