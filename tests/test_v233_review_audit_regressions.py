"""Exercise v2.33 through the real store and authenticated review surface."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import threading
from copy import deepcopy
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import compute_canonical_object_hash
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.proportionate_review_v1 import (
    ProportionateReviewConsole,
    install_proportionate_review_routes,
    normal_risk_batch_queue,
)


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__()
        self.forms: list[dict] = []
        self.links: list[str] = []
        self.form = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form = {"action": attrs.get("action"), "fields": {}, "ids": [], "checked": [], "select_all": False}
            self.forms.append(self.form)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if self.form is not None and tag == "input":
            name, value = attrs.get("name"), attrs.get("value", "")
            if name == "object_ids":
                self.form["ids"].append(value)
                if "checked" in attrs:
                    self.form["checked"].append(value)
            else:
                self.form["fields"][name] = value
        if self.form is not None and "data-select-review-batch" in attrs:
            self.form["select_all"] = True

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = None

    @property
    def batches(self):
        return [form for form in self.forms if form["action"] == "/review/normal-risk/batch-confirm"]


@pytest.fixture
def review_system(tmp_path, *, production_app, production_console):
    console = production_console(processing_binder=bind_fixture_selections, root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    bind_fixture_selections(console)
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group (dJG) is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-08", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    ids = [obj["object_id"] for obj in normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn", bindings=console.object_review_bindings(sid), fragments=console.review_source_fragments(sid))]
    assert len(ids) == 2
    app = production_app(console)
    client = TestClient(app)
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    return console, client, sid, reviewer["account_id"], ids


def test_real_page_links_to_cards_sources_and_writes_exact_object_bindings(review_system):
    console, client, sid, actor, ids = review_system
    page = Page(client.get("/review", params={"document": sid, "task": "batch"}).text)
    form = page.batches[0]
    assert set(form["ids"]) == set(ids)
    assert not form["checked"]  # Presentation alone never selects/approves content.
    for oid in ids:
        card = f"/review?document={sid}&object={oid}&task=batch"
        source = f"/review/bronpassage?document={sid}&object={oid}"
        assert f"{card}#classification-{oid}" in page.links
        assert source not in page.links  # Production removes this duplicate door.
        assert source in client.get(card).text.replace("&amp;", "&")
        assert client.get(card).status_code == 200
        assert client.get(source).status_code == 200
    response = client.post(form["action"], data={**form["fields"], "object_ids": ids}, follow_redirects=False)
    assert response.status_code == 303
    objects = {obj["object_id"]: obj for obj in console.snapshot_objects(sid)}
    for oid in ids:
        obj = objects[oid]
        assert obj["governance"]["validation_status"] == "approved"
        binding = next(row for row in console.object_review_bindings(sid) if row["object_id"] == oid)
        assert binding["object_version"] == obj["object_version"]
        assert binding["canonical_object_hash"] == compute_canonical_object_hash(obj)
        assert binding["reviewer_id"] == actor
    assert len(console.object_review_bindings(sid)) == 2


def test_real_human_reclassification_cannot_be_batch_overwritten(review_system):
    console, client, sid, actor, ids = review_system
    console.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[0], confirmed_object_type="recommendation")
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=console.objects_revision(sid))
    current = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])
    assert current["confirmed_object_type"] == "recommendation"
    assert not console.object_review_bindings(sid)


def test_real_get_pins_text_and_revision_together_and_preserves_conflict_selection(review_system, monkeypatch):
    import src.review_passage_read_v1 as reads

    console, client, sid, actor, ids = review_system
    original_read = reads.read_review_document
    old_text = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])["content"]["clean_text"]
    source_objects = {obj["object_id"]: obj for obj in console.snapshot_objects(sid)}
    new_text = old_text + " " + source_objects[ids[1]]["content"]["clean_text"]
    spans = (deepcopy(source_objects[ids[0]]["metadata"]["semantic_passage"]["spans"])
             + deepcopy(source_objects[ids[1]]["metadata"]["semantic_passage"]["spans"]))

    from tests.production_support import restart_production
    writer = restart_production(console)
    def concurrent_edit(*args, **kwargs):
        snapshot = original_read(*args, **kwargs)
        monkeypatch.setattr(reads, "read_review_document", original_read)
        errors = []
        def edit():
            try:
                writer.submit_review_resolution(actor_id=actor, snapshot_id=sid, object_id=ids[0],
                    expected_revision=writer.objects_revision(sid), suitability='samenvoegen',
                    comment='Concurrent source-bound merge.', repair_kind='merge_objects', merge_object_ids=[ids[1]])
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=edit)
        thread.start()
        thread.join(timeout=10)
        assert not thread.is_alive() and not errors
        return snapshot

    monkeypatch.setattr(reads, "read_review_document", concurrent_edit)
    response = client.get("/review", params={"document": sid, "task": "batch"})
    assert old_text in response.text and new_text not in response.text
    form = Page(response.text).batches[0]
    assert form["fields"]["snapshot_revision"] != console.objects_revision(sid)
    response = client.post(form["action"], data={**form["fields"], "object_ids": ids})
    assert response.status_code == 409
    assert "data-stale-write-conflict" in response.text
    # A valid revision still invalidates the form and its old review binding.
    from src.admission_gate_v1 import admission_of
    corrected = next(o for o in console.snapshot_objects(sid) if o['object_id'] == ids[0])
    assert admission_of(corrected)["gate_result"] in {"allowed", "blocked"}
    assert new_text in client.get('/review', params={'document':sid, 'object':ids[0]}).text
    assert not console.object_review_bindings(sid)
    assert console.snapshot_objects_and_revision(sid)[1] == console.objects_revision(sid)


def test_concurrent_writer_between_members_waits_for_atomic_pg_batch(review_system, monkeypatch):
    console, client, sid, actor, ids = review_system
    original_review = console.review_object
    from tests.production_support import restart_production
    writer = restart_production(console)
    errors, threads = [], []
    started, finished = threading.Event(), threading.Event()
    def review_then_other_writer(**kwargs):
        rows = original_review(**kwargs)
        if kwargs['object_id'] == ids[0]:
            def other_writer():
                started.set()
                try:
                    writer.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[1],
                                               confirmed_object_type='recommendation')
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    finished.set()
            thread = threading.Thread(target=other_writer)
            threads.append(thread)
            thread.start()
            assert started.wait(2)
            assert not finished.wait(0.05), 'The independent writer must wait for the batch transaction'
        return rows
    monkeypatch.setattr(console, 'review_object', review_then_other_writer)
    revision = console.objects_revision(sid)
    try:
        console.batch_review_normal_risk(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=revision)
    finally:
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()
    assert finished.is_set() and len(errors) == 1
    assert isinstance(errors[0], ConsoleError) and errors[0].code == 'snapshot_object_write_conflict'
    committed = {obj['object_id']: obj for obj in console.snapshot_objects(sid)}
    assert all(committed[oid]['governance']['validation_status'] == 'approved' for oid in ids)
    assert {row['object_id'] for row in console.object_review_bindings(sid) if row.get('valid')} == set(ids)
    writer = restart_production(console)
    writer.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[1],
                               confirmed_object_type='recommendation', expected_revision=writer.objects_revision(sid))
    current = {obj['object_id']: obj for obj in writer.snapshot_objects(sid)}
    assert current[ids[0]]['governance']['validation_status'] == 'approved'
    assert current[ids[1]]['confirmed_object_type'] == 'recommendation'
    assert current[ids[1]]['governance']['validation_status'] == 'needs_review'
    assert {row['object_id'] for row in writer.object_review_bindings(sid) if row.get('valid')} == {ids[0]}


def test_http_batch_requires_the_displayed_revision(review_system):
    console, client, sid, actor, ids = review_system
    response = client.post("/review/normal-risk/batch-confirm", data={"snapshot_id": sid, "object_ids": ids})
    assert response.status_code == 400
    assert not console.object_review_bindings(sid)


def test_two_thousand_objects_need_one_selection_and_confirmation_per_twenty(review_system, monkeypatch):
    from dataclasses import replace
    import src.review_passage_read_v1 as reads
    from src.proportionate_review_v1 import render_normal_risk_batch_panel

    console, client, sid, actor, ids = review_system
    template = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])
    rows = []
    for index in range(2000):
        obj = deepcopy(template)
        obj["object_id"] = f"load-{index}"
        rows.append(obj)
    real_capture = reads.read_review_document
    captured = []

    def load_fixture(*args, **kwargs):
        inputs = replace(real_capture(*args, **kwargs), objects=rows, revision='load-revision')
        captured.append(inputs)
        return inputs

    monkeypatch.setattr(reads, 'read_review_document', load_fixture)
    first = Page(client.get('/review', params={'document': sid, 'task': 'batch'}).text)
    inputs = captured[0]
    # Preserve the complete 100-group oracle, then compare real HTTP pages at
    # the beginning, middle and end with those exact group memberships.
    complete = Page(render_normal_risk_batch_panel(console, sid, snapshot=(rows, inputs.revision),
        include_individual=False, source_inputs=(inputs.bindings, inputs.fragments)))
    assert len(complete.batches) == 100
    assert all(form['select_all'] and len(form['ids']) == 20 for form in complete.batches)
    assert all(not form['checked'] for form in complete.batches)
    assert {oid for form in complete.batches for oid in form['ids']} == {f'load-{i}' for i in range(2000)}
    for number in (1, 50, 100):
        page = first if number == 1 else Page(client.get('/review', params={
            'document': sid, 'task': 'batch', 'queue_page': number}).text)
        assert len(page.batches) == 1
        form = page.batches[0]
        assert form['ids'] == complete.batches[number - 1]['ids']
        assert form['select_all'] and not form['checked']
        assert form['fields']['snapshot_revision'] == 'load-revision'
    # Selecting and confirming the 100 coherent groups still takes 200 actions;
    # page navigation and reading are separate from that confirmation count.
    selection_and_confirmation_actions = 2 * len(complete.batches)
    assert selection_and_confirmation_actions == 200


def test_real_uncertain_content_keeps_an_individual_review_route(review_system):
    console, client, sid, actor, ids = review_system
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision="revise", comment="Onduidelijk")
    console.correct_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], patch={
        "reason": "Onduidelijk", "operations": [{"op": "set", "path": "uncertainty.has_uncertainty", "value": True}],
    })
    page = Page(client.get("/review", params={"document": sid, "task": "contextual"}).text)
    assert ids[0] not in {oid for form in page.batches for oid in form["ids"]}
    card = f"/review?document={sid}&object={ids[0]}&task=contextual"
    assert card in page.links
    response = client.get(card)
    assert response.status_code == 200
    for action in ("afwijzen", "later_beoordelen", "goedkeuren_na_correctie"):
        assert f'value="{action}"' in response.text


def test_http_atomic_batch_and_serialized_writer_report_current_work_truthfully(
    review_system, monkeypatch
):
    console, client, sid, actor, ids = review_system
    original_review = console.review_object
    from tests.production_support import restart_production
    writer = restart_production(console)
    errors, threads = [], []
    started, finished = threading.Event(), threading.Event()
    def review_then_other_writer(**kwargs):
        rows = original_review(**kwargs)
        if kwargs['object_id'] == ids[0]:
            def other_writer():
                started.set()
                try:
                    writer.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[1],
                                               confirmed_object_type='recommendation')
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    finished.set()
            thread = threading.Thread(target=other_writer)
            threads.append(thread)
            thread.start()
            assert started.wait(2)
            assert not finished.wait(0.05), 'The independent writer must wait for the batch transaction'
        return rows
    monkeypatch.setattr(console, 'review_object', review_then_other_writer)
    revision = console.objects_revision(sid)
    try:
        response = client.post('/review/normal-risk/batch-confirm', data={
            'snapshot_id': sid, 'snapshot_revision': revision, 'object_ids': ids}, follow_redirects=False)
        assert response.status_code == 303
        assert 'data-partial-batch-conflict' not in response.text
    finally:
        for thread in threads:
            thread.join(timeout=10)
            assert not thread.is_alive()
    assert finished.is_set() and len(errors) == 1
    assert isinstance(errors[0], ConsoleError) and errors[0].code == 'snapshot_object_write_conflict'
    committed = {obj['object_id']: obj for obj in console.snapshot_objects(sid)}
    assert all(committed[oid]['governance']['validation_status'] == 'approved' for oid in ids)
    assert {row['object_id'] for row in console.object_review_bindings(sid) if row.get('valid')} == set(ids)
    writer = restart_production(console)
    writer.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[1],
                               confirmed_object_type='recommendation', expected_revision=writer.objects_revision(sid))
    current = {obj['object_id']: obj for obj in writer.snapshot_objects(sid)}
    assert current[ids[0]]['governance']['validation_status'] == 'approved'
    assert current[ids[1]]['confirmed_object_type'] == 'recommendation'
    assert current[ids[1]]['governance']['validation_status'] == 'needs_review'
    assert {row['object_id'] for row in writer.object_review_bindings(sid) if row.get('valid')} == {ids[0]}
    retry = Page(client.get('/review', params={'document':sid, 'task':'batch'}).text)
    assert all(not form['checked'] for form in retry.batches)
