"""Successor publication keeps one LogicalDocument serving release authoritative.

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
    CanonicalPublicationStoreError,
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.durable_publication_console_v1 import DurablePublicationConsole
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
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for successor PostgreSQL evidence")
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


def _publish(
    store: PostgresCanonicalPublicationStore,
    *,
    logical_document_id: str,
    working_revision_id: str,
    snapshot_id: str,
    release_id: str,
    object_id: str,
    document_id: str,
    checksum: str,
    version: str,
    published_at: str,
) -> None:
    store.persist_published_release(
        logical_document_id=logical_document_id,
        working_revision_id=working_revision_id,
        snapshot_id=snapshot_id,
        source_sha256=checksum,
        source_locator=f"g2://sha256/{checksum}/{version}.html",
        release_id=release_id,
        release_version=version,
        release_owner="successor-hardening",
        published_at=published_at,
        objects=[
            _object(
                object_id=object_id,
                version=version,
                document_id=document_id,
                checksum=checksum,
                text=f"content {version}",
            )
        ],
    )


def _cleanup(
    store: PostgresCanonicalPublicationStore,
    *,
    release_ids: list[str],
    snapshot_ids: list[str],
    object_ids: list[str],
) -> None:
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
    snapshot1, snapshot2 = f"snap1-{suffix}", f"snap2-{suffix}"
    release1, release2 = f"release1-{suffix}", f"release2-{suffix}"
    old_object_id, new_object_id = f"old-{suffix}", f"new-{suffix}"
    releases = [release1, release2]
    snapshots = [snapshot1, snapshot2]
    objects = [old_object_id, new_object_id]

    try:
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            object_id=old_object_id,
            document_id=document_id,
            checksum="1" * 64,
            version="1.0",
            published_at="2026-09-16T15:00:00+00:00",
        )
        assert _active_release_ids(store) == {release1}

        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work2-{suffix}",
            snapshot_id=snapshot2,
            release_id=release2,
            object_id=new_object_id,
            document_id=document_id,
            checksum="2" * 64,
            version="2.0",
            published_at="2026-09-16T15:01:00+00:00",
        )

        active = store.active_publication_rows()
        assert _active_release_ids(store) == {release2}
        assert {str(row["knowledge_object"]["object_id"]) for row in active} == {new_object_id}

        restarted = PostgresCanonicalPublicationStore(store.config)
        assert _active_release_ids(restarted) == {release2}
    finally:
        _cleanup(store, release_ids=releases, snapshot_ids=snapshots, object_ids=objects)


def test_replay_of_superseded_release_cannot_reactivate_removed_object_ids() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1, snapshot2 = f"snap1-{suffix}", f"snap2-{suffix}"
    release1, release2 = f"release1-{suffix}", f"release2-{suffix}"
    old_object_id, new_object_id = f"old-{suffix}", f"new-{suffix}"

    try:
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            object_id=old_object_id,
            document_id=document_id,
            checksum="3" * 64,
            version="1.0",
            published_at="2026-09-16T15:00:00+00:00",
        )
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work2-{suffix}",
            snapshot_id=snapshot2,
            release_id=release2,
            object_id=new_object_id,
            document_id=document_id,
            checksum="4" * 64,
            version="2.0",
            published_at="2026-09-16T15:01:00+00:00",
        )

        with pytest.raises(CanonicalPublicationStoreError, match="stale_release_replay"):
            _publish(
                store,
                logical_document_id=logical_document_id,
                working_revision_id=f"work1-{suffix}",
                snapshot_id=snapshot1,
                release_id=release1,
                object_id=old_object_id,
                document_id=document_id,
                checksum="3" * 64,
                version="1.0",
                published_at="2026-09-16T15:00:00+00:00",
            )

        active = store.active_publication_rows()
        assert _active_release_ids(store) == {release2}
        assert {str(row["knowledge_object"]["object_id"]) for row in active} == {new_object_id}
    finally:
        _cleanup(
            store,
            release_ids=[release1, release2],
            snapshot_ids=[snapshot1, snapshot2],
            object_ids=[old_object_id, new_object_id],
        )


def test_multiple_active_predecessor_releases_fail_closed() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    other_logical_document_id = f"ld-other-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1, snapshot_other, snapshot2 = (
        f"snap1-{suffix}",
        f"snap-other-{suffix}",
        f"snap2-{suffix}",
    )
    release1, release_other, release2 = (
        f"release1-{suffix}",
        f"release-other-{suffix}",
        f"release2-{suffix}",
    )
    object1, object_other, object2 = f"obj1-{suffix}", f"obj-other-{suffix}", f"obj2-{suffix}"

    try:
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            object_id=object1,
            document_id=document_id,
            checksum="5" * 64,
            version="1.0",
            published_at="2026-09-16T15:00:00+00:00",
        )
        _publish(
            store,
            logical_document_id=other_logical_document_id,
            working_revision_id=f"work-other-{suffix}",
            snapshot_id=snapshot_other,
            release_id=release_other,
            object_id=object_other,
            document_id=f"doc-other-{suffix}",
            checksum="6" * 64,
            version="1.0",
            published_at="2026-09-16T15:00:30+00:00",
        )
        with store._connect() as con:
            con.execute(
                """
                UPDATE audit_events
                SET details=jsonb_set(details, '{logical_document_id}', to_jsonb(%s::text), true)
                WHERE entity_type='release'
                  AND entity_id=%s
                  AND event_type='release_published'
                """,
                (logical_document_id, release_other),
            )

        assert _active_release_ids(store) == {release1, release_other}
        with pytest.raises(
            CanonicalPublicationStoreError,
            match="canonical_active_predecessor_ambiguous",
        ):
            _publish(
                store,
                logical_document_id=logical_document_id,
                working_revision_id=f"work2-{suffix}",
                snapshot_id=snapshot2,
                release_id=release2,
                object_id=object2,
                document_id=document_id,
                checksum="7" * 64,
                version="2.0",
                published_at="2026-09-16T15:01:00+00:00",
            )
        assert _active_release_ids(store) == {release1, release_other}
    finally:
        _cleanup(
            store,
            release_ids=[release1, release_other, release2],
            snapshot_ids=[snapshot1, snapshot_other, snapshot2],
            object_ids=[object1, object_other, object2],
        )


def test_lifecycle_readmodel_derives_superseded_from_document_lineage() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1, snapshot2 = f"snap1-{suffix}", f"snap2-{suffix}"
    release1, release2 = f"release1-{suffix}", f"release2-{suffix}"
    object1, object2 = f"obj1-{suffix}", f"obj2-{suffix}"

    try:
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            object_id=object1,
            document_id=document_id,
            checksum="8" * 64,
            version="1.0",
            published_at="2026-09-16T15:00:00+00:00",
        )
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work2-{suffix}",
            snapshot_id=snapshot2,
            release_id=release2,
            object_id=object2,
            document_id=document_id,
            checksum="9" * 64,
            version="2.0",
            published_at="2026-09-16T15:01:00+00:00",
        )

        console = object.__new__(DurablePublicationConsole)
        console.canonical_publication_store = store
        assert console.document_release_serving_status(snapshot1) == {
            "release_status": "superseded",
            "serving_status": "inactive",
        }
        assert console.document_release_serving_status(snapshot2) == {
            "release_status": "published",
            "serving_status": "active",
        }
    finally:
        _cleanup(
            store,
            release_ids=[release1, release2],
            snapshot_ids=[snapshot1, snapshot2],
            object_ids=[object1, object2],
        )
