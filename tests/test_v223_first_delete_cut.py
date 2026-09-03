"""Protocol v2.23 first DELETE cut: nine zero-caller modules gone; fixtures, not v21."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DELETED = (
    "extract_pdf.py",
    "semantic_transform.py",
    "validation_workflow.py",
    "build_second_review_queue.py",
    "pre_step5_gate.py",
    "import_expert_validation.py",
    "reconcile_legacy_review.py",
    "evaluate_safe_retrieval.py",
    "build_retrieval_document.py",
)

KEPT = (
    "semantic_transform_v2.py",
    "prepublication_gate_v2.py",
    "validation_workflow_v2.py",
    "apply_second_review.py",
    "canonical_store.py",
    "service_app.py",
    "product_api_v1.py",
    "semantic_transform_v21.py",
    "semantic_transform_generic_v1.py",
    "extract_pdf_v2.py",
    "extract_html_v1.py",
    "prepublication_gate_v3.py",
    "operations_console_v1.py",
    "operations_console_app.py",
    "context_aware_split_v1.py",
    "object_taxonomy_v1.py",
    "four_eyes_v1.py",
    "serving_relations_v1.py",
    "g2_source_store.py",
    "integrity_kernel.py",
    "build_review_queue_v3.py",
)

FIXTURE = ROOT / "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl"
RAW = ROOT / "data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl"
SPRINT = ROOT / "scripts/run_integrity_sprint.sh"


def test_v223_nine_zero_caller_modules_are_gone() -> None:
    for name in DELETED:
        assert not (ROOT / "src" / name).exists(), name


def test_v223_keep_list_and_live_ingest_remain() -> None:
    for name in KEPT:
        assert (ROOT / "src" / name).is_file(), name


def test_v223_integrity_sprint_uses_committed_fixtures_not_v21() -> None:
    text = SPRINT.read_text(encoding="utf-8")
    assert "python -m src.semantic_transform_v21" not in text
    assert "python -m src.semantic_transform_v2" not in text
    assert "python -m src.semantic_transform_generic_v1" not in text
    assert "data/fixtures/baseline_v0_1/fractuurpreventie_page15_semantic_v21.jsonl" in text
    assert "data/fixtures/baseline_v0_1/fractuurpreventie_page15_raw.jsonl" in text
    assert FIXTURE.is_file() and FIXTURE.stat().st_size > 0
    assert RAW.is_file() and RAW.stat().st_size > 0
    assert "Do not merge v2/v21/generic" in text


def test_v223_does_not_recreate_handoff() -> None:
    assert not (ROOT / "HANDOFF.md").exists()
