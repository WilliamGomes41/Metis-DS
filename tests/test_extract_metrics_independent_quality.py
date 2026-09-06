"""ROADMAP wave 4: independent extract-quality measurement.

Metric definitions in extract_metrics_v1 MUST count false positives,
MUST NOT treat context_scan_done alone as completeness, and MUST NOT
let every non-empty fixture open a quality claim. Phase-4 register
hooks are not this evidence.

Gold/metrics are read-mostly. There is no runtime writer for gold or
metric files in this module (concurrency/interrupt n.v.t. on writes;
half-written gold JSON MUST fail closed). Metric runs are idempotent.
Old extract-gold schema stays readable; unsupported schema fail-closed.

# release-control-evidence: metrics teller noemer score-must-drop
# release-control-evidence: kwaliteit
# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from src.extract_metrics_v1 import (
    EXTRACT_QUALITY_METRICS,
    ExtractGoldError,
    compute_extract_metrics,
    extract_quality_claim_allowed,
    gold_supports_independent_quality_claim,
    load_extract_gold,
)
from src.validate_golden_set import validate_extract_gold


ROOT = Path(__file__).resolve().parents[1]
PHASE4_GOLD = ROOT / "data/golden/v230_phase4_extract_gold_v0.1.json"
INDEPENDENT_GOLD = ROOT / "data/golden/v231_wave4_independent_extract_gold_v0.1.json"
EXTRACT_HOLDOUT = ROOT / "data/holdout/v231_wave4_extract_holdout_v0.1.json"
EXTRACT_HOLDOUT_LOCK = ROOT / "data/holdout/v231_wave4_extract_holdout_v0.1.lock.json"
RETRIEVAL_HOLDOUT = ROOT / "data/holdout/fractuurpreventie_page15_holdout_v1.1.json"
PHASE2_FIXTURE = ROOT / "data/fixtures/v230_phase2_deep_context_regression.html"
CONTINENTIE_FIXTURE = ROOT / "data/fixtures/continentie_v221_wave_a_regression.html"

TRUE_A = "De werkgroep adviseert de verpleegkundige de risicofactoren scorelijst te gebruiken bij iedere intake."
TRUE_B = "De werkgroep adviseert calcium te geven."
FALSE_C = "De werkgroep adviseert de lezer eerst de inleiding te lezen."
EXCLUDED_D = "De dJG wordt in Nederland vaker gebruikt."

pytestmark = [
    pytest.mark.release_control_metrics,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _obj(
    text: str,
    *,
    selected: bool = True,
    scan_done: bool = False,
    before: str = "",
    after: str = "",
    gate: str = "allowed",
    object_type: str = "recommendation",
) -> dict:
    status = "selected_as_candidate" if selected else "excluded_with_reason"
    return {
        "object_id": f"obj-{abs(hash(text)) % 10_000_000}",
        "object_type": object_type,
        "proposed_object_type": object_type,
        "content": {"clean_text": text},
        "metadata": {
            "admission": {
                "gate_result": gate,
                "proposed_type": object_type,
                "context_scan_done": scan_done,
                "context_before": before,
                "context_after": after,
                "context_scan": {
                    "context_scan_done": scan_done,
                    "previous_paragraph": before,
                    "next_paragraph": after,
                },
            },
            "passage_register": {
                "status": status,
                "source": "review",
                "reason_codes": [],
                "suitability": "ja" if selected else "geen_kenniseenheid",
            },
        },
    }


def _gold(*rows: dict) -> dict:
    return {
        "golden_set_id": "inline-metric-gold",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "passages": list(rows),
    }


def _selected_row(text: str, row_id: str) -> dict:
    return {
        "id": row_id,
        "class": "normative",
        "section": "2 Aanbevelingen",
        "source_text": text,
        "expected_register_status": "selected_as_candidate",
        "expected_type": "recommendation",
        "expected_gate": "allowed",
    }


def _excluded_row(text: str, row_id: str) -> dict:
    return {
        "id": row_id,
        "class": "excluded",
        "section": "2 Aanbevelingen",
        "source_text": text,
        "expected_register_status": "excluded_with_reason",
        "expected_gate": "blocked",
    }


# ---------------------------------------------------------------------------
# Precision: teller/noemer must include false positives (score-must-drop)
# ---------------------------------------------------------------------------


def test_precision_counts_false_positives_in_the_denominator() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"), _selected_row(TRUE_B, "G-B"))
    objects = [
        _obj(TRUE_A, selected=True),
        _obj(TRUE_B, selected=True),
        _obj(FALSE_C, selected=True),
    ]
    metrics = compute_extract_metrics(objects, gold=gold)
    # Teller = true positives (2). Noemer = TP + FP (3). Score-must-drop from 1.0.
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 1
    assert metrics["precision"] == round(2 / 3, 3)
    assert metrics["precision"] < 1.0


def test_precision_counts_admitted_excluded_gold_as_false_positive() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"), _excluded_row(EXCLUDED_D, "G-X"))
    objects = [
        _obj(TRUE_A, selected=True),
        _obj(EXCLUDED_D, selected=True, gate="allowed"),
    ]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["true_positives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["precision"] < 1.0


def test_missed_gold_selected_is_a_false_negative_not_a_precision_hit() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"), _selected_row(TRUE_B, "G-B"))
    objects = [_obj(TRUE_A, selected=True)]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["true_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["false_positives"] == 0
    assert metrics["precision"] == 1.0
    assert metrics["coverage_vs_gold"] < 1.0


# ---------------------------------------------------------------------------
# context_completeness MUST NOT treat the scan flag as completeness
# ---------------------------------------------------------------------------


def test_context_completeness_does_not_treat_scan_done_alone_as_complete() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"))
    objects = [_obj(TRUE_A, selected=True, scan_done=True, before="", after="")]
    metrics = compute_extract_metrics(objects, gold=gold)
    # Score-must-drop: scan flag alone is not captured context.
    assert metrics["context_completeness"] == 0.0


def test_context_completeness_requires_captured_neighbor_context() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"))
    complete = _obj(
        TRUE_A,
        selected=True,
        scan_done=True,
        before="Bij een cliënt van 60 jaar of ouder geldt extra aandacht.",
        after="Tenzij er hypercalciëmie bestaat.",
    )
    metrics = compute_extract_metrics([complete], gold=gold)
    assert metrics["context_completeness"] == 1.0


# ---------------------------------------------------------------------------
# Quality claim: independent/representative gold, not every fixture
# ---------------------------------------------------------------------------


def test_phase4_fixture_gold_cannot_claim_independent_quality() -> None:
    gold = json.loads(PHASE4_GOLD.read_text(encoding="utf-8"))
    assert gold["status"] == "fixture_gold"
    assert gold_supports_independent_quality_claim(gold) is False
    assert extract_quality_claim_allowed([], gold=gold) is False
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=gold)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["reason"] == "independent_representative_gold_required"
    assert metrics["precision"] is not None


def test_any_nonempty_fixture_passages_cannot_claim_quality() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"))
    assert extract_quality_claim_allowed([_obj(TRUE_A)], gold=gold) is False
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=gold)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["reason"] == "independent_representative_gold_required"


def test_missing_gold_still_fail_closed() -> None:
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=None)
    assert extract_quality_claim_allowed([_obj(TRUE_A)], gold=None) is False
    assert metrics["quality_claim_allowed"] is False
    assert metrics["reason"] == "gold_standard_required"
    for name in EXTRACT_QUALITY_METRICS:
        assert metrics[name] is None


def test_unsupported_gold_schema_fail_closed() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "9.0",
        "status": "independent_representative",
        "passages": [_selected_row(TRUE_A, "G-A")],
    }
    assert gold_supports_independent_quality_claim(gold) is False
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=gold)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["reason"] == "gold_schema_unsupported"


def test_old_extract_gold_schema_is_readable_but_claim_fail_closed() -> None:
    gold = load_extract_gold(PHASE4_GOLD)
    report = validate_extract_gold(gold)
    assert report["status"] == "PASS"
    assert gold["kind"] == "extract_quality"
    assert gold["version"] == "0.1"
    assert extract_quality_claim_allowed([], gold=gold) is False


# ---------------------------------------------------------------------------
# Multi-source gold + holdout on real richtlijnen
# ---------------------------------------------------------------------------


def test_independent_multi_source_gold_exists_and_validates() -> None:
    assert INDEPENDENT_GOLD.is_file()
    gold = load_extract_gold(INDEPENDENT_GOLD)
    report = validate_extract_gold(gold)
    assert report["status"] == "PASS"
    assert gold["kind"] == "extract_quality"
    assert gold["status"] == "independent_representative"
    assert gold["independence"]["independent"] is True
    assert gold["independence"]["representative"] is True
    assert gold["independence"]["phase4_hooks_are_not_this_evidence"] is True
    sources = gold["sources"]
    assert len(sources) >= 2
    fixtures = {str(row.get("fixture") or "") for row in sources}
    assert "data/fixtures/v230_phase2_deep_context_regression.html" in fixtures
    assert "data/fixtures/continentie_v221_wave_a_regression.html" in fixtures
    assert PHASE2_FIXTURE.is_file()
    assert CONTINENTIE_FIXTURE.is_file()
    assert gold["golden_set_id"] != "v230-phase4-extract-gold-v0.1"


def test_independent_gold_includes_missed_knowledge_and_false_admits() -> None:
    gold = load_extract_gold(INDEPENDENT_GOLD)
    roles = {str(row.get("role") or row.get("class") or "") for row in gold["passages"]}
    assert "missed_knowledge" in roles or "missed" in roles
    assert "false_admit" in roles
    missed = [
        row
        for row in gold["passages"]
        if row.get("role") == "missed_knowledge" or row.get("class") == "missed"
    ]
    false_admits = [row for row in gold["passages"] if row.get("role") == "false_admit" or row.get("class") == "false_admit"]
    assert missed
    assert false_admits
    source_ids = {row.get("source_id") for row in gold["passages"]}
    assert len(source_ids) >= 2
    assert gold_supports_independent_quality_claim(gold) is True
    assert extract_quality_claim_allowed([], gold=gold) is True


def test_independent_gold_is_not_the_phase4_register_fixture() -> None:
    phase4 = json.loads(PHASE4_GOLD.read_text(encoding="utf-8"))
    gold = load_extract_gold(INDEPENDENT_GOLD)
    assert gold["golden_set_id"] != phase4["golden_set_id"]
    assert gold["source_fixture"] != phase4.get("source_fixture")
    assert set(gold.get("source_fixtures") or []) != {phase4.get("source_fixture")}
    phase4_texts = {row["source_text"] for row in phase4["passages"]}
    gold_texts = {row["source_text"] for row in gold["passages"]}
    assert not gold_texts <= phase4_texts


def test_extract_holdout_exists_beyond_retrieval_holdouts() -> None:
    assert EXTRACT_HOLDOUT.is_file()
    assert EXTRACT_HOLDOUT_LOCK.is_file()
    assert EXTRACT_HOLDOUT.resolve() != RETRIEVAL_HOLDOUT.resolve()
    holdout = load_extract_gold(EXTRACT_HOLDOUT)
    report = validate_extract_gold(holdout)
    assert report["status"] == "PASS"
    assert holdout["kind"] == "extract_quality"
    assert holdout["status"] == "locked_holdout"
    assert holdout["rules"]["must_not_tune_on_this_set"] is True
    lock = json.loads(EXTRACT_HOLDOUT_LOCK.read_text(encoding="utf-8"))
    assert lock["holdout_file"].endswith("v231_wave4_extract_holdout_v0.1.json")
    assert lock["sha256"]


def test_holdout_includes_missed_and_false_admits_from_multiple_sources() -> None:
    holdout = load_extract_gold(EXTRACT_HOLDOUT)
    sources = holdout["sources"]
    assert len(sources) >= 2
    roles = {str(row.get("role") or row.get("class") or "") for row in holdout["passages"]}
    assert "missed_knowledge" in roles or "missed" in roles
    assert "false_admit" in roles
    gold = load_extract_gold(INDEPENDENT_GOLD)
    holdout_ids = {row["id"] for row in holdout["passages"]}
    gold_ids = {row["id"] for row in gold["passages"]}
    assert holdout_ids.isdisjoint(gold_ids)
    assert holdout["golden_set_id"] != gold["golden_set_id"]


def test_metrics_on_independent_gold_may_claim_and_must_expose_counts() -> None:
    gold = load_extract_gold(INDEPENDENT_GOLD)
    objects = [
        _obj(TRUE_A, selected=True, before="voor", after="na"),
        _obj(FALSE_C, selected=True, before="voor", after="na"),
    ]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["quality_claim_allowed"] is True
    assert metrics["reason"] == ""
    assert "true_positives" in metrics
    assert "false_positives" in metrics
    assert "false_negatives" in metrics
    assert metrics["false_positives"] >= 1 or metrics["false_negatives"] >= 1
    assert 0.0 <= float(metrics["precision"]) <= 1.0


# ---------------------------------------------------------------------------
# Multiuser: concurrency / interrupt / retry / version
# ---------------------------------------------------------------------------


def test_compute_extract_metrics_does_not_write_gold_or_metrics_files(tmp_path: Path) -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"))
    before = {path.name for path in tmp_path.iterdir()}
    compute_extract_metrics([_obj(TRUE_A)], gold=gold)
    after = {path.name for path in tmp_path.iterdir()}
    assert after == before


def test_truncated_gold_json_does_not_corrupt_or_claim(tmp_path: Path) -> None:
    torn = tmp_path / "torn_gold.json"
    torn.write_text('{"golden_set_id": "torn", "passages": [', encoding="utf-8")
    with pytest.raises(ExtractGoldError) as excinfo:
        load_extract_gold(torn)
    assert "gold_unreadable" in str(excinfo.value)
    leftover = json.loads(PHASE4_GOLD.read_text(encoding="utf-8"))
    assert leftover["golden_set_id"] == "v230-phase4-extract-gold-v0.1"
    assert extract_quality_claim_allowed([], gold=None) is False


def test_metric_runs_are_idempotent() -> None:
    gold = _gold(_selected_row(TRUE_A, "G-A"), _selected_row(TRUE_B, "G-B"))
    objects = [_obj(TRUE_A), _obj(TRUE_B), _obj(FALSE_C)]
    first = compute_extract_metrics(objects, gold=gold)
    second = compute_extract_metrics(objects, gold=gold)
    assert first == second


def test_gold_reads_are_consistent_across_concurrent_readers() -> None:
    gold = json.loads(PHASE4_GOLD.read_text(encoding="utf-8"))
    results: list[dict] = []
    errors: list[BaseException] = []

    def _read() -> None:
        try:
            loaded = load_extract_gold(PHASE4_GOLD)
            results.append(compute_extract_metrics([_obj(TRUE_A)], gold=loaded))
        except BaseException as exc:  # noqa: BLE001 — collect worker failures
            errors.append(exc)

    workers = [threading.Thread(target=_read) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert errors == []
    assert len(results) == 8
    assert all(row == results[0] for row in results)
    assert results[0]["quality_claim_allowed"] is False
    assert gold["status"] == "fixture_gold"
