"""Repair #220 PostgreSQL historical release projection regression.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import os
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.workflow_document_concurrency_v1 import (
    PUBLISHED_WORKING_REVISION_IMMUTABLE,
    PostgresConcurrentWorkflowDocumentStore,
)
from src.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflow_postgres_migration_v1 import apply_migrations, migration_digest, migration_paths


ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _dsn() -> str:
    value = os.getenv("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN not configured")
    return value


def _store() -> PostgresConcurrentWorkflowDocumentStore:
    store = PostgresConcurrentWorkflowDocumentStore(PostgresCanonicalConfig(dsn=_dsn()))
    with store._connect() as con:
        paths = migration_paths(ROOT)
        apply_migrations(con, paths=paths, expected_digest=migration_digest(paths))
        con.execute((ROOT / "db" / "schema_v2.sql").read_text(encoding="utf-8"))
    return store


def test_withdrawn_projection_is_not_forced_back_to_published() -> None:
    store = _store()
    token = uuid.uuid4().hex
    snapshot_id = f"snap-{token[:16]}-{token[16:24]}"
    account_id = f"acc-{token[:20]}"
    document_id = f"console-richtlijn-repair2b-{token[:8]}"
    release_id = f"release-{token}"
    release_version = f"1.0-{token[:8]}"
    published_at = "2026-09-16T11:30:00+00:00"

    envelope: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "source_id": f"src-{token[:16]}",
        "document_id": document_id,
        "title": "Repair 2b PostgreSQL fixture",
        "family": "repair2b",
        "class": "richtlijn",
        "state": "captured_not_published",
        "publication_eligibility": "eligible",
        "content_kind": "html",
        "ingest_kind": "new",
        "version": "1.0",
        "date": "2026-09-16",
        "sha256": token * 2,
        "locator": f"g0-local:sources/private/{token * 2}/fixture.html",
        "immutable_storage_locator": f"azure://aidataservice/canonical-sources/{token * 2}/fixture.html",
        "live_url": "",
        "uploader_account_id": account_id,
        "named_reviewers": [],
        "replaces_snapshot_id": None,
        "object_diff": None,
        "clinical_rereview_required": False,
        "acquired_at": "2026-09-16T11:00:00Z",
        "console_version": "repair2b-test",
    }
    objects = [{
        "object_id": f"{document_id}-object",
        "object_version": "1.0",
        "object_type": "explanation",
        "content": {"clean_text": "Historical release work stays immutable."},
    }]

    try:
        with store._connect() as con:
            con.execute(
                "INSERT INTO workflow.accounts(account_id,username,display_name,roles,password_salt,password_hash,created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                (account_id, f"repair2b-{token}", "Repair 2b", ["researcher"], "salt", "hash"),
            )
        store.write_bundle(envelope=envelope, objects=objects)

        with store._connect() as con:
            con.execute(
                "INSERT INTO publication_releases(release_id,release_version,release_owner,status,created_at,published_at,withdrawn_at) "
                "VALUES(%s,%s,'publisher','withdrawn',%s,%s,%s)",
                (release_id, release_version, published_at, published_at, published_at),
            )
            con.execute(
                "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) "
                "VALUES('release',%s,%s,'release_published','publisher',%s,%s::jsonb)",
                (release_id, release_version, published_at, json.dumps({"snapshot_id": snapshot_id})),
            )

        withdrawn = deepcopy(envelope)
        withdrawn.update({
            "state": "withdrawn",
            "published": False,
            "release_id": release_id,
            "release_version": release_version,
            "published_at": published_at,
            "published_by": "publisher",
        })
        store.write_bundle(envelope=withdrawn)
        stored = store.get_envelope(snapshot_id)
        assert stored is not None
        assert stored["state"] == "withdrawn"
        assert stored["published"] is False

        before = store.list_document_objects(snapshot_id)
        mutated = deepcopy(before)
        mutated[0]["content"]["clean_text"] = "Forbidden historical rewrite"
        with pytest.raises(WorkflowDocumentStoreError, match=PUBLISHED_WORKING_REVISION_IMMUTABLE):
            store.write_bundle(
                envelope=stored,
                objects=mutated,
                expected_revision=store.objects_revision(snapshot_id),
            )
        assert store.list_document_objects(snapshot_id) == before
        assert store.get_envelope(snapshot_id)["state"] == "withdrawn"  # type: ignore[index]
    finally:
        with store._connect() as con:
            con.execute("DELETE FROM workflow.documents WHERE snapshot_id=%s", (snapshot_id,))
            con.execute("DELETE FROM workflow.accounts WHERE account_id=%s", (account_id,))
            con.execute("DELETE FROM audit_events WHERE entity_type='release' AND entity_id=%s", (release_id,))
            con.execute("DELETE FROM publication_releases WHERE release_id=%s", (release_id,))
