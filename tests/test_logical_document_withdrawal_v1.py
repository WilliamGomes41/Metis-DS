"""Release-control evidence for document-wide withdrawal.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag durable stale recovery
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
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for withdrawal PostgreSQL evidence")
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
    return stamp_canonical_hashes(
        {
            "object_id": object_id,
            "object_version": version,
            "document_id": document_id,
            "object_type": "explanation",
            "source": {"source_checksum": checksum},
            "content": {"raw_text": text, "clean_text": text},
            "governance": {"validation_status": "approved"},
            "provenance": {},
        }
    )


def _publish(
    store: PostgresCanonicalPublicationStore,
    *,
    logical_document_id: str,
    working_revision_id: str,
    snapshot_id: str,
    release_id: str,
    release_version: str,
    document_id: str,
    checksum: str,
    published_at: str,
    object_ids: list[str],
) -> None:
    store.persist_published_release(
        logical_document_id=logical_document_id,
        working_revision_id=working_revision_id,
        snapshot_id=snapshot_id,
        source_sha256=checksum,
        source_locator=f"g2://sha256/{checksum}/{release_version}.html",
        release_id=release_id,
        release_version=release_version,
        release_owner="withdrawal-test",
        published_at=published_at,
        objects=[
            _object(
                object_id=object_id,
                version=release_version,
                document_id=document_id,
                checksum=checksum,
                text=f"{release_version}:{object_id}",
            )
            for object_id in object_ids
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


def _active_object_ids(store: PostgresCanonicalPublicationStore) -> set[str]:
    return {str(row["knowledge_object"]["object_id"]) for row in store.active_publication_rows()}


def test_withdrawal_removes_complete_logical_document_without_fallback_or_replay() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1, snapshot2, snapshot3 = f"snap1-{suffix}", f"snap2-{suffix}", f"snap3-{suffix}"
    release1, release2, release3 = f"release1-{suffix}", f"release2-{suffix}", f"release3-{suffix}"
    object_a, object_b, object_c, object_d = (
        f"a-{suffix}",
        f"b-{suffix}",
        f"c-{suffix}",
        f"d-{suffix}",
    )

    try:
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            release_version=f"1.0-{suffix[:8]}",
            document_id=document_id,
            checksum="1" * 64,
            published_at="2026-09-16T18:00:00+00:00",
            object_ids=[object_a],
        )
        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work2-{suffix}",
            snapshot_id=snapshot2,
            release_id=release2,
            release_version=f"2.0-{suffix[:8]}",
            document_id=document_id,
            checksum="2" * 64,
            published_at="2026-09-16T18:01:00+00:00",
            object_ids=[object_b, object_c],
        )
        assert _active_object_ids(store) == {object_b, object_c}

        result = store.withdraw_logical_document(
            logical_document_id=logical_document_id,
            actor="governance-owner",
            reason="Source withdrawn pending correction",
            withdrawn_at="2026-09-16T18:02:00+00:00",
        )
        assert result["status"] == "PASS"
        assert result["release_id"] == release2
        assert result["withdrawn_active_objects"] == 2
        assert _active_object_ids(store) == set()

        with store._connect() as con:
            statuses = {
                str(row["release_id"]): str(row["status"])
                for row in con.execute(
                    "SELECT release_id,status FROM publication_releases WHERE release_id = ANY(%s)",
                    ([release1, release2],),
                ).fetchall()
            }
            registry = con.execute(
                "SELECT object_id,state,unpublish_reason FROM publication_registry WHERE release_id=%s ORDER BY object_id",
                (release2,),
            ).fetchall()
        assert statuses == {release1: "published", release2: "withdrawn"}
        assert {str(row["object_id"]) for row in registry} == {object_b, object_c}
        assert {str(row["state"]) for row in registry} == {"emergency_unpublished"}
        assert {str(row["unpublish_reason"]) for row in registry} == {"Source withdrawn pending correction"}

        console = object.__new__(DurablePublicationConsole)
        console.canonical_publication_store = store
        assert console.document_release_serving_status(snapshot1) == {
            "release_status": "superseded",
            "serving_status": "inactive",
        }
        assert console.document_release_serving_status(snapshot2) == {
            "release_status": "withdrawn",
            "serving_status": "inactive",
        }

        repeated = store.withdraw_logical_document(
            logical_document_id=logical_document_id,
            actor="governance-owner",
            reason="Source withdrawn pending correction",
            withdrawn_at="2026-09-16T18:02:30+00:00",
        )
        assert repeated["status"] == "PASS"
        assert repeated["release_id"] == release2
        assert repeated["withdrawn_active_objects"] == 0
        assert repeated["idempotent"] is True

        restarted = PostgresCanonicalPublicationStore(store.config)
        assert _active_object_ids(restarted) == set()

        with pytest.raises(CanonicalPublicationStoreError, match="stale_release_replay"):
            _publish(
                store,
                logical_document_id=logical_document_id,
                working_revision_id=f"work1-{suffix}",
                snapshot_id=snapshot1,
                release_id=release1,
                release_version=f"1.0-{suffix[:8]}",
                document_id=document_id,
                checksum="1" * 64,
                published_at="2026-09-16T18:00:00+00:00",
                object_ids=[object_a],
            )
        with pytest.raises(CanonicalPublicationStoreError, match="stale_release_replay"):
            _publish(
                store,
                logical_document_id=logical_document_id,
                working_revision_id=f"work2-{suffix}",
                snapshot_id=snapshot2,
                release_id=release2,
                release_version=f"2.0-{suffix[:8]}",
                document_id=document_id,
                checksum="2" * 64,
                published_at="2026-09-16T18:01:00+00:00",
                object_ids=[object_b, object_c],
            )
        assert _active_object_ids(store) == set()

        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work3-{suffix}",
            snapshot_id=snapshot3,
            release_id=release3,
            release_version=f"3.0-{suffix[:8]}",
            document_id=document_id,
            checksum="3" * 64,
            published_at="2026-09-16T18:03:00+00:00",
            object_ids=[object_d],
        )
        assert _active_object_ids(store) == {object_d}
    finally:
        _cleanup(
            store,
            release_ids=[release1, release2, release3],
            snapshot_ids=[snapshot1, snapshot2, snapshot3],
            object_ids=[object_a, object_b, object_c, object_d],
        )


def test_withdrawal_requires_explicit_document_actor_reason_and_unambiguous_active_release() -> None:
    store = _store()
    suffix = uuid.uuid4().hex
    logical_document_id = f"ld-{suffix}"
    document_id = f"doc-{suffix}"
    snapshot1, snapshot2 = f"snap1-{suffix}", f"snap2-{suffix}"
    release1, release2 = f"release1-{suffix}", f"release2-{suffix}"
    object1, object2 = f"obj1-{suffix}", f"obj2-{suffix}"

    try:
        for kwargs, error in [
            ({"logical_document_id": "", "actor": "owner", "reason": "reason"}, "canonical_logical_document_id_required"),
            ({"logical_document_id": logical_document_id, "actor": "", "reason": "reason"}, "canonical_withdrawal_actor_required"),
            ({"logical_document_id": logical_document_id, "actor": "owner", "reason": "  "}, "canonical_withdrawal_reason_required"),
        ]:
            with pytest.raises(CanonicalPublicationStoreError, match=error):
                store.withdraw_logical_document(
                    withdrawn_at="2026-09-16T18:02:00+00:00",
                    **kwargs,
                )

        _publish(
            store,
            logical_document_id=logical_document_id,
            working_revision_id=f"work1-{suffix}",
            snapshot_id=snapshot1,
            release_id=release1,
            release_version=f"1.0-{suffix[:8]}",
            document_id=document_id,
            checksum="4" * 64,
            published_at="2026-09-16T18:00:00+00:00",
            object_ids=[object1],
        )
        _publish(
            store,
            logical_document_id=f"other-{suffix}",
            working_revision_id=f"work-other-{suffix}",
            snapshot_id=snapshot2,
            release_id=release2,
            release_version=f"1.1-{suffix[:8]}",
            document_id=f"other-doc-{suffix}",
            checksum="5" * 64,
            published_at="2026-09-16T18:00:30+00:00",
            object_ids=[object2],
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
                (logical_document_id, release2),
            )

        with pytest.raises(CanonicalPublicationStoreError, match="canonical_active_predecessor_ambiguous"):
            store.withdraw_logical_document(
                logical_document_id=logical_document_id,
                actor="governance-owner",
                reason="Safety incident",
                withdrawn_at="2026-09-16T18:02:00+00:00",
            )
        assert _active_object_ids(store) == {object1, object2}
    finally:
        _cleanup(
            store,
            release_ids=[release1, release2],
            snapshot_ids=[snapshot1, snapshot2],
            object_ids=[object1, object2],
        )
