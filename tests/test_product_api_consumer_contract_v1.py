# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: metrics
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, RefResolver

from scripts.product_api_contract import (
    ContractCompatibilityError,
    assert_backward_compatible,
    assert_contract_complete,
    generate_contract,
)
from src.api_access_v1 import PostgresApiAccessStore
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.product_api_v1 import ProductPaths, create_product_app
from src.usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
DOC = "vvn-osteoporose-fractuurpreventie-2024"


def _dsn() -> str:
    value = os.environ.get("METIS_TEST_POSTGRES_DSN", "").strip()
    if not value:
        pytest.skip("METIS_TEST_POSTGRES_DSN is required for Product API N+1 conformance")
    return value


def _apply_access_schema(dsn: str) -> None:
    import psycopg

    sql = (ROOT / "db" / "migrations" / "010_api_access.sql").read_text(encoding="utf-8")
    with psycopg.connect(dsn) as con:
        with con.transaction():
            con.execute(sql)


def _paths(tmp_path: Path) -> ProductPaths:
    defaults = ProductPaths.defaults(ROOT)
    return ProductPaths(
        real_records=defaults.real_records,
        fixture_records=defaults.fixture_records,
        real_published=defaults.real_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused-tenants.json",
        usage_db=tmp_path / "usage.sqlite",
    )


def _response_schema(spec: dict, path: str, method: str = "get", status: str = "200") -> dict:
    return (
        spec["paths"][path][method]["responses"][status]["content"]["application/json"]["schema"]
    )


def _assert_matches_openapi(spec: dict, path: str, payload: dict, *, method: str = "get") -> None:
    resolver = RefResolver.from_schema(spec)
    Draft202012Validator(_response_schema(spec, path, method), resolver=resolver).validate(payload)


def _cleanup(dsn: str, tenant_id: str, application_id: str) -> None:
    import psycopg

    with psycopg.connect(dsn) as con:
        with con.transaction():
            con.execute("DELETE FROM api_access.audit_events WHERE tenant_id=%s", (tenant_id,))
            con.execute("DELETE FROM api_access.credentials WHERE application_id=%s", (application_id,))
            con.execute(
                "DELETE FROM api_access.application_resources WHERE application_id=%s",
                (application_id,),
            )
            con.execute(
                "DELETE FROM api_access.application_scopes WHERE application_id=%s",
                (application_id,),
            )
            con.execute("DELETE FROM api_access.applications WHERE application_id=%s", (application_id,))
            con.execute("DELETE FROM api_access.tenant_resources WHERE tenant_id=%s", (tenant_id,))
            con.execute("DELETE FROM api_access.tenant_scopes WHERE tenant_id=%s", (tenant_id,))
            con.execute("DELETE FROM api_access.tenants WHERE tenant_id=%s", (tenant_id,))


def test_openapi_is_generated_deterministically_from_running_product_app():
    first = generate_contract()
    second = generate_contract()
    assert first == second
    assert_contract_complete(first)
    for path, item in first["paths"].items():
        if path.startswith("/v1/"):
            for method, operation in item.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
                    assert "$ref" in schema


def test_v1_compatibility_guard_blocks_removed_route_and_new_required_request_field():
    baseline = generate_contract()

    removed = copy.deepcopy(baseline)
    removed["paths"].pop("/v1/documents")
    with pytest.raises(ContractCompatibilityError, match="/v1/documents: path removed"):
        assert_backward_compatible(baseline, removed)

    tightened = copy.deepcopy(baseline)
    retrieve_ref = (
        tightened["paths"]["/v1/retrieve"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    )
    component = retrieve_ref.rsplit("/", 1)[-1]
    tightened["components"]["schemas"][component]["properties"]["consumer_hint"] = {"type": "string"}
    tightened["components"]["schemas"][component]["required"].append("consumer_hint")
    with pytest.raises(ContractCompatibilityError, match="new required request fields"):
        assert_backward_compatible(baseline, tightened)

    response_type_change = copy.deepcopy(baseline)
    response_ref = (
        response_type_change["paths"]["/v1/documents"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    )
    response_component = response_ref.rsplit("/", 1)[-1]
    response_type_change["components"]["schemas"][response_component]["properties"]["tenant_id"] = {
        "type": "integer"
    }
    with pytest.raises(ContractCompatibilityError, match="type changed"):
        assert_backward_compatible(baseline, response_type_change)


def test_fresh_n_plus_one_consumer_uses_same_contract_without_metis_specific_code(tmp_path):
    dsn = _dsn()
    _apply_access_schema(dsn)
    store = PostgresApiAccessStore(PostgresCanonicalConfig(dsn=dsn))
    issued = store.provision_consumer(
        actor_id="contract-test-publisher",
        tenant_name="Generic N+1 consumer",
        tenant_content_scope="RESOURCE_SET",
        tenant_document_ids=[DOC],
        tenant_scopes=[
            "retrieve",
            "knowledge:read",
            "documents:read",
            "updates:read",
            "usage:read",
        ],
        tenant_requests_per_minute=100,
        tenant_max_top_k=5,
        application_name="Generic HTTP client",
        environment="TEST",
        application_content_scope="RESOURCE_SET",
        application_document_ids=[DOC],
        application_scopes=[
            "retrieve",
            "knowledge:read",
            "documents:read",
            "updates:read",
            "usage:read",
        ],
        application_requests_per_minute=100,
        application_max_top_k=5,
    )
    try:
        paths = _paths(tmp_path)
        app = create_product_app(
            "fixture",
            paths=paths,
            api_access_store=store,
            api_access_mode="postgres",
            usage_ledger=UsageLedger(paths.usage_db),
            allow_fixture=True,
        )
        spec = app.openapi()
        client = TestClient(app)
        headers = {
            "Authorization": f"Bearer {issued.credential}",
            "X-Request-ID": "n-plus-one-contract-proof",
        }

        docs = client.get("/v1/documents", headers=headers)
        assert docs.status_code == 200
        assert docs.headers["X-Request-ID"] == "n-plus-one-contract-proof"
        _assert_matches_openapi(spec, "/v1/documents", docs.json())
        assert [row["document_id"] for row in docs.json()["documents"]] == [DOC]

        retrieved = client.post(
            "/v1/retrieve",
            headers=headers,
            json={"query": "Wanneer gebruik je de risicofactorenscore?", "top_k": 3},
        )
        assert retrieved.status_code == 200
        _assert_matches_openapi(spec, "/v1/retrieve", retrieved.json(), method="post")
        assert retrieved.json()["request_id"] == "n-plus-one-contract-proof"
        assert retrieved.json()["results"]

        object_id = retrieved.json()["results"][0]["knowledge_object_id"]
        knowledge = client.get(f"/v1/knowledge/{object_id}", headers=headers)
        assert knowledge.status_code == 200
        _assert_matches_openapi(spec, "/v1/knowledge/{object_id}", knowledge.json())

        updates = client.get("/v1/updates", headers=headers)
        assert updates.status_code == 200
        _assert_matches_openapi(spec, "/v1/updates", updates.json())

        usage = client.get("/v1/usage", headers=headers)
        assert usage.status_code == 200
        _assert_matches_openapi(spec, "/v1/usage", usage.json())
        assert usage.json()["tenant_id"] == issued.tenant_id
        assert usage.json()["requests"] >= 4

        wrong = client.get(
            "/v1/documents",
            headers={"Authorization": "Bearer definitely-wrong"},
        )
        assert wrong.status_code == 401
        assert wrong.json()["detail"]["code"] == "invalid_api_key"
        _assert_matches_openapi(spec, "/v1/documents", wrong.json(), status="401")
    finally:
        _cleanup(dsn, issued.tenant_id, issued.application_id)
