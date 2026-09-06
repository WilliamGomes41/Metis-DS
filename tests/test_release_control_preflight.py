"""Release-control preflight: map changed paths to Metis skill categories.

Skill: metis-ontwikkel-en-releasecontrole. Tooling/CI mapping only.
Product categories opslag–metrics stay n.v.t. until a product path is in
the diff. PROTOCOL.md / PROTOCOL_V2_* are not edited here.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_control_preflight.py"

SKILL_CATEGORIES = (
    "scope/belofte",
    "opslag",
    "beschikbaarheid",
    "toegang",
    "kwaliteit",
    "metrics",
    "slop",
    "releasebewijs",
)
PRODUCT_CATEGORIES = (
    "opslag",
    "beschikbaarheid",
    "toegang",
    "kwaliteit",
    "metrics",
)
PROCESS_CATEGORIES = (
    "scope/belofte",
    "slop",
    "releasebewijs",
)
PR_REPORT_FIELDS = (
    "belofte",
    "wijziging",
    "bewijs",
    "onzekerheid",
    "advies",
)
TOOLING_PATHS = (
    "scripts/release_control_preflight.py",
    "tests/test_release_control_preflight.py",
    ".github/workflows/ci.yml",
    "CONTRIBUTING.md",
)

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _load():
    spec = importlib.util.spec_from_file_location("release_control_preflight", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_cli(args: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_skill_categories_are_the_eight_metis_names() -> None:
    preflight = _load()
    assert tuple(preflight.SKILL_CATEGORIES) == SKILL_CATEGORIES
    assert tuple(preflight.PR_REPORT_FIELDS) == PR_REPORT_FIELDS


def test_classify_always_emits_required_or_nvt_with_reason_template() -> None:
    preflight = _load()
    report = preflight.classify_paths(TOOLING_PATHS)
    assert tuple(report) == SKILL_CATEGORIES
    for category, item in report.items():
        assert item["status"] in {"required", "n.v.t."}
        reason = item["reason"]
        assert reason.startswith(f"{category}: {item['status']} — ")
        assert len(reason) > len(f"{category}: {item['status']} — ")


def test_tooling_only_paths_mark_product_categories_nvt() -> None:
    report = _load().classify_paths(TOOLING_PATHS)
    for category in PRODUCT_CATEGORIES:
        assert report[category]["status"] == "n.v.t.", category
        assert "geen" in report[category]["reason"]
    for category in PROCESS_CATEGORIES:
        assert report[category]["status"] == "required", category


def test_opslag_persistence_paths_require_concurrent_stale_checks() -> None:
    preflight = _load()
    for path in (
        "src/operations_console_v1.py",
        "src/review_ledger.py",
        "src/canonical_store.py",
        "src/g2_source_store.py",
    ):
        item = preflight.classify_paths([path])["opslag"]
        assert item["status"] == "required", path
        reason = item["reason"].lower()
        assert "concurrent" in reason
        assert "stale" in reason
        assert path in item["paths"]


def test_toegang_routes_auth_and_url_ingest_paths() -> None:
    preflight = _load()
    for path in (
        "src/operations_console_app.py",
        "src/console_asgi.py",
        "src/product_security_v1.py",
        "src/product_api_v1.py",
    ):
        item = preflight.classify_paths([path])["toegang"]
        assert item["status"] == "required", path
        assert path in item["paths"]


def test_beschikbaarheid_ingest_and_heavy_paths() -> None:
    preflight = _load()
    for path in (
        "src/extract_html_v1.py",
        "src/extract_pdf_v2.py",
        "src/semantic_transform_v21.py",
        "src/embedding_provider_v1.py",
    ):
        item = preflight.classify_paths([path])["beschikbaarheid"]
        assert item["status"] == "required", path
        assert path in item["paths"]


def test_metrics_modules_require_teller_noemer_and_score_must_drop() -> None:
    preflight = _load()
    for path in (
        "src/extract_metrics_v1.py",
        "src/evaluate_retrieval_baseline.py",
        "src/evaluate_vector_retrieval.py",
        "src/evaluate_hybrid_retrieval.py",
    ):
        item = preflight.classify_paths([path])["metrics"]
        assert item["status"] == "required", path
        reason = item["reason"].lower()
        assert "teller" in reason
        assert "noemer" in reason
        assert "score-must-drop" in reason
        assert path in item["paths"]


def test_kwaliteit_gate_paths_are_required() -> None:
    preflight = _load()
    for path in (
        "src/admission_gate_v1.py",
        "src/prepublication_gate_v3.py",
        "src/answerability_gate_v1.py",
        "src/integrity_kernel.py",
    ):
        item = preflight.classify_paths([path])["kwaliteit"]
        assert item["status"] == "required", path


def test_docs_and_protocol_paths_do_not_force_product_categories() -> None:
    report = _load().classify_paths(
        ["PROTOCOL.md", "docs/PROTOCOL_V2_31_DIT_KLOPT_EXACT_HEADING_BIND_DELTA.md", "CONTRIBUTING.md"]
    )
    for category in PRODUCT_CATEGORIES:
        assert report[category]["status"] == "n.v.t.", category


def test_evaluate_fails_when_required_opslag_lacks_concurrent_stale_evidence(tmp_path: Path) -> None:
    preflight = _load()
    empty = tmp_path / "tests"
    empty.mkdir()
    (empty / "test_empty.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    result = preflight.evaluate_release_control(
        paths=["src/operations_console_v1.py"],
        tests_root=empty,
    )
    assert result["status"] == "BLOCKED"
    errors = " ".join(result["errors"]).lower()
    assert "opslag" in errors
    assert "concurrent" in errors or "stale" in errors or "evidence" in errors


def test_evaluate_fails_when_required_metrics_lacks_score_must_drop(tmp_path: Path) -> None:
    preflight = _load()
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    (tests_root / "test_metrics_partial.py").write_text(
        "# release-control-evidence: metrics teller noemer\n"
        "import pytest\n"
        "pytestmark = pytest.mark.release_control_metrics\n"
        "def test_metrics_partial():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    result = preflight.evaluate_release_control(
        paths=["src/extract_metrics_v1.py"],
        tests_root=tests_root,
    )
    assert result["status"] == "BLOCKED"
    errors = " ".join(result["errors"]).lower()
    assert "metrics" in errors
    assert "score-must-drop" in errors or "score_must_drop" in errors


def test_evaluate_passes_when_required_has_matching_marker_and_tokens(tmp_path: Path) -> None:
    preflight = _load()
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    (tests_root / "test_opslag_guard.py").write_text(
        "# release-control-evidence: opslag concurrent stale\n"
        "# release-control-evidence: scope/belofte\n"
        "# release-control-evidence: slop\n"
        "# release-control-evidence: releasebewijs\n"
        "import pytest\n"
        "pytestmark = [\n"
        "    pytest.mark.release_control_opslag,\n"
        "    pytest.mark.release_control_scope_belofte,\n"
        "    pytest.mark.release_control_slop,\n"
        "    pytest.mark.release_control_releasebewijs,\n"
        "]\n"
        "def test_save_objects_rejects_stale_concurrent_write():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    result = preflight.evaluate_release_control(
        paths=["src/operations_console_v1.py"],
        tests_root=tests_root,
    )
    assert result["status"] == "PASS"
    assert result["errors"] == []
    assert result["categories"]["opslag"]["evidence"]


def test_evaluate_tooling_paths_pass_against_this_suite() -> None:
    result = _load().evaluate_release_control(paths=TOOLING_PATHS, tests_root=ROOT / "tests")
    assert result["status"] == "PASS"
    assert result["errors"] == []
    for category in PRODUCT_CATEGORIES:
        assert result["categories"][category]["status"] == "n.v.t."
    for category in PROCESS_CATEGORIES:
        assert result["categories"][category]["status"] == "required"
        assert result["categories"][category]["evidence"]


def test_pr_report_stub_has_metis_eindrapportage_fields() -> None:
    result = _load().evaluate_release_control(paths=TOOLING_PATHS, tests_root=ROOT / "tests")
    report = result["report"]
    assert tuple(report) == PR_REPORT_FIELDS
    for field in PR_REPORT_FIELDS:
        assert str(report[field]).strip()


def test_cli_fails_closed_without_required_evidence(tmp_path: Path) -> None:
    empty = tmp_path / "tests"
    empty.mkdir()
    (empty / "test_empty.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")
    result = _run_cli(
        [
            "--paths",
            "src/operations_console_v1.py",
            "--tests-root",
            str(empty),
        ]
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "BLOCKED"


def test_cli_passes_for_tooling_only_change() -> None:
    result = _run_cli(
        [
            "--paths",
            *TOOLING_PATHS,
            "--tests-root",
            str(ROOT / "tests"),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert tuple(payload["report"]) == PR_REPORT_FIELDS


def test_ci_runs_release_control_after_repository_preflight() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python scripts/repository_preflight.py" in workflow
    assert "python scripts/release_control_preflight.py" in workflow
    assert workflow.index("repository_preflight") < workflow.index("release_control_preflight")


def test_contributing_names_skill_checks_and_ci_must_not_forget_them() -> None:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for category in SKILL_CATEGORIES:
        assert category in text, category
    assert "release_control_preflight.py" in text
    assert "repository_preflight.py" in text


def test_preflight_script_stays_stdlib_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert "from src." not in text
    assert "import src" not in text


def test_dot_github_paths_keep_leading_dot() -> None:
    report = _load().classify_paths([".github/workflows/ci.yml"])
    assert ".github/workflows/ci.yml" in report["releasebewijs"]["paths"]
    assert "github/workflows/ci.yml" not in report["releasebewijs"]["paths"]
