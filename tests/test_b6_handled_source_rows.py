"""Handled source rows are marked so they read as done, not as open work.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.test_b6_source_batch_scale import _large_pdf, _metadata_ids
from tests.test_source_context_review_ui_v1 import Forms


def test_excluded_rows_and_fully_handled_groups_are_marked_handled(tmp_path, *, production_app, production_console):
    from fastapi.testclient import TestClient
    from src.review.source_context_review_v1 import confirm_source_exclusions
    state, sid, reviewer = _large_pdf(tmp_path, production_console=production_console)
    ids = _metadata_ids(state, sid)[:3]
    confirm_source_exclusions(state, actor_id=reviewer, snapshot_id=sid, source_object_ids=ids,
        reason="Colofon, geen kennis.", command_id="handled-marks", expected_revision=state.objects_revision(sid))
    with TestClient(production_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        html = client.get(f"/source-selection?document={sid}&task=disposition").text
    # The markers do not widen access: a user not named on the document is still refused.
    with TestClient(production_app(state), base_url="https://testserver") as outsider:
        assert outsider.post("/login", data={"username": "author", "password": "long-test-password"},
                             follow_redirects=False).status_code == 303
        assert outsider.get(f"/source-selection?document={sid}&task=disposition").status_code == 403
    for oid in ids:
        assert f'data-source-record="{oid}" data-source-state="handled"><span class="source-state-badge">Afgehandeld</span>' in html
    open_ids = [r["object_id"] for r in state.snapshot_objects(sid) if r["object_id"] not in ids]
    assert any(f'data-source-record="{oid}" data-source-state="open">' in html for oid in open_ids)
    # The group holding only the excluded rows is marked handled; open groups are not.
    assert '<details data-source-group data-source-state="handled">' in html
    assert '<details data-source-group data-source-state="open">' in html
    # Open rows keep their selection checkbox; handled rows have none.
    for form in Forms(html).forms:
        selected = {i.get("value") for i in form["inputs"] if i.get("name") == "source_object_ids"}
        assert not selected & set(ids)
