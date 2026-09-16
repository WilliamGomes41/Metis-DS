"""Repair #230: successor publication cuts over one LogicalDocument atomically.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable concurrent stale recovery
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

from src.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.integrity_kernel import stamp_canonical_hashes

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _store() -> PostgresCanonicalPublicationStore:
    dsn = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not dsn:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for Repair 6 PostgreSQL evidence")
    store = PostgresCanonicalPublicationStore(PostgresCanonicalConfig(dsn=dsn))
    with store._connect() as con:
        con.execute((ROOT / "db" / "schema_v2.sql").read_text(encoding="utf-8"))
        con.execute(
            (ROOT / "db" / "migrations" / "001_canonical_source_lineage.sql").read_text(
                encoding="utf-8"
            )
        )
    return store


def _object(*, object_id: str, version: str, document_id: str, checksum: str, text: str) -> dict:
    obj = {
        "object_id": object_id,
        "object_version": version,
        "document_id": document_id,
        "object_type": "explanation",
        "source": {"source_checksum": checksum},
        "content": {"raw_text": text, "clean_text": text},
        "governance": {"validation_status": "approved"},
        "provenance": {},
    }
    return stamp_canonical_hashes(obj)


def _cleanup(store: PostgresCanonicalPublicationStore, *, release_ids: list[str], snapshot_ids: list[str], object_ids: list[str]) -> None:
    with store._connect() as con:
        con.execute("DELETE FROM publication_registry WHERE release_id = ANY(%s)", (release_ids,))
        con.execute("DELETE FROM publication_release_items WHERE release_id = ANY(%s)", (release_ids,))
        con.execute(
            "DELETE FROM audit_events WHERE entity_id = ANY(%s) OR details->>'release_id' = ANY(%s)",
            (release_ids, release_ids),
        )
        con.execute("DELETE FROM publication_releases WHERE release_id = ANY(%s)", (release_ids,))
        con.execute("DELETE FROM canonical_object_sources WHERE snapshot_id = ANY(%s)", (snapshot_ids,))
        con.execute("DELETE FROM source_snapshots WHERE snapshot_id = ANY(%s)", (snapshot_ids,))
        con.execute("DELETE FROM canonical_object_versions WHERE object_id = ANY(%s)", (object_ids,))


def _active_release_ids(store: PostgresCanonicalPublicationStore) -> set[str]:
    return {str(row["publication"]["release_id"]) for row in store.active_publication_rows()}


def test_successor_release_with_changed_object_set_replaces_entire_logical_document() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1 = f"snap1-{suffix}"
    snapshot2 = f"snap2-{suffix}"
    work1 = f"work1-{suffix}"
    work2 = f"work2-{suffix}"
    release1 = f"release1-{suffix}"
    release2 = f"release2-{suffix}"
    old_object_id = f"old-{suffix}"
    new_object_id = f"new-{suffix}"
    checksum1 = "1" * 64
    checksum2 = "2" * 64
    releases = [release1, release2]
    snapshots = [snapshot1, snapshot2]
    objects = [old_object_id, new_object_id]

    try:
        store.persist_published_release(
            logical_document_id=logical_document_id,
            working_revision_id=work1,
            snapshot_id=snapshot1,
            source_sha256=checksum1,
            source_locator=f"g2://sha256/{checksum1}/v1.html",
            release_id=release1,
            release_version="1.0",
            release_owner="repair6",
            published_at="2026-09-16T15:00:00+00:00",
            objects=[
                _object(
                    object_id=old_object_id,
                    version="1.0",
                    document_id=document_id,
                    checksum=checksum1,
                    text="old v1 content",
                )
            ],
        )
        assert _active_release_ids(store) == {release1}

        store.persist_published_release(
            logical_document_id=logical_document_id,
            working_revision_id=work2,
            snapshot_id=snapshot2,
            source_sha256=checksum2,
            source_locator=f"g2://sha256/{checksum2}/v2.html",
            release_id=release2,
            release_version="2.0",
            release_owner="repair6",
            published_at="2026-09-16T15:01:00+00:00",
            objects=[
                _object(
                    object_id=new_object_id,
                    version="2.0",
                    document_id=document_id,
                    checksum=checksum2,
                    text="replacement v2 content",
                )
            ],
        )

        active = store.active_publication_rows()
        assert _active_release_ids(store) == {release2}
        assert {str(row["knowledge_object"]["object_id"]) for row in active} == {new_object_id}
    finally:
        _cleanup(store, release_ids=releases, snapshot_ids=snapshots, object_ids=objects)
