# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
# release-control-evidence: opslag concurrent stale

import os
from pathlib import Path

import pytest

from src.api_access_v1 import (
    ApiAccessConflict,
    ApiAccessError,
    ApiAccessStoreError,
    PostgresApiAccessStore,
)
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig

ROOT = Path(__file__).resolve().parents[1]


def _dsn() -> str:
    value = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for API access lifecycle evidence")
    return value


def _store() -> PostgresApiAccessStore:
    import psycopg

    dsn = _dsn()
    with psycopg.connect(dsn) as con:
        with con.transaction():
            con.execute((ROOT / "db" / "migrations" / "010_api_access.sql").read_text(encoding="utf-8"))
    return PostgresApiAccessStore(PostgresCanonicalConfig(dsn=dsn))


def _provision(
    store: PostgresApiAccessStore,
    *,
    name: str,
    tenant_docs=("doc-a", "doc-b"),
    app_docs=("doc-a",),
):
    return store.provision_consumer(
        actor_id="publisher-test",
        tenant_name=name,
        tenant_content_scope="RESOURCE_SET",
        tenant_document_ids=tenant_docs,
        tenant_scopes=["retrieve", "documents:read", "knowledge:read"],
        tenant_requests_per_minute=200,
        tenant_max_top_k=10,
        application_name=f"{name} app",
        environment="TEST",
        application_content_scope="RESOURCE_SET",
        application_document_ids=app_docs,
        application_scopes=["retrieve", "documents:read"],
        application_requests_per_minute=100,
        application_max_top_k=5,
    )


def _cleanup(*issued) -> None:
    import psycopg

    dsn = _dsn()
    with psycopg.connect(dsn) as con:
        with con.transaction():
            for item in issued:
                con.execute("DELETE FROM api_access.audit_events WHERE tenant_id=%s", (item.tenant_id,))
                con.execute(
                    "DELETE FROM api_access.credentials WHERE application_id=%s",
                    (item.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.application_resources WHERE application_id=%s",
                    (item.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.application_scopes WHERE application_id=%s",
                    (item.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.applications WHERE application_id=%s",
                    (item.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.tenant_resources WHERE tenant_id=%s",
                    (item.tenant_id,),
                )
                con.execute(
                    "DELETE FROM api_access.tenant_scopes WHERE tenant_id=%s",
                    (item.tenant_id,),
                )
                con.execute("DELETE FROM api_access.tenants WHERE tenant_id=%s", (item.tenant_id,))


def test_application_grant_changes_immediately_and_stale_writer_gets_conflict():
    store = _store()
    issued = _provision(store, name="PR2 grant test")
    try:
        before = store.authenticate(issued.credential)
        assert before is not None
        assert before.allowed_document_ids == frozenset({"doc-a"})

        changed = store.set_application_grant(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            content_scope="RESOURCE_SET",
            document_ids=["doc-b"],
            scopes=["retrieve"],
            requests_per_minute=80,
            max_top_k=4,
        )
        assert changed.changed is True
        assert changed.policy_version == 2

        after = store.authenticate(issued.credential)
        assert after is not None
        assert after.allowed_document_ids == frozenset({"doc-b"})
        assert after.scopes == frozenset({"retrieve"})
        assert after.requests_per_minute == 80
        assert after.max_top_k == 4

        with pytest.raises(ApiAccessConflict, match="policy_version_mismatch"):
            store.set_application_grant(
                actor_id="publisher-b",
                tenant_id=issued.tenant_id,
                application_id=issued.application_id,
                expected_version=1,
                content_scope="RESOURCE_SET",
                document_ids=["doc-a"],
                scopes=["retrieve"],
                requests_per_minute=80,
                max_top_k=4,
            )
    finally:
        _cleanup(issued)


def test_tenant_entitlement_cannot_shrink_below_existing_application_grant():
    store = _store()
    issued = _provision(store, name="PR2 tenant boundary")
    try:
        with pytest.raises(ApiAccessError, match="application_resource_exceeds_tenant_entitlement"):
            store.set_tenant_entitlement(
                actor_id="publisher-a",
                tenant_id=issued.tenant_id,
                expected_version=1,
                content_scope="RESOURCE_SET",
                document_ids=["doc-b"],
                scopes=["retrieve", "documents:read", "knowledge:read"],
                requests_per_minute=200,
                max_top_k=10,
            )

        principal = store.authenticate(issued.credential)
        assert principal is not None
        assert principal.allowed_document_ids == frozenset({"doc-a"})
    finally:
        _cleanup(issued)


def test_suspend_reactivate_and_retire_application_are_enforced_on_next_authentication():
    store = _store()
    issued = _provision(store, name="PR2 app lifecycle")
    try:
        suspended = store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            target_state="SUSPENDED",
        )
        assert suspended.policy_version == 2
        assert store.authenticate(issued.credential) is None

        active = store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=2,
            target_state="ACTIVE",
        )
        assert active.policy_version == 3
        assert store.authenticate(issued.credential) is not None

        retired = store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=3,
            target_state="RETIRED",
        )
        assert retired.policy_version == 4
        assert store.authenticate(issued.credential) is None

        with pytest.raises(ApiAccessError, match="application_retired"):
            store.set_application_state(
                actor_id="publisher-a",
                tenant_id=issued.tenant_id,
                application_id=issued.application_id,
                expected_version=4,
                target_state="ACTIVE",
            )
    finally:
        _cleanup(issued)


def test_tenant_suspend_denies_all_apps_and_reactivate_restores_active_child():
    store = _store()
    issued = _provision(store, name="PR2 tenant lifecycle")
    try:
        store.set_tenant_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=1,
            target_state="SUSPENDED",
        )
        assert store.authenticate(issued.credential) is None

        store.set_tenant_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=2,
            target_state="ACTIVE",
        )
        assert store.authenticate(issued.credential) is not None
    finally:
        _cleanup(issued)


def test_rotation_allows_overlap_then_revoke_is_immediate_and_idempotent():
    store = _store()
    issued = _provision(store, name="PR2 rotation")
    try:
        second = store.issue_credential(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
        )
        assert second.credential_id != issued.credential_id
        assert store.authenticate(issued.credential) is not None
        assert store.authenticate(second.credential) is not None

        first_revoke = store.revoke_credential(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            credential_id=issued.credential_id,
        )
        assert first_revoke.changed is True
        assert store.authenticate(issued.credential) is None
        assert store.authenticate(second.credential) is not None

        second_revoke = store.revoke_credential(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            credential_id=issued.credential_id,
        )
        assert second_revoke.changed is False

        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(_dsn(), row_factory=dict_row) as con:
            rows = con.execute(
                """
                SELECT event_type,count(*) AS n
                FROM api_access.audit_events
                WHERE tenant_id=%s AND credential_id=%s
                GROUP BY event_type
                """,
                (issued.tenant_id, issued.credential_id),
            ).fetchall()
        counts = {row["event_type"]: int(row["n"]) for row in rows}
        assert counts["credential.revoked"] == 1
    finally:
        _cleanup(issued)


def test_cross_tenant_application_and_credential_mutation_is_rejected():
    store = _store()
    left = _provision(store, name="PR2 left")
    right = _provision(store, name="PR2 right")
    try:
        with pytest.raises(ApiAccessError, match="application_not_found"):
            store.set_application_grant(
                actor_id="publisher-a",
                tenant_id=left.tenant_id,
                application_id=right.application_id,
                expected_version=1,
                content_scope="RESOURCE_SET",
                document_ids=["doc-a"],
                scopes=["retrieve"],
                requests_per_minute=50,
                max_top_k=3,
            )

        with pytest.raises(ApiAccessError, match="application_not_found"):
            store.revoke_credential(
                actor_id="publisher-a",
                tenant_id=left.tenant_id,
                application_id=right.application_id,
                credential_id=right.credential_id,
            )
    finally:
        _cleanup(left, right)


def test_policy_mutation_and_audit_roll_back_together():
    store = _store()
    issued = _provision(store, name="PR2 audit rollback")
    try:
        original_audit = store._audit

        def fail_audit(*args, **kwargs):
            raise RuntimeError("synthetic audit failure")

        store._audit = fail_audit
        with pytest.raises(ApiAccessStoreError, match="api_access_application_policy_update_failed"):
            store.set_application_grant(
                actor_id="publisher-a",
                tenant_id=issued.tenant_id,
                application_id=issued.application_id,
                expected_version=1,
                content_scope="RESOURCE_SET",
                document_ids=["doc-b"],
                scopes=["retrieve"],
                requests_per_minute=50,
                max_top_k=3,
            )
        store._audit = original_audit

        principal = store.authenticate(issued.credential)
        assert principal is not None
        assert principal.allowed_document_ids == frozenset({"doc-a"})

        rows = store.list_consumers()
        row = next(item for item in rows if item["application_id"] == issued.application_id)
        assert int(row["application_policy_version"]) == 1
    finally:
        _cleanup(issued)



def test_same_running_product_api_observes_policy_and_lifecycle_changes_without_restart(tmp_path):
    from fastapi.testclient import TestClient

    from src.product_api_v1 import ProductPaths, create_product_app
    from src.usage_ledger_v1 import UsageLedger

    fixture_doc = "vvn-osteoporose-fractuurpreventie-2024"
    store = _store()
    issued = _provision(
        store,
        name="PR2 running API",
        tenant_docs=(fixture_doc, "not-present-document"),
        app_docs=(fixture_doc,),
    )
    try:
        defaults = ProductPaths.defaults(ROOT)
        paths = ProductPaths(
            real_records=defaults.real_records,
            fixture_records=defaults.fixture_records,
            real_published=defaults.real_published,
            lexical_config=defaults.lexical_config,
            vector_config=defaults.vector_config,
            hybrid_config=defaults.hybrid_config,
            tenant_config=tmp_path / "unused.json",
            usage_db=tmp_path / "usage.sqlite",
        )
        app = create_product_app(
            "fixture",
            paths=paths,
            api_access_store=store,
            api_access_mode="postgres",
            usage_ledger=UsageLedger(paths.usage_db),
            allow_fixture=True,
        )
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {issued.credential}"}

        visible = client.get("/v1/documents", headers=headers)
        assert visible.status_code == 200
        assert [row["document_id"] for row in visible.json()["documents"]] == [fixture_doc]

        grant = store.set_application_grant(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            content_scope="RESOURCE_SET",
            document_ids=["not-present-document"],
            scopes=["retrieve", "documents:read"],
            requests_per_minute=100,
            max_top_k=5,
        )
        assert grant.policy_version == 2

        changed = client.get("/v1/documents", headers=headers)
        assert changed.status_code == 200
        assert changed.json()["documents"] == []

        store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=2,
            target_state="SUSPENDED",
        )
        denied = client.get("/v1/documents", headers=headers)
        assert denied.status_code == 401

        store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=3,
            target_state="ACTIVE",
        )
        restored = client.get("/v1/documents", headers=headers)
        assert restored.status_code == 200
        assert restored.json()["documents"] == []

        rotated = store.issue_credential(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
        )
        rotated_headers = {"Authorization": f"Bearer {rotated.credential}"}
        assert client.get("/v1/documents", headers=rotated_headers).status_code == 200

        store.revoke_credential(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            credential_id=issued.credential_id,
        )
        assert client.get("/v1/documents", headers=headers).status_code == 401
        assert client.get("/v1/documents", headers=rotated_headers).status_code == 200
    finally:
        _cleanup(issued)



def test_issue_credential_requires_active_tenant_and_application():
    store = _store()
    issued = _provision(store, name="PR2 issue state gate")
    try:
        store.set_tenant_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=1,
            target_state="SUSPENDED",
        )
        with pytest.raises(ApiAccessError, match="tenant_not_active"):
            store.issue_credential(
                actor_id="publisher-a",
                tenant_id=issued.tenant_id,
                application_id=issued.application_id,
            )

        store.set_tenant_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=2,
            target_state="ACTIVE",
        )
        store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            target_state="SUSPENDED",
        )
        with pytest.raises(ApiAccessError, match="application_not_active"):
            store.issue_credential(
                actor_id="publisher-a",
                tenant_id=issued.tenant_id,
                application_id=issued.application_id,
            )
    finally:
        _cleanup(issued)


def test_duplicate_suspend_is_noop_and_does_not_duplicate_audit_transition():
    store = _store()
    issued = _provision(store, name="PR2 idempotent suspend")
    try:
        first = store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            target_state="SUSPENDED",
        )
        assert first.changed is True
        second = store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=2,
            target_state="SUSPENDED",
        )
        assert second.changed is False
        assert second.policy_version == 2

        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(_dsn(), row_factory=dict_row) as con:
            row = con.execute(
                """
                SELECT count(*) AS n
                FROM api_access.audit_events
                WHERE tenant_id=%s
                  AND application_id=%s
                  AND event_type='application.suspended'
                """,
                (issued.tenant_id, issued.application_id),
            ).fetchone()
        assert int(row["n"]) == 1
    finally:
        _cleanup(issued)



def test_retired_application_grant_can_be_narrowed_before_parent_entitlement_shrinks():
    store = _store()
    issued = _provision(
        store,
        name="PR2 retired grant shrink",
        tenant_docs=("doc-a", "doc-b"),
        app_docs=("doc-a", "doc-b"),
    )
    try:
        store.set_application_state(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=1,
            target_state="RETIRED",
        )

        narrowed = store.set_application_grant(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            application_id=issued.application_id,
            expected_version=2,
            content_scope="RESOURCE_SET",
            document_ids=["doc-b"],
            scopes=["retrieve"],
            requests_per_minute=50,
            max_top_k=3,
        )
        assert narrowed.changed is True
        assert narrowed.policy_version == 3

        tenant = store.set_tenant_entitlement(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=1,
            content_scope="RESOURCE_SET",
            document_ids=["doc-b"],
            scopes=["retrieve"],
            requests_per_minute=100,
            max_top_k=5,
        )
        assert tenant.changed is True
        assert tenant.policy_version == 2
        assert store.authenticate(issued.credential) is None
    finally:
        _cleanup(issued)



def test_tenant_policy_stale_version_is_rejected_without_overwrite():
    store = _store()
    issued = _provision(store, name="PR2 tenant stale version")
    try:
        first = store.set_tenant_entitlement(
            actor_id="publisher-a",
            tenant_id=issued.tenant_id,
            expected_version=1,
            content_scope="RESOURCE_SET",
            document_ids=["doc-a", "doc-b", "doc-c"],
            scopes=["retrieve", "documents:read", "knowledge:read"],
            requests_per_minute=200,
            max_top_k=10,
        )
        assert first.policy_version == 2

        with pytest.raises(ApiAccessConflict, match="policy_version_mismatch"):
            store.set_tenant_entitlement(
                actor_id="publisher-b",
                tenant_id=issued.tenant_id,
                expected_version=1,
                content_scope="RESOURCE_SET",
                document_ids=["doc-a", "doc-b"],
                scopes=["retrieve", "documents:read", "knowledge:read"],
                requests_per_minute=200,
                max_top_k=10,
            )

        rows = store.list_consumers()
        row = next(item for item in rows if item["tenant_id"] == issued.tenant_id)
        assert int(row["tenant_policy_version"]) == 2
        assert row["tenant_document_ids"] == ["doc-a", "doc-b", "doc-c"]
    finally:
        _cleanup(issued)
