"""#665: tier D (PostgreSQL documents without PostgreSQL review) is refused fail-closed.

Design: /workspace/665-change-design.md v5.1 §6 (Class A, rewrite risk high).

T1  naad A: build_app refuses before any PostgreSQL read, credential or store.
T2  naad B: direct construction of the documents-only classes refuses.
T3  naad B: an ad-hoc documents-mixin class without the review mixin refuses.
T4  naad C: every documents-mixin writer refuses on store configuration
    (a) __class__ swap, (b) object.__new__, (c) wrong/foreign review store.
T4b I10 introspection + construction spy: all 6 review classes build with 0 refusals.
T5  I8: no copy-write of bindings / ledger truncation by the documents mixin.
T6  I4: workflow_review_write_failed carries only its code (:120 and :210).
T7  diagnosis scenarios D1b/D4/D5/D6 now fail on construction (tier D).
T9  guard: tier R batch fault leaves state unchanged (D4[review]).
T10 guard: snapshot_object_write_conflict reaches the caller with current_revision.
T13 detection SQL db/checks/tier_d_damage_counts_v1.sql (read-only, aggregate default).

T8 (I6 spy on _refresh_after_rollback) is guarded by tests/test_r2_rollback_remirror_postgres.py.

_config_identity values (dsn) are compared only; NOOIT printed or used in assert text.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import inspect
import importlib
import os
import pkgutil
import secrets
import shutil
import subprocess
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalConfig, PostgresCanonicalPublicationStore
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.review.proportionate_review_v1 import _batch_type, normal_risk_batch_queue
from src.workflows import workflow_documents_cutover_v1 as docs_mod
from src.workflows import workflow_transaction_v1 as tx_mod
from src.workflows.workflow_document_concurrency_v1 import PostgresConcurrentWorkflowDocumentStore
from src.workflows.workflow_documents_cutover_v1 import (
    PostgresWorkflowAzureAuthoritativePublicationConsole,
    PostgresWorkflowDurablePublicationConsole,
    WorkflowDocumentStoreError,
    _PostgresWorkflowDocumentsMixin,
)
from src.workflows.workflow_identity_postgres_v1 import PostgresWorkflowIdentityStore
from src.workflows.workflow_review_cutover_v1 import (
    PostgresReviewWorkflowDurablePublicationConsole,
    _PostgresWorkflowReviewMixin,
)
from src.workflows.workflow_review_postgres_v1 import PostgresWorkflowReviewStore, WorkflowReviewStoreError
from src.workflows.workflow_transaction_v1 import bind_workflow_stores
from tests.complete_workflow_support import complete_postgres as recovery_postgres  # noqa: F401
from tests.complete_workflow_support import complete_postgres as workflow_postgres  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
CODE = "workflow_review_store_required_for_document_store"
CHECK_SQL = ROOT / "db" / "checks" / "tier_d_damage_counts_v1.sql"
CANDIDATE = "kandidaat_geen_event_geen_binding"


def _assert_refused(exc: BaseException) -> None:
    assert type(exc) is RuntimeError
    assert exc.args == (CODE,)
    assert str(exc) == CODE
    assert repr(exc.args) == repr((CODE,))


def _docs_only(root, config):
    return PostgresWorkflowDurablePublicationConsole(
        root=root, source_store=root / "sources", runtime=root / "runtime",
        workflow_identity_store=PostgresWorkflowIdentityStore(config),
        workflow_document_store=PostgresConcurrentWorkflowDocumentStore(config),
    )


from tests.complete_workflow_support import complete_console as _review_tier


def _accounts(console):
    researcher = console.create_account(username="anne", password="anne-secret", roles=("researcher",))
    reviewer = console.create_account(username="bert", password="bert-secret", roles=("reviewer",))
    return researcher["account_id"], reviewer["account_id"]


def _ingest(console, accounts=None, *, title="Begrippen", family="begrippen", filename="begrippen.html"):
    from tests.semantic_fixture_support import bind_fixture_selections
    bind_fixture_selections(console)
    researcher_id, reviewer_id = accounts or _accounts(console)
    receipt = console.ingest(
        actor_id=researcher_id, filename=filename, content_type="text/html",
        data=(b'<html><body><h1>' + title.encode() + b'</h1><h2>1 Begrippen</h2>'
              b'<p>De Dutch Job Group is een meetinstrument voor werkbelasting.</p>'
              b'<p>Een observatie is een systematische waarneming van gedrag.</p></body></html>'),
        ingest_kind="new", title=title, version="1.0", date="2026-09-20", live_url="",
        class_="richtlijn", family=family, named_reviewers=[reviewer_id],
    )
    sid = receipt["snapshot_id"]
    queue = normal_risk_batch_queue(console.snapshot_objects(sid), review_path="richtlijn",
                                    fragments=console.review_source_fragments(sid),
                                    bindings=console.object_review_bindings(sid))
    return sid, reviewer_id, queue


def _approve(console, rid, sid, obj):
    return console.review_object(actor_id=rid, snapshot_id=sid, object_id=obj["object_id"], decision="approve",
                                 confirmed_object_type=_batch_type(obj), suitability="ja",
                                 eindoordeel="goedkeuren", type_action="dit_klopt")


def _document_state(config, sid):
    fresh = PostgresConcurrentWorkflowDocumentStore(config)
    return deepcopy((fresh.get_envelope(sid), fresh.list_document_objects(sid)))


def _durable(console, config, sid):
    reviews = PostgresWorkflowReviewStore(config)
    return {"bindings": reviews.read_bindings().get(sid, []), "events": len(reviews.read_events()),
            "documents": _document_state(config, sid)}


def _workflow_row_counts(config):
    import psycopg
    with psycopg.connect(config.dsn) as con:
        return {table: con.execute(f"SELECT count(*) FROM workflow.{table}").fetchone()[0]
                for table in ("accounts", "documents", "document_objects", "review_events", "publish_authorizations")}


# ---------------------------------------------------------------- T1 naad A

@pytest.mark.parametrize(("document_kind", "review_kind"), [
    ("postgres", None), (" Postgres ", None), ("POSTGRES", None), ("postgres", ""), ("postgres", "file"),
])
def test_t1_build_app_refuses_tier_d_before_any_postgres_read(monkeypatch, tmp_path, document_kind, review_kind):
    import psycopg
    import src.console_asgi as asgi

    for name in ("WEBSITE_SITE_NAME", "METIS_WORKFLOW_REMAINING_STORE", "METIS_WORKFLOW_REVIEW_STORE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("METIS_CANONICAL_STORE", "postgres")
    monkeypatch.setenv("METIS_WORKFLOW_STORE", "postgres")
    monkeypatch.setenv("METIS_WORKFLOW_DOCUMENT_STORE", document_kind)
    if review_kind is not None:
        monkeypatch.setenv("METIS_WORKFLOW_REVIEW_STORE", review_kind)
    data_root = tmp_path / "data"
    monkeypatch.setenv("CONSOLE_DATA_ROOT", str(data_root))
    monkeypatch.setenv("CONSOLE_RUNTIME", str(data_root / "runtime"))
    monkeypatch.setenv("CONSOLE_SOURCE_STORE", str(data_root / "sources"))

    connects: list[str] = []
    constructed: list[str] = []

    def forbidden_connect(*args, **kwargs):
        connects.append("psycopg.connect")
        raise AssertionError("t1_postgres_connect_forbidden")

    monkeypatch.setattr(psycopg, "connect", forbidden_connect)

    def forbid(name):
        def factory(*args, **kwargs):
            constructed.append(name)
            raise AssertionError("t1_construction_forbidden")
        return factory

    for name in ("CachedAzurePostgresCredential", "PostgresCanonicalPublicationStore",
                 "CutoverPostgresWorkflowIdentityStore", "PostgresConcurrentWorkflowDocumentStore",
                 "PostgresWorkflowReviewStore"):
        monkeypatch.setattr(asgi, name, forbid(name))

    with pytest.raises(BaseException) as info:
        asgi.build_app()
    assert constructed == []
    assert connects == []
    if review_kind == "file":
        assert str(info.value) == "unsupported_workflow_review_store"
    else:
        # D6b: selectors no longer choose a tier; without PostgreSQL every start is refused.
        assert str(info.value) == "postgres_authority_configuration_required"
    assert not data_root.exists() or not any(data_root.rglob("*"))


# ---------------------------------------------------------------- T2/T3 naad B

@pytest.mark.parametrize("console_cls", [PostgresWorkflowDurablePublicationConsole,
                                         PostgresWorkflowAzureAuthoritativePublicationConsole])
def test_t2_documents_only_classes_refuse_on_construction(recovery_postgres, tmp_path, console_cls):
    before = _workflow_row_counts(recovery_postgres)
    with pytest.raises(BaseException) as info:
        console_cls(
            root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
            workflow_identity_store=PostgresWorkflowIdentityStore(recovery_postgres),
            workflow_document_store=PostgresConcurrentWorkflowDocumentStore(recovery_postgres),
        )
    _assert_refused(info.value)
    assert not (tmp_path / "runtime").exists()
    assert _workflow_row_counts(recovery_postgres) == before


def test_t3_adhoc_documents_mixin_without_review_refuses(workflow_postgres, tmp_path):
    class AdHocDocumentsConsole(_PostgresWorkflowDocumentsMixin, OperationsConsole):
        pass

    with pytest.raises(BaseException) as info:
        AdHocDocumentsConsole(root=tmp_path, source_store=tmp_path / "sources", runtime=tmp_path / "runtime",
                              workflow_document_store=PostgresConcurrentWorkflowDocumentStore(workflow_postgres))
    _assert_refused(info.value)
    assert not (tmp_path / "runtime").exists()


# ---------------------------------------------------------------- T4 naad C

def _writer_calls(sid, actor_id, envelope, rows):
    def cm(name):
        def run(console):
            with getattr(_PostgresWorkflowDocumentsMixin, name)(console, sid):
                pass
        return run

    def call(name, *args, **kwargs):
        return lambda console: getattr(_PostgresWorkflowDocumentsMixin, name)(console, *args, **kwargs)

    return {
        "_save_objects": call("_save_objects", sid, deepcopy(rows)),
        "_save_envelopes": call("_save_envelopes"),
        "_apply_release_state": call("_apply_release_state", {"snapshot_id": sid}, []),
        "_delete_unpublished_snapshot_authority": call("_delete_unpublished_snapshot_authority", sid),
        "_delete_unpublished_snapshot_locked": call(
            "_delete_unpublished_snapshot_locked", actor_id=actor_id, token=sid, account={}, confirm_title="t4"),
        "_commit_prepared_store[envelopes]": call(
            "_commit_prepared_store", envelopes={sid: deepcopy(envelope)}, snapshot_id=sid),
        "_commit_prepared_store[delegation]": call(
            "_commit_prepared_store", bindings={sid: []}, snapshot_id=sid),
        "_reprocessing_transaction": cm("_reprocessing_transaction"),
        "_heading_batch_mutation": cm("_heading_batch_mutation"),
        "_atomic_snapshot_mutation": cm("_atomic_snapshot_mutation"),
    }


WRITERS = list(_writer_calls("s", "a", {}, []))


class _DuckReviewStore:
    """Non-None, not a PostgresWorkflowReviewStore; same config as the documents store."""

    def __init__(self, config):
        self.config = config

    def __getattr__(self, name):
        raise AssertionError("t4_duck_review_store_used")


def _variant_console(variant, tmp_path, config):
    console = _review_tier(tmp_path, config)
    sid, rid, queue = _ingest(console)
    envelope = console._envelope(sid)
    rows = PostgresConcurrentWorkflowDocumentStore(config).list_document_objects(sid)
    documents = console.workflow_document_store
    if variant == "a_class_swap":
        console.__class__ = type("SwappedDocumentsConsole", (_PostgresWorkflowDocumentsMixin, OperationsConsole), {})
        del console.workflow_review_store
    elif variant == "b_object_new":
        console = object.__new__(PostgresWorkflowDurablePublicationConsole)
        console.workflow_document_store = documents
    elif variant == "c1_duck_store":
        console.workflow_review_store = _DuckReviewStore(config)
    elif variant == "c2_store_without_config":
        console.workflow_review_store = object.__new__(PostgresWorkflowReviewStore)
    elif variant == "c3_store_other_database":
        console.workflow_review_store = PostgresWorkflowReviewStore(
            PostgresCanonicalConfig(host="t4-other-host.invalid", database="t4_other_db", user="t4_user"))
    else:
        raise AssertionError("unknown variant")
    return console, documents, sid, rid, envelope, rows


@pytest.mark.parametrize("writer", WRITERS)
@pytest.mark.parametrize("variant", ["a_class_swap", "b_object_new", "c1_duck_store",
                                     "c2_store_without_config", "c3_store_other_database"])
def test_t4_every_documents_writer_refuses_without_matching_review_store(
        workflow_postgres, tmp_path, monkeypatch, variant, writer):
    console, documents, sid, rid, envelope, rows = _variant_console(variant, tmp_path, workflow_postgres)
    before = _document_state(workflow_postgres, sid)
    writes: list[str] = []

    def spy(name, original):
        def wrapped(*args, **kwargs):
            writes.append(name)
            return original(*args, **kwargs)
        return wrapped

    monkeypatch.setattr(documents, "write_bundle", spy("write_bundle", documents.write_bundle))
    monkeypatch.setattr(documents, "delete_document", spy("delete_document", documents.delete_document))
    from src import operations_console_v1 as operations_mod
    monkeypatch.setattr(operations_mod, "_atomic_write", spy("_atomic_write", operations_mod._atomic_write))
    monkeypatch.setattr(operations_mod, "_atomic_replace_bytes", spy("_atomic_replace_bytes", operations_mod._atomic_replace_bytes))
    monkeypatch.setattr(docs_mod, "workflow_transaction", spy("workflow_transaction", docs_mod.workflow_transaction))

    with pytest.raises(BaseException) as info:
        _writer_calls(sid, rid, envelope, rows)[writer](console)
    assert writes == []
    _assert_refused(info.value)
    assert _document_state(workflow_postgres, sid) == before


def test_t4_documents_atomic_context_refuses_even_in_review_console(workflow_postgres, tmp_path, monkeypatch):
    """I7 enforced: the inherited documents context is never a working rollback path."""
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, _queue = _ingest(console)
    writes: list[str] = []
    original = console.workflow_document_store.write_bundle
    monkeypatch.setattr(console.workflow_document_store, "write_bundle",
                        lambda *a, **k: writes.append("write_bundle") or original(*a, **k))
    with pytest.raises(BaseException) as info:
        with _PostgresWorkflowDocumentsMixin._atomic_snapshot_mutation(console, sid):
            pass
    assert writes == []
    _assert_refused(info.value)


def test_t4_documents_mixin_has_no_suppressed_workflow_write():
    source = inspect.getsource(_PostgresWorkflowDocumentsMixin)
    assert "suppress(Exception)" not in source


# ---------------------------------------------------------------- T4b I10

REVIEW_CLASS_PATHS = (
    ("src.workflows.workflow_review_cutover_v1", "PostgresReviewWorkflowDurablePublicationConsole"),
    ("src.workflows.workflow_review_cutover_v1", "PostgresReviewWorkflowAzureAuthoritativePublicationConsole"),
    ("src.workflows.workflow_remaining_cutover_v1", "PostgresCompleteWorkflowDurablePublicationConsole"),
    ("src.workflows.workflow_remaining_cutover_v1", "PostgresCompleteWorkflowAzureAuthoritativePublicationConsole"),
    ("src.workflows.workflow_badge_counts_postgres_v1", "FastBadgePostgresCompleteWorkflowDurablePublicationConsole"),
    ("src.workflows.workflow_badge_counts_postgres_v1",
     "FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole"),
)
REFUSED_BASES = {PostgresWorkflowDurablePublicationConsole, PostgresWorkflowAzureAuthoritativePublicationConsole}


def _all_subclasses(cls):
    seen, stack = [], list(cls.__subclasses__())
    while stack:
        sub = stack.pop()
        if sub not in seen:
            seen.append(sub)
            stack.extend(sub.__subclasses__())
    return seen


def test_t4b_every_instantiable_documents_class_carries_review_authority():
    import src
    import src.console_asgi  # noqa: F401
    for module in pkgutil.iter_modules(importlib.import_module("src.workflows").__path__, "src.workflows."):
        importlib.import_module(module.name)
    production = [cls for cls in _all_subclasses(_PostgresWorkflowDocumentsMixin) if cls.__module__.startswith("src.")]
    names = {(cls.__module__, cls.__name__) for cls in production}
    assert set(REVIEW_CLASS_PATHS) <= names
    offenders = [f"{cls.__module__}.{cls.__name__}" for cls in production
                 if cls not in REFUSED_BASES and not issubclass(cls, _PostgresWorkflowReviewMixin)]
    assert offenders == []


def _review_store_matches(console) -> bool:
    store = getattr(console, "workflow_review_store", None)
    if not isinstance(store, PostgresWorkflowReviewStore):
        return False
    try:
        return tx_mod._config_identity(store) == tx_mod._config_identity(console.workflow_document_store)
    except Exception:
        return False


@pytest.mark.parametrize(("module_name", "class_name"), REVIEW_CLASS_PATHS)
def test_t4b_all_review_classes_construct_with_zero_seam_c_refusals(
        recovery_postgres, tmp_path, monkeypatch, module_name, class_name):
    from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
    from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore
    from tests.test_durable_publication_console_v1 import MemorySourceStore

    refusals: list[str] = []
    helper = getattr(_PostgresWorkflowDocumentsMixin, "_require_review_store_configured", None)
    if helper is not None:
        def spy_helper(self, _original=helper):
            try:
                return _original(self)
            except RuntimeError:
                refusals.append("_require_review_store_configured")
                raise
        monkeypatch.setattr(_PostgresWorkflowDocumentsMixin, "_require_review_store_configured", spy_helper)
    else:
        for name in ("_save_objects", "_delete_unpublished_snapshot_authority", "_delete_unpublished_snapshot_locked",
                     "_save_envelopes", "_apply_release_state", "_commit_prepared_store",
                     "_reprocessing_transaction", "_heading_batch_mutation", "_atomic_snapshot_mutation"):
            original = getattr(_PostgresWorkflowDocumentsMixin, name)

            def wrapped(self, *args, _original=original, _name=name, **kwargs):
                if not _review_store_matches(self):
                    refusals.append(_name)
                return _original(self, *args, **kwargs)
            monkeypatch.setattr(_PostgresWorkflowDocumentsMixin, name, wrapped)

    console_cls = getattr(importlib.import_module(module_name), class_name)
    config = recovery_postgres
    from tests.production_support import production_application
    console = production_application(
        tmp_path, config, azure="Azure" in class_name,
        immutable_source_store=MemorySourceStore() if "Azure" in class_name else None,
    ).state.operations_kernel
    # Production constructs the supported leaf, exercising each historical ancestor.
    assert isinstance(console, console_cls)
    assert isinstance(console, _PostgresWorkflowReviewMixin)
    assert refusals == []


# ---------------------------------------------------------------- T5 I8

def _ledger_truncations(monkeypatch, ledger_path):
    seen: list[str] = []
    original = Path.open

    def spy(self, mode="r", *args, **kwargs):
        if self == ledger_path and "+" in mode:
            seen.append(mode)
        return original(self, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", spy)
    return seen


@pytest.mark.parametrize("remirror_fails", [False, True])
def test_t5_documents_mixin_writes_no_mirror_copy_after_failed_commit(
        workflow_postgres, tmp_path, monkeypatch, remirror_fails):
    from src.review.review_ledger import read_events

    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)
    copy_writes: list[str] = []
    from src import operations_console_v1 as operations_mod
    original_aw = operations_mod._atomic_write

    def spy_aw(path, payload):
        if Path(path).name == (console.runtime / "publish_authorizations.json").name:
            copy_writes.append("bindings")
        return original_aw(path, payload)
    monkeypatch.setattr(operations_mod, "_atomic_write", spy_aw)
    truncations = _ledger_truncations(monkeypatch, console._ledger_path)
    original_wb = console.workflow_document_store.write_bundle

    def fail_objects(*args, **kwargs):
        if kwargs.get("objects") is not None:
            raise OSError("t5_injected")
        return original_wb(*args, **kwargs)
    monkeypatch.setattr(console.workflow_document_store, "write_bundle", fail_objects)
    if remirror_fails:
        def broken_remirror():
            raise OSError("t5_remirror_injected")
        monkeypatch.setattr(console, "_refresh_review_runtime", broken_remirror)
    with pytest.raises(OSError):
        _approve(console, rid, sid, queue[0])
    assert copy_writes == []
    assert truncations == []
    if not remirror_fails:
        reviews = PostgresWorkflowReviewStore(workflow_postgres)
        assert not (console.runtime / "publish_authorizations.json").exists()
        assert reviews.read_bindings() == {}
        assert len(read_events(console._ledger_path)) == len(reviews.read_events())


# ---------------------------------------------------------------- T6 I4

def _assert_review_write_failed(exc):
    assert isinstance(exc, ConsoleError)
    assert exc.code == "workflow_review_write_failed"
    assert str(exc) == exc.code
    assert exc.args == ("workflow_review_write_failed",)
    assert isinstance(exc.__cause__, WorkflowReviewStoreError)
    assert "t6_store_detail_secret" not in repr(exc.args)


def test_t6_save_bindings_path_carries_only_code(workflow_postgres, tmp_path, monkeypatch):
    """review_cutover:120 (_save_bindings)."""
    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)

    def boom(*args, **kwargs):
        raise WorkflowReviewStoreError("t6_store_detail_secret")
    monkeypatch.setattr(console.workflow_review_store, "replace_snapshot_bindings", boom)
    with pytest.raises(ConsoleError) as info:
        _approve(console, rid, sid, queue[0])
    _assert_review_write_failed(info.value)


def test_t6_commit_prepared_store_path_carries_only_code(workflow_postgres, tmp_path):
    """review_cutover:210 (_commit_prepared_store, WorkflowReviewStoreError branch)."""
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, _queue = _ingest(console)
    envelope = console._envelope(sid)

    def ledger_fault():
        raise WorkflowReviewStoreError("t6_store_detail_secret")
    with pytest.raises(ConsoleError) as info:
        console._commit_prepared_store(envelopes={sid: envelope}, ledger_fn=ledger_fault, snapshot_id=sid)
    _assert_review_write_failed(info.value)


# ---------------------------------------------------------------- T7/T9/T10

@pytest.mark.parametrize("scenario", ["d1b_outer_fault_after_approve", "d4_batch_second_member_fault",
                                      "d5_caught_nested_fault", "d6_commit_fault_after_write_bundle"])
def test_t7_tier_d_diagnosis_scenarios_now_fail_on_construction(workflow_postgres, tmp_path, scenario):
    with pytest.raises(BaseException) as info:
        _docs_only(tmp_path, workflow_postgres)
    _assert_refused(info.value)


def test_t9_tier_r_batch_second_member_fault_leaves_state_unchanged(workflow_postgres, tmp_path, monkeypatch):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)
    before = _durable(console, workflow_postgres, sid)
    original = console._commit_prepared_store
    calls = {"n": 0}

    def second_fails(**kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("t9_injected")
        return original(**kwargs)
    monkeypatch.setattr(console, "_commit_prepared_store", second_fails)
    with pytest.raises(RuntimeError, match="t9_injected"):
        console.batch_review_normal_risk(actor_id=rid, snapshot_id=sid, object_ids=[o["object_id"] for o in queue])
    assert _durable(console, workflow_postgres, sid) == before


def test_t10_tier_r_conflict_reaches_caller_with_current_revision(workflow_postgres, tmp_path, monkeypatch):
    from src.workflows.workflow_document_concurrency_v1 import SNAPSHOT_OBJECT_WRITE_CONFLICT

    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)
    before = _durable(console, workflow_postgres, sid)
    original_wb = console.workflow_document_store.write_bundle

    def conflict(*args, **kwargs):
        if kwargs.get("objects") is not None:
            raise WorkflowDocumentStoreError(SNAPSHOT_OBJECT_WRITE_CONFLICT)
        return original_wb(*args, **kwargs)
    monkeypatch.setattr(console.workflow_document_store, "write_bundle", conflict)
    with pytest.raises(ConsoleError) as info:
        _approve(console, rid, sid, queue[0])
    assert info.value.code == SNAPSHOT_OBJECT_WRITE_CONFLICT
    assert info.value.current_revision
    assert _durable(console, workflow_postgres, sid) == before


# ---------------------------------------------------------------- T13 detection SQL

def _psql() -> str:
    found = shutil.which("psql")
    assert found, "psql is required to execute db/checks/tier_d_damage_counts_v1.sql"
    return found


def _run_check(conninfo: str, *, detail: str | None = None) -> subprocess.CompletedProcess:
    assert CHECK_SQL.is_file(), "db/checks/tier_d_damage_counts_v1.sql is missing"
    from psycopg.conninfo import conninfo_to_dict
    # L-2: connection and password via env, NOOIT via argv (pytest prints argv on failure).
    keys = {"host": "PGHOST", "port": "PGPORT", "user": "PGUSER", "dbname": "PGDATABASE", "password": "PGPASSWORD"}
    params = conninfo_to_dict(conninfo)
    assert set(params) <= set(keys), "unsupported conninfo keyword for T13"
    env = dict(os.environ, **{keys[k]: str(v) for k, v in params.items()})
    args = [_psql(), "-X", "-q", "-A", "-F", "|", "-P", "footer=off", "-f", str(CHECK_SQL)]
    if detail is not None:
        args[1:1] = ["-v", f"detail={detail}"]
    return subprocess.run(args, capture_output=True, text=True, timeout=60, env=env)


@contextmanager
def _role(config, *, privileges=("SELECT",)):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    name = "metis665_t13_" + secrets.token_hex(4)
    password = secrets.token_hex(16)
    tables = ("document_objects", "review_events", "publish_authorizations")
    with psycopg.connect(config.dsn, autocommit=True) as con:
        con.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(name), sql.Literal(password)))
        con.execute(sql.SQL("GRANT USAGE ON SCHEMA workflow TO {}").format(sql.Identifier(name)))
        for table in tables:
            con.execute(sql.SQL("GRANT {} ON workflow.{} TO {}").format(
                sql.SQL(", ").join(sql.SQL(p) for p in privileges), sql.Identifier(table), sql.Identifier(name)))
    try:
        yield make_conninfo(config.dsn, user=name, password=password)
    finally:
        with psycopg.connect(config.dsn, autocommit=True) as con:
            con.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(name)))
            con.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(name)))


def _aggregate(config) -> dict[str, tuple[int, int]]:
    with _role(config) as conninfo:
        result = _run_check(conninfo)
    assert result.returncode == 0, "detection SQL failed under the read-only role"
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[0] == "kandidaten voor handmatige controle"
    assert lines[1] == "redencategorie|versies|snapshots"
    rows = {}
    for line in lines[2:]:
        category, versions, snapshots = line.split("|")
        rows[category] = (int(versions), int(snapshots))
    return rows


def _insert_version(config, sid, object_id, version):
    import psycopg
    with psycopg.connect(config.dsn) as con:
        payload = con.execute(
            "SELECT payload FROM workflow.document_objects WHERE snapshot_id=%s AND object_id=%s "
            "ORDER BY object_version LIMIT 1", (sid, object_id)).fetchone()[0]
        payload = dict(payload, object_version=version)
        from psycopg.types.json import Jsonb
        con.execute("INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,position) "
                    "VALUES(%s,%s,%s,%s,%s)", (sid, object_id, version, Jsonb(payload), 9000 + len(version)))


def _copy_event_to_version(config, sid, object_id, version):
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    with psycopg.connect(config.dsn, row_factory=dict_row) as con:
        row = con.execute("SELECT * FROM workflow.review_events WHERE snapshot_id=%s ORDER BY event_id LIMIT 1",
                          (sid,)).fetchone()
        row.pop("event_id")
        row.update(object_id=object_id, object_version=version, event_hash=f"t13-{secrets.token_hex(8)}")
        values = [Jsonb(v) if isinstance(v, (dict, list)) else v for v in row.values()]
        con.execute(sql.SQL("INSERT INTO workflow.review_events({}) VALUES({})").format(
            sql.SQL(",").join(sql.Identifier(k) for k in row), sql.SQL(",").join(sql.Placeholder() * len(row))),
            values)


def _scenario_review_flow(request, tmp_path, monkeypatch):
    config = request.getfixturevalue("workflow_postgres")
    from src.documents.klasse_wijzigen_v1 import is_cross_model_class_change
    from src.operations_console_v1 import ALLOWED_CLASSES

    console = _review_tier(tmp_path, config)
    accounts = _accounts(console)
    sid, rid, queue = _ingest(console, accounts)
    first, second = queue[0], queue[1]
    _approve(console, rid, sid, first)
    text = second["content"]["clean_text"].rstrip(".")
    console.review_object(actor_id=rid, snapshot_id=sid, object_id=second["object_id"], decision="revise",
                          comment="Corrigeer.", proposed_correction=text)
    console.correct_object(actor_id=rid, snapshot_id=sid, object_id=second["object_id"],
                           patch={"reason": "t13", "operations": [
                               {"op": "set", "path": "content.clean_text", "value": text}]})
    current = console._envelope(sid)["class"]
    target = next(k for k in sorted(ALLOWED_CLASSES)
                  if k != current and not is_cross_model_class_change(current, k))
    console.promote_class(actor_id=rid, snapshot_id=sid, new_class=target)
    other, _rid2, _queue2 = _ingest(console, accounts, title="Tweede", family="tweede", filename="tweede.html")
    console.delete_unpublished_snapshot(actor_id=accounts[0], snapshot_id=other, confirmed=True,
                                        confirm_title=console._envelope(other)["title"])
    return config


def _scenario_heading_batch(request, tmp_path, monkeypatch):
    config = request.getfixturevalue("workflow_postgres")
    from tests import test_a08_heading_batch_atomic as a08
    from tests.test_review_batch_atomic_postgres import _console as native
    a08.test_success_duplicates_repeat_and_stale(
        lambda root: native(root, config), tmp_path,
        production_app=request.getfixturevalue("production_app"),
        production_console=request.getfixturevalue("production_console"))
    return config


def _scenario_source_repair(request, tmp_path, monkeypatch):
    from tests import test_a09_source_repair as a09
    from tests.decision_graph_native_support import native_state
    state, _canonical, _source = native_state(tmp_path, config=request.getfixturevalue("complete_postgres"))
    counter = iter(range(100))
    a09.test_old_approval_is_retained_and_invalidated(
        lambda **kwargs: a09.setup_repair(tmp_path, factory=lambda: state(f"t13-{next(counter)}"), **kwargs),
        production_app=request.getfixturevalue("production_app"),
        production_console=request.getfixturevalue("production_console"))
    return PostgresCanonicalConfig(dsn=os.environ["METIS_TEST_POSTGRES_DSN"])


def _scenario_reprocessing(request, tmp_path, monkeypatch):
    config = request.getfixturevalue("workflow_postgres")
    from tests import test_processing_retry_postgres as retry
    retry.test_failure_deduplication_success_http_and_restart(config, tmp_path, monkeypatch)
    return config


def _scenario_publish_withdraw(request, tmp_path, monkeypatch):
    config = request.getfixturevalue("recovery_postgres")
    from tests import test_lifecycle_withdrawal_recovery_v1 as lifecycle
    lifecycle.test_http_withdrawal_complete_recovery_and_open_work_resume(config, tmp_path, monkeypatch)
    return config


CLEAN_SCENARIOS = {
    "approve_revise_correct_class_change_delete_unpublished": _scenario_review_flow,
    "heading_batch_confirm": _scenario_heading_batch,
    "source_repair": _scenario_source_repair,
    "reprocessing_retry": _scenario_reprocessing,
    "publish_withdraw_recovery": _scenario_publish_withdraw,
}


@pytest.mark.parametrize("scenario", list(CLEAN_SCENARIOS))
def test_t13_clean_tier_r_run_has_zero_candidates(request, tmp_path, monkeypatch, scenario):
    config = CLEAN_SCENARIOS[scenario](request, tmp_path, monkeypatch)
    rows = _aggregate(config)
    print("T13_CLEAN", scenario, rows)
    assert rows.get(CANDIDATE, (0, 0))[0] == 0
    if scenario == "approve_revise_correct_class_change_delete_unpublished":
        # Informative: later versions exist and are classified as covered.
        assert rows.get("gedekt_event", (0, 0))[0] >= 2


def test_t13_synthetic_tier_d_shape_is_a_candidate(workflow_postgres, tmp_path):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, queue = _ingest(console)
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "1.0.7")
    rows = _aggregate(workflow_postgres)
    assert rows.get(CANDIDATE) == (1, 1)


def test_t13_2b_bound_version_does_not_cover_next_version(workflow_postgres, tmp_path):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)
    _approve(console, rid, sid, queue[0])  # creates 1.0.1 with event + binding
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "1.0.2")
    rows = _aggregate(workflow_postgres)
    assert rows.get(CANDIDATE) == (1, 1)


def test_t13_numeric_version_order_and_non_numeric_category(workflow_postgres, tmp_path):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, rid, queue = _ingest(console)
    second = queue[1]
    console.review_object(actor_id=rid, snapshot_id=sid, object_id=second["object_id"], decision="revise",
                          comment="Corrigeer.", proposed_correction=second["content"]["clean_text"].rstrip("."))
    _insert_version(workflow_postgres, sid, second["object_id"], "1.0.9")
    _insert_version(workflow_postgres, sid, second["object_id"], "1.0.10")
    _copy_event_to_version(workflow_postgres, sid, second["object_id"], "1.0.9")
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "x1")
    rows = _aggregate(workflow_postgres)
    # numeric: 1.0.10 follows 1.0.9 (event, no binding) -> covered; text order would make it a candidate
    assert rows.get(CANDIDATE, (0, 0))[0] == 0
    assert rows.get("versie_niet_numeriek") == (1, 1)


def test_t13_default_output_is_aggregate_only_and_detail_needs_flag(workflow_postgres, tmp_path):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, queue = _ingest(console)
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "1.0.7")
    with _role(workflow_postgres) as conninfo:
        default = _run_check(conninfo)
        detail = _run_check(conninfo, detail="1")
    assert default.returncode == 0
    assert sid not in default.stdout
    assert queue[0]["object_id"] not in default.stdout
    assert "schade" not in default.stdout.lower()
    assert detail.returncode == 0
    lines = [line for line in detail.stdout.splitlines() if line.strip()]
    header = lines.index("snapshot_id|object_id|object_version|redencategorie")
    assert lines[header + 1:] == [f"{sid}|{queue[0]['object_id']}|1.0.7|{CANDIDATE}"]


DETAIL_HEADER = "snapshot_id|object_id|object_version|redencategorie"


@pytest.mark.parametrize("value", ["0", "false", "", "nee", None])
def test_t13_detail_only_on_explicit_1_or_true_otherwise_aggregate(workflow_postgres, tmp_path, value):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, queue = _ingest(console)
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "1.0.7")
    with _role(workflow_postgres) as conninfo:
        result = _run_check(conninfo, detail=value)
    assert result.returncode == 0, "detection SQL failed under the read-only role"
    assert DETAIL_HEADER not in result.stdout
    assert sid not in result.stdout
    assert queue[0]["object_id"] not in result.stdout


@pytest.mark.parametrize("value", ["1", "true"])
def test_t13_detail_on_for_explicit_1_or_true(workflow_postgres, tmp_path, value):
    console = _review_tier(tmp_path, workflow_postgres)
    sid, _rid, queue = _ingest(console)
    _insert_version(workflow_postgres, sid, queue[0]["object_id"], "1.0.7")
    with _role(workflow_postgres) as conninfo:
        result = _run_check(conninfo, detail=value)
    assert result.returncode == 0, "detection SQL failed under the read-only role"
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert lines[lines.index(DETAIL_HEADER) + 1:] == [f"{sid}|{queue[0]['object_id']}|1.0.7|{CANDIDATE}"]


def test_t13_l2_psql_argv_carries_no_password(monkeypatch):
    # L-2: pytest prints CompletedProcess/argv on failure, so the password MOET NOOIT in argv staan.
    # Synthetic secret; only booleans reach assert text.
    secret = "l2" + secrets.token_hex(12)
    seen = {}

    def spy(args, **kwargs):
        seen["args"], seen["env"] = list(args), dict(kwargs.get("env") or {})
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", spy)
    _run_check(f"host=/tmp/l2-sock port=1 user=l2user dbname=l2db password={secret}", detail="1")
    argv_leak = any(secret in arg or "password" in arg.lower() for arg in seen["args"])
    assert not argv_leak, "psql argv carries a password"
    env_has_password = seen["env"].get("PGPASSWORD") == secret
    assert env_has_password, "PGPASSWORD is not passed via env"
    routed = [seen["env"].get(k) for k in ("PGHOST", "PGPORT", "PGUSER", "PGDATABASE")]
    assert routed == ["/tmp/l2-sock", "1", "l2user", "l2db"]


@pytest.mark.parametrize("privileges", [None, ("SELECT", "INSERT"), ("SELECT", "TRUNCATE")])
def test_t13_refuses_roles_with_write_privileges(workflow_postgres, tmp_path, privileges):
    console = _review_tier(tmp_path, workflow_postgres)
    _ingest(console)
    if privileges is None:
        result = _run_check(workflow_postgres.dsn)  # test superuser: holds every write privilege
    else:
        with _role(workflow_postgres, privileges=privileges) as conninfo:
            result = _run_check(conninfo)
    assert result.returncode != 0
    assert "redencategorie" not in result.stdout
    assert "weigering" in result.stderr


def test_t13_file_is_read_only_by_construction():
    assert CHECK_SQL.is_file(), "db/checks/tier_d_damage_counts_v1.sql is missing"
    text = CHECK_SQL.read_text(encoding="utf-8")
    statements = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("--")]
    assert statements[0] == "\\set ON_ERROR_STOP on"
    assert statements[1].startswith("BEGIN TRANSACTION READ ONLY")
    assert statements[-1] == "ROLLBACK;"
    upper = text.upper()
    for keyword in ("INSERT ", "UPDATE ", "DELETE ", "CREATE ", "ALTER ", "DROP ", "TRUNCATE ", "COMMIT"):
        code_lines = [l for l in upper.splitlines() if not l.strip().startswith("--")]
        hits = [l for l in code_lines if keyword in l and "'" + keyword.strip() + "'" not in l]
        assert hits == [], keyword
