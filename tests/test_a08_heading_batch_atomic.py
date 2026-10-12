"""A08 heading batch durable all-or-nothing regression evidence.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.operations_console_v1 import ConsoleError, SNAPSHOT_OBJECT_WRITE_CONFLICT
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401
from src.operations_console_app import create_console_app
from src.review_ledger import read_events
from src.review_workboard_v1 import install_review_workboard
from tests.test_v219_review_duty_queue import _console, _accounts, _ingest


def _setup(root, factory=_console):
    console = factory(root)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    sid = receipt["snapshot_id"]
    ids = [row["object_id"] for row in console.snapshot_objects(sid) if row.get("object_type") == "heading"][:2]
    assert len(ids) == 2
    return console, accounts, sid, ids


def _client(console):
    app = create_console_app(console)
    install_review_workboard(app, console)
    client = TestClient(app, raise_server_exceptions=False)
    assert client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"}, follow_redirects=False).status_code == 303
    return client


def _state(console, sid):
    bindings = (console.workflow_review_store.read_bindings()
                if hasattr(console, "workflow_review_store")
                else console._load_map(console._bindings_path))
    storage_revision = None
    if hasattr(console, "workflow_document_store"):
        with console.workflow_document_store._connect() as connection:
            storage_revision = connection.execute(
                "SELECT revision FROM workflow.documents WHERE snapshot_id=%s", (sid,),
            ).fetchone()["revision"]
    return deepcopy((console.snapshot_objects(sid, include_blocked=True), console._envelope(sid),
                     bindings, console.objects_revision(sid), read_events(console._ledger_path), storage_revision))


def test_http_later_binding_failure_is_atomic_after_restart(tmp_path, monkeypatch):
    console, accounts, sid, ids = _setup(tmp_path)
    client = _client(console)
    before = _state(console, sid)
    save = console._save_bindings
    calls = 0

    def fail_second():
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("a08_second_binding_failure")
        save()

    monkeypatch.setattr(console, "_save_bindings", fail_second)
    response = client.post("/review/headings/batch-confirm", data={
        "snapshot_id": sid, "snapshot_revision": before[3], "object_ids": ids,
    }, follow_redirects=False)
    assert response.status_code == 500
    restarted = _console(tmp_path)
    after = _state(restarted, sid)
    statuses = [row["governance"]["validation_status"] for row in after[0] if row["object_id"] in ids]
    assert after == before, f"HTTP {response.status_code}; durable statuses after restart: {statuses}"


@pytest.fixture(params=["local", "postgres", "postgres-local-review"])
def storage(request):
    if request.param == "local":
        return _console
    config = request.getfixturevalue("workflow_postgres")
    if request.param == "postgres":
        from tests.test_review_batch_atomic_postgres import _console as native
        return lambda root: native(root, config)
    from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
    from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
    from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore

    def mixed(root):
        return PostgresWorkflowDurablePublicationConsole(
            root=root, source_store=root / "sources", runtime=root / "runtime",
            workflow_identity_store=PostgresWorkflowIdentityStore(config),
            workflow_document_store=PostgresConcurrentWorkflowDocumentStore(config),
        )
    return mixed


def _post(client, sid, ids, revision):
    return client.post("/review/headings/batch-confirm", data={
        "snapshot_id": sid, "object_ids": ids, "snapshot_revision": revision,
    }, follow_redirects=False)


@pytest.mark.parametrize("position", [1, 2])
@pytest.mark.parametrize("write", ["objects", "bindings", "envelope", "audit"])
def test_write_failure_preserves_complete_state(storage, tmp_path, monkeypatch, position, write):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    client = _client(console)
    before = _state(console, sid)
    native = hasattr(console, "workflow_document_store")
    review_native = hasattr(console, "workflow_review_store")
    if write in {"objects", "envelope"} and native:
        target, name = console.workflow_document_store, "write_bundle"
    elif write == "objects":
        target, name = console, "_save_objects_pinned"
    elif write == "envelope":
        target, name = console, "_save_envelopes"
    elif write == "bindings":
        target, name = console, "_save_bindings"
    elif review_native:
        target, name = console.workflow_review_store, "_insert_event"
    else:
        from src import operations_console_v1
        target, name = operations_console_v1, "append_event"
    original = getattr(target, name)
    calls = 0

    def fail_after_write(*args, **kwargs):
        nonlocal calls
        result = original(*args, **kwargs)
        calls += 1
        if calls == position:
            raise OSError(f"a08_{write}_{position}")
        return result

    monkeypatch.setattr(target, name, fail_after_write)
    assert _post(client, sid, ids, before[3]).status_code == 500
    assert calls == position
    assert _state(storage(tmp_path), sid) == before


def test_late_conflict_discards_own_first_member(storage, tmp_path, monkeypatch):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    before = _state(console, sid)
    original = console.review_object
    calls = 0

    def conflict_second(**command):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        return original(**command)

    monkeypatch.setattr(console, "review_object", conflict_second)
    assert _post(_client(console), sid, ids, before[3]).status_code == 409
    assert _state(storage(tmp_path), sid) == before


def test_success_duplicates_repeat_and_stale(storage, tmp_path):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    client = _client(console)
    revision = console.objects_revision(sid)
    assert _post(client, sid, ids + ids, revision).status_code == 303
    restarted = storage(tmp_path)
    committed = _state(restarted, sid)
    current = restarted.snapshot_objects(sid)
    assert all(row["governance"]["validation_status"] == "approved" for row in current if row["object_id"] in ids)
    assert len([e for e in committed[4] if e.get("object_id") in ids]) == 2
    assert _post(client, sid, ids, revision).status_code == 409
    assert _state(storage(tmp_path), sid) == committed
    assert _post(client, sid, ids, committed[3]).status_code == 303
    assert _state(storage(tmp_path), sid) == committed


@pytest.mark.parametrize("rejection", ["role", "not_named", "unsuitable", "unknown", "empty", "published"])
def test_direct_rejections_make_no_writes(storage, tmp_path, rejection):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    actor = accounts["reviewer"]["account_id"]
    selected = ids
    if rejection == "role":
        actor = accounts["publisher"]["account_id"]
    elif rejection == "not_named":
        actor = console.create_account(username="outsider", password="isolated-test", roles=("reviewer",))["account_id"]
    elif rejection == "unsuitable":
        selected = ids + [next(row["object_id"] for row in console.snapshot_objects(sid) if row.get("object_type") != "heading")]
    elif rejection == "unknown":
        selected = ids + ["nonexistent-a08"]
    elif rejection == "published":
        envelope = deepcopy(console._envelope(sid))
        envelope["state"] = "published"
        if hasattr(console, "workflow_document_store"):
            console.workflow_document_store.write_bundle(envelope=envelope)
        else:
            console._envelopes[sid] = envelope
            console._save_envelopes()
        console = storage(tmp_path)
    else:
        selected = []
    before = _state(console, sid)
    with pytest.raises(ConsoleError):
        console.batch_confirm_headings(actor_id=actor, snapshot_id=sid, object_ids=selected, expected_revision=before[3])
    assert _state(storage(tmp_path), sid) == before


def test_direct_command_success_and_late_failure(storage, tmp_path, monkeypatch):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    actor = accounts["reviewer"]["account_id"]
    before = _state(console, sid)
    original = console.review_object

    def fail_second(**command):
        if command["object_id"] == ids[1]:
            raise RuntimeError("a08_late_member")
        return original(**command)

    monkeypatch.setattr(console, "review_object", fail_second)
    with pytest.raises(RuntimeError, match="a08_late_member"):
        console.batch_confirm_headings(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=before[3])
    assert _state(storage(tmp_path), sid) == before
    monkeypatch.setattr(console, "review_object", original)
    result = console.batch_confirm_headings(actor_id=actor, snapshot_id=sid, object_ids=ids, expected_revision=before[3])
    assert {row["object_id"] for row in result} == set(ids)
    assert console.objects_revision(sid) != before[3]


def test_concurrent_same_revision_preserves_winner(storage, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import contextmanager
    from threading import Event

    first, accounts, sid, ids = _setup(tmp_path, storage)
    # Independent runtimes also prove the native row lock, not just flock.
    second_root = tmp_path / "worker2" if hasattr(first, "workflow_review_store") else tmp_path
    second = storage(second_root)
    clients = [_client(first), _client(second)]
    revision = first.objects_revision(sid)
    first_has_written, second_has_entered = Event(), Event()
    original_review = first.review_object
    original_boundary = second._heading_batch_mutation

    def hold_first(**command):
        result = original_review(**command)
        if command["object_id"] == ids[0]:
            first_has_written.set()
            assert second_has_entered.wait(10)
        return result

    @contextmanager
    def observe_second(snapshot_id):
        second_has_entered.set()
        with original_boundary(snapshot_id):
            yield

    monkeypatch.setattr(first, "review_object", hold_first)
    monkeypatch.setattr(second, "_heading_batch_mutation", observe_second)
    with ThreadPoolExecutor(max_workers=2) as pool:
        winner = pool.submit(_post, clients[0], sid, ids, revision)
        assert first_has_written.wait(10)
        loser = pool.submit(_post, clients[1], sid, ids, revision)
        assert winner.result(timeout=20).status_code == 303
        assert loser.result(timeout=20).status_code == 409
    committed = _state(storage(tmp_path), sid)
    assert all(row["governance"]["validation_status"] == "approved" for row in storage(tmp_path).snapshot_objects(sid) if row["object_id"] in ids)
    assert len([e for e in committed[4] if e.get("object_id") in ids]) == 2
    assert _post(clients[1], sid, ids, revision).status_code == 409
    assert _state(storage(second_root), sid) == committed


@pytest.mark.parametrize("review_authority", [True, False])
def test_native_final_commit_failure_preserves_fresh_state(workflow_postgres, tmp_path, monkeypatch, review_authority):
    import psycopg
    from tests.test_review_batch_atomic_postgres import _console as native

    if review_authority:
        factory = lambda root: native(root, workflow_postgres)
    else:
        from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
        from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
        from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
        factory = lambda root: PostgresWorkflowDurablePublicationConsole(
            root=root, source_store=root / "sources", runtime=root / "runtime",
            workflow_identity_store=PostgresWorkflowIdentityStore(workflow_postgres),
            workflow_document_store=PostgresConcurrentWorkflowDocumentStore(workflow_postgres),
        )
    console, accounts, sid, ids = _setup(tmp_path, factory)
    client = _client(console)
    before = _state(console, sid)
    from contextlib import contextmanager
    original_write = console.workflow_document_store.write_bundle
    original_boundary = console._heading_batch_mutation
    writes, commit_errors = [], []

    def observe_write(**command):
        result = original_write(**command)
        writes.append(command["envelope"]["snapshot_id"])
        return result

    @contextmanager
    def observe_commit(snapshot_id):
        try:
            with original_boundary(snapshot_id):
                yield
        except psycopg.errors.RaiseException as exc:
            commit_errors.append(str(exc))
            raise

    monkeypatch.setattr(console.workflow_document_store, "write_bundle", observe_write)
    monkeypatch.setattr(console, "_heading_batch_mutation", observe_commit)
    # A real deferred constraint trigger fires after all member writes and audit
    # flush, when PostgreSQL executes the outer COMMIT, not at a mocked seam.
    with psycopg.connect(workflow_postgres.dsn, autocommit=True) as connection:
        connection.execute("CREATE FUNCTION workflow.a08_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'a08_deferred_commit_failure'; END $$")
        connection.execute("CREATE CONSTRAINT TRIGGER a08_commit_failure AFTER UPDATE ON workflow.documents DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION workflow.a08_commit_failure()")
    assert _post(client, sid, ids, before[3]).status_code == 500
    assert writes == [sid, sid]
    assert len(commit_errors) == 1 and "a08_deferred_commit_failure" in commit_errors[0]
    assert _state(factory(tmp_path), sid) == before


def test_second_object_storage_conflict_rolls_back_batch(storage, tmp_path, monkeypatch):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    client = _client(console)
    before = _state(console, sid)
    if hasattr(console, "workflow_document_store"):
        target, name = console.workflow_document_store, "write_bundle"
        from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
        error = WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
    else:
        target, name = console, "_save_objects_pinned"
        error = ConsoleError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
    original = getattr(target, name)
    calls = 0

    def conflict_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise error
        return original(*args, **kwargs)

    monkeypatch.setattr(target, name, conflict_second)
    assert _post(client, sid, ids, before[3]).status_code == 409
    assert calls == 2
    assert _state(storage(tmp_path), sid) == before


def test_stale_local_account_roles_are_rechecked(tmp_path):
    console, accounts, sid, ids = _setup(tmp_path)
    other = _console(tmp_path)
    account = accounts["reviewer"]["account_id"]
    other._accounts[account]["roles"] = ["publisher"]
    other._save_accounts()
    before = _state(console, sid)
    with pytest.raises(ConsoleError, match="reviewer_role_required"):
        console.batch_confirm_headings(actor_id=account, snapshot_id=sid, object_ids=ids, expected_revision=before[3])
    assert _state(_console(tmp_path), sid) == before


@pytest.mark.parametrize("rejection", ["role", "unsuitable"])
def test_http_rejection_does_not_write(storage, tmp_path, rejection):
    console, accounts, sid, ids = _setup(tmp_path, storage)
    client = _client(console)
    if rejection == "role":
        assert client.post("/login", data={"username": "publisher.carla", "password": "carla-secret"}, follow_redirects=False).status_code == 303
    else:
        ids.append(next(row["object_id"] for row in console.snapshot_objects(sid) if row.get("object_type") != "heading"))
    before = _state(console, sid)
    response = _post(client, sid, ids, before[3])
    assert response.status_code in {400, 403}
    assert _state(storage(tmp_path), sid) == before


def test_new_process_restart_preserves_failed_and_committed_batch(storage, tmp_path, monkeypatch):
    import json
    import subprocess
    import sys

    console, accounts, sid, ids = _setup(tmp_path, storage)
    native = hasattr(console, "workflow_document_store")
    review_native = hasattr(console, "workflow_review_store")
    mode = "postgres" if review_native else "postgres-local-review" if native else "local"
    before = _state(console, sid)
    original = console.review_object

    def fail_second(**command):
        if command["object_id"] == ids[1]:
            raise RuntimeError("a08_restart_failure")
        return original(**command)

    def restarted_state():
        code = '''
import json, os, sys
from pathlib import Path
from tests.test_a08_heading_batch_atomic import _state
from tests.test_v219_review_duty_queue import _console
root, sid, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
if mode != "local":
    from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
    config = PostgresCanonicalConfig(dsn=os.environ["METIS_TEST_POSTGRES_DSN"])
    if mode == "postgres":
        from tests.test_review_batch_atomic_postgres import _console as native
        console = native(root, config)
    else:
        from src.workflows.workflow_documents_cutover_v1 import PostgresWorkflowDurablePublicationConsole
        from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
        from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
        console = PostgresWorkflowDurablePublicationConsole(
            root=root, source_store=root / "sources", runtime=root / "runtime",
            workflow_identity_store=PostgresWorkflowIdentityStore(config),
            workflow_document_store=PostgresConcurrentWorkflowDocumentStore(config))
else:
    console = _console(root)
print(json.dumps(_state(console, sid)))
'''
        completed = subprocess.run([sys.executable, "-c", code, str(tmp_path), sid, mode],
                                   capture_output=True, text=True, timeout=30, check=True)
        return json.loads(completed.stdout)

    monkeypatch.setattr(console, "review_object", fail_second)
    with pytest.raises(RuntimeError, match="a08_restart_failure"):
        console.batch_confirm_headings(actor_id=accounts["reviewer"]["account_id"], snapshot_id=sid,
                                       object_ids=ids, expected_revision=before[3])
    assert restarted_state() == json.loads(json.dumps(before))
    monkeypatch.setattr(console, "review_object", original)
    console.batch_confirm_headings(actor_id=accounts["reviewer"]["account_id"], snapshot_id=sid,
                                   object_ids=ids, expected_revision=before[3])
    assert restarted_state() == json.loads(json.dumps(_state(console, sid)))


@pytest.mark.parametrize("table", ["documents", "document_objects", "publish_authorizations", "review_events"])
@pytest.mark.parametrize("member", [0, 1])
def test_native_sql_write_failure_rolls_back_batch(workflow_postgres, tmp_path, monkeypatch, table, member):
    from contextlib import contextmanager
    import psycopg
    from psycopg import sql
    from tests.test_review_batch_atomic_postgres import _console as native

    factory = lambda root: native(root, workflow_postgres)
    console, accounts, sid, ids = _setup(tmp_path, factory)
    client = _client(console)
    before = _state(console, sid)
    failures = []
    original_boundary = console._heading_batch_mutation

    @contextmanager
    def observe_failure(snapshot_id):
        try:
            with original_boundary(snapshot_id):
                yield
        except Exception as exc:
            while exc.__cause__ is not None:
                exc = exc.__cause__
            failures.append(exc)
            raise

    monkeypatch.setattr(console, "_heading_batch_mutation", observe_failure)
    with psycopg.connect(workflow_postgres.dsn, autocommit=True) as connection:
        if table == "documents":
            connection.execute("CREATE SEQUENCE workflow.a08_write_counter")
            condition = sql.SQL("nextval('workflow.a08_write_counter') = {} AND NEW.snapshot_id = {}").format(
                sql.Literal(member + 1), sql.Literal(sid))
            action = sql.SQL("UPDATE")
        elif table == "document_objects":
            condition = sql.SQL("NEW.object_id = {} AND NEW.payload->'governance'->>'validation_status' = 'approved'").format(sql.Literal(ids[member]))
            action = sql.SQL("INSERT")
        else:
            condition = sql.SQL("NEW.object_id = {}").format(sql.Literal(ids[member]))
            action = sql.SQL("INSERT")
        # PostgreSQL itself rejects a statement mid-write. The wrapper above
        # only records the propagated native error; it does not mock storage.
        body = sql.SQL("BEGIN IF {} THEN RAISE EXCEPTION 'a08_native_write_failure'; END IF; RETURN NEW; END;").format(condition)
        connection.execute(sql.SQL("CREATE FUNCTION workflow.a08_write_failure() RETURNS trigger LANGUAGE plpgsql AS {}").format(sql.Literal(body.as_string(connection))))
        connection.execute(sql.SQL("CREATE TRIGGER a08_write_failure AFTER {} ON workflow.{} FOR EACH ROW EXECUTE FUNCTION workflow.a08_write_failure()").format(action, sql.Identifier(table)))
    assert _post(client, sid, ids, before[3]).status_code >= 400
    assert len(failures) == 1
    assert isinstance(failures[0], psycopg.errors.RaiseException)
    assert "a08_native_write_failure" in str(failures[0])
    assert _state(factory(tmp_path), sid) == before
