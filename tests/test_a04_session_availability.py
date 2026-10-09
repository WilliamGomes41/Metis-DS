"""A04 HTTP proof on one ASGI loop: actual extraction, sessions and another actor.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale interrupt retry
# release-control-evidence: toegang
# release-control-evidence: beschikbaarheid
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from threading import Event

import pytest
from fastapi.testclient import TestClient

from src.operations_console_app import create_console_app
from src.workflows.workflow_identity_postgres_v1 import _token_hash
from tests.test_availability_repair import bind, drain, login, provider, state
from tests.test_console_entra_v1 import (
    ADMIN, USER, CLIENT, TENANT, FakeMicrosoft, claims, login as entra_login,
)
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_chain_recovery_v1 import recovery_postgres  # noqa: F401

ORIGIN = "https://testserver"


@pytest.fixture(params=["local", "entra-postgres"])
def runtime(request, tmp_path, monkeypatch):
    native = request.param == "entra-postgres"
    console = (_console(tmp_path, request.getfixturevalue("recovery_postgres"))
               if native else state(tmp_path))
    author = console.create_account(username="author", password="fixture-only",
                                    roles=("researcher", "reviewer", "publisher"))["account_id"]
    other = console.create_account(username="other", password="fixture-only",
                                   roles=("researcher", "reviewer"))["account_id"]
    inference_boundary = {"call": provider}
    bind(console, lambda *args: inference_boundary["call"](*args))
    parent = console.ingest(actor_id=author, filename="parent.html",
        data=b"<html><body><p>Gebruik geen zalf.</p></body></html>", content_type="text/html",
        ingest_kind="new", title="Parent", version="1", date="2026-10-09", live_url="",
        class_="richtlijn", family="fixture", named_reviewers=[],
        review_policy={"contract": "explicit-review-v1", "revision": 1,
                       "primary": author, "assignments": []})["snapshot_id"]
    if native:
        import json
        monkeypatch.setenv("METIS_CONSOLE_AUTH", "entra")
        monkeypatch.setenv("METIS_ENTRA_TENANT_ID", TENANT)
        monkeypatch.setenv("METIS_ENTRA_CLIENT_ID", CLIENT)
        monkeypatch.setenv("METIS_ENTRA_CLIENT_SECRET", "synthetic-test-credential")
        monkeypatch.setenv("METIS_ENTRA_ACCOUNT_BINDINGS_JSON", json.dumps({ADMIN: author, USER: other}))
    else:
        monkeypatch.setenv("METIS_CONSOLE_AUTH", "local")
    app = create_console_app(console, trusted_origin=ORIGIN)
    microsoft = FakeMicrosoft()
    if native:
        app.state.microsoft_login = microsoft  # Only the external identity exchange is synthetic.
    return console, app, author, other, parent, native, microsoft, inference_boundary


def _sign_in(client, console, native, microsoft, *, other=False):
    if native:
        roles = ["Metis.Researcher", "Metis.Reviewer"]
        if not other:
            roles.append("Metis.Publisher")
        microsoft.claims = claims(oid=USER if other else ADMIN, roles=roles)
        assert entra_login(client, console.workflow_identity_store).status_code == 303
    else:
        login(client, "other" if other else "author")


def _session_row(console, token):
    with console.workflow_identity_store._connect() as connection:
        return connection.execute(
            "SELECT created_at,expires_at,revoked_at FROM workflow.sessions WHERE token_hash=%s",
            (_token_hash(token),)).fetchone()


def _scenario(runtime, monkeypatch, boundary, *, block_eventloop=False):
    console, app, author, other, parent, native, microsoft, inference_boundary = runtime
    parent_envelope = deepcopy(console._envelope(parent))
    parent_objects = deepcopy(console.snapshot_objects(parent))
    parent_bindings = deepcopy(console.object_review_bindings(parent))
    entered, release = Event(), Event()
    observations, provider_calls, extraction_calls = [], [], []

    def pause():
        from src.workflows.workflow_transaction_v1 import workflow_transaction_active
        try:
            asyncio.get_running_loop()
            on_loop = True
        except RuntimeError:
            on_loop = False
        observations.append((on_loop, console._store_lock_depth, workflow_transaction_active()))
        entered.set()
        assert release.wait(15), "A04_PAUSE_NOT_RELEASED"

    # This is the actual HTML extractor invoked by OperationsConsole._extract,
    # not a pause before the preparation orchestrator. It still extracts real HTML.
    import src.operations_console_v1 as kernel
    original_extract = kernel.extract_html
    def extract(*args, **kwargs):
        extraction_calls.append(1)
        if boundary == "extractor":
            pause()
        return original_extract(*args, **kwargs)
    monkeypatch.setattr(kernel, "extract_html", extract)

    def inference(*args):
        provider_calls.append(1)
        if boundary == "provider":
            pause()
        return provider(*args)
    inference_boundary["call"] = inference

    if block_eventloop:
        from src.source_processing_dispatch_v1 import SourceProcessingDispatcher
        async def synchronous_delivery(dispatcher, sid, attempt):
            dispatcher._execute(sid, attempt)
        monkeypatch.setattr(SourceProcessingDispatcher, "_deliver", synchronous_delivery)

    with TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN},
                    raise_server_exceptions=False) as client, ThreadPoolExecutor(4) as pool:
        # A second TestClient context would start another eventloop and mask A04.
        # Both HTTP clients use the FIRST client's portal but independent cookies.
        second = TestClient(app, base_url=ORIGIN, headers={"Origin": ORIGIN},
                            raise_server_exceptions=False)
        second.portal = client.portal
        try:
            _sign_in(client, console, native, microsoft)
            _sign_in(second, console, native, microsoft, other=True)
            token_a, token_b = client.cookies["console_session"], second.cookies["console_session"]
            assert token_a != token_b
            assert console.session_account(token_a)["account_id"] == author
            assert console.session_account(token_b)["account_id"] == other
            assert client.portal is second.portal

            command = {"document": parent, "expected_revision": console.objects_revision(parent),
                "command_id": "successor", "reason": "Nieuwe controle", "primary": author,
                "policy_revision": "2", "new_class": "richtlijn"}
            receipt = client.post("/review/successor", data=command, follow_redirects=False)
            assert receipt.status_code == 303, receipt.text
            child = receipt.headers["location"].split("document=")[1]
            assert not entered.is_set() and not extraction_calls and not provider_calls
            assert console.snapshot_objects(child) == []
            assert console._envelope(child).get("processing_attempts", []) == []
            assert client.post("/review/successor", data=command,
                               follow_redirects=False).headers["location"] == receipt.headers["location"]
            assert len(console.list_envelopes()) == 2
            revision = console.objects_revision(child)
            start_command = {"document": child, "command_id": "start", "expected_revision": revision}
            start_future = pool.submit(client.post, "/source-selection/start", data=start_command,
                                       follow_redirects=False)
            assert entered.wait(5), "A04_REAL_BOUNDARY_NOT_REACHED"

            def available(http, method, path, **kwargs):
                future = pool.submit(getattr(http, method), path, **kwargs)
                try:
                    response = future.result(timeout=2)
                except TimeoutError:
                    raise AssertionError("A04_HTTP_BLOCKED:" + path) from None
                assert not release.is_set(), "response arrived after extraction/provider release"
                return response

            assert available(client, "get", "/health").status_code == 200
            assert start_future.result(timeout=2).status_code == 303
            assert extraction_calls and (provider_calls if boundary == "provider" else not provider_calls)
            if native:
                # Read-only polling must preserve BOTH persisted session deadlines.
                before = [_session_row(console, token) for token in (token_a, token_b)]
                for http in (client, second):
                    status = available(http, "get", "/session/status")
                    assert status.status_code == 200
                    assert status.json()["remaining_seconds"] > 0
                assert [_session_row(console, token) for token in (token_a, token_b)] == before

            assert available(second, "get", "/ingest").status_code == 200
            denied = available(second, "get", "/review/policy", params={"document": parent})
            assert denied.status_code == 400 and "reviewer_not_named_on_snapshot" in denied.text
            received = available(second, "post", "/ingest", data={
                "ingest_kind": "new", "title": "Independent", "version": "1", "date": "2026-10-09",
                "class_": "richtlijn", "family": "independent", "review_mode": "single",
                "primary_reviewer": other, "command_id": "independent-receipt"},
                files={"file": ("other.html", b"<html><body><p>Andere bron.</p></body></html>", "text/html")},
                follow_redirects=False)
            assert received.status_code == 303, received.text
            independent = received.headers["location"].split("document=")[1].split("&")[0]
            assert console._envelope(independent)["uploader_account_id"] == other
            assert console.snapshot_objects(independent) == []
            assert console._envelope(independent).get("processing_attempts", []) == []
            assert console._verified_source_bytes(console._envelope(independent))[1]

            assert available(client, "post", "/source-selection/start", data=start_command,
                             follow_redirects=False).status_code == 303
            assert len(console._envelope(child)["processing_attempts"]) == 1
            assert len(extraction_calls) == 1
            assert len(provider_calls) == (1 if boundary == "provider" else 0)

            if native:
                # Expire the accepting browser, then revoke the other browser.
                # Neither turns passive polling into renewal, or adds a command.
                with console.workflow_identity_store._connect() as connection:
                    connection.execute("UPDATE workflow.sessions SET created_at=CURRENT_TIMESTAMP - interval '31 minutes', "
                                       "expires_at=CURRENT_TIMESTAMP - interval '1 second' "
                                       "WHERE token_hash=%s", (_token_hash(token_a),))
                expired = _session_row(console, token_a)
                assert available(client, "get", "/session/status").status_code == 401
                assert available(client, "post", "/session/renew").status_code == 401
                assert available(client, "post", "/source-selection/start", data={**start_command,
                    "command_id": "expired-command"}, follow_redirects=False).status_code == 401
                assert _session_row(console, token_a) == expired
                console.workflow_identity_store.revoke_session(token_b)
                revoked = _session_row(console, token_b)
                assert available(second, "get", "/session/status").status_code == 401
                assert available(second, "post", "/session/renew").status_code == 401
                assert available(second, "get", "/ingest", follow_redirects=False).status_code == 303
                assert _session_row(console, token_b) == revoked
                assert len(console._envelope(child)["processing_attempts"]) == 1
            assert observations == [(False, 0, False)]
        finally:
            # Runs on the test thread even when the ASGI eventloop is blocked.
            release.set()
            drain(client, app)
            second.close()

    assert console._envelope(parent) == parent_envelope
    assert console.snapshot_objects(parent) == parent_objects
    assert console.object_review_bindings(parent) == parent_bindings
    assert console._envelope(child)["processing_attempts"][-1]["state"] == "succeeded"
    assert len(console._envelope(child)["processing_attempts"]) == 1
    assert console.snapshot_objects(child)
    assert len(provider_calls) == 1 and len(extraction_calls) == 1


@pytest.mark.parametrize("boundary", ["extractor", "provider"])
def test_successor_http_available_with_independent_session(runtime, monkeypatch, boundary):
    _scenario(runtime, monkeypatch, boundary)


@pytest.mark.parametrize("boundary", ["extractor", "provider"])
@pytest.mark.parametrize("runtime", ["local"], indirect=True)
def test_probe_rejects_eventloop_execution(runtime, monkeypatch, boundary):
    # Controlled mutation confined to a disposable test fixture. The SAME HTTP
    # observer must detect the original failure; a second loop would falsely pass.
    with pytest.raises(AssertionError, match="A04_HTTP_BLOCKED:/health"):
        _scenario(runtime, monkeypatch, boundary, block_eventloop=True)
    print("A04_NEGATIVE_CONTROL=" + boundary + ":A04_HTTP_BLOCKED:/health")
