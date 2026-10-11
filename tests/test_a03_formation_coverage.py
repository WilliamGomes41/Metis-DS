"""A03: current source coverage, review authority and publication/restart.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery version-compat
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json

import pytest

from src.recoverable_formation_v1 import pending_rejections
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from src.semantic_passage_v1 import semantic_source_blocks
from tests.test_recommendation_context_v3 import response_for, source
from tests.test_recommendation_coverage_v1 import FIRST, SECOND
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


def span(start, end, block="b"):
    return {"block_id": block, "start": start, "end": end}


@pytest.mark.parametrize("selections,closed", [
    ([span(0, 100)], True),
    ([span(0, 40), span(40, 100)], True),
    ([span(40, 100), span(0, 40)], True),
    ([span(0, 60), span(40, 100)], True),
    ([span(0, 60), span(40, 99)], False),
    ([span(0, 39), span(40, 100)], False),
    ([span(0, 40), span(40, 100, "other")], False),
])
@pytest.mark.parametrize("kind", ["object", "call", "assessment"])
def test_validated_selection_union(selections, closed, kind):
    failure = {"reason_code": "located", "spans": [span(0, 100)]}
    evidence = ({"error_code": "transport", "target_spans": failure["spans"]}
                if kind == "call" else {"formation": {"rejections": [failure]}})
    proposal = {"objects": [{"spans": [s]} for s in selections], "source_assessments": []}
    if kind == "assessment":
        proposal = {"objects": [], "source_assessments": [{"span": s} for s in selections]}
    before = deepcopy(evidence)
    assert bool(pending_rejections(evidence, proposal)) is not closed
    assert evidence == before


@pytest.mark.parametrize("failure", [
    {"spans": []},
    {"spans": [span(0, 100)], "requires_review": True},
])
def test_selection_never_resolves_unknown_or_review_required(failure):
    evidence = {"formation": {"rejections": [failure]}}
    assert pending_rejections(evidence, {"objects": [{"spans": [span(0, 100)]}]}) == [failure]


def split_system(tmp_path, *, recovery=False, postgres=None):
    """Real HTML pipeline and review, fixture provider/source/canonical adapters."""
    from src.durable_publication_console_v1 import DurablePublicationConsole
    from tests.test_durable_publication_console_v1 import MemoryCanonicalStore, MemorySourceStore
    canonical, immutable = MemoryCanonicalStore(), MemorySourceStore()
    def make():
        kwargs = dict(root=tmp_path, source_store=tmp_path/"sources", runtime=tmp_path/"runtime",
                      immutable_source_store=immutable, canonical_publication_store=canonical)
        if postgres is None:
            return DurablePublicationConsole(**kwargs)
        from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
        from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
        from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
        from src.workflows.workflow_review_cutover_v1 import PostgresReviewWorkflowDurablePublicationConsole
        from src.workflows.workflow_transaction_v1 import bind_workflow_stores
        identity = PostgresWorkflowIdentityStore(postgres)
        documents = PostgresConcurrentWorkflowDocumentStore(postgres)
        reviews = PostgresWorkflowReviewStore(postgres)
        bind_workflow_stores(identity, documents, reviews)
        return PostgresReviewWorkflowDurablePublicationConsole(**kwargs, workflow_identity_store=identity,
            workflow_document_store=documents, workflow_review_store=reviews)
    calls, mode = [], {"broken": recovery}
    extra = "Bespreek de voorkeuren."
    combined = FIRST + " " + SECOND
    def provider(_url, _headers, payload, _timeout):
        calls.append(payload)
        data = json.loads(payload["input"][1]["content"])
        if mode["broken"]:
            proposal = response_for(payload, combined)
            proposal["objects"][0]["field_evidence"]["recommended_action"]["span"]["literal"] = "invented"
            # Preserve independent valid work, so the normal partial formation path runs.
            if any(extra in b["text"] for b in data["source_blocks"]):
                proposal["objects"] += response_for(payload, extra)["objects"]
        else:
            proposal = response_for(payload, FIRST)
            proposal["objects"][0]["spans"][0]["literal"] = FIRST + " "
            proposal["objects"] += response_for(payload, SECOND)["objects"]
            data = json.loads(payload["input"][1]["content"])
            if any(extra in b["text"] for b in data["source_blocks"]):
                proposal["objects"] += response_for(payload, extra)["objects"]
        return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(proposal)}]}]}
    def bind(console):
        bind_pre_review_semantic_processing(console, environ={
            "METIS_PASSAGE_FORMATION_MODE": "semantic-source-bound-v3",
            "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": "fixture"}, post_json=provider)
    state = make()
    author = state.create_account(username="author", password="test-password", roles=("researcher",))["account_id"]
    reviewer = state.create_account(username="reviewer", password="test-password", roles=("reviewer", "publisher"))["account_id"]
    bind(state)
    html = f"<html><body><h1>Aanbevelingen</h1><p>{combined}</p>"
    if recovery:
        html += f"<p>{extra}</p>"
    receipt = state.ingest(actor_id=author, filename="a03.html", data=(html+"</body></html>").encode(),
        content_type="text/html", ingest_kind="new", title="A03", version="1.0", date="2026-10-11",
        live_url="", class_="richtlijn", family="test", named_reviewers=[reviewer])
    return state, receipt["snapshot_id"], author, reviewer, calls, mode, make, bind


def inject_failure(state, sid, *, requires_review=True, spans=None):
    envelope = deepcopy(state._envelope(sid))
    proposal = envelope["semantic_replay"]["proposal"]
    selected = [s for o in proposal["objects"] for s in o["spans"]]
    block = selected[0]["block_id"]
    ref = span(0, max(s["end"] for s in selected if s["block_id"] == block), block)
    failure = {"kind": "object", "reason_code": "synthetic_historical_failure",
               "spans": [ref] if spans is None else spans, "requires_review": requires_review}
    evidence = envelope["semantic_replay"]["provider_evidence"]
    evidence["formation_incomplete"] = True
    evidence["pending_rejections"] = [failure]
    evidence.setdefault("formation", {}).setdefault("rejections", []).append(deepcopy(failure))
    state._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    return deepcopy(evidence)


def approve(state, sid, reviewer, obj):
    state.review_object(actor_id=reviewer, snapshot_id=sid, object_id=obj["object_id"], decision="approve",
        confirmed_object_type="recommendation", recommendation_direction="for",
        recommendation_strength_level="not_stated")


def candidates(state, sid):
    return [o for o in state.snapshot_objects(sid) if o.get("proposed_object_type") == "recommendation"]


def test_reviewed_split_closes_formation_blocker(tmp_path):
    state, sid, _, reviewer, _, _, _, _ = split_system(tmp_path)
    history = inject_failure(state, sid)
    objects = candidates(state, sid)
    assert len(objects) == 2
    approve(state, sid, reviewer, objects[0])
    assert "source_formation_incomplete" in state.publication_readiness(sid)["blockers"]
    approve(state, sid, reviewer, objects[1])
    assert "source_formation_incomplete" not in state.publication_readiness(sid)["blockers"]
    assert state._envelope(sid)["semantic_replay"]["provider_evidence"] == history


def publication_story(tmp_path, monkeypatch, *, recovery=False, postgres=None):
    from fastapi.testclient import TestClient
    from src.operations_console_app import create_console_app, COOKIE
    state, sid, author, reviewer, calls, mode, make, bind = split_system(tmp_path, recovery=recovery, postgres=postgres)
    if recovery:
        history = deepcopy(state._envelope(sid)["semantic_replay"]["provider_evidence"])
        assert history["formation_incomplete"]
        mode["broken"] = False
        state.resume_formation(actor_id=author, snapshot_id=sid, command_id="a03-recover",
                               expected_revision=state.objects_revision(sid))
        current = state._envelope(sid)["semantic_replay"]["provider_evidence"]
        assert not current["formation_incomplete"]
        assert current["formation"]["rejections"] == history["formation"]["rejections"]
        assert not state.publication_readiness(sid)["publication_ready"]
    else:
        inject_failure(state, sid)
    # Fixture provider is used only in source preparation/recovery, never in reads.
    count = len(calls)
    for obj in candidates(state, sid):
        approve(state, sid, reviewer, obj)
    history = deepcopy(state._envelope(sid)["semantic_replay"]["provider_evidence"])
    restarted = make(); bind(restarted)
    def forbidden(*_args, **_kwargs):
        raise AssertionError("closure must not invoke model or extraction")
    monkeypatch.setattr(restarted, "_fragments_and_spec", forbidden)
    client = TestClient(create_console_app(restarted))
    data = {"snapshot_id": sid, "publish_confirmed": "yes"}
    assert client.post("/publish", data=data, follow_redirects=False).status_code in {302, 303, 401, 403}
    client.cookies.set(COOKIE, restarted.authenticate("author", "test-password")["token"])
    assert client.post("/publish", data=data, follow_redirects=False).status_code == 403
    assert restarted._projection_from_authority() == []
    ready = restarted.publication_readiness(sid)
    assert ready["publication_ready"], ready["blockers"]
    assert not restarted.processing_status(sid)["formation_incomplete"]
    client.cookies.set(COOKIE, restarted.authenticate("reviewer", "test-password")["token"])
    assert client.post("/publish", data=data, follow_redirects=False).status_code == 303
    projection = restarted._projection_from_authority()
    assert len(projection) == len(candidates(restarted, sid))
    final = make(); bind(final)
    assert final._projection_from_authority() == projection
    assert final.snapshot_is_published(sid)
    assert final._envelope(sid)["semantic_replay"]["provider_evidence"] == history
    assert len(calls) == count


@pytest.mark.parametrize("recovery", [False, True])
def test_authorized_http_publication_restart(tmp_path, monkeypatch, recovery):
    publication_story(tmp_path, monkeypatch, recovery=recovery)


@pytest.mark.parametrize("recovery", [False, True])
def test_postgres_authorized_http_publication_restart(workflow_postgres, tmp_path, monkeypatch, recovery):
    publication_story(tmp_path, monkeypatch, recovery=recovery, postgres=workflow_postgres)
