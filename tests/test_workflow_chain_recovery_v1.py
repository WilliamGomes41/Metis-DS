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
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.integrity_kernel import stable_hash
from src.workflow_chain_recovery_v1 import (
    PostgresWorkflowRecoveryAdapter,
    backup_workflow_chain,
    check_workflow_integrity,
    restore_workflow_chain,
    verify_workflow_chain_backup,
)
from src.workflow_identity_cutover_v1 import CutoverPostgresWorkflowIdentityStore

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_MIGRATIONS = (
    "002_workflow_schema.sql",
    "003_workflow_document_envelope_payload.sql",
    "004_workflow_review_authority.sql",
    "005_workflow_remaining_authority.sql",
)


def _statements(text: str) -> list[str]:
    sql = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _install_schema(dsn: str) -> None:
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as con:
        con.execute("DROP SCHEMA IF EXISTS workflow CASCADE")
        con.execute("DROP SCHEMA IF EXISTS public CASCADE")
        con.execute("CREATE SCHEMA public")
        for path in (ROOT / "db" / "schema_v2.sql", ROOT / "db" / "migrations" / "001_canonical_source_lineage.sql"):
            for statement in _statements(path.read_text(encoding="utf-8")):
                con.execute(statement)
        for migration in WORKFLOW_MIGRATIONS:
            text = (ROOT / "db" / "migrations" / migration).read_text(encoding="utf-8")
            for statement in _statements(text):
                con.execute(statement)


@pytest.fixture()
def recovery_postgres() -> PostgresCanonicalConfig:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for PostgreSQL recovery evidence")
    _install_schema(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    yield config
    _install_schema(dsn)


class EmptyBlobStore:
    def load_verified(self, locator: str) -> bytes:  # pragma: no cover - no canonical blobs in fixture
        raise KeyError(locator)

    def store_verified(self, *, data: bytes, sha256: str, filename: str) -> str:  # pragma: no cover
        return f"azure://aidataservice/canonical-sources/{sha256}/{filename}"


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
        "sha256": "a" * 64,
        "locator": "source://snap-1",
        "immutable_storage_locator": "azure://snap-1",
        "live_url": "",
        "uploader_account_id": "acc-uploader",
        "named_reviewers": ["acc-reviewer"],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-12T12:00:00+00:00",
        "console_version": "recovery-test",
    }
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
            """INSERT INTO workflow.documents(
            snapshot_id,source_id,document_id,title,family,class,state,publication_eligibility,
            content_kind,ingest_kind,source_version,source_date,source_sha256,source_locator,
            immutable_storage_locator,live_url,uploader_account_id,replaces_snapshot_id,object_diff,
            clinical_rereview_required,acquired_at,console_version,revision,updated_at,envelope_payload)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL,NULL,%s,%s,%s,2,%s,%s::jsonb)""",
            (
                "snap-1", "source-1", "doc-1", "Recovery document", "test", "richtlijn", "review", "eligible",
                "pdf", "upload", "1.0", "2026-09-12", "a" * 64, "source://snap-1", "azure://snap-1", "",
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
    backup_workflow_chain(archive, database=source, source_store=EmptyBlobStore())
    assert verify_workflow_chain_backup(archive)["ok"] is True

    _install_schema(recovery_postgres.dsn)
    target = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    result = restore_workflow_chain(archive, database=target, source_store=EmptyBlobStore())
    after = target.export_state()

    assert result["ok"] is True
    assert result["workflow_integrity"]["ok"] is True
    assert after["workflow_tables"] == before["workflow_tables"]
    assert after["tables"] == before["tables"]


def test_resealed_review_chain_tamper_is_rejected(recovery_postgres: PostgresCanonicalConfig, tmp_path: Path) -> None:
    _seed_workflow(recovery_postgres)
    adapter = PostgresWorkflowRecoveryAdapter(PostgresCanonicalPublicationStore(recovery_postgres))
    archive = tmp_path / "full-chain.zip"
    backup_workflow_chain(archive, database=adapter, source_store=EmptyBlobStore())

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
