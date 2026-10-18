"""#708: refuse ownerless reprocessing and prove R+ mirror/rollback boundaries.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
from src.operations_console_v1 import ConsoleError
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore
from src.workflows.workflow_transaction_v1 import bind_workflow_stores, workflow_transaction
from tests.test_678_store_command_postgres import (
    _assert_document_mirrors_equal_pg, _spy_mirror_writes_inside_transaction,
)
from tests.test_r2_rollback_remirror_postgres import _approve, _assert_disk_mirrors_equal_pg, _state
from tests.test_durable_publication_console_v1 import MemorySourceStore


@pytest.fixture
def isolated_postgres():
    """Own a database; never reset schemas in the supplied test database."""
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN required for native #708 evidence")
    database = "metis_708_" + uuid4().hex
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
    isolated = make_conninfo(dsn, dbname=database)
    try:
        root = Path(__file__).resolve().parents[1]
        with psycopg.connect(isolated, autocommit=True) as connection:
            for path in [root / "db/schema_v2.sql", *sorted((root / "db/migrations").glob("*.sql"))]:
                connection.execute(path.read_text(encoding="utf-8"))
        yield PostgresCanonicalConfig(dsn=isolated)
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


def _console(root, config, console_cls):
    identity = CutoverPostgresWorkflowIdentityStore(config)
    documents = PostgresConcurrentWorkflowDocumentStore(config)
    reviews = PostgresWorkflowReviewStore(config)
    remaining = PostgresWorkflowRemainingStore(config)
    bind_workflow_stores(identity, documents, reviews, remaining)
    return console_cls(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=identity, workflow_document_store=documents,
        workflow_review_store=reviews, workflow_remaining_store=remaining,
        canonical_publication_store=PostgresCanonicalPublicationStore(config),
        immutable_source_store=MemorySourceStore(),
    )


@pytest.fixture(params=[
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
], ids=["local-r-plus", "azure-r-plus"])
def prepared(request, tmp_path, isolated_postgres):
    console = _console(tmp_path, isolated_postgres, request.param)
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    author = console.create_account("anne", "anne-secret", roles=["researcher"])
    reviewer = console.create_account("bert", "bert-secret", roles=["reviewer"])
    receipt = console.ingest(
        actor_id=author["account_id"], filename="begrippen.html", content_type="text/html",
        data=b"<html><body><h1>Begrippen</h1><h2>1 Begrippen</h2>"
             b"<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>"
             b"<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>",
        ingest_kind="new", title="Begrippen", version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family="begrippen", named_reviewers=[reviewer["account_id"]],
    )
    sid = receipt["snapshot_id"]
    from src.proportionate_review_v1 import normal_risk_batch_queue
    objects = normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn",
        fragments=console.review_source_fragments(sid), bindings=console.object_review_bindings(sid))
    assert objects
    return console, reviewer["account_id"], sid, objects[0]


def _assert_mirrors(console, sid):
    _assert_disk_mirrors_equal_pg(console)
    _assert_document_mirrors_equal_pg(console, sid)


def test_ownerless_raw_transaction_refused_before_reload_or_writes(prepared, monkeypatch):
    console, _, sid, _ = prepared
    before = deepcopy(_state(console, sid))
    envelope = console.workflow_document_store.get_envelope(sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    reloads, entered = [], []
    original = console._reload_store_locked

    def reload():
        reloads.append(True)
        return original()

    monkeypatch.setattr(console, "_reload_store_locked", reload)
    with workflow_transaction(console.workflow_review_store):
        with pytest.raises(ConsoleError, match="^reprocessing_store_command_required$"):
            with console._reprocessing_transaction(sid):
                entered.append(True)
        # Catching the refusal does not abort the caller's own transaction.
        assert console.workflow_document_store.get_envelope(sid) == envelope
    assert entered == []
    assert reloads == []
    assert inside == []
    assert _state(console, sid) == before
    _assert_mirrors(console, sid)


@pytest.mark.parametrize("nested", [False, True])
def test_valid_reprocessing_commits_and_mirrors_afterward(prepared, monkeypatch, nested):
    console, reviewer, sid, obj = prepared
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    with console._reprocessing_transaction(sid):
        if nested:
            with console._reprocessing_transaction(sid):
                _approve(console, reviewer, sid, obj)
        else:
            _approve(console, reviewer, sid, obj)
    assert inside == []
    assert any(binding["object_id"] == obj["object_id"]
               for binding in console.workflow_review_store.read_bindings()[sid])
    _assert_mirrors(console, sid)


def test_foreign_reprocessing_is_refused(prepared, tmp_path, isolated_postgres, monkeypatch):
    console, _, sid, _ = prepared
    other = _console(tmp_path / "other", isolated_postgres, type(console))
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    with console._reprocessing_transaction(sid):
        with pytest.raises(ConsoleError, match="^store_command_foreign_owner$"):
            with other._reprocessing_transaction(sid):
                pytest.fail("foreign reprocessing was admitted")
    assert inside == []
    _assert_mirrors(console, sid)


def _change_all(console, reviewer, sid, obj):
    _approve(console, reviewer, sid, obj)
    envelope = deepcopy(console._envelope(sid))
    envelope["title"] = "uncommitted reprocessing title"
    console._commit_prepared_store(envelopes={**console._envelopes, sid: envelope}, snapshot_id=sid)


@pytest.mark.parametrize("fault", ["outer", "caught_participant", "commit"])
def test_reprocessing_rolls_back_all_four_mirrors(prepared, monkeypatch, fault):
    console, reviewer, sid, obj = prepared
    before = deepcopy(_state(console, sid))
    envelope = console.workflow_document_store.get_envelope(sid)
    inside = _spy_mirror_writes_inside_transaction(monkeypatch, console)
    if fault == "commit":
        # Deferred FK validation fails on real COMMIT, after the command body.
        with psycopg.connect(console.workflow_document_store.config.dsn) as connection:
            connection.execute("CREATE TABLE commit_probe (id integer PRIMARY KEY)")
            connection.execute("CREATE TABLE commit_failure (id integer REFERENCES commit_probe(id) DEFERRABLE INITIALLY DEFERRED)")

    @contextmanager
    def changed():
        with console._reprocessing_transaction(sid):
            _change_all(console, reviewer, sid, obj)
            assert _state(console, sid) != before
            assert console.workflow_document_store.get_envelope(sid)["title"] != envelope["title"]
            yield

    if fault == "caught_participant":
        with console._reprocessing_transaction(sid):
            with pytest.raises(RuntimeError, match="^reprocessing_fault$"):
                with changed():
                    raise RuntimeError("reprocessing_fault")
            assert _state(console, sid) == before
    else:
        error = psycopg.errors.ForeignKeyViolation if fault == "commit" else RuntimeError
        with pytest.raises(error, match=None if fault == "commit" else "^reprocessing_fault$"):
            with changed():
                if fault == "commit":
                    with console.workflow_document_store._connect() as connection:
                        connection.execute("INSERT INTO commit_failure VALUES (1)")
                else:
                    raise RuntimeError("reprocessing_fault")
    assert inside == []
    assert _state(console, sid) == before
    assert console.workflow_document_store.get_envelope(sid) == envelope
    _assert_mirrors(console, sid)
