"""A01 admission must not turn denied commands into durable attempts.

# release-control-evidence: scope/belofte opslag concurrent stale interrupt retry version-compat
# release-control-evidence: toegang beschikbaarheid kwaliteit slop releasebewijs
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import json
import sys

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError
from src.source_processing_dispatch_v1 import claim, SourceProcessingDispatcher
from tests.test_availability_repair import accounts, bind, state, provider, installed_app, login
from tests.test_source_dispatch_hardening import receive
from tests.test_review_batch_atomic_postgres import _console
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401


@pytest.fixture(params=["local", "postgres"])
def console(request, tmp_path):
    if request.param == "postgres":
        return _console(tmp_path, request.getfixturevalue("workflow_postgres"))
    return state(tmp_path)


def snapshot(console, sid):
    return deepcopy((console._envelope(sid), console.snapshot_objects(sid),
                     console.object_review_bindings(sid)))


def test_denied_retry_has_no_durable_effect(console):
    author, reviewer = accounts(console)
    outsider = console.create_account(username="outsider", password="fixture-only", roles=("reviewer",))
    calls = []
    bind(console, lambda *args: calls.append(1))
    sid = receive(console, author, reviewer, "denied-retry")
    before = snapshot(console, sid)
    with pytest.raises(ConsoleError, match="reviewer_not_named_on_snapshot"):
        console.retry_pre_review(actor_id=outsider["account_id"], snapshot_id=sid, command_id="denied")
    assert calls == []
    assert snapshot(console, sid) == before, "A01_DENIED_RETRY_MUTATED_WORKFLOW"


def restart(console):
    if hasattr(console, "workflow_identity_store"):
        return _console(console.root, console.workflow_identity_store.config)
    return state(console.root)


def revoke(console, actor, sid, change):
    """A separate kernel writes the existing authorities; the worker stays stale."""
    other = restart(console)
    if change == "assignment":
        with other._reprocessing_transaction(sid):
            envelope = deepcopy(other._envelope(sid))
            envelope["named_reviewers"] = [a for a in envelope["named_reviewers"] if a != actor]
            other._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    elif change == "roles":
        author = next(a for a in other.list_accounts() if a["username"] == "author")
        other.assign_roles(actor_id=author["account_id"], account_id=actor, roles=("publisher",))
    else:
        if hasattr(other, "workflow_identity_store"):
            from src.workflows.account_retirement_v1 import retire_account
            author = next(a for a in other.list_accounts() if a["username"] == "author")
            with other.workflow_identity_store._connect() as connection:
                connection.execute((Path(__file__).parents[1] / "db/migrations/015_historical_accounts.sql").read_text())
            with other.workflow_identity_store._connect() as connection:
                retire_account(connection, account_id=actor, actor_id=author["account_id"],
                               reason="Synthetic A01 retirement", apply=True)
        else:
            rows = other._load_map(other._accounts_path)
            rows[actor]["retirement"] = {"reason": "Synthetic A01 retirement"}
            other._accounts_path.write_text(json.dumps(rows))


@pytest.mark.parametrize("entry", ["retry", "reserve", "resume", "reextract", "cli", "execute", "claim", "internal"])
@pytest.mark.parametrize("role", ["reviewer", "publisher"])
def test_all_denied_entry_points_preserve_source_attempts_and_budget(console, monkeypatch, entry, role):
    author, reviewer = accounts(console)
    actor = console.create_account(username="outsider", password="fixture-only", roles=(role,))["account_id"]
    sid = receive(console, author, reviewer, "all-denials")
    bind(console, provider)
    attempt = console.reserve_source_selection(actor_id=reviewer, snapshot_id=sid,
        command_id="authorized", expected_revision=console.objects_revision(sid))[0]
    before = snapshot(console, sid)
    def forbidden(*args, **kwargs):
        raise AssertionError("A01_DENIED_COMMAND_REACHED_PREPARATION")
    monkeypatch.setattr(console, "_extract", forbidden)
    command = dict(actor_id=actor, snapshot_id=sid, command_id="denied")
    with pytest.raises(ConsoleError) as caught:
        if entry == "retry":
            console.retry_pre_review(**command)
        elif entry == "reserve":
            console.reserve_source_selection(**command, expected_revision=console.objects_revision(sid))
        elif entry == "resume":
            console.resume_formation(**command, expected_revision=console.objects_revision(sid))
        elif entry == "reextract":
            console.reextract_unpublished(actor_id=actor, snapshot_id=sid, _attempt_id=attempt["attempt_id"])
        elif entry == "execute":
            console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
        elif entry == "claim":
            claim(console, actor_id=actor, snapshot_id=sid, attempt_id=attempt["attempt_id"])
        elif entry == "internal":
            console._execute_source_attempt(actor_id=actor, snapshot_id=sid, attempt=attempt, deadline=0)
        else:
            from src.cli import cmd_processing_retry
            monkeypatch.setitem(sys.modules, "src.console_asgi", SimpleNamespace(
                app=SimpleNamespace(state=SimpleNamespace(operations_kernel=console))))
            cmd_processing_retry(SimpleNamespace(**command))
    assert caught.value.code == ("reviewer_not_named_on_snapshot" if role == "reviewer" else "researcher_role_required")
    assert snapshot(restart(console), sid) == before


@pytest.mark.parametrize("change", ["none", "roles", "retirement"])
def test_separate_publisher_recovery_requires_current_authority(console, change):
    from src.bounded_model_call_v1 import ModelCallLimits
    from src.processing_retry_v1 import reserve, finish, now
    author, reviewer = accounts(console)
    publisher = console.create_account(username="recovery-publisher", password="fixture-only",
        roles=("publisher", "reviewer"))["account_id"]
    sid = receive(console, author, publisher, "recovery-authority")
    console.assign_roles(actor_id=author, account_id=publisher, roles=("publisher",))
    limits = ModelCallLimits(max_attempts=1)
    console._model_call_limits_reader = lambda: limits
    with console._reprocessing_transaction(sid):
        envelope = deepcopy(console._envelope(sid))
        attempt, _ = reserve(envelope, actor_id=author, command_id="exhausted",
            revision=console.objects_revision(sid), clock=now(), limits=limits)
        finish(envelope, attempt["attempt_id"], state="failed", error=ConsoleError("fixture_failure"))
        console._commit_prepared_store(envelopes={sid: envelope}, snapshot_id=sid)
    if change == "roles":
        restart(console).assign_roles(actor_id=author, account_id=publisher, roles=("reviewer",))
    elif change == "retirement":
        revoke(console, publisher, sid, change)
    before = snapshot(restart(console), sid)
    if change == "none":
        grant = console.authorize_processing_recovery(actor_id=publisher, snapshot_id=sid, reason="Synthetic repair")
        assert grant["consumed_by"] is None
        with pytest.raises(ConsoleError, match="researcher_role_required"):
            console.retry_pre_review(actor_id=publisher, snapshot_id=sid, command_id="no-processing-right")
        assert console._envelope(sid)["processing_recovery"] == grant
        assert console._envelope(sid)["processing_attempts"] == before[0]["processing_attempts"]
    else:
        with pytest.raises(ConsoleError, match="publisher_role_required" if change == "roles" else "not_authenticated"):
            console.authorize_processing_recovery(actor_id=publisher, snapshot_id=sid, reason="Synthetic repair")
        assert snapshot(restart(console), sid) == before


def test_installed_http_denials_have_no_effect(console, monkeypatch):
    author, reviewer = accounts(console)
    sid = receive(console, author, reviewer, "http-denial")
    console.create_account(username="outsider", password="fixture-only", roles=("reviewer",))
    before = snapshot(console, sid)
    def forbidden(*args, **kwargs):
        raise AssertionError("A01_HTTP_DENIAL_STARTED_EXTRACTION")
    monkeypatch.setattr(console, "_extract", forbidden)
    with TestClient(installed_app(console), base_url="https://testserver") as client:
        login(client, "outsider")
        for route in ("/tree/reprocess", "/tree/resume-formation"):
            assert client.post(route, data={"snapshot_id": sid}, follow_redirects=False).status_code == 400
        assert client.post("/source-selection/start", data={"document": sid, "command_id": "denied",
            "expected_revision": console.objects_revision(sid)}, follow_redirects=False).status_code == 400
    assert snapshot(restart(console), sid) == before


@pytest.mark.parametrize("change", ["assignment", "roles", "retirement"])
def test_revocation_before_claim_duplicate_and_direct_retry_cannot_mutate(console, change):
    author, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, author, reviewer, "revoked")
    revision = console.objects_revision(sid)
    attempt = console.reserve_source_selection(actor_id=reviewer, snapshot_id=sid,
        command_id="existing", expected_revision=revision)[0]
    revoke(console, reviewer, sid, change)
    before = snapshot(restart(console), sid)
    for action in (
        lambda: console.reserve_source_selection(actor_id=reviewer, snapshot_id=sid,
            command_id="existing", expected_revision=revision),
        lambda: console.retry_pre_review(actor_id=reviewer, snapshot_id=sid, command_id="existing"),
        lambda: console.execute_source_selection(actor_id=reviewer, snapshot_id=sid, attempt=attempt),
        lambda: claim(console, snapshot_id=sid, attempt_id=attempt["attempt_id"]),
        lambda: SourceProcessingDispatcher(console)._execute(sid, attempt),
    ):
        with pytest.raises(ConsoleError):
            action()
        assert snapshot(restart(console), sid) == before


@pytest.mark.parametrize("entry", ["retry", "reserve", "reextract"])
@pytest.mark.parametrize("actor_kind", ["named-reviewer", "researcher"])
def test_authorized_controls_and_successful_duplicate_recheck(console, entry, actor_kind):
    author, reviewer = accounts(console)
    actor = reviewer
    if actor_kind == "researcher":
        actor = console.create_account(username="researcher-only", password="fixture-only", roles=("researcher",))["account_id"]
    calls = []
    def success(*args):
        calls.append(1)
        return provider(*args)
    bind(console, success)
    sid = receive(console, author, reviewer, "positive")
    revision = console.objects_revision(sid)
    if entry == "retry":
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="success")
    elif entry == "reserve":
        attempt = console.reserve_source_selection(actor_id=actor, snapshot_id=sid,
            command_id="success", expected_revision=revision)[0]
        console.execute_source_selection(actor_id=actor, snapshot_id=sid, attempt=attempt)
    else:
        console.reextract_unpublished(actor_id=actor, snapshot_id=sid)
    assert calls == [1] and console.snapshot_objects(sid)
    assert console._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded"
    # Successful duplicate is protected too; role loss cannot expose old receipt.
    author_account = next(a for a in console.list_accounts() if a["username"] == "author")
    restart(console).assign_roles(actor_id=author_account["account_id"], account_id=actor, roles=("publisher",))
    before = snapshot(restart(console), sid)
    with pytest.raises(ConsoleError, match="researcher_role_required"):
        console.retry_pre_review(actor_id=actor, snapshot_id=sid, command_id="success")
    assert snapshot(restart(console), sid) == before and calls == [1]


@pytest.mark.parametrize("boundary", ["extraction", "provider"])
@pytest.mark.parametrize("change", ["assignment", "roles"])
def test_revocation_during_preparation_cannot_activate(console, monkeypatch, boundary, change):
    author, reviewer = accounts(console)
    sid = receive(console, author, reviewer, "paused")
    entered, release = Event(), Event()
    calls = []
    original = console._extract
    def extract(*args, **kwargs):
        if boundary == "extraction":
            entered.set()
            assert release.wait(10)
        return original(*args, **kwargs)
    def paused_provider(*args):
        calls.append(1)
        if boundary == "provider":
            entered.set()
            assert release.wait(10)
        return provider(*args)
    monkeypatch.setattr(console, "_extract", extract)
    bind(console, paused_provider)
    attempt = console.reserve_source_selection(actor_id=reviewer, snapshot_id=sid,
        command_id="paused", expected_revision=console.objects_revision(sid))[0]
    source_bytes = console._verified_source_bytes(console._envelope(sid))[1]
    with ThreadPoolExecutor(1) as pool:
        work = pool.submit(console.execute_source_selection, actor_id=reviewer, snapshot_id=sid, attempt=attempt)
        try:
            assert entered.wait(5)
            revoke(console, reviewer, sid, change)
        finally:
            release.set()
        with pytest.raises(ConsoleError):
            work.result(timeout=10)
    final = restart(console)
    assert final.snapshot_objects(sid) == [] and final.object_review_bindings(sid) == []
    assert final._verified_source_bytes(final._envelope(sid))[1] == source_bytes
    assert len(final._envelope(sid)["processing_attempts"]) == 1
    assert final._envelope(sid)["processing_attempts"][0]["state"] == "failed"
    assert len(calls) == (1 if boundary == "provider" else 0)


def test_other_authorized_actor_cannot_claim_or_fail_another_attempt(console):
    author, reviewer = accounts(console)
    bind(console, provider)
    sid = receive(console, author, reviewer, "actor-conflict")
    attempt = console.reserve_source_selection(actor_id=reviewer, snapshot_id=sid,
        command_id="owned", expected_revision=console.objects_revision(sid))[0]
    before = snapshot(console, sid)
    for delivered in (attempt, {k: v for k, v in attempt.items() if k != "dispatch"}):
        with pytest.raises(ConsoleError, match="processing_command_conflict"):
            console.execute_source_selection(actor_id=author, snapshot_id=sid, attempt=delivered)
        assert snapshot(restart(console), sid) == before


def test_actual_resume_preserves_completed_work_and_denies_outsider(console, monkeypatch):
    from tests.test_recoverable_formation_v1 import system
    first, sid, author, reviewer, calls, mode, make, attach = system(
        console.root, make_console=lambda: console)
    outsider = first.create_account(username="outsider", password="fixture-only", roles=("reviewer",))["account_id"]
    before = snapshot(first, sid)
    prior_calls = len(calls)
    with pytest.raises(ConsoleError, match="reviewer_not_named_on_snapshot"):
        first.resume_formation(actor_id=outsider, snapshot_id=sid,
            command_id="denied-resume", expected_revision=first.objects_revision(sid))
    assert snapshot(first, sid) == before and len(calls) == prior_calls
    mode["broken"] = False
    first.resume_formation(actor_id=reviewer, snapshot_id=sid,
        command_id="authorized-resume", expected_revision=first.objects_revision(sid))
    assert len(calls) == prior_calls + 1
    assert first._envelope(sid)["processing_attempts"][-1]["state"] == "succeeded"
    retained = next(row for row in before[1] if row.get("metadata", {}).get("admission", {}).get("gate_result") == "allowed")
    assert next(row for row in first.snapshot_objects(sid) if row["object_id"] == retained["object_id"]) == retained


@pytest.mark.parametrize("boundary", ["admission", "standalone_activation"])
def test_native_revocation_is_ordered_with_short_admission(workflow_postgres, tmp_path, monkeypatch, boundary):
    import psycopg
    from time import monotonic, sleep
    first = _console(tmp_path, workflow_postgres)
    author, reviewer = accounts(first)
    bind(first, provider)
    sid = receive(first, author, reviewer, "native-order")
    if boundary == "standalone_activation":
        first.retry_pre_review(actor_id=reviewer, snapshot_id=sid, command_id="initial")
        # The explicit deterministic reextract path has no reserved attempt.
        first._pre_review_semantic_bound = False
    other = restart(first)
    admitted, release, update_started = Event(), Event(), Event()
    commit = first._commit_prepared_store
    def paused_commit(**kwargs):
        if (kwargs.get("objects") if boundary == "standalone_activation" else
                kwargs.get("envelopes", {}).get(sid, {}).get("processing_attempts")):
            admitted.set()
            assert release.wait(10)
        return commit(**kwargs)
    monkeypatch.setattr(first, "_commit_prepared_store", paused_commit)
    def change_roles():
        update_started.set()
        other.assign_roles(actor_id=author, account_id=reviewer, roles=("publisher",))
    with ThreadPoolExecutor(2) as pool:
        work = (pool.submit(first.reserve_source_selection, actor_id=reviewer, snapshot_id=sid,
            command_id="ordered", expected_revision=first.objects_revision(sid))
            if boundary == "admission" else pool.submit(first.reextract_unpublished,
                actor_id=reviewer, snapshot_id=sid))
        try:
            assert admitted.wait(5)
            update = pool.submit(change_roles)
            assert update_started.wait(2)
            deadline = monotonic() + 3
            blocked = False
            while monotonic() < deadline and not blocked:
                with psycopg.connect(workflow_postgres.dsn) as con:
                    blocked = bool(con.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() "
                        "AND query LIKE 'UPDATE workflow.accounts SET roles=%' AND cardinality(pg_blocking_pids(pid))>0").fetchone())
                if not blocked:
                    sleep(.01)
            assert blocked and not update.done(), "A01_IDENTITY_NOT_FENCED_THROUGH_ADMISSION_COMMIT"
        finally:
            release.set()
        result = work.result(timeout=5)
        update.result(timeout=5)
    if boundary == "standalone_activation":
        assert result["snapshot_id"] == sid
        assert len(first._envelope(sid)["processing_attempts"]) == 1
    else:
        attempt, fresh = result
        assert fresh
    before = snapshot(restart(first), sid)
    with pytest.raises(ConsoleError, match="researcher_role_required"):
        if boundary == "admission":
            first.execute_source_selection(actor_id=reviewer, snapshot_id=sid, attempt=attempt)
        else:
            first.reextract_unpublished(actor_id=reviewer, snapshot_id=sid)
    assert snapshot(restart(first), sid) == before
