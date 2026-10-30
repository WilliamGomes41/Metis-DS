"""B6 step 2b-1 (#933): section-bound group confirmation for open V3 source passages.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import json

import pytest

from src.operations_console_v1 import ConsoleError
from src.vorming.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from tests.test_source_accountability_v1 import DEFINITION, proposal
from tests.test_source_context_review_ui_v1 import Forms

FIRST = "Bij verslechtering is extra observatie nodig."
SECOND = "Overweeg dagelijkse huidinspectie bij bedlegerige cliënten."


def _document(tmp_path, *, production_console, second_reason=None):
    state = production_console(processing_binder=lambda console: None, root=tmp_path,
                               source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    author = state.create_account(username="author", password="long-test-password", roles=("researcher",))
    reviewer = state.create_account(username="reviewer", password="long-test-password", roles=("reviewer",))

    def provider(_url, _headers, payload, _timeout):
        data = json.loads(payload["input"][1]["content"])
        answer = (proposal(data, v3=True) if any(DEFINITION in b["text"] for b in data["source_blocks"])
                  else {"objects": [], "relations": [], "abstain_reason": "uncertain"})
        if second_reason and answer.get("objects"):
            answer["source_assessments"] = [
                {"span": {"block_id": b["block_id"], "literal": b["text"], "occurrence": 0},
                 "role": "unresolved", "reason": second_reason}
                for b in data["source_blocks"] if b["text"] == SECOND]
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(answer)}]}]}
    bind_pre_review_semantic_processing(state, environ={"METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"}, post_json=provider)
    html = f"<html><body><h1>Observatie</h1><p>{DEFINITION}</p><p>{FIRST}</p><p>{SECOND}</p></body></html>".encode()
    sid = state.ingest(actor_id=author["account_id"], filename="source.html", data=html, content_type="text/html",
        ingest_kind="new", title="Observatie", version="1", date="2026-10-04", live_url="",
        class_="richtlijn", family="observatie", named_reviewers=[reviewer["account_id"]])["snapshot_id"]
    return state, sid, reviewer["account_id"]


def _by_text(state, sid, text):
    return next(r for r in state.snapshot_objects(sid) if (r.get("content") or {}).get("clean_text") == text)


def _group(state, sid):
    from src.review.source_context_review_v1 import group_members_hash, source_group_candidates
    (((path, reason), rows),) = source_group_candidates(state.snapshot_objects(sid)).items()
    return (path, reason), rows, group_members_hash(rows)


def _command(state, sid, reviewer, *, ids, command_id="group-1", **overrides):
    (path, reason), rows, members_hash = _group(state, sid)
    command = dict(actor_id=reviewer, snapshot_id=sid, section_path=list(path), group_reason=reason,
                   shown_object_ids=[r["object_id"] for r in rows], source_object_ids=ids,
                   members_hash=members_hash, reason="Geen op te nemen kennis.", command_id=command_id,
                   expected_revision=state.objects_revision(sid))
    return {**command, **overrides}


def test_group_excludes_only_confirmed_members_and_is_idempotent(tmp_path, *, production_console):
    from src.publication.publication_readiness_v1 import source_passage_closure
    from src.review.source_context_review_v1 import confirm_source_group, role_of
    state, sid, reviewer = _document(tmp_path, production_console=production_console)
    first, second = _by_text(state, sid, FIRST), _by_text(state, sid, SECOND)
    _path, rows, _hash = _group(state, sid)
    assert {r["object_id"] for r in rows} == {first["object_id"], second["object_id"]}
    # The reviewer marks SECOND as knowledge: it stays open.
    command = _command(state, sid, reviewer, ids=[first["object_id"]])
    result = confirm_source_group(state, **command)
    assert [m["object_id"] for m in result["members"]] == [first["object_id"]]
    unresolved = source_passage_closure(state.snapshot_objects(sid))["unresolved_source_passage_ids"]
    assert first["object_id"] not in unresolved and second["object_id"] in unresolved
    excluded = _by_text(state, sid, FIRST)
    assert role_of(excluded)["group"] is True and role_of(excluded)["command_id"] == "group-1"
    assert excluded["metadata"]["passage_register"]["status"] == "excluded_with_reason"
    assert any(e["event_type"] == "source_group_confirmed" for e in state.workflow_review_store.read_events())
    restarted = production_console(processing_binder=lambda console: None, root=tmp_path,
                                   source_store=tmp_path / "sources", runtime=tmp_path / "runtime")
    assert confirm_source_group(restarted, **command)["idempotent"] is True
    with pytest.raises(ConsoleError, match="source_context_command_conflict"):
        confirm_source_group(restarted, **{**command, "reason": "Andere reden."})


@pytest.mark.parametrize("change,error", [
    ("hash", "source_group_members_changed"),
    ("stale", "snapshot_object_write_conflict"),
    ("outside", "source_group_command_invalid"),
    ("empty", "source_group_command_invalid"),
    ("too_many", "source_group_command_invalid"),
    ("section", "source_group_members_changed"),
    ("reason", "source_group_members_changed"),
])
def test_group_refuses_without_any_write(change, error, tmp_path, *, production_console):
    from src.review.source_context_review_v1 import confirm_source_group
    state, sid, reviewer = _document(tmp_path, production_console=production_console)
    first = _by_text(state, sid, FIRST)
    command = _command(state, sid, reviewer, ids=[first["object_id"]])
    command = {
        "hash": {**command, "members_hash": "0" * 64},
        "stale": {**command, "expected_revision": "stale"},
        "outside": {**command, "source_object_ids": [first["object_id"], "not-shown"]},
        "empty": {**command, "source_object_ids": []},
        "too_many": {**command, "shown_object_ids": command["shown_object_ids"] + [f"x{i}" for i in range(50)]},
        "section": {**command, "section_path": ["Andere sectie"]},
        "reason": {**command, "group_reason": "document_metadata"},
    }[change]
    before = state.snapshot_objects(sid)
    with pytest.raises(ConsoleError, match=error):
        confirm_source_group(state, **command)
    assert state.snapshot_objects(sid) == before


def test_group_reset_restores_open_state_and_refuses_after_member_drift(tmp_path, *, production_console):
    from src.publication.publication_readiness_v1 import source_passage_closure
    from src.review.source_context_review_v1 import (confirm_source_context, confirm_source_group,
                                                     reset_source_group, role_of)
    state, sid, reviewer = _document(tmp_path, production_console=production_console)
    first, second = _by_text(state, sid, FIRST), _by_text(state, sid, SECOND)
    confirm_source_group(state, **_command(state, sid, reviewer, ids=[first["object_id"], second["object_id"]]))
    reset = dict(actor_id=reviewer, snapshot_id=sid, group_command_id="group-1",
                 reason="Opnieuw beoordelen.", command_id="reset-1", expected_revision=state.objects_revision(sid))
    result = reset_source_group(state, **reset)
    assert set(result["source_versions"]) == {first["object_id"], second["object_id"]}
    rows = state.snapshot_objects(sid)
    unresolved = source_passage_closure(rows)["unresolved_source_passage_ids"]
    assert {first["object_id"], second["object_id"]} <= set(unresolved)
    for text, before in ((FIRST, first), (SECOND, second)):
        row = _by_text(state, sid, text)
        assert not role_of(row) and row["governance"]["validation_status"] == "needs_review"
        # Exactly the pre-group register (extract-owned), so machine/linked closure applies again.
        assert row["metadata"].get("passage_register") == before["metadata"].get("passage_register")
    assert reset_source_group(state, **reset)["idempotent"] is True
    # Confirm again, then change one member individually: the group undo must refuse.
    confirm_source_group(state, **_command(state, sid, reviewer, ids=[first["object_id"], second["object_id"]],
                                           command_id="group-2"))
    confirm_source_context(state, actor_id=reviewer, snapshot_id=sid, source_object_id=first["object_id"],
                           role="reset", target_object_ids=[], reason="Los heropenen.", command_id="single",
                           expected_revision=state.objects_revision(sid))
    before = state.snapshot_objects(sid)
    with pytest.raises(ConsoleError, match="source_group_members_changed"):
        reset_source_group(state, **{**reset, "group_command_id": "group-2", "command_id": "reset-2",
                                     "expected_revision": state.objects_revision(sid)})
    assert state.snapshot_objects(sid) == before


def test_http_group_form_shows_open_members_and_confirms_them(tmp_path, *, production_app, production_console):
    from fastapi.testclient import TestClient
    state, sid, _reviewer = _document(tmp_path, production_console=production_console)
    first, second = _by_text(state, sid, FIRST), _by_text(state, sid, SECOND)
    with TestClient(production_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        page = client.get("/source-selection", params={"document": sid, "task": "disposition"})
        form = next(f for f in Forms(page.text).forms if f["attrs"].get("action") == "/review/source-group")
        shown = [i["value"] for i in form["inputs"] if i.get("name") == "shown_object_ids"]
        assert set(shown) == {first["object_id"], second["object_id"]}
        data = {i["name"]: i.get("value", "") for i in form["inputs"]
                if i.get("type") == "hidden" and i["name"] not in {"shown_object_ids", "section_path"}}
        data.update(shown_object_ids=shown, source_object_ids=[first["object_id"]],
                    section_path=[i["value"] for i in form["inputs"] if i.get("name") == "section_path"],
                    reason="Geen op te nemen kennis.")
        before = state.snapshot_objects(sid)
        assert client.post("/review/source-group", data=data).status_code == 400  # No check, no write.
        assert state.snapshot_objects(sid) == before
        done = client.post("/review/source-group", data={**data, "source_checked": "1"}, follow_redirects=False)
        assert done.status_code == 303
        after = client.get(done.headers["location"])
        reset = next(f for f in Forms(after.text).forms if f["attrs"].get("action") == "/review/source-group/reset")
        assert {i.get("value") for i in reset["inputs"] if i.get("name") == "group_command_id"} == {data["command_id"]}
        remaining = next(f for f in Forms(after.text).forms if f["attrs"].get("action") == "/review/source-group")
        assert [i["value"] for i in remaining["inputs"] if i.get("name") == "shown_object_ids"] == [second["object_id"]]
    with TestClient(production_app(state), base_url="https://testserver") as outsider:
        assert outsider.post("/login", data={"username": "author", "password": "long-test-password"},
                             follow_redirects=False).status_code == 303
        assert outsider.post("/review/source-group", data={**data, "source_checked": "1"}).status_code == 403


def test_single_and_group_commands_write_the_same_source_state(tmp_path, *, production_console):
    """One writer: a group decision equals the single-passage decision, for exclude and undo."""
    from src.review.source_context_review_v1 import confirm_source_context, confirm_source_group, reset_source_group
    state, sid, reviewer = _document(tmp_path, production_console=production_console)
    single, grouped = _by_text(state, sid, FIRST)["object_id"], _by_text(state, sid, SECOND)["object_id"]

    def shape(text):
        row = _by_text(state, sid, text)
        role = {k: v for k, v in (row["metadata"].get("source_role_review") or {}).items()
                if k not in {"command_id", "reviewed_at", "reason", "group", "literal_hash"}}
        governance = {k: v for k, v in row["governance"].items() if k != "validation_date"}
        return role, row["metadata"].get("passage_register"), governance, sorted(row["metadata"])

    confirm_source_context(state, actor_id=reviewer, snapshot_id=sid, source_object_id=single, role="excluded",
                           target_object_ids=[], reason="Los.", command_id="single",
                           expected_revision=state.objects_revision(sid))
    confirm_source_group(state, **_command(state, sid, reviewer, ids=[grouped]))
    assert shape(FIRST) == shape(SECOND)
    confirm_source_context(state, actor_id=reviewer, snapshot_id=sid, source_object_id=single, role="reset",
                           target_object_ids=[], reason="Los terug.", command_id="single-reset",
                           expected_revision=state.objects_revision(sid))
    reset_source_group(state, actor_id=reviewer, snapshot_id=sid, group_command_id="group-1", reason="Terug.",
                       command_id="group-reset", expected_revision=state.objects_revision(sid))
    single_role, _single_register, single_governance, _ = shape(FIRST)
    group_role, group_register, group_governance, _ = shape(SECOND)
    # Same writer for role and governance; the group undo additionally restores the
    # pre-group register, where a single reset records a manual (review-owned) reopen.
    assert (single_role, single_governance) == (group_role, group_governance)
    assert group_register.get("source") != "review"


from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401,E402


def test_native_group_commit_failure_concurrent_reviewer_restart_and_publication(
        recovery_postgres, tmp_path, monkeypatch, *, production_console):
    """All-or-nothing on a failing commit, first writer wins, durable after restart, sealed once published."""
    import psycopg
    from src.review.source_context_review_v1 import confirm_source_group, reset_source_group
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore
    blobs = FakeBlobStore()

    def console_at(name):
        root = tmp_path / name
        root.mkdir()
        return _console(root, recovery_postgres, blobs)

    writer = console_at("writer")
    state, sid, reviewer = _document(tmp_path / "doc", production_console=lambda **_kw: writer)
    first, second = _by_text(state, sid, FIRST)["object_id"], _by_text(state, sid, SECOND)["object_id"]
    command = _command(state, sid, reviewer, ids=[first, second])
    before = state.snapshot_objects(sid)
    with psycopg.connect(recovery_postgres.dsn) as con:
        con.execute("""CREATE FUNCTION workflow.fail_source_group_test() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'source_group_commit_failure'; END; $$""")
        con.execute("""CREATE CONSTRAINT TRIGGER fail_source_group_test
            AFTER INSERT ON workflow.document_objects DEFERRABLE INITIALLY DEFERRED
            FOR EACH ROW EXECUTE FUNCTION workflow.fail_source_group_test()""")
    try:
        with pytest.raises(Exception, match="source_group_commit_failure"):
            confirm_source_group(state, **command)
        assert state.snapshot_objects(sid) == before  # Neither member changed.
    finally:
        with psycopg.connect(recovery_postgres.dsn) as con:
            con.execute("DROP TRIGGER fail_source_group_test ON workflow.document_objects")
            con.execute("DROP FUNCTION workflow.fail_source_group_test()")
    other = console_at("other")  # A second reviewer's worker, same revision seen.
    confirm_source_group(state, **command)
    with pytest.raises(ConsoleError, match="snapshot_object_write_conflict"):
        confirm_source_group(other, **{**command, "command_id": "other-reviewer"})
    fresh = console_at("restart")
    assert fresh.snapshot_objects(sid) == state.snapshot_objects(sid)
    assert confirm_source_group(fresh, **command)["idempotent"] is True
    monkeypatch.setattr(fresh, "snapshot_is_published", lambda _: True)
    with pytest.raises(ConsoleError, match="published_working_revision_immutable"):
        reset_source_group(fresh, actor_id=reviewer, snapshot_id=sid, group_command_id="group-1",
                           reason="Na publicatie.", command_id="late", expected_revision=fresh.objects_revision(sid))


def test_one_section_with_two_proposed_reasons_gets_two_groups_and_reset_stays_with_its_group(
        tmp_path, *, production_app, production_console):
    from fastapi.testclient import TestClient
    from src.review.source_context_review_v1 import confirm_source_group, group_members_hash, source_group_candidates
    state, sid, reviewer = _document(tmp_path, production_console=production_console, second_reason="unformed_meaning")
    groups = source_group_candidates(state.snapshot_objects(sid))
    assert sorted(reason for _path, reason in groups) == ["uncertain_source_role", "unformed_meaning"]
    (path, reason), rows = next(((k, v) for k, v in groups.items() if k[1] == "unformed_meaning"))
    command = dict(actor_id=reviewer, snapshot_id=sid, section_path=list(path), group_reason=reason,
                   shown_object_ids=[r["object_id"] for r in rows], source_object_ids=[r["object_id"] for r in rows],
                   members_hash=group_members_hash(rows), reason="Geen kennis.", command_id="g-unformed",
                   expected_revision=state.objects_revision(sid))
    # One confirmation cannot span both reasons.
    with pytest.raises(ConsoleError, match="source_group_members_changed"):
        confirm_source_group(state, **{**command, "group_reason": "uncertain_source_role"})
    confirm_source_group(state, **command)
    with TestClient(production_app(state), base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "reviewer", "password": "long-test-password"},
                           follow_redirects=False).status_code == 303
        page = client.get("/source-selection", params={"document": sid, "task": "disposition"}).text
    resets = [f for f in Forms(page).forms if f["attrs"].get("action") == "/review/source-group/reset"]
    assert len(resets) == 1  # Only beside the excluded group, not beside the still-open one.
    opened = [f for f in Forms(page).forms if f["attrs"].get("action") == "/review/source-group"]
    assert [i["value"] for f in opened for i in f["inputs"] if i.get("name") == "group_reason"] == ["uncertain_source_role"]
