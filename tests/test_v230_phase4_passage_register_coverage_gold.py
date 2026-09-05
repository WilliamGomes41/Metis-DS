"""Protocol v2.30 Forge Phase 4: passage register + coverage + gold + metrics.

Richtlijn inhoudelijke candidates. Phase 1+2 admission / deep context stay.
Phase 3 review cockpit stays ordinary Dutch. Passage register MUST NOT be a
Phase-1 admission prerequisite. PROTOCOL.md and docs/PROTOCOL_V2_* are not
edited here. publish() stays G2-BLOCKED. Boom path/node/outcome stay v2.25.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admit_candidate,
    admission_of,
    apply_admission_gate,
    blocked_audit_lane,
    build_candidate_record,
    ordinary_review_queue,
)
from src.beslisboom_path_v1 import CLOSED_BOOM_TYPES
from src.extract_coverage_v1 import coverage_by_section
from src.extract_metrics_v1 import (
    EXTRACT_QUALITY_METRICS,
    compute_extract_metrics,
    extract_quality_claim_allowed,
)
from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
from src.operations_console_app import create_console_app
from src.operations_console_v1 import ConsoleError, OperationsConsole, is_slow_review_duty
from src.passage_register_v1 import (
    PASSAGE_REGISTER_STATUSES,
    SUITABILITY_TO_REGISTER,
    apply_passage_register,
    passage_register_of,
    register_status_from_suitability,
)
from src.review_cockpit_v1 import SUITABILITY_VALUES
from src.validate_golden_set import validate, validate_extract_gold


ROOT = Path(__file__).resolve().parents[1]
PHASE2_FIXTURE = ROOT / "data/fixtures/v230_phase2_deep_context_regression.html"
EXTRACT_GOLD = ROOT / "data/golden/v230_phase4_extract_gold_v0.1.json"
RETRIEVAL_GOLD = ROOT / "data/golden/fractuurpreventie_page15_golden_v0.1.json"
DJG = "De dJG wordt in Nederland vaker gebruikt."
ADVISEERT = (
    "De werkgroep adviseert de verpleegkundige de risicofactoren "
    "scorelijst te gebruiken bij iedere intake."
)
CALCIUM = "De werkgroep adviseert calcium te geven."
PREV_CONDITION = (
    "Bij een cliënt van 60 jaar of ouder zonder recente fractuur "
    "geldt extra aandacht voor botgezondheid."
)
CURRENT_HEADING = "2 Aanbevelingen"
PROTOCOL_REGISTER_JARGON = (
    "selected_as_candidate",
    "used_as_context",
    "linked_as_support",
    "excluded_with_reason",
    "not_yet_assessed",
    "passage_register",
    "review_burden",
    "coverage vs gold",
    "type_accuracy",
    "context_completeness",
)


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
    return {"researcher": researcher, "reviewer": reviewer}


def _ingest(console: OperationsConsole, accounts: dict, fixture: Path = PHASE2_FIXTURE, **overrides) -> dict:
    kwargs = {
        "actor_id": accounts["researcher"]["account_id"],
        "filename": fixture.name,
        "data": fixture.read_bytes(),
        "content_type": "text/html",
        "ingest_kind": "new",
        "title": "Phase 4 passage register",
        "version": "1.0",
        "date": "2025-04-01",
        "live_url": "",
        "class_": "richtlijn",
        "family": "fractuurpreventie",
        "named_reviewers": [accounts["reviewer"]["account_id"]],
    }
    kwargs.update(overrides)
    return console.ingest(**kwargs)


def _boom_freeze_bytes() -> bytes:
    payload = {
        "kind": "beslisboom-freeze",
        "paths": [{"id": "path-screening", "text": "Screening op valrisico"}],
        "nodes": [
            {
                "id": "node-vraag",
                "text": "Is er een verhoogd valrisico?",
                "scorelist": False,
            }
        ],
        "outcomes": [
            {
                "id": "out-verwijs",
                "text": "Verwijs naar de valpoli.",
                "applies_if": ["node-vraag"],
            }
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _text_of(obj: dict) -> str:
    return ((obj.get("content") or {}).get("clean_text") or obj.get("candidate_text") or "").strip()


def _admission(obj: dict) -> dict:
    return admission_of(obj)


def _find_by_text(objects: list[dict], snippet: str) -> dict:
    for obj in objects:
        if snippet in _text_of(obj):
            return obj
    raise AssertionError(f"no object contains {snippet!r}")


def _passages(objects: list[dict]) -> list[dict]:
    return [obj for obj in objects if obj.get("object_type") != "document"]


def _client(console: OperationsConsole) -> TestClient:
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "reviewer.bert", "password": "bert-secret"})
    return client


def _card(html: str, object_id: str) -> str:
    match = re.search(
        rf'<article class="[^"]*review-card[^"]*"[^>]*>.*?</article>',
        html,
        flags=re.S,
    )
    if match and object_id in match.group(0):
        return match.group(0)
    raise AssertionError("review cockpit card not found")


def _complete_adviseert_candidate(**overrides) -> dict:
    record = build_candidate_record(
        candidate_id="cand-adviseert",
        document_id="doc-phase4",
        document_version="1.0",
        source_hash="a" * 64,
        section_path=["2 Aanbevelingen"],
        source_locator_start="lines:16-16",
        source_locator_end="lines:16-16",
        source_text_exact=ADVISEERT,
        candidate_text=ADVISEERT,
        subject_span="De werkgroep",
        predicate_span="adviseert",
        proposed_type="recommendation",
        type_evidence_spans=["adviseert"],
        context_before=PREV_CONDITION,
        context_after=DJG,
        actor_of_scope="de verpleegkundige",
        recommended_action="te gebruiken",
        action_object_or_goal="de risicofactoren scorelijst",
        recommendation_evidence_span=ADVISEERT,
    )
    record.update(overrides)
    return record


# ---------------------------------------------------------------------------
# Closed register
# ---------------------------------------------------------------------------


def test_register_statuses_are_the_closed_protocol_set() -> None:
    assert PASSAGE_REGISTER_STATUSES == (
        "selected_as_candidate",
        "used_as_context",
        "linked_as_support",
        "excluded_with_reason",
        "not_yet_assessed",
    )
    assert len(set(PASSAGE_REGISTER_STATUSES)) == 5


def test_unknown_register_status_is_rejected() -> None:
    with pytest.raises((ValueError, ConsoleError), match="unknown_passage_register_status"):
        apply_passage_register(
            [
                {
                    "object_id": "obj-1",
                    "object_type": "unclassified",
                    "content": {"clean_text": ADVISEERT},
                    "metadata": {"passage_register": {"status": "dropped_silently"}},
                }
            ]
        )


def test_suitability_maps_onto_closed_register_statuses() -> None:
    assert set(SUITABILITY_VALUES) <= set(SUITABILITY_TO_REGISTER)
    assert register_status_from_suitability("ja") == "selected_as_candidate"
    assert register_status_from_suitability("mist_context") == "used_as_context"
    assert register_status_from_suitability("samenvoegen") == "used_as_context"
    assert register_status_from_suitability("alleen_onderbouwing") == "linked_as_support"
    assert register_status_from_suitability("geen_kenniseenheid") == "excluded_with_reason"
    for status in SUITABILITY_TO_REGISTER.values():
        assert status in PASSAGE_REGISTER_STATUSES


# ---------------------------------------------------------------------------
# Extract stamps every passage — MUST NOT silently drop
# ---------------------------------------------------------------------------


def test_ingest_stamps_every_passage_and_does_not_silently_drop(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    passages = _passages(objects)
    assert passages
    for obj in passages:
        register = passage_register_of(obj)
        assert register.get("status") in PASSAGE_REGISTER_STATUSES, _text_of(obj)
    assert all(passage_register_of(obj).get("status") != "dropped_silently" for obj in passages)


def test_allowed_candidate_is_selected_and_blocked_djg_is_excluded_with_reason(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    adviseert = _find_by_text(objects, ADVISEERT)
    djg = _find_by_text(objects, DJG)
    assert _admission(adviseert).get("gate_result") == GATE_ALLOWED
    assert passage_register_of(adviseert).get("status") == "selected_as_candidate"
    assert _admission(djg).get("gate_result") == GATE_BLOCKED
    assert passage_register_of(djg).get("status") == "excluded_with_reason"
    reasons = passage_register_of(djg).get("reason_codes") or _admission(djg).get("reason_codes") or []
    assert "recommendation_evidence_missing" in reasons
    ordinary = ordinary_review_queue(_passages(objects))
    assert adviseert["object_id"] in {obj["object_id"] for obj in ordinary}
    assert djg["object_id"] not in {obj["object_id"] for obj in ordinary}
    assert djg in blocked_audit_lane(objects) or djg in blocked_audit_lane(_passages(objects))


def test_context_and_heading_passages_are_registered_not_dropped(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    heading = _find_by_text(objects, CURRENT_HEADING)
    assert passage_register_of(heading).get("status") in PASSAGE_REGISTER_STATUSES
    condition = _find_by_text(objects, PREV_CONDITION)
    assert passage_register_of(condition).get("status") in PASSAGE_REGISTER_STATUSES


# ---------------------------------------------------------------------------
# Phase 3 suitability updates the register
# ---------------------------------------------------------------------------


def test_review_save_maps_suitability_onto_register(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = console.snapshot_objects(receipt["snapshot_id"])
    adviseert = _find_by_text(objects, ADVISEERT)
    calcium = _find_by_text(objects, CALCIUM)
    djg = _find_by_text(objects, DJG)
    condition = _find_by_text(objects, PREV_CONDITION)
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=adviseert["object_id"],
        decision="later",
        suitability="ja",
        eindoordeel="later_beoordelen",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=condition["object_id"],
        decision="later",
        suitability="mist_context",
        eindoordeel="later_beoordelen",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=calcium["object_id"],
        decision="later",
        suitability="alleen_onderbouwing",
        eindoordeel="later_beoordelen",
    )
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=djg["object_id"],
        decision="later",
        suitability="geen_kenniseenheid",
        eindoordeel="later_beoordelen",
    )
    live = {obj["object_id"]: obj for obj in console.snapshot_objects(receipt["snapshot_id"])}
    assert passage_register_of(live[adviseert["object_id"]]).get("status") == "selected_as_candidate"
    assert passage_register_of(live[condition["object_id"]]).get("status") == "used_as_context"
    assert passage_register_of(live[calcium["object_id"]]).get("status") == "linked_as_support"
    assert passage_register_of(live[djg["object_id"]]).get("status") == "excluded_with_reason"
    samenvoegen_target = live[adviseert["object_id"]]
    console.review_object(
        actor_id=accounts["reviewer"]["account_id"],
        snapshot_id=receipt["snapshot_id"],
        object_id=samenvoegen_target["object_id"],
        decision="later",
        suitability="samenvoegen",
        eindoordeel="later_beoordelen",
    )
    refreshed = next(
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj["object_id"] == adviseert["object_id"]
    )
    assert passage_register_of(refreshed).get("status") == "used_as_context"


# ---------------------------------------------------------------------------
# Register is not an admission prerequisite
# ---------------------------------------------------------------------------


def test_missing_register_does_not_block_phase1_admission(tmp_path: Path) -> None:
    admitted = admit_candidate(_complete_adviseert_candidate())
    assert admitted["gate_result"] == GATE_ALLOWED
    assert "passage_register" not in admitted
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    adviseert = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), ADVISEERT)
    assert _admission(adviseert).get("gate_result") == GATE_ALLOWED
    assert "passage_register" not in _admission(adviseert)
    assert passage_register_of(adviseert).get("status") == "selected_as_candidate"


def test_register_does_not_open_the_hard_gate(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    djg = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), DJG)
    assert _admission(djg).get("gate_result") == GATE_BLOCKED
    with pytest.raises(ConsoleError, match="blocked_candidate_not_reviewable"):
        console.review_object(
            actor_id=accounts["reviewer"]["account_id"],
            snapshot_id=receipt["snapshot_id"],
            object_id=djg["object_id"],
            decision="approve",
            confirmed_object_type="recommendation",
            suitability="ja",
            eindoordeel="goedkeuren",
        )


# ---------------------------------------------------------------------------
# Coverage per section
# ---------------------------------------------------------------------------


def test_coverage_is_reported_per_section_without_objectifying_every_sentence(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    report = coverage_by_section(objects)
    assert report.get("objectify_every_sentence") is False
    assert report.get("duty") == "normative_application_critical"
    sections = report.get("sections") or {}
    assert sections
    aanbevelingen = next(
        (row for key, row in sections.items() if CURRENT_HEADING in str(key) or CURRENT_HEADING in str(row)),
        None,
    )
    assert aanbevelingen is not None
    counts = aanbevelingen.get("counts") or aanbevelingen
    assert int(counts.get("selected_as_candidate") or 0) >= 1
    assert int(counts.get("excluded_with_reason") or 0) >= 1
    total = sum(int(counts.get(status) or 0) for status in PASSAGE_REGISTER_STATUSES)
    assert total >= 1


# ---------------------------------------------------------------------------
# Gold + metrics (fail-closed)
# ---------------------------------------------------------------------------


def test_extract_gold_fixture_is_structurally_valid() -> None:
    data = json.loads(EXTRACT_GOLD.read_text(encoding="utf-8"))
    report = validate_extract_gold(data)
    assert report["status"] == "PASS"
    assert report["passages"] >= 5
    assert data["kind"] == "extract_quality"
    assert data["rules"]["gold_required_before_quality_claim"] is True
    statuses = {row["expected_register_status"] for row in data["passages"]}
    assert statuses <= set(PASSAGE_REGISTER_STATUSES)
    assert "selected_as_candidate" in statuses
    assert "excluded_with_reason" in statuses


def test_existing_retrieval_golden_still_validates() -> None:
    data = json.loads(RETRIEVAL_GOLD.read_text(encoding="utf-8"))
    report = validate(data)
    assert report["status"] == "PASS"
    assert report["questions"] == 24


def test_missing_gold_cannot_claim_extract_quality(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    assert extract_quality_claim_allowed(objects, gold=None) is False
    soft = compute_extract_metrics(objects, gold=None, soft_scores={"relevant": 0.99, "complete": 0.99})
    assert soft["quality_claim_allowed"] is False
    assert soft["reason"] == "gold_standard_required"
    for name in EXTRACT_QUALITY_METRICS:
        assert soft.get(name) is None


def test_metrics_with_gold_record_the_required_hooks(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    gold = json.loads(EXTRACT_GOLD.read_text(encoding="utf-8"))
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["quality_claim_allowed"] is True
    for name in (
        "precision",
        "type_accuracy",
        "context_completeness",
        "coverage_vs_gold",
        "review_burden",
    ):
        assert name in EXTRACT_QUALITY_METRICS
        assert name in metrics
        assert metrics[name] is not None
        assert 0.0 <= float(metrics[name]) <= 1.0
    assert metrics["coverage_vs_gold"] > 0
    assert metrics["precision"] > 0


def test_soft_scores_or_single_guideline_without_gold_are_not_quality(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    claim = compute_extract_metrics(
        objects,
        gold=None,
        soft_scores={"relevant": 1.0, "understandable": 1.0},
        guideline_count=1,
    )
    assert claim["quality_claim_allowed"] is False
    assert claim["reason"] == "gold_standard_required"


# ---------------------------------------------------------------------------
# Primary reviewer UI stays ordinary Dutch
# ---------------------------------------------------------------------------


def test_primary_review_card_has_no_register_or_metrics_jargon(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    adviseert = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), ADVISEERT)
    client = _client(console)
    html = client.get(
        f"/review?document={receipt['snapshot_id']}&object={adviseert['object_id']}"
    ).text
    card = _card(html, adviseert["object_id"])
    for token in PROTOCOL_REGISTER_JARGON:
        assert token not in card
    assert "Ja" in card
    assert "mist context" in card
    assert "Review opslaan en volgende" in card


def test_researcher_ops_surface_may_show_coverage_without_touching_the_card(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    adviseert = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), ADVISEERT)
    client = _client(console)
    index = client.get(f"/review?document={receipt['snapshot_id']}").text
    card_html = client.get(
        f"/review?document={receipt['snapshot_id']}&object={adviseert['object_id']}"
    ).text
    card = _card(card_html, adviseert["object_id"])
    assert "Dekking per kop" in index
    assert "Dekking per kop" not in card
    assert "selected_as_candidate" not in card


# ---------------------------------------------------------------------------
# Non-regressions
# ---------------------------------------------------------------------------


def test_boom_path_stays_v225_and_is_not_a_richtlijn_admission_gate(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename="valrisico-boom.json",
        data=_boom_freeze_bytes(),
        content_type="application/json",
        ingest_kind="new",
        title="Valrisico boom",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="beslisboom",
        family="valrisico",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    assert objects
    types = {obj.get("proposed_object_type") or obj.get("object_type") for obj in objects}
    assert types <= set(CLOSED_BOOM_TYPES) | {"unclassified", "document"}
    for obj in objects:
        assert admission_of(obj).get("gate_result") in {None, "", GATE_ALLOWED} or not admission_of(obj)
        register = passage_register_of(obj)
        if register:
            assert register.get("status") in PASSAGE_REGISTER_STATUSES


def test_phase3_cockpit_and_sterkte_still_present(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    adviseert = _find_by_text(console.snapshot_objects(receipt["snapshot_id"]), ADVISEERT)
    client = _client(console)
    html = client.get(
        f"/review?document={receipt['snapshot_id']}&object={adviseert['object_id']}"
    ).text
    card = _card(html, adviseert["object_id"])
    assert "Gevonden onder" in card
    assert "Dit klopt" in card
    assert "Andere kop kiezen" in card
    assert "Open volledige richtlijn" in card or "broncontext" in card.lower()
    assert "geen kenniseenheid" in card
    assert is_slow_review_duty(adviseert) is True


def test_phase4_does_not_invent_serving_types() -> None:
    assert "factual_finding" not in CLOSED_OBJECT_TYPES
    assert set(CLOSED_OBJECT_TYPES) == {
        "heading",
        "definition",
        "explanation",
        "condition",
        "exception",
        "recommendation",
    }


def test_djg_still_cannot_enter_ordinary_queue_as_aanbeveling(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = _ingest(console, accounts)
    objects = _passages(console.snapshot_objects(receipt["snapshot_id"]))
    djg = _find_by_text(objects, DJG)
    assert _admission(djg).get("gate_result") == GATE_BLOCKED
    assert is_slow_review_duty(djg) is False
    assert djg not in ordinary_review_queue(objects)
