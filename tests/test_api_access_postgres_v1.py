import os
from pathlib import Path

import pytest

from src.api_access_v1 import PostgresApiAccessStore
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig

ROOT = Path(__file__).resolve().parents[1]


def _dsn() -> str:
    value = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for API access persistence evidence")
    return value


def _apply_api_access_migration(dsn: str) -> None:
    import psycopg

    sql = (ROOT / "db" / "migrations" / "010_api_access.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn) as con:
        with con.transaction():
            con.execute(sql)


def test_provisioned_credential_survives_fresh_store_and_plaintext_is_not_persisted():
    dsn = _dsn()
    _apply_api_access_migration(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    store = PostgresApiAccessStore(config)
    store.verify_schema()

    issued = store.provision_consumer(
        actor_id="test-publisher",
        tenant_name="API access persistence test",
        tenant_content_scope="RESOURCE_SET",
        tenant_document_ids=["doc-a", "doc-b"],
        tenant_scopes=["retrieve", "documents:read"],
        tenant_requests_per_minute=200,
        tenant_max_top_k=10,
        application_name="Test EPD",
        environment="TEST",
        application_content_scope="RESOURCE_SET",
        application_document_ids=["doc-a"],
        application_scopes=["retrieve"],
        application_requests_per_minute=100,
        application_max_top_k=5,
    )

    # Fresh process/store semantics: authorization is reconstructed from durable state.
    fresh = PostgresApiAccessStore(config)
    principal = fresh.authenticate(issued.credential)
    assert principal is not None
    assert principal.tenant_id == issued.tenant_id
    assert principal.application_id == issued.application_id
    assert principal.credential_id == issued.credential_id
    assert principal.scopes == frozenset({"retrieve"})
    assert principal.allowed_document_ids == frozenset({"doc-a"})

    import psycopg
    from psycopg.rows import dict_row

    try:
        with psycopg.connect(dsn, row_factory=dict_row) as con:
            credential = con.execute(
                "SELECT secret_sha256 FROM api_access.credentials WHERE credential_id=%s",
                (issued.credential_id,),
            ).fetchone()
            audit = con.execute(
                "SELECT details::text AS details FROM api_access.audit_events WHERE tenant_id=%s",
                (issued.tenant_id,),
            ).fetchall()
            assert credential is not None
            assert len(str(credential["secret_sha256"])) == 64
            assert issued.credential not in str(credential["secret_sha256"])
            assert all(issued.credential not in str(row["details"]) for row in audit)
    finally:
        with psycopg.connect(dsn) as con:
            with con.transaction():
                con.execute(
                    "DELETE FROM api_access.audit_events WHERE tenant_id=%s",
                    (issued.tenant_id,),
                )
                con.execute(
                    "DELETE FROM api_access.credentials WHERE application_id=%s",
                    (issued.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.application_resources WHERE application_id=%s",
                    (issued.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.application_scopes WHERE application_id=%s",
                    (issued.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.applications WHERE application_id=%s",
                    (issued.application_id,),
                )
                con.execute(
                    "DELETE FROM api_access.tenant_resources WHERE tenant_id=%s",
                    (issued.tenant_id,),
                )
                con.execute(
                    "DELETE FROM api_access.tenant_scopes WHERE tenant_id=%s",
                    (issued.tenant_id,),
                )
                con.execute(
                    "DELETE FROM api_access.tenants WHERE tenant_id=%s",
                    (issued.tenant_id,),
                )



def test_authentication_rechecks_current_credential_application_and_tenant_state():
    dsn = _dsn()
    _apply_api_access_migration(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    store = PostgresApiAccessStore(config)

    issued = store.provision_consumer(
        actor_id="test-publisher-state",
        tenant_name="API access current-state test",
        tenant_content_scope="ALL_PUBLISHED",
        tenant_document_ids=[],
        tenant_scopes=["retrieve"],
        tenant_requests_per_minute=100,
        tenant_max_top_k=5,
        application_name="State reader",
        environment="TEST",
        application_content_scope="ALL_PUBLISHED",
        application_document_ids=[],
        application_scopes=["retrieve"],
        application_requests_per_minute=100,
        application_max_top_k=5,
    )

    import psycopg

    try:
        assert store.authenticate(issued.credential) is not None
        with psycopg.connect(dsn) as con:
            with con.transaction():
                con.execute(
                    "UPDATE api_access.credentials SET state='REVOKED', revoked_at=now() WHERE credential_id=%s",
                    (issued.credential_id,),
                )
        assert store.authenticate(issued.credential) is None

        with psycopg.connect(dsn) as con:
            with con.transaction():
                con.execute(
                    "UPDATE api_access.credentials SET state='ACTIVE', revoked_at=NULL WHERE credential_id=%s",
                    (issued.credential_id,),
                )
                con.execute(
                    "UPDATE api_access.applications SET state='SUSPENDED' WHERE application_id=%s",
                    (issued.application_id,),
                )
        assert store.authenticate(issued.credential) is None

        with psycopg.connect(dsn) as con:
            with con.transaction():
                con.execute(
                    "UPDATE api_access.applications SET state='ACTIVE' WHERE application_id=%s",
                    (issued.application_id,),
                )
                con.execute(
                    "UPDATE api_access.tenants SET state='SUSPENDED' WHERE tenant_id=%s",
                    (issued.tenant_id,),
                )
        assert store.authenticate(issued.credential) is None
    finally:
        with psycopg.connect(dsn) as con:
            with con.transaction():
                con.execute("DELETE FROM api_access.audit_events WHERE tenant_id=%s", (issued.tenant_id,))
                con.execute("DELETE FROM api_access.credentials WHERE application_id=%s", (issued.application_id,))
                con.execute("DELETE FROM api_access.application_resources WHERE application_id=%s", (issued.application_id,))
                con.execute("DELETE FROM api_access.application_scopes WHERE application_id=%s", (issued.application_id,))
                con.execute("DELETE FROM api_access.applications WHERE application_id=%s", (issued.application_id,))
                con.execute("DELETE FROM api_access.tenant_resources WHERE tenant_id=%s", (issued.tenant_id,))
                con.execute("DELETE FROM api_access.tenant_scopes WHERE tenant_id=%s", (issued.tenant_id,))
                con.execute("DELETE FROM api_access.tenants WHERE tenant_id=%s", (issued.tenant_id,))


def test_provisioning_and_audit_roll_back_together_on_audit_failure():
    dsn = _dsn()
    _apply_api_access_migration(dsn)
    config = PostgresCanonicalConfig(dsn=dsn)
    store = PostgresApiAccessStore(config)
    tenant_name = "API access rollback test"

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    store._audit = fail_audit

    from src.api_access_v1 import ApiAccessStoreError

    with pytest.raises(ApiAccessStoreError, match="api_access_provision_failed"):
        store.provision_consumer(
            actor_id="test-publisher-rollback",
            tenant_name=tenant_name,
            tenant_content_scope="ALL_PUBLISHED",
            tenant_document_ids=[],
            tenant_scopes=["retrieve"],
            tenant_requests_per_minute=100,
            tenant_max_top_k=5,
            application_name="Rollback reader",
            environment="TEST",
            application_content_scope="ALL_PUBLISHED",
            application_document_ids=[],
            application_scopes=["retrieve"],
            application_requests_per_minute=100,
            application_max_top_k=5,
        )

    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, row_factory=dict_row) as con:
        row = con.execute(
            "SELECT tenant_id FROM api_access.tenants WHERE name=%s",
            (tenant_name,),
        ).fetchone()
    assert row is None
