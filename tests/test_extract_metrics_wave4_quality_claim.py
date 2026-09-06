"""Post-#120 audit remediation 4: Wave-4 quality claim incomplete.

Fixture / v231_wave4 gold stays usable for development regressions.
It MUST NOT open an independent quality claim on status strings or
self-declared booleans. Metrics use a defined unit, 1:1 source+passage
assignment, explicit duplicates, annotated context (not scan-done),
and MUST NOT treat undefined review burden as progress.

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

from src.extract_metrics_v1 import (
    compute_extract_metrics,
    extract_quality_claim_allowed,
    gold_supports_independent_quality_claim,
    load_extract_gold,
    measure_admission_language_variation,
)
from src.validate_golden_set import validate_extract_gold


ROOT = Path(__file__).resolve().parents[1]
WAVE4_FIXTURE_GOLD = ROOT / "data/golden/v231_wave4_independent_extract_gold_v0.1.json"
WAVE4_FIXTURE_HOLDOUT = ROOT / "data/holdout/v231_wave4_extract_holdout_v0.1.json"
WAVE4_LANGUAGE_GOLD = ROOT / "data/golden/v231_wave4_language_variation_gold_v0.1.json"
PHASE4_GOLD = ROOT / "data/golden/v230_phase4_extract_gold_v0.1.json"
PACKAGE_TRAIN = ROOT / "data/golden/v231_post120_independent_extract_gold_v0.1.json"
PACKAGE_HOLDOUT = ROOT / "data/holdout/v231_post120_extract_holdout_v0.1.json"
PACKAGE_LOCK = ROOT / "data/golden/v231_post120_independent_extract_package.lock.json"

CON_DOC = "vvn-continentie-kwetsbare-ouderen-2025"
CON_SRC = "vvn-continentie-kwetsbare-ouderen-2025-source-html"
FP_DOC = "vvn-osteoporose-fractuurpreventie-2024"
FP_SRC = "vvn-osteoporose-fractuurpreventie-2024-source-pdf"

CON_TP = "Bespreek incontinentie met de cliënt en de mantelzorger."
CON_MISS = "Continentie is het vermogen om urine en ontlasting op te houden."
CON_FA = "Eventueel met hulp van de mantelzorger."
FP_TP = (
    "Controleer of aanvullend onderzoek naar osteoporose is uitgevoerd. "
    "Dit bestaat uit DXA-VFA, aanvullend laboratoriumonderzoek en inschatting valrisico."
)
FP_MISS = "Bij een cliënt in zorg ≥ 50 jaar met een recente fractuur (≤ 2 jaar geleden)"
FP_FA = "Risicofactoren scorelijst"

TRUE_A = "De werkgroep adviseert de verpleegkundige de risicofactoren scorelijst te gebruiken bij iedere intake."
TRUE_B = "De werkgroep adviseert calcium te geven."
FALSE_C = "De werkgroep adviseert de lezer eerst de inleiding te lezen."

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
    source_id: str = "",
    document_id: str = "",
    selected: bool = True,
    scan_done: bool = False,
    before: str = "",
    after: str = "",
    object_type: str = "recommendation",
    object_id: str | None = None,
) -> dict:
    status = "selected_as_candidate" if selected else "excluded_with_reason"
    return {
        "object_id": object_id or f"obj-{abs(hash((source_id, text, object_id))) % 10_000_000}",
        "object_type": object_type,
        "proposed_object_type": object_type,
        "source_id": source_id,
        "document_id": document_id,
        "content": {"clean_text": text},
        "source": {"source_id": source_id} if source_id else {},
        "metadata": {
            "admission": {
                "gate_result": "allowed" if selected else "blocked",
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


def _row(
    text: str,
    row_id: str,
    *,
    source_id: str = "",
    document_id: str = "",
    role: str = "true_positive_expected",
    cls: str = "normative",
    expected_type: str = "recommendation",
    expected_status: str = "selected_as_candidate",
    expected_context_before: str | None = None,
    expected_context_after: str | None = None,
) -> dict:
    row = {
        "id": row_id,
        "source_id": source_id,
        "document_id": document_id,
        "class": cls,
        "role": role,
        "section": "2 Aanbevelingen",
        "source_text": text,
        "expected_register_status": expected_status,
        "expected_type": expected_type,
        "expected_gate": "allowed" if expected_status == "selected_as_candidate" else "blocked",
    }
    if expected_context_before is not None:
        row["expected_context_before"] = expected_context_before
    if expected_context_after is not None:
        row["expected_context_after"] = expected_context_after
    return row


def _claim_checks(gold, holdout=None, lock=None):
    from src.extract_metrics_v1 import independent_quality_claim_checks

    return independent_quality_claim_checks(gold, holdout=holdout, lock=lock)


def _overlap(train, holdout):
    from src.extract_metrics_v1 import train_holdout_source_overlap

    return train_holdout_source_overlap(train, holdout)


def _minimal_rules() -> dict:
    return {
        "gold_required_before_quality_claim": True,
        "soft_scores_must_not_claim_quality": True,
        "single_guideline_without_gold_is_not_quality": True,
        "no_duty_to_objectify_every_sentence": True,
        "unknown_register_status_rejected": True,
    }


def _status_only_gold() -> dict:
    return {
        "golden_set_id": "status-only-not-a-claim",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_representative",
        "independence": {"independent": True, "representative": True},
        "rules": {**_minimal_rules(), "independent_quality_claim": True},
        "sources": [
            {"id": "a", "document_id": "doc-a", "source_id": "src-a"},
            {"id": "b", "document_id": "doc-b", "source_id": "src-b"},
        ],
        "passages": [
            _row(TRUE_A, "S-1", source_id="src-a", document_id="doc-a", role="missed_knowledge", cls="missed"),
            _row(FALSE_C, "S-2", source_id="src-b", document_id="doc-b", role="false_admit", cls="false_admit", expected_status="excluded_with_reason"),
        ],
    }


# ---------------------------------------------------------------------------
# Fixture gold = development/regression only (claim fail-closed)
# ---------------------------------------------------------------------------


def test_wave4_fixture_independent_gold_cannot_open_quality_claim() -> None:
    gold = load_extract_gold(WAVE4_FIXTURE_GOLD)
    assert gold["status"] == "independent_representative"
    assert gold["independence"]["independent"] is True
    assert gold["rules"]["independent_quality_claim"] is True
    assert gold_supports_independent_quality_claim(gold) is False
    assert extract_quality_claim_allowed([], gold=gold) is False
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=gold)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["precision"] is not None
    assert metrics["reason"]


def test_wave4_fixture_holdout_cannot_open_quality_claim() -> None:
    holdout = load_extract_gold(WAVE4_FIXTURE_HOLDOUT)
    assert holdout["status"] == "locked_holdout"
    assert holdout["rules"]["independent_quality_claim"] is True
    assert gold_supports_independent_quality_claim(holdout) is False
    assert extract_quality_claim_allowed([], gold=holdout) is False
    metrics = compute_extract_metrics([_obj(TRUE_A)], gold=holdout)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["precision"] is not None


def test_wave4_language_variation_gold_cannot_open_quality_claim() -> None:
    gold = load_extract_gold(WAVE4_LANGUAGE_GOLD)
    assert gold["status"] == "language_variation"
    assert gold_supports_independent_quality_claim(gold) is False
    assert extract_quality_claim_allowed([], gold=gold) is False


def test_self_declared_booleans_and_status_string_cannot_open_claim() -> None:
    gold = _status_only_gold()
    assert gold["status"] == "independent_representative"
    assert gold["independence"]["independent"] is True
    assert gold["rules"]["independent_quality_claim"] is True
    assert gold_supports_independent_quality_claim(gold) is False
    assert extract_quality_claim_allowed([], gold=gold) is False
    metrics = compute_extract_metrics([_obj(TRUE_A, source_id="src-a")], gold=gold)
    assert metrics["quality_claim_allowed"] is False


def test_phase4_and_inline_fixture_gold_remain_regression_usable() -> None:
    gold = load_extract_gold(PHASE4_GOLD)
    metrics = compute_extract_metrics([_obj(TRUE_A, selected=True)], gold=gold)
    assert metrics["quality_claim_allowed"] is False
    assert metrics["precision"] is not None
    assert 0.0 <= float(metrics["precision"]) <= 1.0


# ---------------------------------------------------------------------------
# Train / holdout overlap fail-closed
# ---------------------------------------------------------------------------


def test_overlapping_document_ids_fail_closed() -> None:
    train = {
        "golden_set_id": "overlap-train",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_train",
        "rules": _minimal_rules(),
        "sources": [{"id": "same", "document_id": CON_DOC, "source_id": CON_SRC}],
        "passages": [_row(CON_TP, "T-1", source_id=CON_SRC, document_id=CON_DOC)],
    }
    holdout = {
        "golden_set_id": "overlap-holdout",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_holdout",
        "rules": _minimal_rules(),
        "sources": [{"id": "same", "document_id": CON_DOC, "source_id": "other-src"}],
        "passages": [_row(CON_MISS, "H-1", source_id="other-src", document_id=CON_DOC)],
    }
    overlap = _overlap(train, holdout)
    assert overlap["shared_document_ids"]
    assert gold_supports_independent_quality_claim(train, holdout=holdout) is False
    checks = _claim_checks(train, holdout=holdout)
    assert checks["allowed"] is False
    assert "train_holdout_overlap" in checks["failures"]


def test_overlapping_source_ids_fail_closed() -> None:
    train = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_train",
        "rules": _minimal_rules(),
        "sources": [{"source_id": CON_SRC, "document_id": CON_DOC}],
        "passages": [_row(CON_TP, "T-1", source_id=CON_SRC, document_id=CON_DOC)],
    }
    holdout = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_holdout",
        "rules": _minimal_rules(),
        "sources": [{"source_id": CON_SRC, "document_id": "other-doc"}],
        "passages": [_row(CON_FA, "H-1", source_id=CON_SRC, document_id="other-doc")],
    }
    overlap = _overlap(train, holdout)
    assert overlap["shared_source_ids"]
    assert gold_supports_independent_quality_claim(train, holdout=holdout) is False


def test_overlapping_source_plus_passage_text_fail_closed() -> None:
    train = {
        "kind": "extract_quality",
        "version": "0.1",
        "rules": _minimal_rules(),
        "sources": [{"source_id": CON_SRC, "document_id": CON_DOC}],
        "passages": [_row(CON_TP, "T-1", source_id=CON_SRC, document_id=CON_DOC)],
    }
    holdout = {
        "kind": "extract_quality",
        "version": "0.1",
        "rules": _minimal_rules(),
        "sources": [{"source_id": CON_SRC, "document_id": CON_DOC}],
        "passages": [_row(CON_TP, "H-1", source_id=CON_SRC, document_id=CON_DOC)],
    }
    overlap = _overlap(train, holdout)
    assert overlap["shared_passage_keys"]
    assert gold_supports_independent_quality_claim(train, holdout=holdout) is False


def test_wave4_fixture_train_and_holdout_overlap_fail_closed() -> None:
    train = load_extract_gold(WAVE4_FIXTURE_GOLD)
    holdout = load_extract_gold(WAVE4_FIXTURE_HOLDOUT)
    overlap = _overlap(train, holdout)
    assert overlap["shared_passage_texts"] or overlap["shared_passage_keys"]
    assert gold_supports_independent_quality_claim(train, holdout=holdout) is False
    assert extract_quality_claim_allowed([], gold=train, holdout=holdout) is False


# ---------------------------------------------------------------------------
# Metrics: unit / 1:1 source+passage / duplicates / context / burden
# ---------------------------------------------------------------------------


def test_precision_unit_is_one_to_one_source_plus_passage() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [
            _row(TRUE_A, "G-A", source_id="src-a", document_id="doc-a"),
            _row(TRUE_A, "G-B", source_id="src-b", document_id="doc-b"),
        ],
    }
    objects = [
        _obj(TRUE_A, source_id="src-a", document_id="doc-a", selected=True),
        _obj(TRUE_A, source_id="src-b", document_id="doc-b", selected=True),
    ]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["assignment_unit"] == "source_id+passage"
    assert metrics["true_positives"] == 2
    assert metrics["false_positives"] == 0
    assert metrics["precision"] == 1.0


def test_same_text_on_other_source_does_not_match() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [_row(TRUE_A, "G-A", source_id="src-a", document_id="doc-a")],
    }
    objects = [_obj(TRUE_A, source_id="src-b", document_id="doc-b", selected=True)]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["true_positives"] == 0
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["precision"] == 0.0


def test_duplicate_selected_passages_are_explicit_and_not_double_counted() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [_row(TRUE_A, "G-A", source_id="src-a", document_id="doc-a")],
    }
    objects = [
        _obj(TRUE_A, source_id="src-a", document_id="doc-a", selected=True, object_id="dup-1"),
        _obj(TRUE_A, source_id="src-a", document_id="doc-a", selected=True, object_id="dup-2"),
    ]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["true_positives"] == 1
    assert metrics["duplicate_predictions"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["precision"] < 1.0


def test_context_completeness_is_none_without_annotated_expectations() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [_row(TRUE_A, "G-A", source_id="src-a")],
    }
    objects = [_obj(TRUE_A, source_id="src-a", selected=True, scan_done=True, before="voor", after="na")]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["context_completeness"] is None
    assert metrics["neighbor_context_present"] == 1.0


def test_context_scan_done_alone_is_not_annotated_completeness() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [
            _row(
                TRUE_A,
                "G-A",
                source_id="src-a",
                expected_context_before="Vorige alinea over de doelgroep.",
                expected_context_after="Volgende alinea over vervolgonderzoek.",
            )
        ],
    }
    objects = [_obj(TRUE_A, source_id="src-a", selected=True, scan_done=True, before="", after="")]
    metrics = compute_extract_metrics(objects, gold=gold)
    assert metrics["context_completeness"] == 0.0
    assert metrics["neighbor_context_present"] == 0.0


def test_context_completeness_scores_against_annotated_expectations() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [
            _row(
                TRUE_A,
                "G-A",
                source_id="src-a",
                expected_context_before="Vorige alinea over de doelgroep.",
                expected_context_after="Volgende alinea over vervolgonderzoek.",
            )
        ],
    }
    complete = _obj(
        TRUE_A,
        source_id="src-a",
        selected=True,
        scan_done=True,
        before="Vorige alinea over de doelgroep.",
        after="Volgende alinea over vervolgonderzoek.",
    )
    metrics = compute_extract_metrics([complete], gold=gold)
    assert metrics["context_completeness"] == 1.0


def test_undefined_review_burden_is_not_a_progress_score() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [_row(TRUE_A, "G-A", source_id="src-a")],
    }
    metrics = compute_extract_metrics([_obj(TRUE_A, source_id="src-a")], gold=gold)
    assert metrics["review_burden"] is None
    assert metrics.get("review_burden_defined") is False


def test_controlled_worsening_drops_precision_type_and_context() -> None:
    gold = {
        "kind": "extract_quality",
        "version": "0.1",
        "status": "fixture_gold",
        "rules": _minimal_rules(),
        "passages": [
            _row(
                TRUE_A,
                "G-A",
                source_id="src-a",
                expected_type="recommendation",
                expected_context_before="voor",
                expected_context_after="na",
            ),
            _row(
                TRUE_B,
                "G-B",
                source_id="src-a",
                expected_type="recommendation",
                expected_context_before="voor",
                expected_context_after="na",
            ),
        ],
    }
    good = [
        _obj(TRUE_A, source_id="src-a", selected=True, before="voor", after="na"),
        _obj(TRUE_B, source_id="src-a", selected=True, before="voor", after="na"),
    ]
    baseline = compute_extract_metrics(good, gold=gold)
    worse = compute_extract_metrics(
        [
            _obj(TRUE_A, source_id="src-a", selected=True, before="voor", after="na"),
            _obj(
                TRUE_B,
                source_id="src-a",
                selected=True,
                before="",
                after="",
                object_type="condition",
                object_id="wrong-type",
            ),
            _obj(FALSE_C, source_id="src-a", selected=True, before="", after="", object_type="recommendation"),
            _obj(TRUE_A, source_id="src-a", selected=True, before="", after="", object_id="dup-worse"),
        ],
        gold=gold,
    )
    assert baseline["precision"] == 1.0
    assert baseline["type_accuracy"] == 1.0
    assert baseline["context_completeness"] == 1.0
    assert worse["precision"] < baseline["precision"]
    assert worse["type_accuracy"] < baseline["type_accuracy"]
    assert worse["context_completeness"] < baseline["context_completeness"]
    assert worse["duplicate_predictions"] >= 1
    assert worse["false_positives"] >= 1


# ---------------------------------------------------------------------------
# Independent package: claim only when concrete checks pass
# ---------------------------------------------------------------------------


def test_independent_package_missing_reviewers_lock_or_rules_fail_closed() -> None:
    train = {
        "golden_set_id": "pkg-train",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_train",
        "rules": _minimal_rules(),
        "sources": [
            {
                "id": "continentie",
                "document_id": CON_DOC,
                "source_id": CON_SRC,
                "title": "V&VN Richtlijn Continentie bij (kwetsbare) ouderen",
                "publisher": "V&VN",
                "version": "april 2025",
                "material": "data/fixtures/continentie_v221_wave_a_regression.html",
            }
        ],
        "passages": [
            _row(CON_TP, "T-1", source_id=CON_SRC, document_id=CON_DOC),
            _row(CON_MISS, "T-2", source_id=CON_SRC, document_id=CON_DOC, role="missed_knowledge", cls="missed", expected_type="definition"),
            _row(CON_FA, "T-3", source_id=CON_SRC, document_id=CON_DOC, role="false_admit", cls="false_admit", expected_status="excluded_with_reason"),
        ],
    }
    holdout = {
        "golden_set_id": "pkg-holdout",
        "kind": "extract_quality",
        "version": "0.1",
        "status": "independent_holdout",
        "rules": _minimal_rules(),
        "sources": [
            {
                "id": "fractuurpreventie-p15",
                "document_id": FP_DOC,
                "source_id": FP_SRC,
                "title": "V&VN Richtlijn Osteoporose en fractuurpreventie",
                "publisher": "V&VN",
                "version": "augustus 2024",
                "material": "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl",
            }
        ],
        "passages": [
            _row(FP_TP, "H-1", source_id=FP_SRC, document_id=FP_DOC),
            _row(FP_MISS, "H-2", source_id=FP_SRC, document_id=FP_DOC, role="missed_knowledge", cls="missed", expected_type="condition"),
            _row(FP_FA, "H-3", source_id=FP_SRC, document_id=FP_DOC, role="false_admit", cls="false_admit", expected_status="excluded_with_reason"),
        ],
    }
    empty_lock = {"kind": "extract_quality_claim_package", "version": "0.1"}
    checks = _claim_checks(train, holdout=holdout, lock=empty_lock)
    assert checks["allowed"] is False
    for code in (
        "reviewers_missing",
        "annotation_rules_missing",
        "lock_moment_missing",
        "locked_scope_missing",
        "source_identity_incomplete",
    ):
        assert code in checks["failures"]
    assert gold_supports_independent_quality_claim(train, holdout=holdout, lock=empty_lock) is False


def test_independent_package_unlocks_claim_only_when_concrete_checks_pass() -> None:
    train = load_extract_gold(PACKAGE_TRAIN)
    holdout = load_extract_gold(PACKAGE_HOLDOUT)
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    checks = _claim_checks(train, holdout=holdout, lock=lock)
    assert checks["allowed"] is True
    assert checks["failures"] == []
    assert gold_supports_independent_quality_claim(train, holdout=holdout, lock=lock) is True
    assert extract_quality_claim_allowed([], gold=train, holdout=holdout, lock=lock) is True
    metrics = compute_extract_metrics(
        [_obj(CON_TP, source_id=CON_SRC, document_id=CON_DOC, before="voor", after="na")],
        gold=train,
        holdout=holdout,
        lock=lock,
    )
    assert metrics["quality_claim_allowed"] is True
    assert metrics["reason"] == ""


def test_independent_package_files_record_identity_rules_reviewers_and_split() -> None:
    train = load_extract_gold(PACKAGE_TRAIN)
    holdout = load_extract_gold(PACKAGE_HOLDOUT)
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    assert validate_extract_gold(train)["status"] == "PASS"
    assert validate_extract_gold(holdout)["status"] == "PASS"
    assert lock["kind"] == "extract_quality_claim_package"
    assert lock["locked_at"]
    assert lock["gold_schema_version"]
    assert lock["reviewers"]
    assert all("Metis" not in str(row.get("name") or "") for row in lock["reviewers"])
    assert all("Forge" not in str(row.get("name") or "") for row in lock["reviewers"])
    assert all("Auditor" not in str(row.get("name") or "") for row in lock["reviewers"])
    assert lock["annotation_rules"]["unit"]
    assert lock["scope"]["locked"] is True
    train_docs = {str(row.get("document_id") or "") for row in train["sources"]}
    holdout_docs = {str(row.get("document_id") or "") for row in holdout["sources"]}
    assert train_docs.isdisjoint(holdout_docs)
    assert train_docs
    assert holdout_docs
    overlap = _overlap(train, holdout)
    assert not overlap["shared_document_ids"]
    assert not overlap["shared_source_ids"]
    assert not overlap["shared_passage_keys"]
    assert CON_DOC in train_docs
    assert FP_DOC in holdout_docs


def test_stripping_a_concrete_check_closes_the_claim() -> None:
    train = load_extract_gold(PACKAGE_TRAIN)
    holdout = load_extract_gold(PACKAGE_HOLDOUT)
    lock = json.loads(PACKAGE_LOCK.read_text(encoding="utf-8"))
    broken = dict(lock)
    broken["reviewers"] = []
    assert gold_supports_independent_quality_claim(train, holdout=holdout, lock=broken) is False
    checks = _claim_checks(train, holdout=holdout, lock=broken)
    assert "reviewers_missing" in checks["failures"]


def test_language_variation_admission_still_green() -> None:
    gold = load_extract_gold(WAVE4_LANGUAGE_GOLD)
    report = measure_admission_language_variation(gold=gold)
    assert report["false_admits"] or report["misses"]
    assert report["precision"] < 1.0 or report["recall"] < 1.0
    assert gold_supports_independent_quality_claim(gold) is False
