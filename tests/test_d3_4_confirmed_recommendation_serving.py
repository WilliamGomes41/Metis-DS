"""D3.4 confirmed recommendation semantics serving regressions.

Proves the authority chain:
real source -> review confirmation -> retrieval projection -> Product API.
"""

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.integrity_kernel import stamp_canonical_hashes
from src.operations_console_v1 import OperationsConsole
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.recommendation_semantics_v1 import CONFIRMED_FIELD, PROPOSED_FIELD
from src.retrieval.retrieval_projection_v2 import build_projection
from src.usage_ledger_v1 import UsageLedger


ROOT = Path(__file__).resolve().parents[1]
KEY = "d34-fixture-key"
RECOMMENDATION_TEXT = "De werkgroep adviseert de verpleegkundige de interventie te gebruiken."


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "runtime" / "console",
    )


def _accounts(console: OperationsConsole) -> tuple[dict, dict]:
    researcher = console.create_account(
        username="d34.researcher",
        password="researcher-secret",
        roles=("researcher", "reviewer"),
        display_name="D3.4 Researcher",
    )
    reviewer = console.create_account(
        username="d34.reviewer",
        password="reviewer-secret",
        roles=("reviewer",),
        display_name="D3.4 Reviewer",
    )
    return researcher, reviewer


def _source_html(label: str, text: str) -> bytes:
    return (
        "<!doctype html><html lang='nl'><body>"
        "<h1>D3.4 richtlijn</h1>"
        f"<h2>{label}</h2>"
        f"<p>{text}</p>"
        "</body></html>"
    ).encode("utf-8")


def _semantics_proposal(
    *,
    direction: str,
    strength: str | None,
    status: str,
    label: str | None,
    text: str,
) -> dict:
    return {
        "version": "recommendation-semantics-v1",
        "direction": direction,
        "strength": strength,
        "strength_status": status,
        "direction_evidence_span": text,
        "strength_evidence_span": label if status == "explicit" else None,
        "source_label": label if status == "explicit" else None,
        "normalization_scheme": "source_literal_v1",
    }


def _reviewed_source_objects(
    tmp_path: Path,
    *,
    direction: str,
    strength_choice: str,
    label: str,
    text: str = RECOMMENDATION_TEXT,
) -> tuple[list[dict], str]:
    console = _console(tmp_path)
    researcher, reviewer = _accounts(console)
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="d34.html",
        data=_source_html(label, text),
        content_type="text/html",
        ingest_kind="new",
        title="D3.4 guideline",
        version="1.0",
        date="2026-09-25",
        live_url="https://example.test/d34",
        class_="richtlijn",
        family="test",
        named_reviewers=[researcher["account_id"], reviewer["account_id"]],
    )
    snapshot_id = receipt["snapshot_id"]
    current = console.snapshot_objects(snapshot_id)
    target = next(
        row
        for row in current
        if text in str((row.get("content") or {}).get("clean_text") or "")
    )

    rows = console._load_objects(snapshot_id)
    for row in rows:
        if row["object_id"] != target["object_id"]:
            continue
        row["proposed_object_type"] = "recommendation"
        row.pop("proposed_recommendation_strength", None)
        row[PROPOSED_FIELD] = _semantics_proposal(
            direction=direction,
            strength=None if strength_choice == "not_stated" else strength_choice,
            status="not_stated" if strength_choice == "not_stated" else "explicit",
            label=None if strength_choice == "not_stated" else label,
            text=text,
        )
        stamp_canonical_hashes(row)
    console._save_objects(snapshot_id, rows)

    console.review_object(
        actor_id=reviewer["account_id"],
        snapshot_id=snapshot_id,
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
        recommendation_direction=direction,
        recommendation_strength_level=strength_choice,
        expected_revision=console.objects_revision(snapshot_id),
    )

    live = console.snapshot_objects(snapshot_id)
    reviewed = next(row for row in live if row["object_id"] == target["object_id"])
    assert CONFIRMED_FIELD in reviewed
    return live, target["object_id"]


def _published_envelopes(objects: list[dict]) -> list[dict]:
    envelopes = []
    for source in objects:
        obj = copy.deepcopy(source)
        obj.setdefault("governance", {})["validation_status"] = "approved"
        obj["uncertainty"] = {"has_uncertainty": False, "items": []}
        envelopes.append(
            {
                "knowledge_object": obj,
                "publication": {
                    "release_id": "d34-regression",
                    "release_version": "1",
                    "published_at": "2026-09-25T12:00:00+00:00",
                },
            }
        )
    return envelopes


def _registry() -> TenantRegistry:
    return TenantRegistry(
        [
            TenantPolicy.from_dict(
                {
                    "tenant_id": "d34-test",
                    "name": "D3.4 test",
                    "enabled": True,
                    "api_key_sha256": hash_api_key(KEY),
                    "scopes": ["knowledge:read"],
                    "allowed_document_ids": ["*"],
                    "allowed_topics": ["*"],
                    "requests_per_minute": 100,
                    "max_top_k": 5,
                }
            )
        ]
    )


def _product_client(tmp_path: Path, records: list[dict]) -> TestClient:
    records_path = tmp_path / "d34-records.jsonl"
    records_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    defaults = ProductPaths.defaults(ROOT)
    paths = ProductPaths(
        real_records=defaults.real_records,
        fixture_records=records_path,
        real_published=defaults.real_published,
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused-tenants.json",
        usage_db=tmp_path / "usage.sqlite",
    )
    app = create_product_app(
        "fixture",
        paths=paths,
        tenant_registry=_registry(),
        usage_ledger=UsageLedger(paths.usage_db),
        allow_fixture=True,
    )
    return TestClient(app)


@pytest.mark.parametrize(
    ("direction", "strength_choice", "label", "expected_strength", "expected_status"),
    [
        ("for", "strong", "Sterke aanbeveling", "strong", "explicit"),
        ("for", "weak", "Zwakke aanbeveling", "weak", "explicit"),
        ("against", "strong", "Sterke aanbeveling", "strong", "explicit"),
        ("against", "weak", "Zwakke aanbeveling", "weak", "explicit"),
        ("for", "not_stated", "Aanbeveling", None, "not_stated"),
    ],
)
def test_real_source_review_projection_api_preserves_confirmed_semantics(
    tmp_path: Path,
    direction: str,
    strength_choice: str,
    label: str,
    expected_strength: str | None,
    expected_status: str,
) -> None:
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction=direction,
        strength_choice=strength_choice,
        label=label,
    )
    records, blocked = build_projection(_published_envelopes(objects))
    assert blocked == []
    record = next(row for row in records if row["metadata"]["object_id"] == object_id)
    semantics = record["metadata"]["confirmed_recommendation_semantics"]
    assert semantics["direction"] == direction
    assert semantics["strength"] == expected_strength
    assert semantics["strength_status"] == expected_status

    client = _product_client(tmp_path, records)
    response = client.get(
        f"/v1/knowledge/{object_id}",
        headers={"Authorization": f"Bearer {KEY}"},
    )
    assert response.status_code == 200
    served = response.json()["recommendation_semantics"]
    assert served == semantics


def test_clinical_condition_does_not_rewrite_strong_to_weak(tmp_path: Path) -> None:
    text = "Bij patiënten met een verhoogd risico adviseert de werkgroep de interventie te gebruiken."
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction="for",
        strength_choice="strong",
        label="Sterke aanbeveling",
        text=text,
    )
    records, blocked = build_projection(_published_envelopes(objects))
    assert blocked == []
    semantics = next(
        row for row in records if row["metadata"]["object_id"] == object_id
    )["metadata"]["confirmed_recommendation_semantics"]
    assert semantics["direction"] == "for"
    assert semantics["strength"] == "strong"


def test_proposal_is_never_promoted_over_confirmed_semantics(tmp_path: Path) -> None:
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction="for",
        strength_choice="strong",
        label="Sterke aanbeveling",
    )
    live = next(row for row in objects if row["object_id"] == object_id)
    live[PROPOSED_FIELD] = _semantics_proposal(
        direction="against",
        strength="weak",
        status="explicit",
        label="Zwakke aanbeveling",
        text=RECOMMENDATION_TEXT,
    )

    records, blocked = build_projection(_published_envelopes(objects))
    assert blocked == []
    projected = next(row for row in records if row["metadata"]["object_id"] == object_id)
    assert projected["metadata"]["confirmed_recommendation_semantics"]["direction"] == "for"
    assert projected["metadata"]["confirmed_recommendation_semantics"]["strength"] == "strong"
    assert "proposed_recommendation_semantics" not in projected["metadata"]


def test_legacy_only_strength_is_not_promoted_to_new_serving_semantics(tmp_path: Path) -> None:
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction="for",
        strength_choice="strong",
        label="Sterke aanbeveling",
    )
    live = next(row for row in objects if row["object_id"] == object_id)
    live.pop(CONFIRMED_FIELD, None)
    live.pop(PROPOSED_FIELD, None)
    live["confirmed_recommendation_strength"] = "doen"

    records, blocked = build_projection(_published_envelopes(objects))
    assert blocked == []
    projected = next(row for row in records if row["metadata"]["object_id"] == object_id)
    assert "confirmed_recommendation_semantics" not in projected["metadata"]
    assert "confirmed_recommendation_strength" not in projected["metadata"]


def test_dual_new_and_legacy_confirmed_authority_is_blocked(tmp_path: Path) -> None:
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction="for",
        strength_choice="strong",
        label="Sterke aanbeveling",
    )
    live = next(row for row in objects if row["object_id"] == object_id)
    live["confirmed_recommendation_strength"] = "niet_doen"

    records, blocked = build_projection(_published_envelopes(objects))
    assert all(row["metadata"]["object_id"] != object_id for row in records)
    error_row = next(row for row in blocked if row["object_id"] == object_id)
    assert any(
        "confirmed_recommendation_semantics_legacy_authority_conflict" in error
        for error in error_row["errors"]
    )


def test_unconfirmed_new_format_proposal_remains_absent_from_api(tmp_path: Path) -> None:
    objects, object_id = _reviewed_source_objects(
        tmp_path,
        direction="for",
        strength_choice="weak",
        label="Zwakke aanbeveling",
    )
    live = next(row for row in objects if row["object_id"] == object_id)
    live.pop(CONFIRMED_FIELD, None)
    live["confirmed_object_type"] = "recommendation"

    records, blocked = build_projection(_published_envelopes(objects))
    assert blocked == []
    projected = next(row for row in records if row["metadata"]["object_id"] == object_id)
    assert "confirmed_recommendation_semantics" not in projected["metadata"]

    client = _product_client(tmp_path, records)
    response = client.get(
        f"/v1/knowledge/{object_id}",
        headers={"Authorization": f"Bearer {KEY}"},
    )
    assert response.status_code == 200
    assert "recommendation_semantics" not in response.json()
