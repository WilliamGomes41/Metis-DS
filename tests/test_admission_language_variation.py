"""ROADMAP wave 4: admission-gate / regex extract on language variation.

Alternative formulations, negations, conditions, exceptions and
references MUST be measured for both false admits and misses. This is
tied to admission_gate_v1 and the extract path. Phase-4 hooks are not
this evidence. Prefer honest score-must-drop over fake-green metrics.

# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.admission_gate_v1 import GATE_ALLOWED, GATE_BLOCKED, admit_candidate, admission_of
from src.extract_metrics_v1 import measure_admission_language_variation
from src.operations_console_v1 import OperationsConsole
from src.validate_golden_set import validate_extract_gold


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_FIXTURE = ROOT / "data/fixtures/v231_wave4_language_variation.html"
LANGUAGE_GOLD = ROOT / "data/golden/v231_wave4_language_variation_gold_v0.1.json"

# Gold labels: expected_gate is independent truth, not current regex behaviour.
LANGUAGE_CASES = (
    {
        "id": "LV-ALT-01",
        "variation": "alternative_formulation",
        "proposed_type": "recommendation",
        "source_text": (
            "Het wordt aanbevolen de risicofactoren scorelijst te gebruiken bij iedere intake."
        ),
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-ALT-02",
        "variation": "alternative_formulation",
        "proposed_type": "recommendation",
        "source_text": (
            "Men dient de cliënt te verwijzen bij een vastgesteld verhoogd fractuurrisico."
        ),
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-ALT-03",
        "variation": "alternative_formulation",
        "proposed_type": "recommendation",
        "source_text": "Calciumsuppletie is geïndiceerd bij iedere intake.",
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-NEG-01",
        "variation": "negation",
        "proposed_type": "recommendation",
        "source_text": (
            "De werkgroep adviseert dit niet als klinische aanbeveling op te vatten."
        ),
        "expected_gate": GATE_BLOCKED,
        "role": "false_admit",
    },
    {
        "id": "LV-ED-01",
        "variation": "editorial",
        "proposed_type": "recommendation",
        "source_text": "De werkgroep adviseert de lezer eerst de inleiding te lezen.",
        "expected_gate": GATE_BLOCKED,
        "role": "false_admit",
    },
    {
        "id": "LV-COND-01",
        "variation": "condition",
        "proposed_type": "condition",
        "source_text": (
            "Als de cliënt 60 jaar of ouder is, geldt extra aandacht voor botgezondheid."
        ),
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-COND-02",
        "variation": "condition",
        "proposed_type": "condition",
        "source_text": "Op voorwaarde dat de cliënt 60 jaar of ouder is, geldt extra aandacht.",
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-EXC-01",
        "variation": "exception",
        "proposed_type": "exception",
        "source_text": "Met uitzondering van hypercalciëmie mag calcium worden gegeven.",
        "expected_gate": GATE_ALLOWED,
        "role": "missed_knowledge",
    },
    {
        "id": "LV-REF-01",
        "variation": "reference",
        "proposed_type": "recommendation",
        "source_text": "Zie ook module 3 voor de cutoff van het risico.",
        "expected_gate": GATE_BLOCKED,
        "role": "true_negative",
    },
    {
        "id": "LV-REF-02",
        "variation": "reference",
        "proposed_type": "recommendation",
        "source_text": "Conform tabel 4 geldt de cutoff van het risico.",
        "expected_gate": GATE_BLOCKED,
        "role": "true_negative",
    },
    {
        "id": "LV-OK-01",
        "variation": "canonical_adviseert",
        "proposed_type": "recommendation",
        "source_text": (
            "De werkgroep adviseert de verpleegkundige de risicofactoren "
            "scorelijst te gebruiken bij iedere intake."
        ),
        "expected_gate": GATE_ALLOWED,
        "role": "true_positive_expected",
    },
)

VARIATION_KINDS = {
    "alternative_formulation",
    "negation",
    "condition",
    "exception",
    "reference",
}

pytestmark = [
    pytest.mark.release_control_metrics,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


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


def test_language_variation_cases_cover_the_required_families() -> None:
    kinds = {row["variation"] for row in LANGUAGE_CASES}
    assert VARIATION_KINDS <= kinds
    assert any(row["expected_gate"] == GATE_ALLOWED for row in LANGUAGE_CASES)
    assert any(row["expected_gate"] == GATE_BLOCKED for row in LANGUAGE_CASES)
    assert any(row["role"] == "missed_knowledge" for row in LANGUAGE_CASES)
    assert any(row["role"] == "false_admit" for row in LANGUAGE_CASES)


def test_measure_admission_language_variation_counts_false_admits_and_misses() -> None:
    report = measure_admission_language_variation(LANGUAGE_CASES)
    assert report["false_admits"]
    assert report["misses"]
    # Teller/noemer: precision = true_admits / (true_admits + false_admits)
    true_admits = len(report["true_admits"])
    false_admits = len(report["false_admits"])
    misses = len(report["misses"])
    assert report["true_positives"] == true_admits
    assert report["false_positives"] == false_admits
    assert report["false_negatives"] == misses
    assert report["precision"] == round(true_admits / (true_admits + false_admits), 3)
    assert report["recall"] == round(true_admits / (true_admits + misses), 3)
    # Score-must-drop: regex/rule extract is not complete Dutch coverage.
    assert report["precision"] < 1.0
    assert report["recall"] < 1.0


def test_language_variation_ties_to_admission_gate_v1() -> None:
    report = measure_admission_language_variation(LANGUAGE_CASES)
    by_id = {row["id"]: row for row in report["cases"]}
    assert by_id["LV-ALT-01"]["live_gate"] == GATE_BLOCKED
    assert by_id["LV-ALT-01"]["outcome"] == "miss"
    assert by_id["LV-NEG-01"]["live_gate"] == GATE_ALLOWED
    assert by_id["LV-NEG-01"]["outcome"] == "false_admit"
    assert by_id["LV-ED-01"]["live_gate"] == GATE_ALLOWED
    assert by_id["LV-ED-01"]["outcome"] == "false_admit"
    assert by_id["LV-OK-01"]["live_gate"] == GATE_ALLOWED
    assert by_id["LV-OK-01"]["outcome"] == "true_admit"
    assert by_id["LV-REF-01"]["live_gate"] == GATE_BLOCKED
    assert by_id["LV-REF-01"]["outcome"] == "true_block"


def test_language_variation_gold_and_fixture_exist() -> None:
    assert LANGUAGE_FIXTURE.is_file()
    assert LANGUAGE_GOLD.is_file()
    html = LANGUAGE_FIXTURE.read_text(encoding="utf-8")
    gold = json.loads(LANGUAGE_GOLD.read_text(encoding="utf-8"))
    report = validate_extract_gold(gold)
    assert report["status"] == "PASS"
    kinds = {row.get("variation") for row in gold["passages"]}
    assert VARIATION_KINDS <= kinds
    for row in LANGUAGE_CASES:
        assert row["source_text"] in html
        assert any(item["id"] == row["id"] for item in gold["passages"])


def test_extract_path_language_variation_measures_false_admits_and_misses(tmp_path: Path) -> None:
    console = _console(tmp_path)
    accounts = _accounts(console)
    receipt = console.ingest(
        actor_id=accounts["researcher"]["account_id"],
        filename=LANGUAGE_FIXTURE.name,
        data=LANGUAGE_FIXTURE.read_bytes(),
        content_type="text/html",
        ingest_kind="new",
        title="Wave 4 language variation",
        version="1.0",
        date="2025-04-01",
        live_url="",
        class_="richtlijn",
        family="fractuurpreventie",
        named_reviewers=[accounts["reviewer"]["account_id"]],
    )
    objects = [
        obj
        for obj in console.snapshot_objects(receipt["snapshot_id"])
        if obj.get("object_type") != "document"
    ]
    gold = json.loads(LANGUAGE_GOLD.read_text(encoding="utf-8"))
    report = measure_admission_language_variation(gold=gold, objects=objects)
    assert report["false_admits"] or report["misses"]
    assert report["precision"] < 1.0 or report["recall"] < 1.0
    admitted = [
        obj
        for obj in objects
        if admission_of(obj).get("gate_result") == GATE_ALLOWED
    ]
    assert admitted or report["misses"]
    for obj in objects:
        if admission_of(obj):
            assert "admission_gate_v1" not in str(obj.get("object_id") or "")


def test_measure_from_language_gold_is_idempotent() -> None:
    first = measure_admission_language_variation(LANGUAGE_CASES)
    second = measure_admission_language_variation(LANGUAGE_CASES)
    assert first == second


def test_admit_candidate_still_decides_each_language_case() -> None:
    from src.admission_gate_v1 import build_candidate_record

    for row in LANGUAGE_CASES:
        candidate = build_candidate_record(
            candidate_id=row["id"],
            document_id="doc-lang",
            document_version="1.0",
            source_hash="b" * 64,
            section_path=["2 Aanbevelingen"],
            source_locator_start="lines:1-1",
            source_locator_end="lines:1-1",
            source_text_exact=row["source_text"],
            candidate_text=row["source_text"],
            proposed_type=row["proposed_type"],
            context_before="Vorige alinea over de doelgroep.",
            context_after="Volgende alinea over vervolgonderzoek.",
        )
        admitted = admit_candidate(candidate)
        assert admitted["gate_result"] in {GATE_ALLOWED, GATE_BLOCKED}
