"""ROADMAP wave 5: gericht vereenvoudigen.

Locks fail-closed admission/console behaviour that local simplification
must not change, plus the compactness / complexity bar this wave must
land. PROTOCOL.md and docs/PROTOCOL_V2_* are not edited. publish() stays
G2-BLOCKED. No wave 6. No store/session change.

# release-control-evidence: kwaliteit
# release-control-evidence: toegang
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.admission_gate_v1 import (
    GATE_ALLOWED,
    GATE_BLOCKED,
    admit_candidate,
    build_candidate_record,
    is_admission_blocked,
    ordinary_review_queue,
)
from src.operations_console_app import (
    _heading_chooser,
    _unpublished_delete_control,
    create_console_app,
)
from src.operations_console_v1 import OperationsConsole


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "src/operations_console_app.py"
GATE_SOURCE = ROOT / "src/admission_gate_v1.py"
DJG = "De dJG wordt in Nederland vaker gebruikt."
ADVISEERT = (
    "De werkgroep adviseert de verpleegkundige de risicofactoren "
    "scorelijst te gebruiken bij iedere intake."
)
LONE_EXCEPTION = "Tenzij er een recente fractuur is vastgesteld."
ONE_WORD = "Scorelijst."
IMPLIED = "impliciet de verpleegkundige"

pytestmark = [
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def _complexity(source: str, name: str) -> int:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            count = 1
            for child in ast.walk(node):
                if isinstance(
                    child,
                    (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert),
                ):
                    count += 1
                elif isinstance(child, ast.BoolOp):
                    count += max(0, len(child.values) - 1)
                elif isinstance(child, ast.comprehension):
                    count += 1
                elif isinstance(child, ast.IfExp):
                    count += 1
            return count
    raise AssertionError(f"function {name} not found")


def _complete_adviseert(**overrides: Any) -> dict[str, Any]:
    record = build_candidate_record(
        candidate_id="cand-adviseert",
        document_id="doc-wave5",
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
        context_before="Deze richtlijn beschrijft signalering van fractuurrisico.",
        context_after=DJG,
        actor_of_scope="de verpleegkundige",
        recommended_action="te gebruiken",
        action_object_or_goal="de risicofactoren scorelijst",
        recommendation_evidence_span=ADVISEERT,
    )
    record.update(overrides)
    return record


def _djg_candidate(**overrides: Any) -> dict[str, Any]:
    record = build_candidate_record(
        candidate_id="cand-djg",
        document_id="doc-wave5",
        document_version="1.0",
        source_hash="a" * 64,
        section_path=["2 Aanbevelingen"],
        source_locator_start="lines:17-17",
        source_locator_end="lines:17-17",
        source_text_exact=DJG,
        candidate_text=DJG,
        subject_span="De dJG",
        predicate_span="wordt",
        proposed_type="recommendation",
        type_evidence_spans=[],
        context_before=ADVISEERT,
        context_after=ONE_WORD,
    )
    record.update(overrides)
    return record


def _queue_row(object_id: str, admitted: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "unclassified",
        "proposed_object_type": admitted.get("proposed_type") or "recommendation",
        "content": {"clean_text": text},
        "metadata": {"admission": admitted},
    }


def _heading(object_id: str, text: str) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "heading",
        "proposed_object_type": "heading",
        "content": {"heading": text, "clean_text": text},
        "structure": {"heading": text, "section_path": [text]},
        "provenance": {"source_locator": {"locator_value": text}},
    }


# ---------------------------------------------------------------------------
# Fail-closed pins (must stay identical after simplify)
# ---------------------------------------------------------------------------


def test_soft_scores_must_not_open_blocked_admission() -> None:
    blocked = admit_candidate(
        _djg_candidate(),
        soft_scores={"relevant": 1.0, "complete": 1.0, "understandable": 1.0},
    )
    assert blocked["gate_result"] == GATE_BLOCKED
    assert blocked["gate_result"] != GATE_ALLOWED
    for code in (
        "recommendation_evidence_missing",
        "comparison_target_missing",
        "abbreviation_unresolved",
    ):
        assert code in blocked["reason_codes"], code
    assert ordinary_review_queue([_queue_row("djg-1", blocked, DJG)]) == []
    assert is_admission_blocked(_queue_row("djg-1", blocked, DJG)) is True


def test_impliciet_filler_and_invented_spans_stay_source_fidelity_failures() -> None:
    impliciet = admit_candidate(_complete_adviseert(actor_of_scope=IMPLIED))
    assert impliciet["gate_result"] == GATE_BLOCKED
    assert "source_fidelity_failure" in impliciet["reason_codes"]

    invented = admit_candidate(
        _complete_adviseert(
            predicate_span="IMPLIED-VERB",
            type_evidence_spans=["IMPLIED-EVIDENCE"],
            actor_of_scope="niet in de bron aanwezige actor",
            recommended_action="verzinnen",
            action_object_or_goal="verzonnen doel",
            recommendation_evidence_span="verzonnen bewijs dat adviseert",
        )
    )
    assert invented["gate_result"] == GATE_BLOCKED
    assert "source_fidelity_failure" in invented["reason_codes"]
    assert "span_not_in_source" in invented["reason_codes"]


def test_lone_exception_and_missing_locator_stay_blocked() -> None:
    lone = admit_candidate(
        _djg_candidate(
            candidate_id="cand-lone-exc",
            source_text_exact=LONE_EXCEPTION,
            candidate_text=LONE_EXCEPTION,
            subject_span="",
            predicate_span="Tenzij",
            proposed_type="exception",
            type_evidence_spans=["Tenzij"],
            exception_span=LONE_EXCEPTION,
            exception_target="",
        )
    )
    assert lone["gate_result"] == GATE_BLOCKED
    assert "exception_target_missing" in lone["reason_codes"]
    assert "no_independent_claim" in lone["reason_codes"]

    missing_locator = admit_candidate(
        _complete_adviseert(
            source_locator_start="",
            source_locator_end="",
        )
    )
    assert missing_locator["gate_result"] == GATE_BLOCKED
    assert "locator_invalid" in missing_locator["reason_codes"]


def test_complete_adviseert_stays_allowed_and_boom_is_not_gated() -> None:
    allowed = admit_candidate(_complete_adviseert())
    assert allowed["gate_result"] == GATE_ALLOWED
    assert allowed["reason_codes"] == []
    queue = ordinary_review_queue([_queue_row("rec-ok", allowed, ADVISEERT)])
    assert [row["object_id"] for row in queue] == ["rec-ok"]

    boom = {
        "object_id": "boom-1",
        "object_type": "outcome",
        "proposed_object_type": "outcome",
        "confirmed_object_type": "outcome",
        "metadata": {"admission": {"gate_result": GATE_BLOCKED, "reason_codes": ["type_contract_incomplete"]}},
    }
    assert is_admission_blocked(boom, review_path="boom") is False


def test_heading_chooser_omits_radio_for_self_and_structurally_invalid_parent() -> None:
    child = _heading("h-541", "5.4.1 Anamnese")
    nearby_two = _heading("h-2", "2 Doel")
    structural = _heading("h-54", "5.4 Diagnostiek")
    objects = [nearby_two, structural, child]
    html = _heading_chooser(child, objects, "snap-wave5")
    assert 'data-heading-role="body"' in html
    assert 'name="parent_choice" value="h-54"' in html
    assert 'name="parent_choice" value="h-2"' not in html
    assert 'name="parent_choice" value="h-541"' not in html


def test_unpublished_delete_control_stays_tree_only(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
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
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="wave5.html",
        data=(
            "<!doctype html><html lang='nl'><head><title>Wave5</title></head>"
            "<body><h1>Wave5</h1><p>De werkgroep adviseert de verpleegkundige "
            "de risicofactoren scorelijst te gebruiken bij iedere intake.</p>"
            "</body></html>"
        ).encode("utf-8"),
        content_type="text/html",
        ingest_kind="new",
        title="Wave5 delete fixture",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="richtlijn",
        family="wave5",
        named_reviewers=[reviewer["account_id"]],
    )
    row = {
        "snapshot_id": receipt["snapshot_id"],
        "title": "Wave5 delete fixture",
        "state": "captured_not_published",
    }
    tree = _unpublished_delete_control(
        row, account=researcher, console=console, next_path="/tree"
    )
    assert "Verwijder unpublished document" in tree
    assert 'name="confirm_title"' in tree
    for other in ("/review", "/ingest", "/publish", "/accounts"):
        assert _unpublished_delete_control(
            row, account=researcher, console=console, next_path=other
        ) == ""


def test_blocked_candidates_stay_out_of_ordinary_review_lane(tmp_path: Path) -> None:
    console = OperationsConsole(
        root=tmp_path,
        source_store=tmp_path / "sources" / "private",
        runtime=tmp_path / "output" / "runtime" / "operations-console",
    )
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
    fixture = ROOT / "data/fixtures/v230_phase1_admission_regression.html"
    receipt = console.ingest(
        actor_id=researcher["account_id"],
        filename="phase1.html",
        data=fixture.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Phase 1 admission regression",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="richtlijn",
        family="fractuurpreventie",
        named_reviewers=[reviewer["account_id"]],
    )
    client = TestClient(create_console_app(console))
    client.post("/login", data={"username": "researcher.anne", "password": "anne-secret"})
    review = client.get(f"/review?document={receipt['snapshot_id']}").text
    slow = review.split('class="review-lane-slow"', 1)[-1].split("review-blocked-audit", 1)[0]
    assert DJG not in slow
    assert "review-blocked-audit" in review
    assert DJG in review.split("review-blocked-audit", 1)[-1]


# ---------------------------------------------------------------------------
# Compactness / complexity bar (red on current main; green after wave 5)
# ---------------------------------------------------------------------------


def test_roadmap_live_norm_is_readable_and_historical_stacks_are_demoted() -> None:
    roadmap = _read(ROOT / "ROADMAP.md")
    changelog = _read(ROOT / "CHANGELOG.md")
    assert "## Geldende norm (live)" in roadmap
    assert "Historische supersessie-index" in roadmap
    niet = _section(roadmap, "## Niet-onderhandelbare doelen", "## Vastgestelde architectuurclusters")
    assert len(niet) < 9000, f"Niet-onderhandelbare doelen still a supersession stack ({len(niet)} chars)"
    cluster2 = _section(roadmap, "| 2 | Open-origineel", "| 3 | Levenscyclus")
    assert len(cluster2) < 3000, f"cluster 2 cell still restates the stack ({len(cluster2)} chars)"
    fase1 = _section(roadmap, "### Fase 1 —", "- Gezaghebbende remote")
    assert len(fase1) < 7000, f"Fase 1 status still a supersession stack ({len(fase1)} chars)"
    assert "Gericht vereenvoudigen" in roadmap
    assert "geen volledige herschrijving" in roadmap
    assert "Die vereenvoudigingsgolf is in code" in roadmap
    assert "wave 5" in changelog.lower() or "golf 5" in changelog.lower()
    assert "MUST NOT G2/`publish()` openen" in roadmap
    assert "HANDOFF.md MUST NOT opnieuw worden aangemaakt" in roadmap
    assert not (ROOT / "HANDOFF.md").exists()
    assert "De geldende normatieve baseline is Protocol v2.31.0" in _read(ROOT / "PROTOCOL.md")
    assert not (ROOT / "docs" / "PROTOCOL_V2_32_RELIABILITY_EVIDENCE_BACKLOG_DELTA.md").exists()


def test_named_console_and_admission_hotspots_are_locally_simpler() -> None:
    app = _read(APP_SOURCE)
    gate = _read(GATE_SOURCE)
    assert _complexity(gate, "admit_candidate") < 70
    assert _complexity(gate, "_enrich_from_text") < 50
    assert _complexity(app, "_render_review_room") < 45
    assert _complexity(app, "_heading_chooser") < 14
    assert app.count('data-heading-role="body"') <= 2
    assert gate.count('"exception_target_missing"') <= 2
    assert "PROTOCOL.md" not in APP_SOURCE.read_text(encoding="utf-8")[:80]
    assert not (ROOT / "HANDOFF.md").exists()
