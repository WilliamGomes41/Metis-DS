"""Issue #542: selected origin must not bypass explicit context obligations.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest

from src.knowledge_path_v1 import content_reviewable
from src.publication_readiness_v1 import review_followup_queues, source_passage_closure
from src.review_closure_v1 import ReviewClosureConsole
from src.source_accountability_v1 import is_source_record
from src.source_containers_v1 import source_accountability
from src.source_context_review_v1 import context_issues
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_vsa_publish_document_v1 import MemorySourceStore
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401


def _system(root, console=None, role="context", multiple=False):
    console = console or ReviewClosureConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        immutable_source_store=MemorySourceStore(),
    )
    author = console.create_account(username="author", password=__name__, roles=("researcher",))
    reviewer = console.create_account(username="reviewer", password=__name__, roles=("reviewer",))
    publisher = console.create_account(username="publisher", password=__name__, roles=("publisher",))
    texts = ["Oedeem is een ophoping van vocht.",
             "Een observatie is een systematische waarneming van gedrag.",
             "Een registratie is een vastlegging van gegevens."]
    bind_fixture_selections(console, [(text, "definition") for text in texts])
    sid = console.ingest(
        actor_id=author["account_id"], filename="source.html", content_type="text/html",
        data=("<html><body>" + "".join("<p>" + text + "</p>" for text in texts) + "</body></html>").encode(),
        ingest_kind="new", title="Context closure", version="1.0", date="2026-10-08",
        live_url="", class_="richtlijn", family="context", named_reviewers=[reviewer["account_id"]],
    )["snapshot_id"]
    source, target, other = [o for o in console.snapshot_objects(sid) if content_reviewable(o)]
    assert not is_source_record(source)
    command = dict(actor_id=reviewer["account_id"], snapshot_id=sid,
                   source_object_id=source["object_id"], role=role,
                   target_object_ids=[target["object_id"], other["object_id"]] if multiple else [target["object_id"]],
                   reason="Broncontext bij de doelpassage.", command_id="selected-context",
                   expected_revision=console.objects_revision(sid))
    console.confirm_source_context(**command)
    _review(console, reviewer, sid, other, "approved")
    return console, reviewer, publisher, sid, source, target, command


def _review(console, reviewer, sid, target, status):
    if status == "pending":
        return
    args = dict(actor_id=reviewer["account_id"], snapshot_id=sid, object_id=target["object_id"])
    if status == "approved":
        console.review_object(**args, decision="approve", confirmed_object_type="definition")
    elif status == "rejected":
        console.review_object(**args, decision="reject", suitability="ja",
                              eindoordeel="afwijzen", comment="Geen zelfstandige kennis.")
    else:
        console.review_object(**args, decision="revise", comment="Context opnieuw beoordelen.")


def _projection(console, sid):
    return source_accountability(console.snapshot_objects(sid),
                                bindings=console.object_review_bindings(sid),
                                fragments=console.review_source_fragments(sid))


@pytest.mark.parametrize("role", ["context", "label"])
@pytest.mark.parametrize("status, closure, action", [
    ("pending", "waiting_on_target", "none"),
    ("rejected", "open", "source_disposition"),
    ("revise", "open", "source_disposition"),
    ("approved", "accounted", "none"),
])
def test_selected_context_follows_current_target_and_survives_restart(tmp_path, role, status, closure, action):
    console, reviewer, _, sid, source, target, command = _system(tmp_path, role=role, multiple=True)
    _review(console, reviewer, sid, target, status)
    before = deepcopy(console.snapshot_objects(sid))
    assert not context_issues(before)
    assert not is_source_record(next(o for o in before if o["object_id"] == source["object_id"]))
    for state in (console, ReviewClosureConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime")):
        projection = _projection(state, sid)
        row = projection[source["object_id"]]
        assert row["closure"] == closure
        assert row["human_action"] == action
        assert len(row["target_ids"]) == 2
        assert row["accounted"] == (status == "approved")
        summary = source_passage_closure(state.snapshot_objects(sid), projection=projection)
        assert (source["object_id"] in summary["unresolved_source_passage_ids"]) == (status != "approved")
        queues = review_followup_queues(state.snapshot_objects(sid), review_path="richtlijn", projection=projection)
        assert (source["object_id"] in {o["object_id"] for o in queues["disposition"]}) == (action == "source_disposition")
        assert state.snapshot_objects(sid) == before
    assert console.confirm_source_context(**command)["idempotent"] is True


@pytest.mark.parametrize("status", ["pending", "rejected", "approved"])
def test_selected_context_controls_authorized_publication(tmp_path, status):
    console, reviewer, publisher, sid, source, target, _ = _system(tmp_path)
    _review(console, reviewer, sid, target, status)
    readiness = console.publication_readiness(sid)
    assert readiness["publication_ready"] == (status == "approved")
    result = console.publish(actor_id=publisher["account_id"], snapshot_id=sid)
    assert result["status"] == ("PASS" if status == "approved" else "BLOCKED")


@pytest.mark.parametrize("damage", ["missing_target", "changed_text", "superseded", "stale_approval"])
def test_selected_context_cannot_hide_stale_evidence(tmp_path, damage):
    console, reviewer, _, sid, source, target, _ = _system(tmp_path)
    _review(console, reviewer, sid, target, "approved")
    rows = deepcopy(console.snapshot_objects(sid))
    bindings = deepcopy(console.object_review_bindings(sid))
    current = next(o for o in rows if o["object_id"] == target["object_id"])
    if damage == "missing_target":
        rows.remove(current)
    elif damage == "changed_text":
        current["content"]["clean_text"] += " Gewijzigd."
    elif damage == "superseded":
        current["governance"]["validation_status"] = "superseded"
    else:
        bindings = [b for b in bindings if b.get("object_id") != target["object_id"]]
    row = source_accountability(rows, bindings=bindings, fragments=console.review_source_fragments(sid))[source["object_id"]]
    assert not row["accounted"]
    assert row["closure"] == {"missing_target": "repair_required", "changed_text": "repair_required",
                              "superseded": "open", "stale_approval": "waiting_on_target"}[damage]


@pytest.mark.parametrize("role, closure", [("excluded", "accounted"), ("reset", "waiting_on_target")])
def test_selected_context_can_be_explicitly_excluded_or_reset(tmp_path, role, closure):
    console, _, _, sid, source, _, command = _system(tmp_path)
    console.confirm_source_context(**{**command, "role": role, "target_object_ids": [],
        "reason": "Nieuw expliciet bronbesluit.", "command_id": role,
        "expected_revision": console.objects_revision(sid)})
    assert _projection(console, sid)[source["object_id"]]["closure"] == closure


def test_native_selected_context_rejection_blocks_publication_after_restart(recovery_postgres, tmp_path):
    from tests.test_lifecycle_withdrawal_recovery_v1 import _console
    from tests.test_publication_chain_recovery_v1 import FakeBlobStore

    blobs = FakeBlobStore()
    console = _console(tmp_path, recovery_postgres, blobs)
    console, reviewer, publisher, sid, source, target, _ = _system(tmp_path, console)
    _review(console, reviewer, sid, target, "rejected")
    root = tmp_path / "restarted"
    root.mkdir()
    restarted = _console(root, recovery_postgres, blobs)
    before = deepcopy(restarted.snapshot_objects(sid))
    assert _projection(restarted, sid)[source["object_id"]]["closure"] == "open"
    assert not restarted.publication_readiness(sid)["publication_ready"]
    assert restarted.publish(actor_id=publisher["account_id"], snapshot_id=sid)["status"] == "BLOCKED"
    assert restarted.canonical_publication_store.release_for_snapshot(sid) is None
    assert restarted.snapshot_objects(sid) == before
