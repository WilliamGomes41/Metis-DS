"""B6 step 2a (#933): V3 source records reach the existing exact exclusion command per section.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.vorming.source_accountability_v1 import CONTAINERS_VERSION, evidence_of
from tests.test_source_accountability_v1 import CONDITION, DEFINITION, proposal
from tests.test_source_context_review_ui_v1 import Forms

COLOFON = "Werkgroep Observatie en adviescommissie Huidzorg"


def _v3_document(tmp_path, *, production_console):
    state = production_console(processing_binder=lambda console: None, root=tmp_path,
                               source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    author = state.create_account(username="author", password="long-test-password", roles=("researcher",))
    reviewer = state.create_account(username="reviewer", password="long-test-password", roles=("reviewer",))

    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        if not any(DEFINITION in b["text"] for b in data["source_blocks"]):
            answer = {"objects": [], "relations": [], "abstain_reason": "uncertain"}
        else:
            answer = proposal(data, v3=True)
            answer["source_assessments"] = [
                {"span": {"block_id": b["block_id"], "literal": b["text"], "occurrence": 0},
                 "role": "metadata", "reason": "document_metadata"}
                for b in data["source_blocks"] if b["text"] == COLOFON]
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}]}
    bind_pre_review_semantic_processing(state, environ={"METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"}, post_json=provider)
    html = (f"<html><body><h1>Observatie</h1><p>{COLOFON}</p><p>{DEFINITION}</p>"
            f"<p>{CONDITION}</p></body></html>").encode()
    sid = state.ingest(actor_id=author["account_id"], filename="source.html", data=html, content_type="text/html",
        ingest_kind="new", title="Observatie", version="1", date="2026-10-04", live_url="",
        class_="richtlijn", family="observatie", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    return state, sid


def _record(state, sid, text):
    return next(r for r in state.snapshot_objects(sid) if (r.get("content") or {}).get("clean_text") == text)


def test_v3_metadata_proposal_is_excluded_per_section_and_clinical_text_stays_open(
        tmp_path, *, production_app, production_console):
    from fastapi.testclient import TestClient
    from src.publication.publication_readiness_v1 import source_passage_closure
    state, sid = _v3_document(tmp_path, production_console=production_console)
    colofon, condition = _record(state, sid, COLOFON), _record(state, sid, CONDITION)
    assert evidence_of(colofon)["version"] == CONTAINERS_VERSION and evidence_of(colofon)["proposed_role"] == "metadata"
    assert evidence_of(condition)["proposed_role"] == "unresolved"
    before = state.snapshot_objects(sid)
    with TestClient(production_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        page = client.get("/source-selection", params={"document": sid, "task": "disposition"})
        assert page.status_code == 200
        forms = [f for f in Forms(page.text).forms if f["attrs"].get("action") == "/review/source-exclusions"]
        assert len(forms) == 1 and "data-source-group-exclusion" in forms[0]["attrs"]
        selected = [f["value"] for f in forms[0]["inputs"] if f.get("name") == "source_object_ids"]
        # Only the model's metadata proposal is offered; the clinical remainder is not.
        assert selected == [colofon["object_id"]]
        data = {f["name"]: f.get("value", "") for f in forms[0]["inputs"] if f.get("type") == "hidden"}
        data.update(source_object_ids=selected, reason="Colofon, geen kennis.")
        # No write without the explicit check, nor from a stale page.
        assert client.post("/review/source-exclusions", data=data).status_code == 400
        assert client.post("/review/source-exclusions",
                           data={**data, "snapshot_revision": "stale", "source_checked": "1"}).status_code == 400
        assert state.snapshot_objects(sid) == before
        done = client.post("/review/source-exclusions", data={**data, "source_checked": "1"}, follow_redirects=False)
        assert done.status_code == 303
        after = client.get(done.headers["location"])
        assert not any(f["attrs"].get("action") == "/review/source-exclusions" for f in Forms(after.text).forms)
    rows = state.snapshot_objects(sid)
    unresolved = source_passage_closure(rows)["unresolved_source_passage_ids"]
    assert colofon["object_id"] not in unresolved and condition["object_id"] in unresolved
    excluded = _record(state, sid, COLOFON)
    assert excluded["metadata"]["passage_register"]["status"] == "excluded_with_reason"
    assert excluded["metadata"]["source_role_review"]["role"] == "excluded"
    assert excluded["governance"]["validation_status"] == "rejected"
    # Durable: a restarted console reads the same closure, and the command replays idempotently.
    restarted = production_console(processing_binder=lambda console: None, root=tmp_path,
                                   source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert source_passage_closure(restarted.snapshot_objects(sid))["unresolved_source_passage_ids"] == unresolved


def test_published_or_unnamed_viewers_get_no_group_form(tmp_path, monkeypatch, *, production_app, production_console):
    from fastapi.testclient import TestClient
    state, sid = _v3_document(tmp_path, production_console=production_console)
    with TestClient(production_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        monkeypatch.setattr(state, "snapshot_is_published", lambda _: True)
        frozen = client.get("/source-selection", params={"document": sid, "task": "disposition"})
        assert frozen.status_code == 200 and 'name="source_object_ids"' not in frozen.text
    with TestClient(production_app(state), base_url="https://testserver") as outsider:
        assert outsider.post("/login", data={"username": "author", "password": "long-test-password"},
                             follow_redirects=False).status_code == 303
        assert outsider.get("/source-selection", params={"document": sid, "task": "disposition"}).status_code == 403


def test_section_groups_key_on_the_raw_path_not_its_display_text(tmp_path, *, production_console):
    """["Risico / preventie"] and ["Risico", "preventie"] render as two separate forms."""
    from copy import deepcopy
    from src.operations_console_app import _review_inventory
    state, sid = _v3_document(tmp_path, production_console=production_console)
    rows = deepcopy(state.snapshot_objects(sid))
    colofon = next(r for r in rows if (r.get("content") or {}).get("clean_text") == COLOFON)
    twin = deepcopy(colofon)
    twin["object_id"] = colofon["object_id"] + "-twin"
    colofon.setdefault("structure", {})["section_path"] = ["Risico / preventie"]
    twin.setdefault("structure", {})["section_path"] = ["Risico", "preventie"]
    rows.append(twin)
    page = _review_inventory(sid, rows, review_path="richtlijn", bindings=None, reviewer_id="r",
                             task="inventory", snapshot_revision="rev", source_only=True, edit_exclusions=True)
    forms = [f for f in Forms(page).forms if "data-source-group-exclusion" in f["attrs"]]
    selected = [[i["value"] for i in f["inputs"] if i.get("name") == "source_object_ids"] for f in forms]
    assert sorted(selected) == sorted([[colofon["object_id"]], [twin["object_id"]]])
