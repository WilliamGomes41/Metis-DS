"""Removal proof for the 17 unused functions (#689, Class C).

Deleting a function that has no reference cannot change storage, access,
quality or metric behavior. That behavior stays proven by the unchanged suites
named below, which run in the same CI job; this file proves only the removal.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale tests/test_audit_archive_store_v1.py tests/test_publish_refusal_audit_v1.py
# release-control-evidence: toegang tests/test_review_section_presentation.py
# release-control-evidence: kwaliteit tests/test_answerability_gate_v1.py
# release-control-evidence: metrics teller noemer score-must-drop tests/test_extract_metrics_independent_quality.py
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import importlib
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]

REMOVED = {
    "src.audit_archive_store_v1": ("_archive_coordinates",),
    "src.vorming.extract_metrics_v1": ("_source_count", "_match_gold_row", "_status_ok"),
    "src.forensic_trace_v1": ("_objects_for_span", "pending_rejection_keys", "source_lineage_acceptance"),
    "src.knowledge_relations_v1": ("legacy_confirmed_semantic_relations_exist",),
    "src.operations_console_app": ("_relation_checkboxes",),
    "src.operations_console_v1": ("_invalidate_all_bindings",),
    "src.publication.publication_chain_recovery_v1": ("live_publication_chain_integrity",),
    "src.vorming.recommendation_coverage_v1": ("supplementary_blocks",),
    "src.vorming.recommendation_semantics_v1": ("has_source_literal_strength",),
    "src.retrieval.answerability_gate_v1": ("_record_text",),
    "src.review.review_duty_v1": ("first_review_open",),
    "src.review.review_workboard_v1": ("_pending_count",),
    "src.workflows.workflow_remaining_postgres_v1": ("delete_secret",),
}
NAMES = sorted(name for names in REMOVED.values() for name in names)
# This file and the evidence report name the functions on purpose.
NAMING_FILES = {Path(__file__).resolve(), ROOT / "DEAD_CODE_REMOVAL.md"}
SEARCHED = ("src", "scripts", "tests", "config", "db", "docs", ".github")


def test_scope_is_exactly_seventeen_functions():
    assert len(NAMES) == len(set(NAMES)) == 17


@pytest.mark.parametrize("module", sorted(REMOVED))
def test_module_imports_without_removed_definitions(module):
    loaded = importlib.import_module(module)
    present = [name for name in REMOVED[module] if name in vars(loaded)
               or any(name in vars(cls) for cls in vars(loaded).values() if isinstance(cls, type)
                      and cls.__module__ == loaded.__name__)]
    assert present == []


def _word(text, name):
    return re.search(r"\b" + re.escape(name) + r"\b", text) is not None


def test_repository_has_no_reference_to_removed_functions():
    # Per module: de naam MAG NIET in de definierende module staan, en NIET in een bestand dat die module noemt.
    hits = []
    for top in SEARCHED:
        for path in (ROOT / top).rglob("*"):
            if not path.is_file() or path.resolve() in NAMING_FILES or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for module, names in REMOVED.items():
                defining = path.resolve() == (ROOT / (module.replace(".", "/") + ".py")).resolve()
                if defining or _word(text, module.rsplit(".", 1)[-1]):
                    hits.extend(f"{path.relative_to(ROOT)}:{name}" for name in names if _word(text, name))
    assert hits == []


def _plant(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_unrelated_same_name_elsewhere_is_not_a_reference(tmp_path, monkeypatch):
    # Codex P2 op #735: een ongerelateerde helper met dezelfde kale naam MAG CI NIET breken.
    _plant(tmp_path, "src/other_v1.py", "def _status_ok(row):\n    return True\n\n\ndef delete_secret(name):\n    return name\n")
    _plant(tmp_path, "docs/notes.md", "`_pending_count` telt iets anders in een andere module.\n")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    test_repository_has_no_reference_to_removed_functions()


@pytest.mark.parametrize("rel,text", [
    ("src/caller_v1.py", "from src.vorming.extract_metrics_v1 import _status_ok\n"),
    ("src/caller_v1.py", "import src.vorming.extract_metrics_v1 as metrics\nmetrics._status_ok({})\n"),
    ("tests/test_caller.py", "getattr(importlib.import_module('src.workflows.workflow_remaining_postgres_v1'), 'delete_secret')\n"),
    ("src/vorming/extract_metrics_v1.py", "def _status_ok(row):\n    return True\n"),
])
def test_reference_through_defining_module_is_still_caught(tmp_path, monkeypatch, rel, text):
    _plant(tmp_path, rel, text)
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    with pytest.raises(AssertionError):
        test_repository_has_no_reference_to_removed_functions()
