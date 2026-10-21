import pytest

from src.api_access_v1 import (
    ApiAccessError,
    effective_document_ids,
    validate_content_scope,
    validate_grant_subset,
)


def test_document_scope_rejects_wildcard_and_empty_resource_set():
    with pytest.raises(ApiAccessError, match="wildcard_resource_not_allowed"):
        validate_content_scope("RESOURCE_SET", ["*"])
    with pytest.raises(ApiAccessError, match="resource_set_requires_document"):
        validate_content_scope("RESOURCE_SET", [])


def test_application_capabilities_must_remain_within_tenant_entitlement():
    with pytest.raises(ApiAccessError, match="application_scope_exceeds_tenant_entitlement"):
        validate_grant_subset(
            tenant_content_scope="ALL_PUBLISHED",
            tenant_document_ids=frozenset(),
            tenant_scopes=frozenset({"retrieve"}),
            tenant_requests_per_minute=100,
            tenant_max_top_k=10,
            application_content_scope="ALL_PUBLISHED",
            application_document_ids=frozenset(),
            application_scopes=frozenset({"retrieve", "knowledge:read"}),
            application_requests_per_minute=100,
            application_max_top_k=10,
        )


def test_application_resources_must_remain_within_restricted_tenant_entitlement():
    with pytest.raises(ApiAccessError, match="application_resource_exceeds_tenant_entitlement"):
        validate_grant_subset(
            tenant_content_scope="RESOURCE_SET",
            tenant_document_ids=frozenset({"doc-a"}),
            tenant_scopes=frozenset({"retrieve"}),
            tenant_requests_per_minute=100,
            tenant_max_top_k=10,
            application_content_scope="RESOURCE_SET",
            application_document_ids=frozenset({"doc-b"}),
            application_scopes=frozenset({"retrieve"}),
            application_requests_per_minute=100,
            application_max_top_k=10,
        )


def test_all_published_application_inside_restricted_tenant_means_full_tenant_subset():
    docs = effective_document_ids(
        tenant_content_scope="RESOURCE_SET",
        tenant_document_ids=frozenset({"doc-a", "doc-b"}),
        application_content_scope="ALL_PUBLISHED",
        application_document_ids=frozenset(),
    )
    assert docs == frozenset({"doc-a", "doc-b"})


def test_application_limits_cannot_exceed_tenant_limits():
    with pytest.raises(ApiAccessError, match="application_rate_limit_exceeds_tenant_entitlement"):
        validate_grant_subset(
            tenant_content_scope="ALL_PUBLISHED",
            tenant_document_ids=frozenset(),
            tenant_scopes=frozenset({"retrieve"}),
            tenant_requests_per_minute=100,
            tenant_max_top_k=10,
            application_content_scope="ALL_PUBLISHED",
            application_document_ids=frozenset(),
            application_scopes=frozenset({"retrieve"}),
            application_requests_per_minute=101,
            application_max_top_k=10,
        )
