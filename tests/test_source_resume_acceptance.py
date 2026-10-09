"""Adversarial checkpoint compatibility through installed routes and legacy API.
# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry version-compat
# release-control-evidence: beschikbaarheid toegang kwaliteit slop releasebewijs
"""
from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import bind_pre_review_semantic_processing
from tests.test_availability_repair import installed_app, drain
from tests.test_recoverable_formation_v1 import system
from tests.test_recommendation_coverage_v1 import FIRST, SECOND
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.fixture(params=["file", "postgres"])
def partial(request, tmp_path):
    make = None
    if request.param == "postgres":
        config = request.getfixturevalue("workflow_postgres")
        make = lambda: _console(tmp_path, config)
    return system(tmp_path, make_console=make)


@pytest.mark.parametrize("changed_mode,changed_model", [
    ("deterministic-v1", "fixture"),
    ("semantic-source-bound-v2", "fixture"),
    ("semantic-source-bound-v1", "fixture"),
    ("semantic-source-bound-v3", "another-model"),
], ids=["deterministic", "v2", "v1", "model"])
@pytest.mark.parametrize("entry", ["http", "legacy"])
def test_incompatible_resume_rejected_before_work(partial, changed_mode, changed_model, entry):
    first, sid, actor, _, calls, _, make, _ = partial
    before = deepcopy(first._envelope(sid))
    objects = deepcopy(first.snapshot_objects(sid))
    assert first.processing_status(sid)["resume_allowed"]
    restarted = make()
    extraction_calls = []
    original = restarted._extract
    def counted(*args, **kwargs):
        extraction_calls.append(1)
        return original(*args, **kwargs)
    restarted._extract = counted
    def provider(*args):
        calls.append("unexpected-call")
        raise ConsoleError("processing_dependency_failed")
    bind_pre_review_semantic_processing(restarted, environ={
        "METIS_PASSAGE_FORMATION_MODE": changed_mode,
        "METIS_LLM_API_KEY": "fixture", "METIS_LLM_MODEL": changed_model,
    }, post_json=provider)
    previous_calls = len(calls)
    command = dict(actor_id=actor, snapshot_id=sid, command_id="changed-strategy",
                   expected_revision=restarted.objects_revision(sid))
    if entry == "http":
        app = installed_app(restarted)
        with TestClient(app, base_url="https://testserver", raise_server_exceptions=False) as client:
            assert client.post("/login", data={"username": "author", "password": "strong-test-password"},
                               follow_redirects=False).status_code == 303
            result = client.post("/source-selection/start", data={
                "document": sid, "command_id": command["command_id"],
                "expected_revision": command["expected_revision"],
            }, follow_redirects=False)
            assert result.status_code == 400, "INCOMPATIBLE_RESUME_ACCEPTED"
            assert "processing_resume_configuration_incompatible" in result.text
            drain(client, app)
    else:
        with pytest.raises(ConsoleError, match="processing_resume_configuration_incompatible"):
            restarted.resume_formation(**command)
    assert extraction_calls == [] and len(calls) == previous_calls
    assert restarted._envelope(sid) == before
    assert restarted.snapshot_objects(sid) == objects
    assert restarted._verified_source_bytes(before)[1]
    assert not restarted.publication_readiness(sid)["publish_allowed"]


def test_compatible_http_resume_preserves_checkpoint_and_only_sends_open_range(partial):
    console, sid, actor, _, calls, mode, make, bind = partial
    before = deepcopy(console.snapshot_objects(sid))
    retained = next(o for o in before if o["content"]["clean_text"] == FIRST)
    prior_attempts = deepcopy(console._envelope(sid)["processing_attempts"])
    mode["broken"] = False
    restarted = make()
    bind(restarted)
    prior_calls = len(calls)
    app = installed_app(restarted)
    with TestClient(app, base_url="https://testserver") as client:
        assert client.post("/login", data={"username": "author", "password": "strong-test-password"},
                           follow_redirects=False).status_code == 303
        command = {"document": sid, "command_id": "compatible-resume",
                   "expected_revision": restarted.objects_revision(sid)}
        assert client.post("/source-selection/start", data=command, follow_redirects=False).status_code == 303
        drain(client, app)
        assert client.post("/source-selection/start", data=command, follow_redirects=False).status_code == 303
    assert len(calls) == prior_calls + 1
    payload = json.loads(calls[-1]["input"][1]["content"])
    assert [b["text"] for b in payload["source_blocks"]] == [SECOND]
    final = make()
    assert final._envelope(sid)["processing_attempts"][:-1] == prior_attempts
    assert final._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded"
    assert next(o for o in final.snapshot_objects(sid) if o["object_id"] == retained["object_id"]) == retained
    assert not final.processing_status(sid)["formation_incomplete"]
    assert not final.publication_readiness(sid)["publish_allowed"]


def test_configuration_change_after_resume_reservation_cannot_activate(partial):
    console, sid, actor, _, calls, _, _, _ = partial
    objects = deepcopy(console.snapshot_objects(sid))
    evidence = deepcopy(console._envelope(sid)["semantic_replay"])
    attempt, fresh = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
        command_id="accepted-resume", expected_revision=console.objects_revision(sid))
    assert fresh and attempt["kind"] == "resume"
    console._processing_configuration_reader = lambda: {"mode": "deterministic-v1", "model": "fixture"}
    prior_calls = len(calls)
    with pytest.raises(ConsoleError, match="processing_configuration_changed"):
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    assert len(calls) == prior_calls
    assert console.snapshot_objects(sid) == objects
    assert console._envelope(sid)["semantic_replay"] == evidence
    assert console._envelope(sid)["processing_attempts"][-1]["state"] == "failed"
