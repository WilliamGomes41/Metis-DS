"""PR-D2: retirement evidence and bounded Bend/Python conformance (#775)."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "experiments/bend/pr_d2"
BEND = shutil.which("bend")
VERDICT = ["--verdict"] if os.environ.get("METIS_BEND_VERDICT") == "1" else []


def test_retired_module_cannot_be_imported_or_run(tmp_path):
    assert importlib.util.find_spec("src.second_review_workflow_v3") is None
    output = tmp_path / "reviewed.jsonl"
    report = tmp_path / "report.json"
    result = subprocess.run(
        [sys.executable, "-m", "src.second_review_workflow_v3", "--out", str(output),
         "--report", str(report)], cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "No module named src.second_review_workflow_v3" in result.stderr
    assert not output.exists() and not report.exists()


def test_no_active_caller_of_retired_entrypoint():
    paths = [ROOT / name for name in ("src", "scripts", ".github/workflows")]
    files = [p for parent in paths for p in parent.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts]
    files += [ROOT / "pyproject.toml", *ROOT.glob("Dockerfile*")]
    callers = [str(p.relative_to(ROOT)) for p in files
               if "second_review_workflow_v3" in p.read_text(encoding="utf-8", errors="ignore")]
    assert callers == []


def _bend(path, entry, *, verdict=False):
    return subprocess.run(
        [BEND, entry, *(VERDICT if verdict else [])], cwd=path,
        env={**os.environ, "BEND_NO_TELEMETRY": "1"},
        capture_output=True, text=True, timeout=120,
    )


@pytest.mark.skipif(not BEND, reason="Bend is optional outside its dedicated CI job")
def test_bend_laws_hold():
    result = _bend(MODEL, "PROOF.bend", verdict=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL PROOFS CHECK" in result.stdout


@pytest.mark.skipif(not BEND, reason="Bend is optional outside its dedicated CI job")
@pytest.mark.parametrize("mutation", ["standalone", "same_reviewer"])
def test_bend_rejects_a_semantic_violation(tmp_path, mutation):
    for name in ("PendingSecond.bend", "LAWS.bend", "PROOF.bend"):
        shutil.copyfile(MODEL / name, tmp_path / name)
    path = tmp_path / "PendingSecond.bend"
    text = path.read_text()
    if mutation == "standalone":
        text = text.replace("case Standalone{}:\n      False{}", "case Standalone{}:\n      True{}")
    else:
        text = text.replace("case Console{}:\n      independent", "case Console{}:\n      True{}")
    path.write_text(text)
    result = _bend(tmp_path, "PROOF.bend", verdict=True)
    assert result.returncode != 0
    assert "SOME PROOFS FAIL" in result.stdout + result.stderr


@pytest.mark.skipif(not BEND, reason="Bend is optional outside its dedicated CI job")
@pytest.mark.parametrize("route", ["Standalone", "Console"])
@pytest.mark.parametrize("independent", [False, True])
def test_bend_matches_existing_pending_second_review_route(tmp_path, route, independent):
    """All four inputs of the abstraction; other console preconditions hold."""
    from test_d5_3a_binding_aware_review_duty import _obj, _binding
    from test_t4_single_knowledge_path_invariants import _allowed_source
    from src.review.review_duty_v1 import reviewer_route_for

    if route == "Standalone":
        actual = importlib.util.find_spec("src.second_review_workflow_v3") is not None
    else:
        obj = _obj()
        projection = reviewer_route_for(
            obj, review_path="richtlijn",
            reviewer_id="reviewer-b" if independent else "reviewer-a",
            bindings=[_binding(obj, "reviewer-a")], fragments=_allowed_source(),
        )
        assert projection["canonical_task"] == "second_review"
        actual = projection["actionable"]

    shutil.copyfile(MODEL / "PendingSecond.bend", tmp_path / "PendingSecond.bend")
    value = "True" if independent else "False"
    (tmp_path / "Run.bend").write_text(
        "import Base\nimport ./PendingSecond.bend as P\n"
        "def flag(value: Bool) -> U32:\n"
        "  match value:\n    case False{}:\n      0\n    case True{}:\n      1\n"
        f"def main() -> U32:\n  flag(P.actionable(P.{route}{{}}, {value}{{}}))\n"
    )
    result = _bend(tmp_path, "Run.bend")
    assert result.returncode == 0, result.stdout + result.stderr
    assert int(result.stdout.strip()) == int(actual)
