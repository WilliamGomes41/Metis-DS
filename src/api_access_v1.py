"""Durable API access domain and PostgreSQL store.

This context owns customer/application access and credentials only. It never
publishes knowledge. publication_registry remains the sole serving authority.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from azure.identity import DefaultAzureCredential

from src.canonical_publication_postgres_v1 import (
    AZURE_POSTGRES_SCOPE,
    PostgresCanonicalConfig,
)

VALID_SCOPES = frozenset(
    {
        "retrieve",
        "knowledge:read",
        "documents:read",
        "updates:read",
        "usage:read",
    }
)
VALID_CONTENT_SCOPES = frozenset({"ALL_PUBLISHED", "RESOURCE_SET"})
REQUIRED_TABLES = frozenset(
    {
        "tenants",
        "tenant_scopes",
        "tenant_resources",
        "applications",
        "application_scopes",
        "application_resources",
        "credentials",
        "audit_events",
    }
)


class ApiAccessError(RuntimeError):
    """Domain validation failure for API access commands."""


class ApiAccessStoreError(RuntimeError):
    """Fail-closed durable API access store failure."""


@dataclass(frozen=True)
class ResourceRef:
    resource_type: str
    resource_id: str

    @classmethod
    def document(cls, document_id: str) -> "ResourceRef":
        value = str(document_id or "").strip()
        if not value:
            raise ApiAccessError("resource_id_missing")
        return cls(resource_type="DOCUMENT", resource_id=value)


@dataclass(frozen=True)
class ApiAccessPrincipal:
    tenant_id: str
    application_id: str
    credential_id: str
    scopes: frozenset[str]
    allowed_document_ids: frozenset[str]
    requests_per_minute: int
    max_top_k: int
    allowed_topics: frozenset[str] = frozenset({"*"})

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def allows_document(self, document_id: str | None) -> bool:
        if not document_id:
            return False
        return "*" in self.allowed_document_ids or document_id in self.allowed_document_ids

    def allows_topics(self, _topics: list[str] | tuple[str, ...] | None) -> bool:
        # Topic is retrieval metadata, not a v1 commercial entitlement boundary.
        return True


@dataclass(frozen=True)
class ProvisionedConsumer:
    tenant_id: str
    application_id: str
    credential_id: str
    api_key: str


def hash_api_key(value: str) -> str:
    # High-entropy random API key lookup digest, not a password KDF.
    # codeql[py/weak-sensitive-data-hashing]
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _clean_text(value: str, *, code: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ApiAccessError(code)
    return cleaned


def _scope_set(values: Iterable[str]) -> frozenset[str]:
    scopes = frozenset(str(value or "").strip() for value in values if str(value or "").strip())
    invalid = sorted(scopes - VALID_SCOPES)
    if invalid:
        raise ApiAccessError("unsupported_scope:" + ",".join(invalid))
    if not scopes:
        raise ApiAccessError("scope_required")
    return scopes


def _document_set(values: Iterable[str]) -> frozenset[str]:
    docs = frozenset(str(value or "").strip() for value in values if str(value or "").strip())
    if "*" in docs:
        raise ApiAccessError("wildcard_resource_not_allowed")
    return docs


def validate_content_scope(mode: str, document_ids: Iterable[str]) -> tuple[str, frozenset[str]]:
    normalized = str(mode or "").strip().upper()
    if normalized not in VALID_CONTENT_SCOPES:
        raise ApiAccessError("unsupported_content_scope")
    docs = _document_set(document_ids)
    if normalized == "ALL_PUBLISHED" and docs:
        raise ApiAccessError("all_published_must_not_list_resources")
    if normalized == "RESOURCE_SET" and not docs:
        raise ApiAccessError("resource_set_requires_document")
    return normalized, docs


def validate_grant_subset(
    *,
    tenant_content_scope: str,
    tenant_document_ids: frozenset[str],
    tenant_scopes: frozenset[str],
    tenant_requests_per_minute: int,
    tenant_max_top_k: int,
    application_content_scope: str,
    application_document_ids: frozenset[str],
    application_scopes: frozenset[str],
    application_requests_per_minute: int,
    application_max_top_k: int,
) -> None:
    if not application_scopes.issubset(tenant_scopes):
        raise ApiAccessError("application_scope_exceeds_tenant_entitlement")
    if application_requests_per_minute > tenant_requests_per_minute:
        raise ApiAccessError("application_rate_limit_exceeds_tenant_entitlement")
    if application_max_top_k > tenant_max_top_k:
        raise ApiAccessError("application_top_k_exceeds_tenant_entitlement")
    if tenant_content_scope == "RESOURCE_SET" and application_content_scope == "RESOURCE_SET":
        if not application_document_ids.issubset(tenant_document_ids):
            raise ApiAccessError("application_resource_exceeds_tenant_entitlement")


def effective_document_ids(
    *,
    tenant_content_scope: str,
    tenant_document_ids: frozenset[str],
    application_content_scope: str,
    application_document_ids: frozenset[str],
) -> frozenset[str]:
    if tenant_content_scope == "ALL_PUBLISHED" and application_content_scope == "ALL_PUBLISHED":
        return frozenset({"*"})
    if tenant_content_scope == "ALL_PUBLISHED":
        return application_document_ids
    if application_content_scope == "ALL_PUBLISHED":
        return tenant_document_ids
    return tenant_document_ids.intersection(application_document_ids)


class PostgresApiAccessStore:
    """Transactional API access authority.

    Every authenticate call reads current durable state. There is deliberately no
    JSON fallback or authorization cache in PostgreSQL mode.
    """

    def __init__(
        self,
        config: PostgresCanonicalConfig | None = None,
        *,
        credential: Any | None = None,
        connection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._credential = credential
        self.config = config or PostgresCanonicalConfig.from_environ()
        if connection_factory is None:
            try:
                self.config.validate()
            except Exception as exc:
                raise ApiAccessStoreError("api_access_postgres_configuration_incomplete") from exc

    def _connect(self) -> Any:
        if self._connection_factory is not None:
            return self._connection_factory()
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - deployment dependency guard
            raise ApiAccessStoreError("psycopg_unavailable") from exc
        try:
            if self.config.dsn:
                return psycopg.connect(
                    self.config.dsn,
                    row_factory=dict_row,
                    connect_timeout=10,
                )
            credential = self._credential or DefaultAzureCredential()
            token = credential.get_token(AZURE_POSTGRES_SCOPE).token
            return psycopg.connect(
                host=self.config.host,
                dbname=self.config.database,
                user=self.config.user,
                password=token,
                sslmode="require",
                connect_timeout=10,
                row_factory=dict_row,
            )
        except Exception as exc:
            raise ApiAccessStoreError("api_access_postgres_unavailable") from exc

    def verify_schema(self) -> None:
        try:
            with self._connect() as con:
                rows = con.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'api_access'
                    """
                ).fetchall()
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_schema_check_failed") from exc
        found = {str(row["table_name"]) for row in rows}
        missing = sorted(REQUIRED_TABLES - found)
        if missing:
            raise ApiAccessStoreError("api_access_schema_missing:" + ",".join(missing))

    @staticmethod
    def _audit(
        con: Any,
        *,
        event_type: str,
        actor_id: str,
        tenant_id: str,
        application_id: str | None = None,
        credential_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        con.execute(
            """
            INSERT INTO api_access.audit_events(
                event_id,event_type,actor_id,tenant_id,application_id,credential_id,details
            ) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
            """,
            (
                "aae_" + uuid.uuid4().hex,
                event_type,
                actor_id,
                tenant_id,
                application_id,
                credential_id,
                json.dumps(details or {}, ensure_ascii=False, sort_keys=True),
            ),
        )

    def provision_consumer(
        self,
        *,
        actor_id: str,
        tenant_name: str,
        tenant_content_scope: str,
        tenant_document_ids: Iterable[str],
        tenant_scopes: Iterable[str],
        tenant_requests_per_minute: int,
        tenant_max_top_k: int,
        application_name: str,
        environment: str,
        application_content_scope: str,
        application_document_ids: Iterable[str],
        application_scopes: Iterable[str],
        application_requests_per_minute: int,
        application_max_top_k: int,
    ) -> ProvisionedConsumer:
        actor = _clean_text(actor_id, code="actor_id_missing")
        customer_name = _clean_text(tenant_name, code="tenant_name_missing")
        app_name = _clean_text(application_name, code="application_name_missing")
        app_environment = _clean_text(environment, code="application_environment_missing").upper()

        tenant_mode, tenant_docs = validate_content_scope(
            tenant_content_scope,
            tenant_document_ids,
        )
        app_mode, app_docs = validate_content_scope(
            application_content_scope,
            application_document_ids,
        )
        tenant_scope_set = _scope_set(tenant_scopes)
        app_scope_set = _scope_set(application_scopes)

        tenant_rpm = int(tenant_requests_per_minute)
        tenant_top_k = int(tenant_max_top_k)
        app_rpm = int(application_requests_per_minute)
        app_top_k = int(application_max_top_k)
        if min(tenant_rpm, tenant_top_k, app_rpm, app_top_k) < 1:
            raise ApiAccessError("access_limit_must_be_positive")

        validate_grant_subset(
            tenant_content_scope=tenant_mode,
            tenant_document_ids=tenant_docs,
            tenant_scopes=tenant_scope_set,
            tenant_requests_per_minute=tenant_rpm,
            tenant_max_top_k=tenant_top_k,
            application_content_scope=app_mode,
            application_document_ids=app_docs,
            application_scopes=app_scope_set,
            application_requests_per_minute=app_rpm,
            application_max_top_k=app_top_k,
        )

        tenant_id = "ten_" + uuid.uuid4().hex
        application_id = "app_" + uuid.uuid4().hex
        credential_id = "cred_" + uuid.uuid4().hex
        api_key = f"metis_live_{credential_id}.{secrets.token_urlsafe(32)}"
        secret_sha256 = hash_api_key(api_key)

        try:
            with self._connect() as con:
                with con.transaction():
                    con.execute(
                        """
                        INSERT INTO api_access.tenants(
                            tenant_id,name,state,content_scope,requests_per_minute,max_top_k
                        ) VALUES (%s,%s,'ACTIVE',%s,%s,%s)
                        """,
                        (tenant_id, customer_name, tenant_mode, tenant_rpm, tenant_top_k),
                    )
                    for scope in sorted(tenant_scope_set):
                        con.execute(
                            "INSERT INTO api_access.tenant_scopes(tenant_id,scope) VALUES (%s,%s)",
                            (tenant_id, scope),
                        )
                    for document_id in sorted(tenant_docs):
                        con.execute(
                            """
                            INSERT INTO api_access.tenant_resources(tenant_id,resource_type,resource_id)
                            VALUES (%s,'DOCUMENT',%s)
                            """,
                            (tenant_id, document_id),
                        )
                    con.execute(
                        """
                        INSERT INTO api_access.applications(
                            application_id,tenant_id,name,environment,state,content_scope,
                            requests_per_minute,max_top_k
                        ) VALUES (%s,%s,%s,%s,'ACTIVE',%s,%s,%s)
                        """,
                        (
                            application_id,
                            tenant_id,
                            app_name,
                            app_environment,
                            app_mode,
                            app_rpm,
                            app_top_k,
                        ),
                    )
                    for scope in sorted(app_scope_set):
                        con.execute(
                            """
                            INSERT INTO api_access.application_scopes(application_id,scope)
                            VALUES (%s,%s)
                            """,
                            (application_id, scope),
                        )
                    for document_id in sorted(app_docs):
                        con.execute(
                            """
                            INSERT INTO api_access.application_resources(
                                application_id,resource_type,resource_id
                            ) VALUES (%s,'DOCUMENT',%s)
                            """,
                            (application_id, document_id),
                        )
                    con.execute(
                        """
                        INSERT INTO api_access.credentials(
                            credential_id,application_id,secret_sha256,state
                        ) VALUES (%s,%s,%s,'ACTIVE')
                        """,
                        (credential_id, application_id, secret_sha256),
                    )
                    self._audit(
                        con,
                        event_type="tenant.created",
                        actor_id=actor,
                        tenant_id=tenant_id,
                        details={
                            "name": customer_name,
                            "content_scope": tenant_mode,
                            "scopes": sorted(tenant_scope_set),
                            "resource_count": len(tenant_docs),
                        },
                    )
                    self._audit(
                        con,
                        event_type="application.created",
                        actor_id=actor,
                        tenant_id=tenant_id,
                        application_id=application_id,
                        details={
                            "name": app_name,
                            "environment": app_environment,
                            "content_scope": app_mode,
                            "scopes": sorted(app_scope_set),
                            "resource_count": len(app_docs),
                        },
                    )
                    self._audit(
                        con,
                        event_type="credential.issued",
                        actor_id=actor,
                        tenant_id=tenant_id,
                        application_id=application_id,
                        credential_id=credential_id,
                        details={},
                    )
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_provision_failed") from exc

        # Plaintext deliberately exists only in this command result.
        return ProvisionedConsumer(
            tenant_id=tenant_id,
            application_id=application_id,
            credential_id=credential_id,
            api_key=api_key,
        )

    def authenticate(self, api_key: str) -> ApiAccessPrincipal | None:
        supplied = str(api_key or "")
        if not supplied:
            return None
        digest = hash_api_key(supplied)
        try:
            with self._connect() as con:
                row = con.execute(
                    """
                    SELECT
                        c.credential_id,
                        c.state AS credential_state,
                        a.application_id,
                        a.state AS application_state,
                        a.content_scope AS application_content_scope,
                        a.requests_per_minute AS application_rpm,
                        a.max_top_k AS application_max_top_k,
                        t.tenant_id,
                        t.state AS tenant_state,
                        t.content_scope AS tenant_content_scope,
                        t.requests_per_minute AS tenant_rpm,
                        t.max_top_k AS tenant_max_top_k
                    FROM api_access.credentials c
                    JOIN api_access.applications a ON a.application_id=c.application_id
                    JOIN api_access.tenants t ON t.tenant_id=a.tenant_id
                    WHERE c.secret_sha256=%s
                    """,
                    (digest,),
                ).fetchone()
                if row is None:
                    return None
                if (
                    row["credential_state"] != "ACTIVE"
                    or row["application_state"] != "ACTIVE"
                    or row["tenant_state"] != "ACTIVE"
                ):
                    return None
                tenant_scopes = {
                    str(item["scope"])
                    for item in con.execute(
                        "SELECT scope FROM api_access.tenant_scopes WHERE tenant_id=%s",
                        (row["tenant_id"],),
                    ).fetchall()
                }
                app_scopes = {
                    str(item["scope"])
                    for item in con.execute(
                        "SELECT scope FROM api_access.application_scopes WHERE application_id=%s",
                        (row["application_id"],),
                    ).fetchall()
                }
                tenant_docs = frozenset(
                    str(item["resource_id"])
                    for item in con.execute(
                        """
                        SELECT resource_id FROM api_access.tenant_resources
                        WHERE tenant_id=%s AND resource_type='DOCUMENT'
                        """,
                        (row["tenant_id"],),
                    ).fetchall()
                )
                app_docs = frozenset(
                    str(item["resource_id"])
                    for item in con.execute(
                        """
                        SELECT resource_id FROM api_access.application_resources
                        WHERE application_id=%s AND resource_type='DOCUMENT'
                        """,
                        (row["application_id"],),
                    ).fetchall()
                )
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_authentication_failed") from exc

        effective_scopes = frozenset(tenant_scopes.intersection(app_scopes))
        docs = effective_document_ids(
            tenant_content_scope=str(row["tenant_content_scope"]),
            tenant_document_ids=tenant_docs,
            application_content_scope=str(row["application_content_scope"]),
            application_document_ids=app_docs,
        )
        return ApiAccessPrincipal(
            tenant_id=str(row["tenant_id"]),
            application_id=str(row["application_id"]),
            credential_id=str(row["credential_id"]),
            scopes=effective_scopes,
            allowed_document_ids=docs,
            requests_per_minute=min(int(row["tenant_rpm"]), int(row["application_rpm"])),
            max_top_k=min(int(row["tenant_max_top_k"]), int(row["application_max_top_k"])),
        )

    def list_consumers(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as con:
                rows = con.execute(
                    """
                    SELECT
                        t.tenant_id,
                        t.name AS tenant_name,
                        t.state AS tenant_state,
                        a.application_id,
                        a.name AS application_name,
                        a.environment,
                        a.state AS application_state,
                        count(c.credential_id) FILTER (WHERE c.state='ACTIVE') AS active_credentials
                    FROM api_access.tenants t
                    JOIN api_access.applications a ON a.tenant_id=t.tenant_id
                    LEFT JOIN api_access.credentials c ON c.application_id=a.application_id
                    GROUP BY
                        t.tenant_id,t.name,t.state,
                        a.application_id,a.name,a.environment,a.state
                    ORDER BY t.name,a.name,a.environment
                    """
                ).fetchall()
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_list_failed") from exc
        return [dict(row) for row in rows]
