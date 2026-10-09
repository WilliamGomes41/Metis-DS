"""Real PostgreSQL recovery evidence for canonical + workflow authority.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.integrity_kernel import stable_hash
from src.topic_identity_v1 import topic_identity
from src.publication_chain_recovery_v1 import PublicationChainRecoveryError
from src.workflows import workflow_chain_recovery_v1 as recovery
from src.workflows.workflow_chain_recovery_v1 import (
    PostgresWorkflowRecoveryAdapter,
    backup_workflow_chain,
    check_workflow_integrity,
    restore_workflow_chain,
    verify_workflow_chain_backup,
)
from src.workflows.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore
from tests.test_publication_chain_recovery_v1 import FakeBlobStore

ROOT = Path(__file__).resolve().parents[1]
SOURCE_BYTES = b"immutable workflow-only source"
SOURCE_SHA = hashlib.sha256(SOURCE_BYTES).hexdigest()
SOURCE_LOCATOR = f"azure://aidataservice/canonical-sources/{SOURCE_SHA}/source.pdf"
def _install_schema(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
        con.execute("DROP SCHEMA IF EXISTS api_access CASCADE")
        con.execute("DROP SCHEMA IF EXISTS public CASCADE")
        con.execute("CREATE SCHEMA public")
        paths = [ROOT / "db" / "schema_v2.sql", *sorted((ROOT / "db" / "migrations").glob("*.sql"))]
        for path in paths:
            con.execute(path.read_text(encoding="utf-8"))


@pytest.fixture()
def recovery_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for PostgreSQL recovery evidence")
    _install_schema(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    yield config
    _install_schema(dsn)


def _seed_workflow(config: PostgresCanonicalConfig) -> None:
    import psycopg

    event_body = {
        "event_type": "review_approve",
        "object_id": "obj-1",
        "object_version": "1.0",
        "actor": "reviewer",
        "occurred_at": "2026-09-12T12:00:00+00:00",
        "details": {"snapshot_id": "snap-1"},
        "previous_event_hash": None,
    }
    event = dict(event_body)
    event["event_hash"] = stable_hash(event_body)
    envelope = {
        "snapshot_id": "snap-1",
        "source_id": "source-1",
        "document_id": "doc-1",
        "title": "Recovery document",
        "family": "test",
        "class": "richtlijn",
        "state": "review",
        "publication_eligibility": "eligible",
        "content_kind": "pdf",
        "ingest_kind": "upload",
        "version": "1.0",
        "date": "2026-09-12",
        "sha256": SOURCE_SHA,
        "locator": "source://snap-1",
        "immutable_storage_locator": SOURCE_LOCATOR,
        "live_url": "",
        "uploader_account_id": "acc-uploader",
        "named_reviewers": ["acc-reviewer"],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-12T12:00:00+00:00",
        "console_version": "recovery-test",
    }
    topic_id, identity_key, display_name = topic_identity(envelope["family"])
    with psycopg.connect(config.dsn, autocommit=True) as con:
        con.execute(
            "INSERT INTO workflow.accounts VALUES(%s,%s,%s,%s,%s,%s,%s)",
            ("acc-uploader", "uploader", "Uploader", ["researcher", "publisher"], "salt", "hash", "2026-09-12T12:00:00Z"),
        )
        con.execute(
            "INSERT INTO workflow.accounts VALUES(%s,%s,%s,%s,%s,%s,%s)",
            ("acc-reviewer", "reviewer", "Reviewer", ["reviewer"], "salt", "hash", "2026-09-12T12:00:00Z"),
        )
        token_hash = hashlib.sha256(b"session-token").hexdigest()
        con.execute(
            "INSERT INTO workflow.sessions(token_hash,account_id,created_at,expires_at,revoked_at) VALUES(%s,%s,%s,%s,NULL)",
            (token_hash, "acc-uploader", "2026-09-12T12:00:00Z", "2027-09-12T12:00:00Z"),
        )
        con.execute(
            "INSERT INTO workflow.topics(topic_id,identity_key,display_name,created_at) VALUES(%s,%s,%s,%s)",
            (topic_id, identity_key, display_name, "2026-09-12T12:00:00Z"),
        )
        envelope["topic_id"] = topic_id
        con.execute(
            """INSERT INTO workflow.documents(
            snapshot_id,source_id,document_id,title,family,topic_id,class,state,publication_eligibility,
            content_kind,ingest_kind,source_version,source_date,source_sha256,source_locator,
            immutable_storage_locator,live_url,uploader_account_id,replaces_snapshot_id,object_diff,
            clinical_rereview_required,acquired_at,console_version,revision,updated_at,envelope_payload)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,2,%s,%s::jsonb)""",
            (
                "snap-1", "source-1", "doc-1", "Recovery document", "test", topic_id, "richtlijn", "review", "eligible",
                "pdf", "upload", "1.0", "2026-09-12", SOURCE_SHA, "source://snap-1", SOURCE_LOCATOR, "",
                "acc-uploader", False, "2026-09-12T12:00:00Z", "recovery-test", "2026-09-12T12:01:00Z",
                json.dumps(envelope, sort_keys=True),
            ),
        )
        con.execute(
            "INSERT INTO workflow.document_reviewers(snapshot_id,account_id,assigned_at) VALUES(%s,%s,%s)",
            ("snap-1", "acc-reviewer", "2026-09-12T12:00:00Z"),
        )
        con.execute(
            "INSERT INTO workflow.document_objects(snapshot_id,object_id,object_version,payload,revision,updated_at,position) VALUES(%s,%s,%s,%s::jsonb,2,%s,0)",
            ("snap-1", "obj-1", "1.0", json.dumps({"object_id": "obj-1", "object_version": "1.0", "text": "A"}), "2026-09-12T12:01:00Z"),
        )
        con.execute(
            """INSERT INTO workflow.review_events(
            event_id,snapshot_id,object_id,object_version,event_type,actor_account_id,occurred_at,
            details,previous_event_hash,event_hash,actor_text,event_payload)
            VALUES(1,%s,%s,%s,%s,%s,%s,%s::jsonb,NULL,%s,%s,%s::jsonb)""",
            (
                "snap-1", "obj-1", "1.0", "review_approve", "acc-reviewer", "2026-09-12T12:00:00Z",
                json.dumps({"snapshot_id": "snap-1"}), event["event_hash"], "reviewer", json.dumps(event, sort_keys=True),
            ),
        )
        con.execute(
            """INSERT INTO workflow.publish_authorizations(
            authorization_id,snapshot_id,object_id,object_version,canonical_object_hash,confirmed_object_type,
            reviewer_account_id,reviewer_display_name,decision,valid,created_at,position)
            VALUES(1,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,0)""",
            ("snap-1", "obj-1", "1.0", "b" * 64, "recommendation", "acc-reviewer", "Reviewer", "approve", "2026-09-12T12:00:00Z"),
        )
        con.execute(
            "INSERT INTO workflow.audit_records(audit_id,audit_type,title,created_by,created_at,updated_at,payload) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",
            ("audit-1", "quality", "Audit", "acc-uploader", "2026-09-12T12:00:00Z", "2026-09-12T12:00:00Z", json.dumps({"status": "open"})),
        )
        con.execute(
            "INSERT INTO workflow.audit_secrets(secret_name,secret_payload,updated_at) VALUES(%s,%s::jsonb,%s)",
            ("llm_api_key", json.dumps({"ciphertext": "encrypted"}), "2026-09-12T12:00:00Z"),
        )


def test_workflow_backup_restore_roundtrip_uses_one_database_authority(recovery_postgres: PostgresCanonicalConfig, tmp_path: Path) -> None:
    _seed_workflow(recovery_postgres)
    source = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    before = source.export_state()
    assert check_workflow_integrity(before)["ok"] is True

    archive = tmp_path / "full-chain.zip"
    backup_workflow_chain(archive, database=source, source_store=FakeBlobStore({SOURCE_LOCATOR: SOURCE_BYTES}))
    assert verify_workflow_chain_backup(archive)["ok"] is True

    _install_schema(recovery_postgres.dsn)
    target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    restored_blobs = FakeBlobStore()
    result = restore_workflow_chain(archive, database=target, source_store=restored_blobs)
    after = target.export_state()

    assert result["ok"] is True
    assert result["workflow_integrity"]["ok"] is True
    assert after["workflow_tables"] == before["workflow_tables"]
    assert after["tables"] == before["tables"]
    assert restored_blobs.load_verified(SOURCE_LOCATOR) == SOURCE_BYTES
    assert len(after["workflow_tables"]["topics"]) == 1
    assert after["workflow_tables"]["documents"][0]["topic_id"] == after["workflow_tables"]["topics"][0]["topic_id"]


def test_legacy_v5_workflow_backup_is_deterministically_upgraded(
    recovery_postgres: PostgresCanonicalConfig,
) -> None:
    _seed_workflow(recovery_postgres)
    source = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    current = source.export_state()
    expected_topic_id = current["workflow_tables"]["topics"][0]["topic_id"]

    legacy = deepcopy(current)
    legacy["workflow_recovery_version"] = 5
    legacy["workflow_tables"].pop("topics")
    legacy["workflow_tables"].pop("source_representations")
    legacy["workflow_tables"].pop("source_representation_bindings")
    for row in legacy["workflow_tables"]["documents"]:
        row.pop("topic_id", None)

    _install_schema(recovery_postgres.dsn)
    target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    target.restore_state(legacy)
    restored = target.export_state()

    assert check_workflow_integrity(restored)["ok"] is True
    assert restored["workflow_tables"]["topics"][0]["topic_id"] == expected_topic_id
    assert restored["workflow_tables"]["documents"][0]["topic_id"] == expected_topic_id


def test_resealed_review_chain_tamper_is_rejected(recovery_postgres: PostgresCanonicalConfig, tmp_path: Path) -> None:
    _seed_workflow(recovery_postgres)
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    archive = tmp_path / "full-chain.zip"
    backup_workflow_chain(archive, database=adapter, source_store=FakeBlobStore({SOURCE_LOCATOR: SOURCE_BYTES}))

    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive) as src:
        manifest = json.loads(src.read("chain_manifest.json").decode("utf-8"))
        state = json.loads(src.read("database.json").decode("utf-8"))
        state["workflow_tables"]["review_events"][0]["actor_text"] = "tampered"
        state["workflow_tables"]["review_events"][0]["event_payload"]["actor"] = "tampered"
        db_bytes = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest["database"]["sha256"] = hashlib.sha256(db_bytes).hexdigest()
        with zipfile.ZipFile(broken, "w") as dst:
            for name in src.namelist():
                if name == "database.json":
                    dst.writestr(name, db_bytes)
                elif name == "chain_manifest.json":
                    dst.writestr(name, json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
                else:
                    dst.writestr(name, src.read(name))

    report = verify_workflow_chain_backup(broken)
    assert report["ok"] is False
    assert any("workflow_review_hash_invalid" in error for error in report["errors"])


def test_runtime_identity_store_never_imports_legacy_files(recovery_postgres: PostgresCanonicalConfig) -> None:
    store = CutoverPostgresWorkflowIdentityStore(recovery_postgres)
    migrated = store.migrate_legacy_if_empty(
        {"acc-local": {"account_id": "acc-local"}},
        {"token": {"account_id": "acc-local"}},
    )
    assert migrated is False
    assert store.list_accounts() == []


def test_identity_migration_is_explicit_operator_command() -> None:
    script = (ROOT / "scripts" / "migrate_workflow_identity_postgres.py").read_text(encoding="utf-8")
    asgi = (ROOT / "src" / "console_asgi.py").read_text(encoding="utf-8")
    assert "--runtime" in script
    assert "migrate_legacy_if_empty" in script
    assert "store = CutoverPostgresWorkflowIdentityStore()" in asgi
    assert "store = PostgresWorkflowIdentityStore()" not in asgi


def _successor(config: PostgresCanonicalConfig, sid: str, predecessor: str, *, number: int | None = None) -> None:
    import psycopg

    with psycopg.connect(config.dsn, autocommit=True) as con:
        con.execute(
            """INSERT INTO workflow.documents SELECT (jsonb_populate_record(
                NULL::workflow.documents, to_jsonb(d) || jsonb_build_object(
                    'snapshot_id', %s::text, 'ingest_kind', 'new_version',
                    'replaces_snapshot_id', %s::text,
                    'working_revision_id', %s::text, 'working_revision_number', %s::integer,
                    'envelope_payload', d.envelope_payload || jsonb_build_object(
                        'snapshot_id', %s::text, 'replaces_snapshot_id', %s::text)
                ))).* FROM workflow.documents d WHERE snapshot_id=%s""",
            (sid, predecessor, f"original-work-{sid}", number, sid, predecessor, predecessor),
        )


def _identity_trigger_enabled(config: PostgresCanonicalConfig) -> bool:
    import psycopg

    with psycopg.connect(config.dsn) as con:
        return con.execute(
            "SELECT tgenabled='O' FROM pg_trigger WHERE tgrelid='workflow.documents'::regclass "
            "AND tgname='trg_workflow_documents_lifecycle_identity'"
        ).fetchone()[0]


def test_restore_preserves_successors_custom_identity_and_revision_gaps(recovery_postgres: PostgresCanonicalConfig) -> None:
    import psycopg

    _seed_workflow(recovery_postgres)
    _successor(recovery_postgres, "deleted-work", "snap-1")
    _successor(recovery_postgres, "sorts-before-parent", "snap-1")
    _successor(recovery_postgres, "another-successor", "snap-1")
    with psycopg.connect(recovery_postgres.dsn, autocommit=True) as con:
        con.execute("DELETE FROM workflow.documents WHERE snapshot_id='deleted-work'")
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    before = adapter.export_state()
    _install_schema(recovery_postgres.dsn)
    adapter.restore_state(before)
    after = adapter.export_state()
    assert after["workflow_tables"] == before["workflow_tables"]
    assert after["tables"] == before["tables"]
    assert _identity_trigger_enabled(recovery_postgres)
    _successor(recovery_postgres, "next-work", "sorts-before-parent")
    with psycopg.connect(recovery_postgres.dsn, autocommit=True) as con:
        assert con.execute("SELECT working_revision_number FROM workflow.documents WHERE snapshot_id='next-work'").fetchone()[0] == 5
        with pytest.raises(psycopg.Error, match="lifecycle_identity_immutable"):
            con.execute("UPDATE workflow.documents SET working_revision_number=99 WHERE snapshot_id='snap-1'")
    with pytest.raises(psycopg.Error, match="working_revision_number_mismatch"):
        _successor(recovery_postgres, "invalid-work", "snap-1", number=99)
    with pytest.raises(PublicationChainRecoveryError, match="target_not_empty"):
        adapter.restore_state(before)


def test_restore_rollback_restores_allocator_and_empty_target(recovery_postgres: PostgresCanonicalConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_workflow(recovery_postgres)
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    state = adapter.export_state()
    _install_schema(recovery_postgres.dsn)
    original = recovery._insert_rows

    def interrupted(con, **kwargs):
        original(con, **kwargs)
        if kwargs["table"] == "documents":
            raise RuntimeError("interrupted after identity import")

    monkeypatch.setattr(recovery, "_insert_rows", interrupted)
    with pytest.raises(PublicationChainRecoveryError, match="workflow_database_restore_failed"):
        adapter.restore_state(state)
    adapter.assert_empty()
    assert _identity_trigger_enabled(recovery_postgres)
    monkeypatch.setattr(recovery, "_insert_rows", original)
    adapter.restore_state(state)
    assert adapter.export_state()["workflow_tables"] == state["workflow_tables"]


@pytest.mark.parametrize("fault", ["projection", "duplicate", "missing_predecessor", "cycle", "legacy"])
def test_invalid_lifecycle_archive_fails_before_writes(recovery_postgres: PostgresCanonicalConfig, fault: str) -> None:
    _seed_workflow(recovery_postgres)
    _successor(recovery_postgres, "snap-2", "snap-1")
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    state = deepcopy(adapter.export_state())
    root, child = state["workflow_tables"]["documents"]
    if fault == "projection":
        child["envelope_payload"]["working_revision_id"] = "untrusted-projection"
    elif fault == "duplicate":
        child["working_revision_id"] = root["working_revision_id"]
        child["envelope_payload"]["working_revision_id"] = root["working_revision_id"]
    elif fault == "missing_predecessor":
        child["replaces_snapshot_id"] = "absent"
        child["envelope_payload"]["replaces_snapshot_id"] = "absent"
    elif fault == "cycle":
        root["replaces_snapshot_id"] = "snap-2"
        root["envelope_payload"]["replaces_snapshot_id"] = "snap-2"
    else:
        state["workflow_recovery_version"] = 1
    _install_schema(recovery_postgres.dsn)
    assert check_workflow_integrity(state)["ok"] is False
    with pytest.raises(PublicationChainRecoveryError):
        adapter.restore_state(state)
    adapter.assert_empty()
    assert _identity_trigger_enabled(recovery_postgres)


def test_restore_rechecks_nonempty_destination_inside_lock(recovery_postgres: PostgresCanonicalConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    _seed_workflow(recovery_postgres)
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    state = adapter.export_state()
    _install_schema(recovery_postgres.dsn)
    original = adapter.assert_empty

    def concurrent_write_after_preflight():
        original()
        with psycopg.connect(recovery_postgres.dsn, autocommit=True) as con:
            con.execute(
                "INSERT INTO workflow.accounts VALUES('other','other','Other',ARRAY['researcher'],'salt','hash',now())"
            )

    monkeypatch.setattr(adapter, "assert_empty", concurrent_write_after_preflight)
    with pytest.raises(PublicationChainRecoveryError, match="target_not_empty"):
        adapter.restore_state(state)
    after = adapter.export_state()
    assert [row["account_id"] for row in after["workflow_tables"]["accounts"]] == ["other"]
    assert not after["workflow_tables"]["documents"]
    assert _identity_trigger_enabled(recovery_postgres)

@pytest.mark.parametrize("version", [6, 7])
def test_representation_backup_version_requires_explicit_historical_migration(recovery_postgres, version):
    _seed_workflow(recovery_postgres)
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    state = adapter.export_state()
    state["workflow_recovery_version"] = version
    state["workflow_tables"].pop("source_representations")
    state["workflow_tables"].pop("source_representation_bindings")
    _install_schema(recovery_postgres.dsn)
    if version == 7:
        with pytest.raises(PublicationChainRecoveryError, match="workflow_backup_tables_missing"):
            adapter.restore_state(state)
    else:
        adapter.restore_state(state)
        assert adapter.export_state()["workflow_tables"]["source_representations"] == []
