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


class ApiAccessConflict(ApiAccessError):
    """Optimistic concurrency or dependent-policy conflict."""


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
    credential: str


@dataclass(frozen=True)
class PolicyMutationResult:
    entity_id: str
    policy_version: int
    changed: bool


@dataclass(frozen=True)
class LifecycleMutationResult:
    entity_id: str
    state: str
    policy_version: int
    changed: bool


@dataclass(frozen=True)
class CredentialIssueResult:
    tenant_id: str
    application_id: str
    credential_id: str
    credential: str


@dataclass(frozen=True)
class CredentialRevokeResult:
    tenant_id: str
    application_id: str
    credential_id: str
    state: str
    changed: bool


def hash_api_key(value: str) -> str:
    # High-entropy random API key lookup digest, not a password KDF.
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
        credential = f"metis_live_{credential_id}.{secrets.token_urlsafe(32)}"
        secret_sha256 = hash_api_key(credential)

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
            credential=credential,
        )

    @staticmethod
    def _policy_details(
        *,
        content_scope: str,
        scopes: Iterable[str],
        document_ids: Iterable[str],
        requests_per_minute: int,
        max_top_k: int,
    ) -> dict[str, Any]:
        return {
            "content_scope": str(content_scope),
            "scopes": sorted(str(value) for value in scopes),
            "document_ids": sorted(str(value) for value in document_ids),
            "requests_per_minute": int(requests_per_minute),
            "max_top_k": int(max_top_k),
        }

    @staticmethod
    def _tenant_policy_for_update(con: Any, tenant_id: str) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT tenant_id,name,state,content_scope,requests_per_minute,max_top_k,policy_version
            FROM api_access.tenants
            WHERE tenant_id=%s
            FOR UPDATE
            """,
            (tenant_id,),
        ).fetchone()
        if row is None:
            raise ApiAccessError("tenant_not_found")
        return dict(row)

    @staticmethod
    def _application_policy_for_update(
        con: Any,
        *,
        tenant_id: str,
        application_id: str,
    ) -> dict[str, Any]:
        row = con.execute(
            """
            SELECT application_id,tenant_id,name,environment,state,content_scope,
                   requests_per_minute,max_top_k,policy_version
            FROM api_access.applications
            WHERE application_id=%s AND tenant_id=%s
            FOR UPDATE
            """,
            (application_id, tenant_id),
        ).fetchone()
        if row is None:
            raise ApiAccessError("application_not_found")
        return dict(row)

    @staticmethod
    def _scopes_for_tenant(con: Any, tenant_id: str) -> frozenset[str]:
        return frozenset(
            str(row["scope"])
            for row in con.execute(
                "SELECT scope FROM api_access.tenant_scopes WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchall()
        )

    @staticmethod
    def _documents_for_tenant(con: Any, tenant_id: str) -> frozenset[str]:
        return frozenset(
            str(row["resource_id"])
            for row in con.execute(
                """
                SELECT resource_id
                FROM api_access.tenant_resources
                WHERE tenant_id=%s AND resource_type='DOCUMENT'
                """,
                (tenant_id,),
            ).fetchall()
        )

    @staticmethod
    def _scopes_for_application(con: Any, application_id: str) -> frozenset[str]:
        return frozenset(
            str(row["scope"])
            for row in con.execute(
                "SELECT scope FROM api_access.application_scopes WHERE application_id=%s",
                (application_id,),
            ).fetchall()
        )

    @staticmethod
    def _documents_for_application(con: Any, application_id: str) -> frozenset[str]:
        return frozenset(
            str(row["resource_id"])
            for row in con.execute(
                """
                SELECT resource_id
                FROM api_access.application_resources
                WHERE application_id=%s AND resource_type='DOCUMENT'
                """,
                (application_id,),
            ).fetchall()
        )

    @staticmethod
    def _check_expected_version(current: int, expected: int) -> None:
        if int(current) != int(expected):
            raise ApiAccessConflict(
                f"policy_version_mismatch:expected={int(expected)}:current={int(current)}"
            )

    @staticmethod
    def _replace_tenant_policy(
        con: Any,
        *,
        tenant_id: str,
        content_scope: str,
        document_ids: frozenset[str],
        scopes: frozenset[str],
        requests_per_minute: int,
        max_top_k: int,
        next_version: int,
    ) -> None:
        con.execute("DELETE FROM api_access.tenant_scopes WHERE tenant_id=%s", (tenant_id,))
        con.execute("DELETE FROM api_access.tenant_resources WHERE tenant_id=%s", (tenant_id,))
        for scope in sorted(scopes):
            con.execute(
                "INSERT INTO api_access.tenant_scopes(tenant_id,scope) VALUES (%s,%s)",
                (tenant_id, scope),
            )
        for document_id in sorted(document_ids):
            con.execute(
                """
                INSERT INTO api_access.tenant_resources(tenant_id,resource_type,resource_id)
                VALUES (%s,'DOCUMENT',%s)
                """,
                (tenant_id, document_id),
            )
        con.execute(
            """
            UPDATE api_access.tenants
            SET content_scope=%s, requests_per_minute=%s, max_top_k=%s, policy_version=%s
            WHERE tenant_id=%s
            """,
            (content_scope, requests_per_minute, max_top_k, next_version, tenant_id),
        )

    @staticmethod
    def _replace_application_policy(
        con: Any,
        *,
        application_id: str,
        content_scope: str,
        document_ids: frozenset[str],
        scopes: frozenset[str],
        requests_per_minute: int,
        max_top_k: int,
        next_version: int,
    ) -> None:
        con.execute(
            "DELETE FROM api_access.application_scopes WHERE application_id=%s",
            (application_id,),
        )
        con.execute(
            "DELETE FROM api_access.application_resources WHERE application_id=%s",
            (application_id,),
        )
        for scope in sorted(scopes):
            con.execute(
                """
                INSERT INTO api_access.application_scopes(application_id,scope)
                VALUES (%s,%s)
                """,
                (application_id, scope),
            )
        for document_id in sorted(document_ids):
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
            UPDATE api_access.applications
            SET content_scope=%s, requests_per_minute=%s, max_top_k=%s, policy_version=%s
            WHERE application_id=%s
            """,
            (
                content_scope,
                requests_per_minute,
                max_top_k,
                next_version,
                application_id,
            ),
        )

    def set_tenant_entitlement(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        expected_version: int,
        content_scope: str,
        document_ids: Iterable[str],
        scopes: Iterable[str],
        requests_per_minute: int,
        max_top_k: int,
    ) -> PolicyMutationResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        mode, docs = validate_content_scope(content_scope, document_ids)
        scope_set = _scope_set(scopes)
        rpm = int(requests_per_minute)
        top_k = int(max_top_k)
        if min(rpm, top_k) < 1:
            raise ApiAccessError("access_limit_must_be_positive")

        try:
            with self._connect() as con:
                with con.transaction():
                    tenant = self._tenant_policy_for_update(con, tenant_key)
                    self._check_expected_version(
                        int(tenant["policy_version"]),
                        int(expected_version),
                    )
                    if str(tenant["state"]) == "CLOSED":
                        raise ApiAccessError("tenant_closed")

                    application_rows = con.execute(
                        """
                        SELECT application_id,state,content_scope,requests_per_minute,max_top_k
                        FROM api_access.applications
                        WHERE tenant_id=%s
                        ORDER BY application_id
                        FOR UPDATE
                        """,
                        (tenant_key,),
                    ).fetchall()
                    for app_row in application_rows:
                        app_id = str(app_row["application_id"])
                        validate_grant_subset(
                            tenant_content_scope=mode,
                            tenant_document_ids=docs,
                            tenant_scopes=scope_set,
                            tenant_requests_per_minute=rpm,
                            tenant_max_top_k=top_k,
                            application_content_scope=str(app_row["content_scope"]),
                            application_document_ids=self._documents_for_application(con, app_id),
                            application_scopes=self._scopes_for_application(con, app_id),
                            application_requests_per_minute=int(app_row["requests_per_minute"]),
                            application_max_top_k=int(app_row["max_top_k"]),
                        )

                    current_scopes = self._scopes_for_tenant(con, tenant_key)
                    current_docs = self._documents_for_tenant(con, tenant_key)
                    before = self._policy_details(
                        content_scope=str(tenant["content_scope"]),
                        scopes=current_scopes,
                        document_ids=current_docs,
                        requests_per_minute=int(tenant["requests_per_minute"]),
                        max_top_k=int(tenant["max_top_k"]),
                    )
                    after = self._policy_details(
                        content_scope=mode,
                        scopes=scope_set,
                        document_ids=docs,
                        requests_per_minute=rpm,
                        max_top_k=top_k,
                    )
                    if before == after:
                        return PolicyMutationResult(
                            entity_id=tenant_key,
                            policy_version=int(tenant["policy_version"]),
                            changed=False,
                        )

                    next_version = int(tenant["policy_version"]) + 1
                    self._replace_tenant_policy(
                        con,
                        tenant_id=tenant_key,
                        content_scope=mode,
                        document_ids=docs,
                        scopes=scope_set,
                        requests_per_minute=rpm,
                        max_top_k=top_k,
                        next_version=next_version,
                    )
                    self._audit(
                        con,
                        event_type="tenant.entitlement.changed",
                        actor_id=actor,
                        tenant_id=tenant_key,
                        details={
                            "old_policy_version": int(tenant["policy_version"]),
                            "new_policy_version": next_version,
                            "before": before,
                            "after": after,
                        },
                    )
                    return PolicyMutationResult(
                        entity_id=tenant_key,
                        policy_version=next_version,
                        changed=True,
                    )
        except (ApiAccessError, ApiAccessConflict):
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_tenant_policy_update_failed") from exc

    def set_application_grant(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        application_id: str,
        expected_version: int,
        content_scope: str,
        document_ids: Iterable[str],
        scopes: Iterable[str],
        requests_per_minute: int,
        max_top_k: int,
    ) -> PolicyMutationResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        application_key = _clean_text(application_id, code="application_id_missing")
        mode, docs = validate_content_scope(content_scope, document_ids)
        scope_set = _scope_set(scopes)
        rpm = int(requests_per_minute)
        top_k = int(max_top_k)
        if min(rpm, top_k) < 1:
            raise ApiAccessError("access_limit_must_be_positive")

        try:
            with self._connect() as con:
                with con.transaction():
                    tenant = self._tenant_policy_for_update(con, tenant_key)
                    application = self._application_policy_for_update(
                        con,
                        tenant_id=tenant_key,
                        application_id=application_key,
                    )
                    self._check_expected_version(
                        int(application["policy_version"]),
                        int(expected_version),
                    )
                    # RETIRED is terminal for lifecycle transitions, not an
                    # immutable policy snapshot. Its stored grant must remain
                    # within the current tenant entitlement, so publishers may
                    # narrow it before shrinking the parent entitlement.
                    tenant_scopes = self._scopes_for_tenant(con, tenant_key)
                    tenant_docs = self._documents_for_tenant(con, tenant_key)
                    validate_grant_subset(
                        tenant_content_scope=str(tenant["content_scope"]),
                        tenant_document_ids=tenant_docs,
                        tenant_scopes=tenant_scopes,
                        tenant_requests_per_minute=int(tenant["requests_per_minute"]),
                        tenant_max_top_k=int(tenant["max_top_k"]),
                        application_content_scope=mode,
                        application_document_ids=docs,
                        application_scopes=scope_set,
                        application_requests_per_minute=rpm,
                        application_max_top_k=top_k,
                    )

                    current_scopes = self._scopes_for_application(con, application_key)
                    current_docs = self._documents_for_application(con, application_key)
                    before = self._policy_details(
                        content_scope=str(application["content_scope"]),
                        scopes=current_scopes,
                        document_ids=current_docs,
                        requests_per_minute=int(application["requests_per_minute"]),
                        max_top_k=int(application["max_top_k"]),
                    )
                    after = self._policy_details(
                        content_scope=mode,
                        scopes=scope_set,
                        document_ids=docs,
                        requests_per_minute=rpm,
                        max_top_k=top_k,
                    )
                    if before == after:
                        return PolicyMutationResult(
                            entity_id=application_key,
                            policy_version=int(application["policy_version"]),
                            changed=False,
                        )

                    next_version = int(application["policy_version"]) + 1
                    self._replace_application_policy(
                        con,
                        application_id=application_key,
                        content_scope=mode,
                        document_ids=docs,
                        scopes=scope_set,
                        requests_per_minute=rpm,
                        max_top_k=top_k,
                        next_version=next_version,
                    )
                    self._audit(
                        con,
                        event_type="application.grant.changed",
                        actor_id=actor,
                        tenant_id=tenant_key,
                        application_id=application_key,
                        details={
                            "old_policy_version": int(application["policy_version"]),
                            "new_policy_version": next_version,
                            "before": before,
                            "after": after,
                        },
                    )
                    return PolicyMutationResult(
                        entity_id=application_key,
                        policy_version=next_version,
                        changed=True,
                    )
        except (ApiAccessError, ApiAccessConflict):
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_application_policy_update_failed") from exc

    def set_tenant_state(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        expected_version: int,
        target_state: str,
    ) -> LifecycleMutationResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        target = str(target_state or "").strip().upper()
        if target not in {"ACTIVE", "SUSPENDED"}:
            raise ApiAccessError("unsupported_tenant_transition")

        try:
            with self._connect() as con:
                with con.transaction():
                    tenant = self._tenant_policy_for_update(con, tenant_key)
                    self._check_expected_version(
                        int(tenant["policy_version"]),
                        int(expected_version),
                    )
                    current = str(tenant["state"])
                    if current == "CLOSED":
                        raise ApiAccessError("tenant_closed")
                    if current == target:
                        return LifecycleMutationResult(
                            entity_id=tenant_key,
                            state=current,
                            policy_version=int(tenant["policy_version"]),
                            changed=False,
                        )
                    if {current, target} != {"ACTIVE", "SUSPENDED"}:
                        raise ApiAccessError("unsupported_tenant_transition")
                    next_version = int(tenant["policy_version"]) + 1
                    con.execute(
                        """
                        UPDATE api_access.tenants
                        SET state=%s, policy_version=%s
                        WHERE tenant_id=%s
                        """,
                        (target, next_version, tenant_key),
                    )
                    self._audit(
                        con,
                        event_type=(
                            "tenant.suspended"
                            if target == "SUSPENDED"
                            else "tenant.reactivated"
                        ),
                        actor_id=actor,
                        tenant_id=tenant_key,
                        details={
                            "old_state": current,
                            "new_state": target,
                            "old_policy_version": int(tenant["policy_version"]),
                            "new_policy_version": next_version,
                        },
                    )
                    return LifecycleMutationResult(
                        entity_id=tenant_key,
                        state=target,
                        policy_version=next_version,
                        changed=True,
                    )
        except (ApiAccessError, ApiAccessConflict):
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_tenant_state_update_failed") from exc

    def set_application_state(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        application_id: str,
        expected_version: int,
        target_state: str,
    ) -> LifecycleMutationResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        application_key = _clean_text(application_id, code="application_id_missing")
        target = str(target_state or "").strip().upper()
        if target not in {"ACTIVE", "SUSPENDED", "RETIRED"}:
            raise ApiAccessError("unsupported_application_transition")

        try:
            with self._connect() as con:
                with con.transaction():
                    self._tenant_policy_for_update(con, tenant_key)
                    application = self._application_policy_for_update(
                        con,
                        tenant_id=tenant_key,
                        application_id=application_key,
                    )
                    self._check_expected_version(
                        int(application["policy_version"]),
                        int(expected_version),
                    )
                    current = str(application["state"])
                    if current == target:
                        return LifecycleMutationResult(
                            entity_id=application_key,
                            state=current,
                            policy_version=int(application["policy_version"]),
                            changed=False,
                        )
                    if current == "RETIRED":
                        raise ApiAccessError("application_retired")
                    if target not in {"ACTIVE", "SUSPENDED", "RETIRED"}:
                        raise ApiAccessError("unsupported_application_transition")
                    next_version = int(application["policy_version"]) + 1
                    con.execute(
                        """
                        UPDATE api_access.applications
                        SET state=%s, policy_version=%s
                        WHERE application_id=%s AND tenant_id=%s
                        """,
                        (target, next_version, application_key, tenant_key),
                    )
                    event_type = {
                        "ACTIVE": "application.reactivated",
                        "SUSPENDED": "application.suspended",
                        "RETIRED": "application.retired",
                    }[target]
                    self._audit(
                        con,
                        event_type=event_type,
                        actor_id=actor,
                        tenant_id=tenant_key,
                        application_id=application_key,
                        details={
                            "old_state": current,
                            "new_state": target,
                            "old_policy_version": int(application["policy_version"]),
                            "new_policy_version": next_version,
                        },
                    )
                    return LifecycleMutationResult(
                        entity_id=application_key,
                        state=target,
                        policy_version=next_version,
                        changed=True,
                    )
        except (ApiAccessError, ApiAccessConflict):
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_application_state_update_failed") from exc

    def issue_credential(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        application_id: str,
    ) -> CredentialIssueResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        application_key = _clean_text(application_id, code="application_id_missing")
        credential_id = "cred_" + uuid.uuid4().hex
        credential = f"metis_live_{credential_id}.{secrets.token_urlsafe(32)}"
        secret_sha256 = hash_api_key(credential)

        try:
            with self._connect() as con:
                with con.transaction():
                    tenant = self._tenant_policy_for_update(con, tenant_key)
                    application = self._application_policy_for_update(
                        con,
                        tenant_id=tenant_key,
                        application_id=application_key,
                    )
                    if str(tenant["state"]) != "ACTIVE":
                        raise ApiAccessError("tenant_not_active")
                    if str(application["state"]) != "ACTIVE":
                        raise ApiAccessError("application_not_active")
                    con.execute(
                        """
                        INSERT INTO api_access.credentials(
                            credential_id,application_id,secret_sha256,state
                        ) VALUES (%s,%s,%s,'ACTIVE')
                        """,
                        (credential_id, application_key, secret_sha256),
                    )
                    self._audit(
                        con,
                        event_type="credential.issued",
                        actor_id=actor,
                        tenant_id=tenant_key,
                        application_id=application_key,
                        credential_id=credential_id,
                        details={},
                    )
        except ApiAccessError:
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_credential_issue_failed") from exc

        return CredentialIssueResult(
            tenant_id=tenant_key,
            application_id=application_key,
            credential_id=credential_id,
            credential=credential,
        )

    def revoke_credential(
        self,
        *,
        actor_id: str,
        tenant_id: str,
        application_id: str,
        credential_id: str,
    ) -> CredentialRevokeResult:
        actor = _clean_text(actor_id, code="actor_id_missing")
        tenant_key = _clean_text(tenant_id, code="tenant_id_missing")
        application_key = _clean_text(application_id, code="application_id_missing")
        credential_key = _clean_text(credential_id, code="credential_id_missing")

        try:
            with self._connect() as con:
                with con.transaction():
                    self._tenant_policy_for_update(con, tenant_key)
                    self._application_policy_for_update(
                        con,
                        tenant_id=tenant_key,
                        application_id=application_key,
                    )
                    row = con.execute(
                        """
                        SELECT c.credential_id,c.state
                        FROM api_access.credentials c
                        JOIN api_access.applications a ON a.application_id=c.application_id
                        WHERE c.credential_id=%s
                          AND c.application_id=%s
                          AND a.tenant_id=%s
                        FOR UPDATE
                        """,
                        (credential_key, application_key, tenant_key),
                    ).fetchone()
                    if row is None:
                        raise ApiAccessError("credential_not_found")
                    current = str(row["state"])
                    if current == "REVOKED":
                        return CredentialRevokeResult(
                            tenant_id=tenant_key,
                            application_id=application_key,
                            credential_id=credential_key,
                            state="REVOKED",
                            changed=False,
                        )
                    con.execute(
                        """
                        UPDATE api_access.credentials
                        SET state='REVOKED', revoked_at=now()
                        WHERE credential_id=%s
                        """,
                        (credential_key,),
                    )
                    self._audit(
                        con,
                        event_type="credential.revoked",
                        actor_id=actor,
                        tenant_id=tenant_key,
                        application_id=application_key,
                        credential_id=credential_key,
                        details={"old_state": current, "new_state": "REVOKED"},
                    )
                    return CredentialRevokeResult(
                        tenant_id=tenant_key,
                        application_id=application_key,
                        credential_id=credential_key,
                        state="REVOKED",
                        changed=True,
                    )
        except ApiAccessError:
            raise
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_credential_revoke_failed") from exc

    def authenticate(self, credential: str) -> ApiAccessPrincipal | None:
        supplied = str(credential or "")
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
                        t.content_scope AS tenant_content_scope,
                        t.requests_per_minute AS tenant_requests_per_minute,
                        t.max_top_k AS tenant_max_top_k,
                        t.policy_version AS tenant_policy_version,
                        a.application_id,
                        a.name AS application_name,
                        a.environment,
                        a.state AS application_state,
                        a.content_scope AS application_content_scope,
                        a.requests_per_minute AS application_requests_per_minute,
                        a.max_top_k AS application_max_top_k,
                        a.policy_version AS application_policy_version
                    FROM api_access.tenants t
                    JOIN api_access.applications a ON a.tenant_id=t.tenant_id
                    ORDER BY t.name,a.name,a.environment
                    """
                ).fetchall()
                result: list[dict[str, Any]] = []
                for raw in rows:
                    row = dict(raw)
                    tenant_id = str(row["tenant_id"])
                    application_id = str(row["application_id"])
                    row["tenant_scopes"] = sorted(self._scopes_for_tenant(con, tenant_id))
                    row["tenant_document_ids"] = sorted(
                        self._documents_for_tenant(con, tenant_id)
                    )
                    row["application_scopes"] = sorted(
                        self._scopes_for_application(con, application_id)
                    )
                    row["application_document_ids"] = sorted(
                        self._documents_for_application(con, application_id)
                    )
                    row["credentials"] = [
                        {
                            "credential_id": str(item["credential_id"]),
                            "state": str(item["state"]),
                            "created_at": item["created_at"],
                            "revoked_at": item["revoked_at"],
                        }
                        for item in con.execute(
                            """
                            SELECT credential_id,state,created_at,revoked_at
                            FROM api_access.credentials
                            WHERE application_id=%s
                            ORDER BY created_at,credential_id
                            """,
                            (application_id,),
                        ).fetchall()
                    ]
                    row["active_credentials"] = sum(
                        1 for item in row["credentials"] if item["state"] == "ACTIVE"
                    )
                    result.append(row)
        except ApiAccessStoreError:
            raise
        except Exception as exc:
            raise ApiAccessStoreError("api_access_list_failed") from exc
        return result
