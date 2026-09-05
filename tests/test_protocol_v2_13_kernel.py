"""Acceptance tests for Protocol v2.13 kernel implementation.

Atomic split, closed relations, type confirmation, high-risk four-eyes,
open-original, G2-blocked publish, Documentenhiërarchie.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.answerability_gate_v1 import evaluate_answerability
from src.atomic_split_v1 import (
    fusion_is_forbidden,
    is_single_grammatical_claim,
    split_meaning_units,
    token_budget_must_not_define_identity,
)
from src.four_eyes_v1 import (
    four_eyes_satisfied,
    is_forbidden_reviewer,
    publish_authorization_contract,
    requires_four_eyes,
)
from src.integrity_kernel import compute_canonical_object_hash, sha256_bytes
from src.object_taxonomy_v1 import published_object_type
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole
from src.product_api_v1 import ProductPaths, create_product_app
from src.product_security_v1 import TenantPolicy, TenantRegistry, hash_api_key
from src.published_projection_v1 import atomic_replace_projection
from src.serving_relations_v1 import (
    CLOSED_RELATION_SET,
    HISTORICAL_NON_SERVING_TYPES,
    applies_if_targets,
    binding_relations,
    except_if_targets,
    historical_type_must_not_serve,
    serving_relation_type,
)
from src.usage_ledger_v1 import UsageLedger


ROOT = Path(__file__).resolve().parents[1]
HTML_FIXTURE = ROOT / "data/fixtures/source2_html_factory_fixture.html"
SCHEMA = ROOT / "schemas/knowledge_object.schema.v1.2.json"


def _console(tmp_path: Path) -> OperationsConsole:
    return OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )


def _accounts(console: OperationsConsole) -> dict[str, dict]:
    researcher = console.create_account(
        username="researcher.anne",
        password="anne-secret",
        roles=("researcher", "reviewer"),
        display_name="Anne Onderzoeker",
    )
    reviewer = console.create_account(
        username="reviewer.bert",
        password="bert-secret",
        roles=("reviewer",),
        display_name="Bert Reviewer",
    )
    publisher = console.create_account(
        username="publisher.carla",
        password="carla-secret",
        roles=("publisher",),
        display_name="Carla Publisher",
    )
    return {"researcher": researcher, "reviewer": reviewer, "publisher": publisher}


def _ingest_html(console: OperationsConsole, accounts: dict, data: bytes | None = None, **kwargs) -> dict:
    defaults = dict(
        actor_id=accounts["researcher"]["account_id"],
        filename="continentie.html",
        data=data if data is not None else HTML_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Continentie fixture",
        version="1.0",
        date="2025-04-01",
        live_url="https://example.test/continentie",
        class_="richtlijn",
        family="continentie",
        named_reviewers=[
            accounts["researcher"]["account_id"],
            accounts["reviewer"]["account_id"],
        ],
    )
    defaults.update(kwargs)
    return console.ingest(**defaults)


def _record(
    *,
    object_id: str,
    object_type: str,
    text: str,
    confirmed: str | None = None,
    proposed: str | None = None,
    locator: dict | None = None,
    source_class: str = "richtlijn",
    published: bool = True,
    confirmed_relations: list | None = None,
    relations: list | None = None,
) -> dict:
    loc = locator if locator is not None else {
        "locator_type": "web_line_range",
        "locator_value": "lines:4-4;p:1",
    }
    md = {
        "object_id": object_id,
        "object_version": "1.0",
        "document_id": "doc-1",
        "object_type": object_type,
        "proposed_object_type": proposed,
        "confirmed_object_type": confirmed,
        "source_class": source_class,
        "source_locator": loc,
        "content_hash": "a" * 64,
        "topic": ["continentie", f"class:{source_class}"],
        "confirmed_relations": confirmed_relations or [],
        "relations": relations or [],
    }
    if published:
        md["published_at"] = "2026-08-28T00:00:00Z"
        md["release_id"] = "proj-1"
        md["release_version"] = "1"
        md["source_title"] = "Fixture"
        md["source_version"] = "1.0"
    return {
        "metadata": md,
        "retrieval_id": f"{object_id}@1.0",
        "retrieval_text": text,
        "structured_logic": None,
        "projection_hash": "b" * 64,
        "relations": relations or [],
        "confirmed_relations": confirmed_relations or [],
        "confirmed_object_type": confirmed,
    }


def _eval(query: str, records: list[dict]) -> dict:
    raw = {
        "behavior": "retrieve",
        "results": [
            {
                "object_id": r["metadata"]["object_id"],
                "object_version": r["metadata"]["object_version"],
            }
            for r in records
        ],
    }
    by_id = {r["metadata"]["object_id"]: r for r in records}
    return evaluate_answerability(query, raw, by_id)


def _product_client(tmp_path: Path, records_path: Path):
    key = "fixture-client-secret-key"
    registry = TenantRegistry(
        [
            TenantPolicy.from_dict(
                {
                    "tenant_id": "test-tenant",
                    "name": "Test Tenant",
                    "enabled": True,
                    "api_key_sha256": hash_api_key(key),
                    "scopes": ["retrieve", "knowledge:read"],
                    "allowed_document_ids": ["*"],
                    "allowed_topics": ["*"],
                    "requests_per_minute": 100,
                    "max_top_k": 5,
                }
            )
        ]
    )
    defaults = ProductPaths.defaults(ROOT)
    paths = ProductPaths(
        real_records=records_path,
        fixture_records=records_path,
        real_published=tmp_path / "published.jsonl",
        lexical_config=defaults.lexical_config,
        vector_config=defaults.vector_config,
        hybrid_config=defaults.hybrid_config,
        tenant_config=tmp_path / "unused.json",
        usage_db=tmp_path / "usage.sqlite",
    )
    app = create_product_app(
        "fixture",
        paths=paths,
        tenant_registry=registry,
        usage_ledger=UsageLedger(paths.usage_db),
        allow_fixture=True,
    )
    return TestClient(app), {"Authorization": f"Bearer {key}"}


def test_split_at_meaning_boundaries_not_token_budget() -> None:
    fused = (
        "Bij een cliënt van 70 jaar of ouder. "
        "Verwijs naar de huisarts voor aanvullend onderzoek."
    )
    units = split_meaning_units(fused)
    assert len(units) == 2
    assert fusion_is_forbidden(fused) is True
    assert is_single_grammatical_claim(fused) is False

    one_claim = "Verwijs bij een cliënt van 70 jaar of ouder naar de huisarts."
    assert is_single_grammatical_claim(one_claim) is True
    assert fusion_is_forbidden(one_claim) is False
    assert split_meaning_units(one_claim) == [one_claim]


def test_fusion_of_condition_exception_into_recommendation_rejected_except_one_claim() -> None:
    fused_exception = (
        "Verwijs de cliënt naar de huisarts. "
        "Tenzij samen met de cliënt hiervan wordt afgezien."
    )
    assert fusion_is_forbidden(fused_exception) is True
    assert len(split_meaning_units(fused_exception)) == 2

    grammatical = "Verwijs de cliënt niet bij contra-indicatie naar de huisarts."
    assert fusion_is_forbidden(grammatical) is False
    assert split_meaning_units(grammatical) == [grammatical]


def test_token_budget_does_not_define_object_identity() -> None:
    claims = [f"Bespreek onderwerp {i} met de zorgvrager." for i in range(40)]
    blob = " ".join(claims)
    units = token_budget_must_not_define_identity(blob)
    assert len(units) == 40
    assert all(unit.startswith("Bespreek onderwerp") for unit in units)
    # A 300–700 token window would merge these. Meaning units must not.
    assert max(len(unit.split()) for unit in units) < 20


def test_ingest_splits_fused_html_into_separate_objects(tmp_path: Path) -> None:
    html = """<!doctype html><html lang="nl"><body>
<h1>Voorbeeldrichtlijn</h1>
<p>Bij een cliënt van 70 jaar of ouder. Verwijs naar de huisarts.</p>
</body></html>"""
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts, data=html.encode("utf-8"), filename="fused.html")
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    texts = [(obj.get("content") or {}).get("clean_text") or "" for obj in objects]
    body = [text for text in texts if "Verwijs" in text or "70 jaar" in text]
    assert len(body) >= 2
    assert not any("70 jaar" in text and "Verwijs" in text for text in body)


def test_unclassified_unconfirmed_not_supported_and_not_published_type() -> None:
    unclassified = _record(
        object_id="u1",
        object_type="unclassified",
        text="Bespreek het onderwerp met de zorgvrager.",
        confirmed=None,
        proposed="recommendation",
    )
    result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [unclassified])
    assert result["answerability"] != "supported"
    assert result["behavior"] == "abstain"
    assert published_object_type(unclassified) == "unclassified"


def test_historical_types_not_served() -> None:
    for historical in (
        "decision",
        "action",
        "score_rule",
        "table",
        "background",
        "patient_information",
        "section",
    ):
        assert historical_type_must_not_serve(historical)
        record = _record(
            object_id=f"hist-{historical}",
            object_type=historical,
            text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
            confirmed=None,
        )
        result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [record])
        assert result["answerability"] != "supported"
        assert result["results"] == []


def test_closed_relation_set_only_schema_names_are_not_serving_law() -> None:
    schema = __import__("json").loads(SCHEMA.read_text(encoding="utf-8"))
    enum = schema["properties"]["relations"]["items"]["properties"]["relation_type"]["enum"]
    assert set(enum) == set(CLOSED_RELATION_SET)
    for historical in ("conditioned_by", "exception_to", "supports", "child_of", "superseded_by"):
        assert historical not in enum
        assert serving_relation_type(historical) in CLOSED_RELATION_SET
    obj = {
        "relations": [{"relation_type": "conditioned_by", "target_object_id": "c1", "confirmed": False}],
        "confirmed_relations": [],
    }
    assert binding_relations(obj) == []
    assert applies_if_targets(obj) == []


def test_unconfirmed_relations_do_not_bind() -> None:
    rec = _record(
        object_id="r1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Verwijs naar de huisarts. Geadviseerd wordt verwijzing.",
        relations=[{"relation_type": "applies_if", "target_object_id": "c1", "confirmed": False}],
        confirmed_relations=[],
    )
    condition = _record(
        object_id="c1",
        object_type="condition",
        confirmed="condition",
        text="Bij een cliënt van 70 jaar of ouder.",
    )
    assert applies_if_targets(rec) == []
    assert binding_relations(rec) == []
    rec["confirmed_relations"] = [
        {"relation_type": "applies_if", "target_object_id": "c1", "confirmed": True}
    ]
    rec["metadata"]["confirmed_relations"] = rec["confirmed_relations"]
    assert applies_if_targets(rec) == ["c1"]
    _ = condition


def test_changed_confirmed_relations_invalidate_publish_authorization(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    html = """<!doctype html><html lang="nl"><body>
<h1>Voorbeeldrichtlijn</h1>
<p>Wanneer de cliënt 70 jaar of ouder is.</p>
<p>Verwijs naar de huisarts.</p>
</body></html>"""
    receipt = _ingest_html(console, accounts, data=html.encode("utf-8"), filename="rel.html")
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    rec = next(obj for obj in objects if "Verwijs" in ((obj.get("content") or {}).get("clean_text") or ""))
    cond = next(obj for obj in objects if "70 jaar" in ((obj.get("content") or {}).get("clean_text") or ""))
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        confirmed_object_type="recommendation",
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=cond["object_id"],
        confirmed_object_type="condition",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        decision="approve",
        confirmed_object_type="recommendation",
    )
    before = console.object_review_bindings(receipt["snapshot_id"])
    assert any(item.get("valid") and item["object_id"] == rec["object_id"] for item in before)
    console.confirm_relations(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=rec["object_id"],
        relations=[{"relation_type": "applies_if", "target_object_id": cond["object_id"]}],
    )
    after = console.object_review_bindings(receipt["snapshot_id"])
    assert not any(
        item.get("valid") is True and item["object_id"] == rec["object_id"]
        for item in after
    )


def test_published_recommendation_served_with_applies_if_except_if(tmp_path: Path) -> None:
    condition = _record(
        object_id="c1",
        object_type="condition",
        confirmed="condition",
        text="Bij een cliënt van 70 jaar of ouder.",
    )
    exception = _record(
        object_id="x1",
        object_type="exception",
        confirmed="exception",
        text="Tenzij samen met de cliënt hiervan wordt afgezien.",
    )
    rec = _record(
        object_id="r1",
        object_type="recommendation",
        confirmed="recommendation",
        text="Verwijs naar de huisarts. Geadviseerd wordt verwijzing bij 70 jaar.",
        confirmed_relations=[
            {"relation_type": "applies_if", "target_object_id": "c1", "confirmed": True},
            {"relation_type": "except_if", "target_object_id": "x1", "confirmed": True},
        ],
    )
    rec["metadata"]["applies_if_object_ids"] = ["c1"]
    rec["metadata"]["except_if_object_ids"] = ["x1"]
    path = tmp_path / "projection.jsonl"
    atomic_replace_projection(path, [rec, condition, exception])
    client, headers = _product_client(tmp_path, path)
    data = client.post(
        "/v1/retrieve",
        headers=headers,
        json={"query": "Wat adviseert deze richtlijn over verwijzing naar de huisarts?"},
    ).json()
    assert data["answerability"] == "supported"
    rec_row = next(row for row in data["results"] if row["knowledge_object_id"] == "r1")
    applies_ids = {item["knowledge_object_id"] for item in rec_row.get("applies_if") or []}
    except_ids = {item["knowledge_object_id"] for item in rec_row.get("except_if") or []}
    assert applies_ids == {"c1"}
    assert except_ids == {"x1"}
    for bound in (rec_row.get("applies_if") or []) + (rec_row.get("except_if") or []):
        assert bound.get("advice_weight") is not True


def test_four_eyes_required_for_exception_and_risk_fields_uploader_insufficient(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    html = """<!doctype html><html lang="nl"><body>
<h1>Voorbeeldrichtlijn</h1>
<p>Tenzij samen met de cliënt hiervan wordt afgezien.</p>
</body></html>"""
    receipt = _ingest_html(console, accounts, data=html.encode("utf-8"), filename="exc.html")
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="exception",
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == target["object_id"]
    )
    assert requires_four_eyes(refreshed, confirmed_type="exception") is True
    console.review_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
        confirmed_object_type="exception",
    )
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert considered["g2"] == "BLOCKED"
    assert "four_eyes_required" in considered["blockers"] or considered.get("four_eyes_satisfied") is False

    dosage = {
        "object_id": "dose-1",
        "confirmed_object_type": "recommendation",
        "risk": {"risk_level": "standard", "risk_fields": ["dosage", "unit"], "requires_second_review": True},
        "logic": {"predicates": [{"field": "dosage", "operator": "eq", "threshold": 5, "unit": "mg", "source_text": "5 mg"}], "score_points": None, "result_threshold": None, "result_action": None},
    }
    assert requires_four_eyes(dosage, confirmed_type="recommendation") is True


def test_agents_cannot_satisfy_four_eyes() -> None:
    for name in ("AI", "Grok Bot", "Metis", "Implementation engineer", "Auditor"):
        assert is_forbidden_reviewer(name)
    bindings = [
        {
            "valid": True,
            "decision": "approve",
            "object_id": "exc-1",
            "reviewer_id": "acc-human",
            "reviewer": "bert",
        },
        {
            "valid": True,
            "decision": "approve",
            "object_id": "exc-1",
            "reviewer_id": "acc-metis",
            "reviewer": "Metis",
        },
    ]
    assert four_eyes_satisfied(bindings, object_id="exc-1", uploader_id="acc-uploader") is False
    contract = publish_authorization_contract(
        obj={"object_id": "exc-1", "confirmed_object_type": "exception", "risk": {"risk_level": "high", "risk_fields": ["exception"]}},
        bindings=bindings,
        uploader_id="acc-uploader",
        immutable_locator=None,
        envelope_review_passes={"acc-human": {"passed": True}},
    )
    assert contract["publish_allowed"] is False
    assert contract["g2"] == "BLOCKED"
    assert contract["envelope_review_passes_authorizes"] is False
    assert "four_eyes_required" in contract["blockers"]
    assert "blocked_pending_immutable_locator" in contract["blockers"]


def test_reviewer_opens_exact_source_passage_v211_locator(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    data = HTML_FIXTURE.read_bytes()
    receipt = _ingest_html(console, accounts, data=data)
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    ]
    target = next(
        obj
        for obj in objects
        if "Bespreek" in ((obj.get("content") or {}).get("clean_text") or "")
    )
    opened = console.open_source_passage(
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
    )
    assert opened["locator_type"] == "web_line_range"
    assert opened["reserialized"] is False
    assert "Bespreek het onderwerp met de zorgvrager." in opened["passage"]
    freeze_text = Path(receipt["binary_path"]).read_bytes().decode("utf-8")
    assert opened["passage"] in freeze_text
    assert opened["passage"] != json_only_locator(target)

    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    review_html = client.get(
        f"/review?document={receipt['snapshot_id']}&object={target['object_id']}"
    ).text
    assert "Bespreek het onderwerp met de zorgvrager." in review_html
    assert "Onderbouwing uit het brondocument" in review_html
    passage_page = client.get(
        f"/review/bronpassage?document={receipt['snapshot_id']}&object={target['object_id']}"
    )
    assert passage_page.status_code == 200
    assert "Bespreek het onderwerp met de zorgvrager." in passage_page.text
    assert "envelope" not in passage_page.text.lower()
    assert "snapshot-id" not in passage_page.text.lower()


def json_only_locator(obj: dict) -> str:
    loc = ((obj.get("provenance") or {}).get("source_fragments") or [{}])[0].get("source_locator") or {}
    return str(loc.get("locator_value") or "")


def test_missing_locator_abstains() -> None:
    missing = _record(
        object_id="no-loc",
        object_type="recommendation",
        confirmed="recommendation",
        text="Bespreek het onderwerp met de zorgvrager. Geadviseerd wordt een dagboek.",
        locator=None,
    )
    missing["metadata"]["source_locator"] = None
    result = _eval("Wat adviseert deze richtlijn de zorgvrager?", [missing])
    assert result["answerability"] != "supported"
    assert result["behavior"] == "abstain"
    assert result["results"] == []


def test_g2_still_blocks_publish(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest_html(console, accounts)
    target = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_type"] != "document"
    )
    console.confirm_object_type(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        confirmed_object_type="heading" if target["object_type"] == "heading" else "explanation",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
    )
    console.review_object(
        actor_id=accounts["researcher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=target["object_id"],
        decision="approve",
    )
    result = console.publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert result["status"] == "BLOCKED"
    assert result["g2"] == "BLOCKED"
    assert result.get("cutover") is False
    considered = console.consider_publish(
        actor_id=accounts["publisher"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
    )
    assert considered["publish_allowed"] is False
    assert "blocked_pending_immutable_locator" in considered["blockers"]


def test_documentenhierarchie_ui_heading_unchanged(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    html = client.get("/tree").text
    assert "Documentenhiërarchie" in html
    assert "Documentenhierarchie" not in html
    source = (ROOT / "src/operations_console_app.py").read_text(encoding="utf-8")
    assert "Documentenhiërarchie" in source
    assert "Documentenhierarchie" not in source


def test_schema_v12_serving_law_relation_names_and_confirmed_relations() -> None:
    schema = __import__("json").loads(SCHEMA.read_text(encoding="utf-8"))
    rel = schema["properties"]["relations"]["items"]["properties"]
    assert set(rel["relation_type"]["enum"]) == set(CLOSED_RELATION_SET)
    assert "confirmed" in rel
    assert "confirmed_relations" in schema["properties"]
    from jsonschema import Draft202012Validator, FormatChecker
    from src.semantic_transform_generic_v1 import transform

    html = ROOT / "data/fixtures/source2_html_factory_fixture.html"
    from src.extract_html_v1 import extract

    raw = extract(html, document_id="doc-schema", source_id="src-schema")
    spec = {
        "spec_version": "1.0",
        "document_id": "doc-schema",
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": ["test"],
        "objects": [
            {
                "object_id": "doc-schema-document",
                "object_type": "document",
                "text": "Test",
                "review_track": "technical",
            },
            {
                "object_id": "doc-schema-rec",
                "object_type": "unclassified",
                "proposed_object_type": "recommendation",
                "text": "Bespreek het onderwerp met de zorgvrager.",
                "source_fragment_ids": [raw[-1]["fragment_id"]],
                "relations": [
                    {"relation_type": "applies_if", "target_object_id": "doc-schema-cond", "confirmed": False}
                ],
                "confirmed_relations": [],
            },
        ],
    }
    manifest = {
        "canonical_source": {
            "source_id": "src-schema",
            "title": "Test",
            "publisher": "V&VN",
            "source_url": "https://example.org/test",
            "source_type": "html",
            "source_level": 1,
            "canonicality": "canonical",
            "source_checksum": sha256_bytes(html.read_bytes()),
            "checksum_algorithm": "sha256",
            "integrity_status": "verified",
            "publication_date": "2025-04-01",
            "version": "1.0",
        }
    }
    rows = transform(spec, manifest, raw)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = [err.message for row in rows for err in validator.iter_errors(row)]
    assert errors == []
    rec = next(row for row in rows if row["object_id"] == "doc-schema-rec")
    assert rec["relations"][0]["relation_type"] == "applies_if"
    assert rec.get("confirmed_relations") == []
    hashed = compute_canonical_object_hash(rec)
    rec["confirmed_relations"] = [
        {"relation_type": "applies_if", "target_object_id": "doc-schema-cond", "confirmed": True}
    ]
    assert compute_canonical_object_hash(rec) != hashed
