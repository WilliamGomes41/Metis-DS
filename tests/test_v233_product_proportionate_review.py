from __future__ import annotations

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from copy import deepcopy
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.passage_register_v1 import apply_passage_register, passage_register_of
from src.proportionate_review_v1 import (
    ProportionateReviewConsole,
    install_proportionate_review_routes,
    normal_risk_batch_eligible,
    normal_risk_batch_queue,
    regular_review_queue,
    render_normal_risk_batch_panel,
)
from src.operations_console_v1 import ConsoleError


def _obj(
    object_id: str,
    proposed_type: str,
    *,
    gate: str = "allowed",
    high: bool = False,
    second: bool = False,
    uncertain: bool = False,
    section: tuple[str, ...] = ("1 Achtergrond",),
) -> dict:
    return {
        "object_id": object_id,
        "object_version": "1.0",
        "object_type": "unclassified",
        "proposed_object_type": proposed_type,
        "content": {"clean_text": f"Inhoud {object_id}."},
        "structure": {"section_path": list(section)},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "proposed_type": proposed_type,
                "section_path": list(section),
                "reason_codes": ["machine_reason"] if gate == "blocked" else [],
            }
        },
        "risk": {
            "level": "high" if high else "standard",
            "requires_second_review": second,
        },
        "uncertainty": {
            "has_uncertainty": uncertain,
            "items": ["onduidelijk"] if uncertain else [],
        },
        "governance": {
            "validation_status": "needs_review",
            "review_track": "clinical",
        },
    }


def test_admission_blocked_is_open_work_not_substantive_exclusion() -> None:
    row = apply_passage_register([_obj("blocked", "recommendation", gate="blocked")])[0]
    register = passage_register_of(row)
    assert register["status"] == "not_yet_assessed"
    assert register["source"] == "extract"
    assert register["reason_codes"] == ["machine_reason"]


def test_human_exclusion_remains_authoritative_after_register_refresh() -> None:
    row = _obj("blocked", "recommendation", gate="blocked")
    row["metadata"]["passage_register"] = {
        "status": "excluded_with_reason",
        "reason_codes": ["geen_kenniseenheid"],
        "suitability": "geen_kenniseenheid",
        "source": "review",
        "linked_object_id": "",
        "section_path": ["1 Achtergrond"],
    }
    refreshed = apply_passage_register([row])[0]
    assert passage_register_of(refreshed)["status"] == "excluded_with_reason"
    assert passage_register_of(refreshed)["source"] == "review"


def test_regular_review_queue_is_broader_than_priority_duty_but_still_fail_closed() -> None:
    definition = _obj("definition", "definition")
    explanation = _obj("explanation", "explanation")
    recommendation = _obj("recommendation", "recommendation")
    blocked = _obj("blocked", "definition", gate="blocked")
    heading = _obj("heading", "heading")
    ids = {
        row["object_id"]
        for row in regular_review_queue(
            [definition, explanation, recommendation, blocked, heading],
            review_path="richtlijn",
        )
    }
    assert ids == {"definition", "explanation", "recommendation"}


def test_normal_risk_batch_excludes_action_high_risk_second_review_blocked_and_uncertain() -> None:
    eligible = _obj("definition", "definition")
    explanation = _obj("explanation", "explanation")
    recommendation = _obj("recommendation", "recommendation")
    high = _obj("high", "definition", high=True)
    second = _obj("second", "definition", second=True)
    blocked = _obj("blocked", "definition", gate="blocked")
    uncertain = _obj("uncertain", "definition", uncertain=True)
    rows = [eligible, explanation, recommendation, high, second, blocked, uncertain]
    assert normal_risk_batch_eligible(eligible, review_path="richtlijn") is True
    assert normal_risk_batch_eligible(explanation, review_path="richtlijn") is True
    assert normal_risk_batch_eligible(uncertain, review_path="richtlijn") is False
    assert [row["object_id"] for row in normal_risk_batch_queue(rows, review_path="richtlijn")] == [
        "definition",
        "explanation",
    ]


class _BatchHarness(ProportionateReviewConsole):
    def __init__(self, objects: list[dict]) -> None:
        self._objects = {row["object_id"]: deepcopy(row) for row in objects}
        self.calls: list[dict] = []
        self.opened: list[str] = []
        self.revision = "rev-1"

    def _require_role(self, actor_id: str, role: str) -> dict:
        assert actor_id == "reviewer-1"
        assert role == "reviewer"
        return {"account_id": actor_id, "username": "reviewer.one"}

    def _envelope(self, snapshot_id: str) -> dict:
        assert snapshot_id == "snap-1"
        return {"class": "richtlijn", "named_reviewers": ["reviewer-1"]}

    def snapshot_objects(self, snapshot_id: str, *args, **kwargs) -> list[dict]:
        assert snapshot_id == "snap-1"
        return [deepcopy(row) for row in self._objects.values()]

    def _require_open_original(self, snapshot_id: str, object_id: str) -> dict:
        self.opened.append(object_id)
        return {"passage": object_id}

    def review_object(self, **kwargs) -> list[dict]:
        self.calls.append(dict(kwargs))
        object_id = kwargs["object_id"]
        row = self._objects[object_id]
        row["confirmed_object_type"] = kwargs["confirmed_object_type"]
        row["object_type"] = kwargs["confirmed_object_type"]
        row["governance"]["validation_status"] = "approved"
        self.revision = f"rev-{len(self.calls) + 1}"
        return self.snapshot_objects("snap-1")

    def objects_revision(self, snapshot_id: str) -> str:
        assert snapshot_id == "snap-1"
        return self.revision


def test_one_batch_interaction_delegates_to_individual_object_reviews() -> None:
    console = _BatchHarness([
        _obj("d1", "definition"),
        _obj("e1", "explanation"),
    ])
    updated = console.batch_review_normal_risk(
        actor_id="reviewer-1",
        snapshot_id="snap-1",
        object_ids=["d1", "e1"],
        expected_revision="rev-1",
    )
    assert console.opened == ["d1", "e1"]
    assert [call["object_id"] for call in console.calls] == ["d1", "e1"]
    assert [call["decision"] for call in console.calls] == ["approve", "approve"]
    assert [call["confirmed_object_type"] for call in console.calls] == ["definition", "explanation"]
    assert all(call["suitability"] == "ja" for call in console.calls)
    assert [call["expected_revision"] for call in console.calls] == ["rev-1", "rev-2"]
    assert {row["object_id"] for row in updated} == {"d1", "e1"}


def test_batch_preflights_all_objects_before_writing() -> None:
    console = _BatchHarness([
        _obj("d1", "definition"),
        _obj("high", "definition", high=True),
    ])
    with pytest.raises(ConsoleError, match="normal_risk_batch_ineligible"):
        console.batch_review_normal_risk(
            actor_id="reviewer-1",
            snapshot_id="snap-1",
            object_ids=["d1", "high"],
        )
    assert console.calls == []
    assert console.opened == []


def test_batch_cannot_cross_sections() -> None:
    console = _BatchHarness([
        _obj("d1", "definition", section=("1 Achtergrond",)),
        _obj("e1", "explanation", section=("2 Uitwerking",)),
    ])
    with pytest.raises(ConsoleError, match="normal_risk_batch_mixed_section"):
        console.batch_review_normal_risk(
            actor_id="reviewer-1",
            snapshot_id="snap-1",
            object_ids=["d1", "e1"],
        )
    assert console.calls == []


def test_rendered_batch_panel_exposes_only_eligible_normal_risk_items() -> None:
    console = _BatchHarness([
        _obj("d1", "definition"),
        _obj("e1", "explanation"),
        _obj("r1", "recommendation"),
        _obj("u1", "definition", uncertain=True),
    ])
    html = render_normal_risk_batch_panel(console, "snap-1")
    assert 'action="/review/normal-risk/batch-confirm"' in html
    assert 'value="d1"' in html
    assert 'value="e1"' in html
    assert 'value="r1"' not in html
    assert 'value="u1"' not in html
    assert "Reguliere inhoud beoordelen" in html


def test_review_index_middleware_makes_batch_work_reachable() -> None:
    console = _BatchHarness([_obj("d1", "definition")])
    app = FastAPI()

    @app.get("/review", response_class=HTMLResponse)
    async def review_index() -> HTMLResponse:
        return HTMLResponse("<html><body><main><h1>Beoordelen</h1></main></body></html>")

    install_proportionate_review_routes(app, console)
    response = TestClient(app).get("/review?document=snap-1")
    assert response.status_code == 200
    assert "Reguliere inhoud beoordelen" in response.text
    assert "/review/normal-risk/batch-confirm" in response.text
    assert 'name="object_ids"' in response.text


def test_source_contains_no_new_store_or_review_tier() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "proportionate_review_v1.py").read_text(encoding="utf-8")
    assert "light/standard/strict" not in source
    assert "use_scope" not in source
    assert "new database" not in source.lower()
