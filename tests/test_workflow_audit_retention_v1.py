"""Audit retention over the actual PostgreSQL authority and external bytes.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient

from scripts.migrate_workflow_remaining_postgres import _migrate_audits
from src import audit_room_v1 as room
from src.audit_archive_store_v1 import AuditArchiveStoreError
from src.audit_retention_v1 import AuditRetentionService
from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError
from src.publication_chain_recovery_v1 import backup_publication_chain, PublicationChainRecoveryError
from src.publication_chain_recovery_guard_v1 import restore_publication_chain, verify_publication_chain_backup
from src.workflows.workflow_chain_recovery_v1 import (
    PostgresWorkflowRecoveryAdapter, backup_workflow_chain, restore_workflow_chain,
    verify_workflow_chain_backup,
)
from src.workflows.workflow_remaining_cutover_v1 import PostgresAuditRegistry
from src.workflows.workflow_remaining_postgres_v1 import PostgresWorkflowRemainingStore, audit_retention_lock
from tests.test_audit_retention_v1 import _MemoryArchiveStore
from tests.test_publication_chain_recovery_v1 import FakeBlobStore, FakeDatabase
from tests.test_vsa_publish_document_v1 import _console, MemorySourceStore, TEST_PASSWORD
from tests.test_workflow_chain_recovery_v1 import recovery_postgres, _install_schema  # noqa: F401


class Archive(_MemoryArchiveStore):
    def _locator(self, audit_id):
        return f"azure-audit://aidataservice/audit-archive/audits/{audit_id}.json"


def _system(tmp_path, config, monkeypatch, *, create=True, archive=None):
    canonical = PostgresCanonicalPublicationStore(config)
    console = _console(tmp_path, config, canonical, MemorySourceStore(), runtime_name="runtime")
    if create:
        account = console.create_account(username="researcher", password=TEST_PASSWORD, roles=("researcher",))
    else:
        account = next(row for row in console.list_accounts() if row["username"] == "researcher")
    store = PostgresWorkflowRemainingStore(config)
    store.verify_remaining_schema()
    registry = PostgresAuditRegistry(store)
    monkeypatch.setattr(room, "AuditRegistry", lambda runtime: registry)
    archive = archive or Archive()
    app = create_console_app(console)
    room.install_audit_routes(app, console, archive_store=archive)
    client = TestClient(app)
    assert client.post("/login", data={"username": "researcher", "password": TEST_PASSWORD}, follow_redirects=False).status_code == 303
    service = AuditRetentionService(live_store=registry, archive_store=archive, runtime=console.runtime)
    return store, registry, service, archive, client, account


def _create(registry, account, title="Duurzaam auditbewijs"):
    return registry.create(audit_type="experiment", title=title, actor_id=account["account_id"],
                           payload={"state": "setup", "question": "Exacte bewijsinhoud"})


def test_http_archive_fresh_runtime_restore_and_pending_purge(recovery_postgres, tmp_path, monkeypatch):
    store, registry, service, archive, client, account = _system(tmp_path / "first", recovery_postgres, monkeypatch)
    record = _create(registry, account)
    sid = record["audit_id"]
    assert client.post(f"/audit/{sid}/archive", follow_redirects=False).status_code == 303
    assert not list((tmp_path / "first" / "runtime").glob("audits/*.json"))
    _, fresh, service, _, client, _ = _system(tmp_path / "fresh", recovery_postgres, monkeypatch, create=False, archive=archive)
    assert record["title"] in client.get("/audit/archive").text
    assert "Exacte bewijsinhoud" in client.get(f"/audit/archive/{sid}").text
    archive.fail_delete = True
    restored = client.post(f"/audit/archive/{sid}/restore", follow_redirects=False)
    assert restored.status_code == 503 and "Audit is hersteld" in restored.text
    assert fresh.get_audit(sid) == record
    archive.fail_delete = False
    assert client.post(f"/audit/archive/{sid}/restore", follow_redirects=False).status_code == 303
    assert archive.data == {}
    assert client.post(f"/audit/{sid}/archive", follow_redirects=False).status_code == 303

    def crash_after_blob(*args):
        raise ConsoleError("simulated_after_blob_delete")
    monkeypatch.setattr(service.live_store.store, "remove_archived_ref", crash_after_blob)
    with pytest.raises(ConsoleError, match="simulated_after_blob_delete"):
        service.purge(sid, actor_id=account["account_id"], confirm_title=record["title"])
    assert archive.data == {}
    _, fresh, _, _, client, _ = _system(tmp_path / "again", recovery_postgres, monkeypatch, create=False, archive=archive)
    detail = client.get(f"/audit/archive/{sid}")
    assert detail.status_code == 200 and "wacht op afronding" in detail.text
    assert f'action="/audit/archive/{sid}/restore"' not in detail.text
    assert client.post(f"/audit/archive/{sid}/restore", follow_redirects=False).status_code == 409
    for _ in range(2):
        assert client.post(f"/audit/archive/{sid}/purge", data={"confirm_title": record["title"]}, follow_redirects=False).status_code == 303
    assert fresh.get_archived_reference(sid) is None
    assert fresh.get_audit(sid) is None


@pytest.mark.parametrize("committed", [False, True])
def test_archive_resolves_uncertain_commit_without_deleting_owned_blob(recovery_postgres, tmp_path, monkeypatch, committed):
    store, registry, service, archive, _, account = _system(tmp_path, recovery_postgres, monkeypatch)
    record = _create(registry, account)
    real = store.replace_with_archived_ref
    def lost_ack(sid, reference):
        if committed:
            real(sid, reference)
        raise RuntimeError("database connection lost")
    monkeypatch.setattr(store, "replace_with_archived_ref", lost_ack)
    if committed:
        service.archive(record["audit_id"], actor_id=account["account_id"])
        assert service.load_archived(record["audit_id"]) == record
    else:
        with pytest.raises(ConsoleError, match="audit_store_unavailable"):
            service.archive(record["audit_id"], actor_id=account["account_id"])
        assert registry.get_audit(record["audit_id"]) == record
        assert archive.data == {}


def test_same_audit_commands_wait_across_independent_database_connections(recovery_postgres, tmp_path, monkeypatch):
    store, registry, service, archive, _, account = _system(tmp_path, recovery_postgres, monkeypatch)
    record = _create(registry, account)
    other = AuditRetentionService(live_store=PostgresAuditRegistry(PostgresWorkflowRemainingStore(recovery_postgres)),
                                  archive_store=archive, runtime=tmp_path / "empty")
    entered, release, second_started = Event(), Event(), Event()
    original = archive.store_verified
    def paused(**kwargs):
        entered.set()
        assert release.wait(10)
        return original(**kwargs)
    monkeypatch.setattr(archive, "store_verified", paused)
    def restore():
        second_started.set()
        return other.restore(record["audit_id"], actor_id=account["account_id"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.archive, record["audit_id"], actor_id=account["account_id"])
        assert entered.wait(10)
        second = pool.submit(restore)
        assert second_started.wait(10)
        # The first session holds the per-audit lock over the Blob operation.
        with store._connect() as con:
            assert not con.execute("SELECT pg_try_advisory_lock(2110022, hashtext(%s)) AS ok", (record["audit_id"],)).fetchone()["ok"]
        assert not second.done()
        release.set()
        first.result(timeout=10)
        assert second.result(timeout=10) == record
    assert registry.get_audit(record["audit_id"]) == record and archive.data == {}


def test_unknown_archive_outcome_keeps_blob_and_purge_requires_committed_intent(recovery_postgres, tmp_path, monkeypatch):
    store, registry, service, archive, _, account = _system(tmp_path, recovery_postgres, monkeypatch)
    record = _create(registry, account)
    def unavailable(*args, **kwargs):
        raise RuntimeError("database unavailable")
    with monkeypatch.context() as patch:
        def unknown_commit(*args):
            patch.setattr(store, "get_archived_reference", unavailable)
            raise RuntimeError("outcome unknown")
        patch.setattr(store, "replace_with_archived_ref", unknown_commit)
        with pytest.raises(ConsoleError, match="audit_store_unavailable"):
            service.archive(record["audit_id"], actor_id=account["account_id"])
    assert archive.data and registry.get_audit(record["audit_id"]) == record
    ref = service.archive(record["audit_id"], actor_id=account["account_id"])
    with monkeypatch.context() as patch:
        patch.setattr(store, "mark_purge", unavailable)
        with pytest.raises(ConsoleError, match="audit_store_unavailable"):
            service.purge(record["audit_id"], actor_id=account["account_id"], confirm_title=record["title"])
    assert registry.get_archived_reference(record["audit_id"]) == ref and archive.data
    pending = store.mark_purge(record["audit_id"], ref, actor_id=account["account_id"])
    with pytest.raises(ConsoleError, match="audit_archive_reference_changed"):
        store.replace_archived_ref_with_live(record["audit_id"], ref, record)
    assert registry.get_archived_reference(record["audit_id"]) == pending


def test_backup_lock_excludes_retention_and_full_restore_preserves_all_audit_states(recovery_postgres, tmp_path, monkeypatch):
    store, registry, service, archive, _, account = _system(tmp_path, recovery_postgres, monkeypatch)
    live = _create(registry, account, "Live")
    archived = _create(registry, account, "Archived")
    purging = _create(registry, account, "Purging")
    service.archive(archived["audit_id"], actor_id=account["account_id"])
    reference = service.archive(purging["audit_id"], actor_id=account["account_id"])
    store.mark_purge(purging["audit_id"], reference, actor_id=account["account_id"])
    archive.delete_verified(reference["archive_locator"])
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    before = adapter.export_state()
    with audit_retention_lock(store._connect):
        with store._connect() as con:
            assert not con.execute("SELECT pg_try_advisory_lock_shared(2110021,0) AS ok").fetchone()["ok"]
    path = tmp_path / "full.zip"
    original_load = archive.load_verified
    def read_under_snapshot_lock(*args, **kwargs):
        with store._connect() as con:
            assert not con.execute("SELECT pg_try_advisory_lock_shared(2110021,0) AS ok").fetchone()["ok"]
        return original_load(*args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(archive, "load_verified", read_under_snapshot_lock)
        manifest = backup_workflow_chain(path, database=adapter, source_store=FakeBlobStore(), audit_archive_store=archive)
    assert [row["audit_id"] for row in manifest["audit_blobs"]] == [archived["audit_id"]]
    assert verify_workflow_chain_backup(path)["ok"]
    _install_schema(recovery_postgres.dsn)
    target = Archive()
    restore_workflow_chain(path, database=adapter, source_store=FakeBlobStore(), audit_archive_store=target)
    after = adapter.export_state()
    for key in ("tables", "workflow_tables", "api_access_tables"):
        assert after[key] == before[key]
    fresh = PostgresAuditRegistry(PostgresWorkflowRemainingStore(recovery_postgres))
    resumed = AuditRetentionService(live_store=fresh, archive_store=target, runtime=tmp_path / "empty")
    assert fresh.get_audit(live["audit_id"]) == live
    assert resumed.load_archived(archived["audit_id"]) == archived
    assert resumed.restore(archived["audit_id"], actor_id=account["account_id"]) == archived
    assert resumed.purge(purging["audit_id"], actor_id=account["account_id"], confirm_title=purging["title"])["purged"]


def test_legacy_archive_import_is_explicit_idempotent_and_preserves_conflicts(recovery_postgres, tmp_path, monkeypatch):
    store, registry, _, archive, _, account = _system(tmp_path, recovery_postgres, monkeypatch)
    # Use the actual file registry, unaffected by the route constructor binding.
    from tests.test_audit_retention_v1 import AuditRegistry
    legacy = AuditRegistry(tmp_path / "legacy")
    original = _create(legacy, account)
    old_service = AuditRetentionService(live_store=legacy, archive_store=archive, runtime=tmp_path / "legacy")
    ref = old_service.archive(original["audit_id"], actor_id=account["account_id"])
    path = tmp_path / "legacy" / "audits" / f'{original["audit_id"]}.json'
    contents = path.read_bytes()
    assert _migrate_audits(tmp_path / "legacy", store, archive_store=archive) == 1
    assert _migrate_audits(tmp_path / "legacy", store, archive_store=archive) == 1
    assert registry.get_archived_reference(original["audit_id"]) == ref
    assert path.read_bytes() == contents
    bad = dict(ref, title="Conflict")
    path.write_text(json.dumps(bad))
    with pytest.raises(ConsoleError, match="audit_archive_record_mismatch"):
        _migrate_audits(tmp_path / "legacy", store, archive_store=archive)
    assert registry.get_archived_reference(original["audit_id"]) == ref
    assert json.loads(path.read_text()) == bad


def _archived_state(tmp_path):
    from tests.test_audit_retention_v1 import AuditRegistry
    registry = AuditRegistry(tmp_path)
    record = _create(registry, {"account_id": "researcher"})
    archive = Archive()
    service = AuditRetentionService(live_store=registry, archive_store=archive, runtime=tmp_path)
    reference = service.archive(record["audit_id"], actor_id="researcher")
    database = FakeDatabase()
    database.state["workflow_tables"] = {
        "documents": [], "audit_records": [{**record, "payload": reference, "retention_state": "ARCHIVED"}],
    }
    return database, archive, reference


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_missing_audit_bytes_preserve_previous_backup(tmp_path, failure):
    database, archive, ref = _archived_state(tmp_path / "records")
    path = tmp_path / "backup.zip"
    backup_publication_chain(path, database=database, source_store=FakeBlobStore(), audit_archive_store=archive)
    prior = path.read_bytes()
    if failure == "missing":
        archive.data.clear()
    else:
        archive.data[ref["archive_locator"]] = b"corrupt"
    with pytest.raises(PublicationChainRecoveryError, match="audit_blob_read_failed"):
        backup_publication_chain(path, database=database, source_store=FakeBlobStore(), audit_archive_store=archive)
    assert path.read_bytes() == prior


@pytest.mark.parametrize("failure", ["missing_manifest", "extra_manifest", "readback", "write"])
def test_invalid_audit_restore_cannot_commit_database(tmp_path, monkeypatch, failure):
    database, archive, _ = _archived_state(tmp_path / "records")
    good = tmp_path / "backup.zip"
    backup_publication_chain(good, database=database, source_store=FakeBlobStore(), audit_archive_store=archive)
    target = Archive()
    if failure.endswith("manifest"):
        with zipfile.ZipFile(good) as zipf:
            members = {name: zipf.read(name) for name in zipf.namelist()}
        manifest = json.loads(members["chain_manifest.json"])
        if failure == "missing_manifest":
            member = manifest["audit_blobs"].pop()["member"]
            del members[member]
        else:
            manifest["audit_blobs"].append(dict(manifest["audit_blobs"][0]))
        members["chain_manifest.json"] = json.dumps(manifest).encode()
        with zipfile.ZipFile(good, "w") as zipf:
            for name, data in members.items():
                zipf.writestr(name, data)
        assert not verify_publication_chain_backup(good)["ok"]
    elif failure == "readback":
        monkeypatch.setattr(target, "load_verified", lambda *args, **kwargs: b"wrong")
    else:
        target.fail_store = True
    destination = FakeDatabase()
    with pytest.raises(PublicationChainRecoveryError):
        restore_publication_chain(good, database=destination, source_store=FakeBlobStore(), audit_archive_store=target)
    assert destination.restore_calls == 0
