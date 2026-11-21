"""#1111: the Product API returns the source's publication date, target group
and care setting of each published knowledge object, exactly as published.

Behavior proof on the REAL path (PostgreSQL registry rows + Blob read-back),
not on documentation text. An absent value stays absent: the release time or
ingest time is never substituted for the source's own publication date.
"""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from src.product_api_v1 import create_product_app
from src.retrieval.retrieval_projection_v2 import build_projection
from src.usage_ledger_v1 import UsageLedger
from tests.test_product_api_postgres_authority_v1 import (
    KEY,
    Authority,
    BlobAuthority,
    _object,
    _paths,
    _registry,
)

PUBLISHED_AT = "2026-09-11T20:00:00+00:00"
PUBLICATION = {"release_id": "release-postgres-1", "release_version": "1.0", "published_at": PUBLISHED_AT}


def _published_object(**overrides) -> dict:
    obj = _object()
    obj["content"].update(
        clean_text=(
            "Bij een cliënt van 50 jaar of ouder met een recente fractuur wordt "
            "aanvullend onderzoek naar osteoporose verricht met een DXA-meting."
        ),
        topic=["osteoporose"],
        target_group=["cliënten van 50 jaar of ouder met een recente fractuur"],
        care_setting=["wijkverpleging"],
    )
    obj["source"]["publication_date"] = "2024-03-01"
    obj["provenance"]["source_fragments"] = [
        {"source_locator": {"locator_type": "pdf_page_bbox", "locator_value": "p1#ko-postgres-1"}}
    ]
    for key, value in overrides.items():
        obj[key] = value
    return obj


def _app(tmp_path, obj: dict):
    paths = _paths(tmp_path)
    authority = Authority([
        {"knowledge_object": obj, "publication": dict(PUBLICATION), "snapshot_id": "snap-authority", "release_owner": "publisher"}
    ])
    app = create_product_app(
        "real",
        paths=paths,
        tenant_registry=_registry(),
        canonical_publication_store=authority,
        immutable_source_store=BlobAuthority(),
        usage_ledger=UsageLedger(paths.usage_db),
    )
    return TestClient(app)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {KEY}"}


def test_projection_carries_the_source_publication_date_not_the_release_time():
    records, blocked = build_projection([{"knowledge_object": _published_object(), "publication": dict(PUBLICATION)}])
    assert blocked == []
    metadata = records[0]["metadata"]
    assert metadata["source_publication_date"] == "2024-03-01"
    assert metadata["published_at"] == PUBLISHED_AT


def test_knowledge_route_returns_publication_date_target_group_and_care_setting(tmp_path):
    response = _app(tmp_path, _published_object()).get("/v1/knowledge/ko-postgres-1", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["source"]["publication_date"] == "2024-03-01"
    assert body["target_group"] == ["cliënten van 50 jaar of ouder met een recente fractuur"]
    assert body["care_setting"] == ["wijkverpleging"]
    assert body["release"]["published_at"] == PUBLISHED_AT


def test_retrieve_result_returns_publication_date_target_group_and_care_setting(tmp_path):
    response = _app(tmp_path, _published_object()).post(
        "/v1/retrieve",
        headers=_headers(),
        json={"query": "Welk aanvullend onderzoek naar osteoporose bij een recente fractuur?", "top_k": 3},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answerability"] == "supported", body
    result = next(r for r in body["results"] if r["knowledge_object_id"] == "ko-postgres-1")
    assert result["source"]["publication_date"] == "2024-03-01"
    assert result["target_group"] == ["cliënten van 50 jaar of ouder met een recente fractuur"]
    assert result["care_setting"] == ["wijkverpleging"]


def test_absent_values_stay_absent_and_are_never_inferred(tmp_path):
    obj = _published_object()
    obj["source"] = copy.deepcopy(obj["source"])
    obj["source"].pop("publication_date")
    obj["content"]["target_group"] = []
    obj["content"].pop("care_setting")
    body = _app(tmp_path, obj).get("/v1/knowledge/ko-postgres-1", headers=_headers()).json()
    assert body["source"]["publication_date"] is None
    assert body["target_group"] == []
    assert body["care_setting"] == []
    # Neither the release time nor any other date is substituted.
    assert PUBLISHED_AT not in str(body["source"])
