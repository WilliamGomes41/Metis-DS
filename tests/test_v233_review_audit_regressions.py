"""Exercise v2.33 through the real store and authenticated review surface."""
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations

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
def review_system(tmp_path):
    console = ProportionateReviewConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    receipt = console.ingest(
        actor_id=researcher["account_id"], filename="begrippen.html", content_type="text/html",
        data=b'<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>'
             b'<p>De Dutch Job Group (dJG) is een meetinstrument voor werkbelasting.</p>'
             b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>',
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-08", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    ids = [obj["object_id"] for obj in normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn")]
    assert len(ids) == 2
    app = create_console_app(console)
    install_proportionate_review_routes(app, console)
    client = TestClient(app)
    client.post("/login", data={"username": "bert", "password": "bert-secret"})
    return console, client, sid, reviewer["account_id"], ids


def test_real_page_links_to_cards_sources_and_writes_exact_object_bindings(review_system):
    console, client, sid, actor, ids = review_system
    page = Page(client.get("/review", params={"document": sid, "task": "together"}).text)
    form = page.batches[0]
    assert set(form["ids"]) == set(ids)
    assert not form["checked"]  # Presentation alone never selects/approves content.
    for oid in ids:
        card = f"/review?document={sid}&object={oid}&task=together"
        source = f"/review/bronpassage?document={sid}&object={oid}"
        assert card in page.links and source in page.links
        assert client.get(card).status_code == 200
        assert client.get(source).status_code == 200
    response = client.post(form["action"], data={**form["fields"], "object_ids": ids}, follow_redirects=False)
    assert response.status_code == 303
    objects = {obj["object_id"]: obj for obj in console.snapshot_objects(sid)}
    for oid in ids:
        obj = objects[oid]
        assert obj["governance"]["validation_status"] == "approved"
        binding = next(row for row in console._bindings[sid] if row["object_id"] == oid)
        assert binding["object_version"] == obj["object_version"]
        assert binding["canonical_object_hash"] == compute_canonical_object_hash(obj)
        assert binding["reviewer_id"] == actor
    assert len(console._bindings[sid]) == 2


def test_real_human_reclassification_cannot_be_batch_overwritten(review_system):
    console, client, sid, actor, ids = review_system
    console.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[0], confirmed_object_type="recommendation")
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=console.objects_revision(sid))
    current = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])
    assert current["confirmed_object_type"] == "recommendation"
    assert not console._bindings.get(sid)


def test_real_get_pins_text_and_revision_together_and_preserves_conflict_selection(review_system, monkeypatch):
    console, client, sid, actor, ids = review_system
    original_read = console.snapshot_objects_and_revision
    old_text = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])["content"]["clean_text"]
    new_text = "De Dutch Job Group (dJG) is een meetinstrument."

    def concurrent_edit(snapshot_id):
        snapshot = original_read(snapshot_id)
        monkeypatch.setattr(console, "snapshot_objects_and_revision", original_read)
        console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision="revise", comment="Correctie")
        console.correct_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], patch={
            "reason": "Correctie", "operations": [{"op": "set", "path": "content.clean_text", "value": new_text}],
        })
        return snapshot

    monkeypatch.setattr(console, "snapshot_objects_and_revision", concurrent_edit)
    response = client.get("/review", params={"document": sid, "task": "together"})
    assert old_text in response.text and new_text not in response.text
    form = Page(response.text).batches[0]
    assert form["fields"]["snapshot_revision"] != console.objects_revision(sid)
    response = client.post(form["action"], data={**form["fields"], "object_ids": ids})
    assert response.status_code == 409
    assert "data-stale-write-conflict" in response.text
    assert new_text in response.text
    assert not console._bindings.get(sid)
    retry = Page(response.text).batches[0]
    assert set(retry["checked"]) == set(ids)
    assert retry["fields"]["snapshot_revision"] == console.objects_revision(sid)


def test_concurrent_writer_between_members_is_not_adopted_as_batch_revision(review_system, monkeypatch):
    console, client, sid, actor, ids = review_system
    original_review = console.review_object
    errors = []

    def review_then_other_writer(**kwargs):
        rows = original_review(**kwargs)
        if kwargs["object_id"] == ids[0]:
            def other_writer():
                try:
                    console.confirm_object_type(actor_id=actor, snapshot_id=sid, object_id=ids[1], confirmed_object_type="recommendation")
                except Exception as exc:
                    errors.append(exc)
            thread = threading.Thread(target=other_writer)
            thread.start()
            thread.join(timeout=10)
            assert not thread.is_alive()
            assert not errors
        return rows

    monkeypatch.setattr(console, "review_object", review_then_other_writer)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        console.batch_review_normal_risk(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=console.objects_revision(sid))
    current = {obj["object_id"]: obj for obj in console.snapshot_objects(sid)}
    assert current[ids[1]]["confirmed_object_type"] == "recommendation"
    assert current[ids[1]]["governance"]["validation_status"] == "needs_review"
    assert {row["object_id"] for row in console._bindings[sid]} == {ids[0]}


def test_http_batch_requires_the_displayed_revision(review_system):
    console, client, sid, actor, ids = review_system
    response = client.post("/review/normal-risk/batch-confirm", data={"snapshot_id": sid, "object_ids": ids})
    assert response.status_code == 400
    assert not console._bindings.get(sid)


def test_two_thousand_objects_need_one_selection_and_confirmation_per_twenty(review_system, monkeypatch):
    console, client, sid, actor, ids = review_system
    template = next(obj for obj in console.snapshot_objects(sid) if obj["object_id"] == ids[0])
    rows = []
    for index in range(2000):
        obj = deepcopy(template)
        obj["object_id"] = f"load-{index}"
        rows.append(obj)
    monkeypatch.setattr(console, "snapshot_objects_and_revision", lambda _sid: (rows, "load-revision"))
    page = Page(client.get("/review", params={"document": sid, "task": "together"}).text)
    assert len(page.batches) == 100
    assert all(form["select_all"] and len(form["ids"]) == 20 for form in page.batches)
    assert all(not form["checked"] for form in page.batches)
    assert len({oid for form in page.batches for oid in form["ids"]}) == 2000
    # Reading remains necessary; selecting and confirming a coherent section
    # requires 200 UI actions, not 2000 individual open/select/save cycles.
    selection_and_confirmation_actions = 2 * len(page.batches)
    assert selection_and_confirmation_actions == 200


def test_real_uncertain_content_keeps_an_individual_review_route(review_system):
    console, client, sid, actor, ids = review_system
    console.review_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], decision="revise", comment="Onduidelijk")
    console.correct_object(actor_id=actor, snapshot_id=sid, object_id=ids[0], patch={
        "reason": "Onduidelijk", "operations": [{"op": "set", "path": "uncertainty.has_uncertainty", "value": True}],
    })
    page = Page(client.get("/review", params={"document": sid, "task": "individual"}).text)
    assert ids[0] not in {oid for form in page.batches for oid in form["ids"]}
    card = f"/review?document={sid}&object={ids[0]}&task=individual"
    assert card in page.links
    response = client.get(card)
    assert response.status_code == 200
    for action in ("afwijzen", "later_beoordelen", "goedkeuren_na_correctie"):
        assert f'value="{action}"' in response.text
