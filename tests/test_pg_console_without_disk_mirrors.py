"""D4 evidence for D5/#730: real R+ lifecycle, absent and unusable mirrors.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs

Only the native test needs METIS_TEST_POSTGRES_DSN. The imported fixture owns
and drops a separate temporary database; no supplied database is reset.
"""
from contextlib import contextmanager
from copy import deepcopy
import builtins
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
import uuid

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_v1 import ConsoleError
from src.review_duty_v1 import exact_current_approver_ids
from src.review_ledger import unregister_backend
from src import quality_evidence_v1
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
)
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
from tests.complete_workflow_support import complete_console, complete_postgres  # noqa: F401
from tests.semantic_fixture_support import bind_fixture_selections, install_fixture_history
from tests.test_live_v1_working_v2_v1 import _complete_review
from tests.test_vsa_publish_readiness_ui_v1 import HTML_FIXTURE, MemorySourceStore
from tests.test_workflow_chain_recovery_v1 import _install_schema


ROOT = Path(__file__).resolve().parents[1]
MIRROR_NAMES = {
    "accounts.json", "sessions.json", "envelopes.json", "review_ledger.jsonl",
    "publish_authorizations.json", "published_projection.jsonl",
}
# Expected owners are a D5 work list, not permission to use mirrors. Unknown
# owners and unrelated lifecycle/harness failures remain ordinary failures.
EXPECTED_MIRROR_OWNERS = {
    "_mirror_envelopes", "_mirror_objects", "_mirror_bindings", "_mirror_events",
    "_remirror_review_runtime", "_ledger_mirror_tail_hash", "_apply_local_release_copy",
    "_read_optional", "_load_map", "_load_objects", "_save_accounts", "_save_sessions",
    "_delete_unpublished_snapshot_locked", "_delete_unpublished_snapshot_authority",
    "_commit_prepared_store", "_objects_write_lock", "_durable_receipt",
    "reconcile_durable_publications",
}
PHASES = (
    "startup", "accounts-and-session", "ingest-v1", "review-v1-four-eyes", "publish-v1",
    "build-app-startup", "successor-v2", "review-v2-four-eyes", "publish-v2", "successor-v3", "withdraw", "restart", "resume-successor",
    "ingest-delete", "delete-unpublished",
)
CONSOLES = {
    "durable": FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
    "azure": FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
}
BASELINE = Path(__file__).with_name("fixtures") / "pg_mirror_baseline_629d63c.json"


def _assert_access_baseline(rows, console_kind):
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = {tuple(row) for row in json.loads(BASELINE.read_text())[version][console_kind]}
    actual = {(row["owner"], row["mirror"], row["access"], row["phase"]) for row in rows}
    assert actual == expected, (f"Mirror baseline changed for {console_kind}: "
        f"added={sorted(actual - expected)}, missing={sorted(expected - actual)}")


class MirrorDenied(PermissionError):
    """An identified mirror access, distinguishable from incidental OS faults."""


class MirrorAccess:
    def __init__(self, runtime, *, deny):
        self.runtime = runtime.resolve()
        self.deny = deny
        self.phase = "setup"
        self.rows = {}

    def mirror(self, file):
        if isinstance(file, int):
            return None
        try:
            # No stat/resolve here: metadata operations themselves are guarded.
            path = Path(os.path.abspath(os.fsdecode(file)))
            relative = path.relative_to(self.runtime)
        except (ValueError, TypeError):
            return None
        if relative.name.endswith(".lock"):
            return None  # Synchronization files are not data mirrors.
        if relative.parts and relative.parts[0] in {"objects", "release_manifests"}:
            return f"{relative.parts[0]}/*"
        if len(relative.parts) == 1:
            for name in MIRROR_NAMES:
                if (relative.name == name or relative.name.startswith(f".{name}.")
                        or relative.name.startswith(f"{name}.")):
                    return name  # Includes atomic-write mkstemp files.
        return None

    def check(self, file, mode):
        mirror = self.mirror(file)
        if mode == "rmtree" and Path(os.path.abspath(os.fsdecode(file))) == self.runtime:
            mirror = "runtime/*"
        if mirror is None:
            return
        frames = [frame for frame in traceback.extract_stack()[:-1]
                  if str(ROOT / "src") + os.sep in frame.filename]
        owner = next((frame.name for frame in reversed(frames)
                      if frame.name in EXPECTED_MIRROR_OWNERS), frames[-1].name if frames else None)
        stack = [f"{Path(f.filename).relative_to(ROOT)}:{f.lineno}:{f.name}" for f in frames]
        key = (self.phase, mirror, mode, owner, tuple(stack))
        row = self.rows.setdefault(key, dict(phase=self.phase, mirror=mirror, access=mode,
            owner=owner, file=os.fsdecode(file), stack=stack, denied=self.deny, count=0))
        row["count"] += 1
        if self.deny:
            raise MirrorDenied(errno.EACCES, f"D4 forbids mirror {mode}: {mirror}", os.fsdecode(file))

    @contextmanager
    def installed(self, monkeypatch):
        original_open, original_io, original_os = builtins.open, io.open, os.open
        def checked_open(original):
            def call(file, mode="r", *args, **kwargs):
                self.check(file, "read+write" if "+" in mode else "write" if any(c in mode for c in "wax") else "read")
                return original(file, mode, *args, **kwargs)
            return call
        def low_level(file, flags, *args, **kwargs):
            candidate = resolved(file, kwargs.get("dir_fd"))
            access = "read+write" if flags & os.O_RDWR else "write" if flags & (os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_APPEND) else "read"
            self.check(candidate, access)
            return original_os(file, flags, *args, **kwargs)
        def resolved(file, directory_fd):
            candidate = file
            if directory_fd is not None and not isinstance(file, int):
                candidate = Path(os.readlink(f"/proc/self/fd/{directory_fd}")) / os.fsdecode(file)
            return candidate
        def unary(original, mode):
            def call(file, *args, **kwargs):
                self.check(resolved(file, kwargs.get("dir_fd")), mode)
                return original(file, *args, **kwargs)
            return call
        def binary(original, mode):
            def call(source, destination, *args, **kwargs):
                self.check(resolved(source, kwargs.get("src_dir_fd")), mode + "-source")
                self.check(resolved(destination, kwargs.get("dst_dir_fd")), mode + "-destination")
                return original(source, destination, *args, **kwargs)
            return call
        with monkeypatch.context() as patch:
            patch.setattr(builtins, "open", checked_open(original_open))
            patch.setattr(io, "open", checked_open(original_io))
            patch.setattr(os, "open", low_level)
            for name in ("replace", "rename"):
                patch.setattr(os, name, binary(getattr(os, name), name))
            for name in ("unlink", "remove", "stat", "lstat"):
                patch.setattr(os, name, unary(getattr(os, name), name))
            patch.setattr(shutil, "rmtree", unary(shutil.rmtree, "rmtree"))
            yield self


def test_mirror_guard_rejects_real_io_even_as_root(tmp_path, monkeypatch):
    original = (builtins.open, io.open, os.open)
    guard = MirrorAccess(tmp_path, deny=True)
    path = tmp_path / "envelopes.json"
    with guard.installed(monkeypatch):
        for action in (lambda: open(path, "w"), lambda: io.open(path, "r"),
                       lambda: path.read_bytes(), lambda: os.open(path, os.O_CREAT | os.O_WRONLY),
                       lambda: os.open(path, os.O_RDONLY),
                       lambda: (tmp_path / "published_projection.jsonl.tmp").write_text("forbidden")):
            with pytest.raises(MirrorDenied):
                action()
        (tmp_path / "store.lock").touch()
    assert not path.exists()
    assert not (tmp_path / "published_projection.jsonl.tmp").exists()
    assert sum(row["count"] for row in guard.rows.values()) == 6
    assert (builtins.open, io.open, os.open) == original


@pytest.mark.parametrize("operation", ["replace", "rename", "unlink", "remove", "rmtree", "stat"])
def test_mirror_guard_rejects_mutations_and_metadata(tmp_path, monkeypatch, operation):
    path = tmp_path / "envelopes.json"
    path.write_text("unchanged")
    directory = tmp_path / "objects"
    directory.mkdir()
    (directory / "snapshot.jsonl").write_text("unchanged")
    ordinary = tmp_path / "ordinary.txt"
    ordinary.write_text("ordinary")
    guard = MirrorAccess(tmp_path, deny=True)
    with guard.installed(monkeypatch), pytest.raises(MirrorDenied):
        if operation in {"replace", "rename"}:
            # Check the destination too: an unclassified source cannot bypass it.
            getattr(os, operation)(ordinary, path)
        elif operation == "rmtree":
            shutil.rmtree(directory)
        else:
            getattr(os, operation)(path)
    assert path.read_text() == "unchanged"
    assert (directory / "snapshot.jsonl").read_text() == "unchanged"


def test_baseline_rejects_known_owner_in_new_phase():
    version = f"{sys.version_info.major}.{sys.version_info.minor}"
    expected = json.loads(BASELINE.read_text())[version]["durable"]
    rows = [dict(zip(("owner", "mirror", "access", "phase"), row)) for row in expected]
    _assert_access_baseline(rows, "durable")
    rows.append(dict(owner="_mirror_envelopes", mirror="envelopes.json", access="write", phase="accounts-and-session"))
    with pytest.raises(AssertionError, match="Mirror baseline changed"):
        _assert_access_baseline(rows, "durable")


def _normalise(state, root):
    # Compare all exported PG tables, keeping object content/hashes, identities,
    # decisions and relationships. Independent export validates chain integrity.
    # Per-run clocks, password salts/hashes, session token hashes and the review
    # chain's time-dependent hashes differ without any mirror-related change.
    volatile = {"exported_at", "snapshot_at", "password_salt", "password_hash", "token_hash",
                "event_hash", "previous_event_hash", "duration_ms", "elapsed_ms", "duration_seconds"}
    def visit(value):
        if isinstance(value, dict):
            return {k: visit(v) for k, v in value.items() if k not in volatile}
        if isinstance(value, list):
            return [visit(v) for v in value]
        if isinstance(value, str):
            if re.fullmatch(r"\d{4}-\d\d-\d\d[T ].*", value):
                return "<time>"
            return value.replace(str(root), "<test-root>")
        return value
    return visit(state)


def _run(config, root, guard, monkeypatch, checkpoints, completed, expected=None, console_kind="durable"):
    source = MemorySourceStore()
    canonical = PostgresCanonicalPublicationStore(config)
    adapter = PostgresWorkflowRecoveryAdapter(canonical)
    counters = {}
    def fixture_uuid():
        # Mirror/diagnostic UUID consumption may differ in the denied run.
        # Separate call-site sequences keep unrelated durable IDs comparable.
        caller = sys._getframe(1)
        key = (caller.f_code.co_filename, caller.f_code.co_name, caller.f_lineno)
        counters[key] = counters.get(key, 0) + 1
        return uuid.UUID(hex=hashlib.sha256(repr((key, counters[key])).encode()).hexdigest()[:32])
    def step(phase, action):
        guard.phase = phase
        result = action()
        checkpoints[phase] = _normalise(adapter.export_state(), root)
        if expected is not None:
            assert checkpoints[phase] == expected[phase], f"PostgreSQL state diverged after {phase}"
        completed.append(phase)
        return result
    def construct():
        console = complete_console(root, config, console_cls=CONSOLES[console_kind], immutable_source_store=source)
        bind_fixture_selections(console)
        return console
    def build():
        from src import console_asgi as asgi
        from src.workflow_store_configuration import POSTGRES_STORE_SETTINGS
        with monkeypatch.context() as setup:
            for name in POSTGRES_STORE_SETTINGS:
                setup.setenv(name, "postgres")
            setup.setenv("METIS_CANONICAL_DB_DSN", config.dsn)
            setup.setenv("CONSOLE_DATA_ROOT", str(root))
            setup.setenv("CONSOLE_RUNTIME", str(root / "runtime"))
            setup.setenv("CONSOLE_SOURCE_STORE", str(root / "sources"))
            setup.setenv("CONSOLE_PUBLIC_ORIGIN", "https://console.example.test")
            setup.setenv("WEB_CONCURRENCY", "1")
            for name in ("CONSOLE_BOOTSTRAP_USERNAME", "CONSOLE_BOOTSTRAP_REVIEWER_USERNAME", "WEBSITE_SITE_NAME"):
                setup.delenv(name, raising=False)
            if console_kind == "azure":
                setup.setenv("WEBSITE_SITE_NAME", "d4b-test")
            setup.setattr(asgi, "ROOT", root)
            setup.setattr(asgi, "_postgres_credential", lambda: None)
            setup.setattr(asgi, "_immutable_source_store", lambda: source)
            # Same synthetic provider as direct construction; no live model call.
            setup.setattr(asgi, "bind_pre_review_semantic_processing", bind_fixture_selections)
            setup.setattr(asgi, "install_structured_logging", lambda: None)
            kernel = asgi.build_app().state.operations_kernel
        bind_fixture_selections(kernel)
        return kernel
    with monkeypatch.context() as patch, guard.installed(monkeypatch):
        # Stable UUID identities across the two isolated runs, not a mocked store.
        patch.setattr(uuid, "uuid4", fixture_uuid)
        patch.setattr(quality_evidence_v1, "uuid4", fixture_uuid)
        console = step("startup", construct)
        def accounts_and_session():
            accounts = {name: console.create_account(name, "D4-test-password", roles=roles)
                for name, roles in (("researcher", ["researcher"]), ("reviewer", ["reviewer"]),
                                    ("second", ["reviewer"]), ("publisher", ["publisher"]))}
            session = console.authenticate("reviewer", "D4-test-password")
            assert console.session_account(session["token"])["account_id"] == accounts["reviewer"]["account_id"]
            console.logout(session["token"])
            return accounts
        accounts = step("accounts-and-session", accounts_and_session)
        def ingest(version, prior=None):
            return console.ingest(actor_id=accounts["researcher"]["account_id"],
                filename=f"d4-v{version}.html", data=HTML_FIXTURE.read_bytes() + f"<!-- D4 v{version} -->".encode(),
                content_type="text/html", ingest_kind="new_version" if prior else "new",
                replaces_snapshot_id=prior, title="D4 mirror lifecycle", version=version,
                date="2026-09-16", live_url="https://example.test/d4", class_="richtlijn", family="d4",
                named_reviewers=[accounts["reviewer"]["account_id"], accounts["second"]["account_id"]])
        def review(sid):
            # Existing synthetic-history helper seeds high-risk fixture input;
            # all approvals and four-eyes checks use real console commands/PG.
            history = deepcopy(console._load_objects(sid))
            target = next(row for row in history if row.get("object_type") == "unclassified")
            target.setdefault("risk", {}).update(risk_level="high", risk_fields=["exception"])
            stamp_canonical_hashes(target)
            install_fixture_history(console, sid, history)
            _complete_review(console, reviewer_id=accounts["reviewer"]["account_id"], snapshot_id=sid)
            current = next(row for row in console.snapshot_objects(sid) if row["object_id"] == target["object_id"])
            assert exact_current_approver_ids(current, console.object_review_bindings(sid)) == (accounts["reviewer"]["account_id"],)
            with pytest.raises(ConsoleError, match="^independent_second_reviewer_required$"):
                console.approve_second_review(actor_id=accounts["reviewer"]["account_id"], snapshot_id=sid, object_id=target["object_id"])
            console.approve_second_review(actor_id=accounts["second"]["account_id"], snapshot_id=sid, object_id=target["object_id"])
            current = next(row for row in console.snapshot_objects(sid) if row["object_id"] == target["object_id"])
            assert set(exact_current_approver_ids(current, console.object_review_bindings(sid))) == {
                accounts["reviewer"]["account_id"], accounts["second"]["account_id"]}
        def publish(sid):
            result = console.publish(actor_id=accounts["publisher"]["account_id"], snapshot_id=sid)
            assert result["status"] == "PASS", result
            return result
        v1 = step("ingest-v1", lambda: ingest("1.0"))
        step("review-v1-four-eyes", lambda: review(v1["snapshot_id"]))
        r1 = step("publish-v1", lambda: publish(v1["snapshot_id"]))
        console = step("build-app-startup", build)
        v2 = step("successor-v2", lambda: ingest("2.0", v1["snapshot_id"]))
        assert canonical.active_publication_rows()
        assert console.document_release_serving_status(v1["snapshot_id"])["serving_status"] == "active"
        step("review-v2-four-eyes", lambda: review(v2["snapshot_id"]))
        r2 = step("publish-v2", lambda: publish(v2["snapshot_id"]))
        assert r1["release_id"] != r2["release_id"]
        assert console._envelope(v1["snapshot_id"])["logical_document_id"] == console._envelope(v2["snapshot_id"])["logical_document_id"]
        v3 = step("successor-v3", lambda: ingest("3.0", v2["snapshot_id"]))
        step("withdraw", lambda: console.withdraw_document(actor_id=accounts["publisher"]["account_id"],
            snapshot_id=v2["snapshot_id"], expected_release_id=r2["release_id"], reason="D4 fixture withdrawn"))
        assert canonical.active_publication_rows() == []
        console = step("restart", construct)
        assert canonical.active_publication_rows() == []
        assert console.document_release_serving_status(v2["snapshot_id"])["serving_status"] == "inactive"
        step("resume-successor", lambda: review(v3["snapshot_id"]))
        assert console.snapshot_objects(v3["snapshot_id"])
        assert canonical.active_publication_rows() == []
        disposable = step("ingest-delete", lambda: ingest("4.0"))
        step("delete-unpublished", lambda: console.delete_unpublished_snapshot(
            actor_id=accounts["publisher"]["account_id"], snapshot_id=disposable["snapshot_id"],
            confirmed=True, confirm_title="D4 mirror lifecycle"))
        assert disposable["snapshot_id"] not in console.list_snapshot_ids()


def _mirror_cause(error):
    seen = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, MirrorDenied):
            return True
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return False


@pytest.mark.parametrize("console_kind", CONSOLES)
def test_pg_console_without_disk_mirrors(complete_postgres, tmp_path, monkeypatch, capsys, record_property, console_kind):
    config = complete_postgres
    # The fixture owns this disposable DB. Never call the reset helper on the
    # supplied DSN (which could point at an existing development database).
    from psycopg.conninfo import conninfo_to_dict
    assert conninfo_to_dict(config.dsn)["dbname"].startswith("metis_718_")
    roots = {mode: tmp_path / mode for mode in ("control", "guarded")}
    reports, baseline = {}, {}
    try:
        control = MirrorAccess(roots["control"] / "runtime", deny=False)
        completed = []
        _run(config, roots["control"], control, monkeypatch, baseline, completed, console_kind=console_kind)
        assert completed == list(PHASES), "Writable control must complete the lifecycle"
        reports["control"] = dict(completed=completed, accesses=list(control.rows.values()))
        _assert_access_baseline(reports["control"]["accesses"], console_kind)
        _install_schema(config.dsn)  # Only the fixture-owned disposable database.
        runtime = roots["guarded"] / "runtime"
        runtime.mkdir(parents=True)
        # Empty child directories allow lock creation, not JSON data: all mirror
        # opens (including atomic temp files) are denied independently of UID.
        for name in ("objects", "release_manifests"):
            (runtime / name).mkdir()
        for name in ("store.lock", "sessions.json.lock"):
            (runtime / name).touch()
        assert not any(path.is_file() and not path.name.endswith(".lock") for path in runtime.rglob("*"))
        runtime.chmod(0o555)
        assert runtime.stat().st_mode & 0o222 == 0
        guard = MirrorAccess(runtime, deny=True)
        completed, checkpoints, fault = [], {}, None
        try:
            _run(config, roots["guarded"], guard, monkeypatch, checkpoints, completed, expected=baseline, console_kind=console_kind)
        except Exception as error:
            if not _mirror_cause(error):
                raise  # Connection, harness, assertion and unrelated faults are never xfailed.
            fault = dict(phase=guard.phase, type=type(error).__name__, code=getattr(error, "code", None))
        finally:
            reports["guarded"] = dict(completed=completed, blocked=fault,
                not_reached=[phase for phase in PHASES if phase not in completed],
                pg_equivalence="complete" if completed == list(PHASES) else "completed-prefix-only",
                accesses=list(guard.rows.values()))
            runtime.chmod(0o755)
            assert not any(path.is_file() and not path.name.endswith(".lock") for path in runtime.rglob("*")), "Mirror guard leaked a data write"
        unknown = [row for report in reports.values() for row in report["accesses"] if row["owner"] is None]
        assert not unknown, f"New mirror owner needs explicit D4 review: {unknown}"
        if guard.rows:
            pytest.xfail("D4 known mirror accesses; see PG_MIRROR_MAP for stacks and blocked/unreached phases. D5 must remove the conditional xfail.")
        assert completed == list(PHASES)
    finally:
        for root in roots.values():
            unregister_backend(root / "runtime" / "review_ledger.jsonl")
        record_property("pg_mirror_map", json.dumps(reports, sort_keys=True))
        # Visible even with CI's normal pytest capture and -q; no locals, DSNs,
        # source bytes, credentials or full PG records enter this report.
        with capsys.disabled():
            print("\nPG_MIRROR_MAP " + json.dumps(reports, sort_keys=True))
