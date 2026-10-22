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
import ast
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
        "src/ingest_limits_v1.py",
        "src/extract_html_v1.py",
        "src/extract_pdf_v2.py",
        "src/semantic_transform_generic_v1.py",
        "src/retrieval/semantic_vector_retrieval_v1.py",
        "src/retrieval/hybrid_retrieval_v1.py",
    ):
        item = preflight.classify_paths([path])["beschikbaarheid"]
        assert item["status"] == "required", path
        assert path in item["paths"]


def test_metrics_modules_require_teller_noemer_and_score_must_drop() -> None:
    preflight = _load()
    for path in (
        "src/extract_metrics_v1.py",
        "src/evaluation/evaluate_retrieval_baseline.py",
        "src/evaluation/evaluate_vector_retrieval.py",
        "src/evaluation/evaluate_hybrid_retrieval.py",
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
        "src/retrieval/answerability_gate_v1.py",
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
        paths=["src/extract_metrics_v1.py", "tests/test_metrics_partial.py"],
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
        paths=["src/operations_console_v1.py", "tests/test_opslag_guard.py"],
        tests_root=tests_root,
    )
    assert result["status"] == "PASS"
    assert result["errors"] == []
    assert result["categories"]["opslag"]["evidence"]


def test_historical_markers_do_not_satisfy_unrelated_product_change(tmp_path: Path) -> None:
    preflight = _load()
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    (tests_root / "test_historical_opslag.py").write_text(
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
        paths=["src/canonical_store.py"],
        tests_root=tests_root,
    )
    assert result["status"] == "BLOCKED"
    errors = " ".join(result["errors"]).lower()
    assert "opslag" in errors
    assert result["categories"]["opslag"]["evidence"] == []


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


def test_ci_retains_required_matrix_and_full_verification() -> None:
    """Scheduling/cache optimizations must preserve both required test checks."""
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    test_job = workflow.split("\n  test:\n", 1)[1]
    assert "python-version: ['3.12', '3.13']" in test_job
    for command in (
        "python scripts/repository_preflight.py",
        "python scripts/release_control_preflight.py --base origin/main",
        "python scripts/product_api_contract.py --check --base-ref origin/main",
        "python -m compileall -q src tests",
        "python scripts/measure_test_suite.py --output output/d6a-after.json",
    ):
        assert command in test_job, f"Required CI verification removed: {command}"
    # The timed runner must execute the whole suite, without paths or filters.
    runner = ast.parse((ROOT / "scripts/measure_test_suite.py").read_text())
    commands = [node.args[0].elts for node in ast.walk(runner)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "run" and node.args and isinstance(node.args[0], ast.List)
                and any(isinstance(arg, ast.Constant) and arg.value == "pytest" for arg in node.args[0].elts)]
    assert len(commands) == 1
    command, = commands
    assert len(command) == 5
    assert [ast.literal_eval(arg) for arg in command[1:4]] == ["-m", "pytest", "-q"]
    assert isinstance(command[4], ast.JoinedStr) and command[4].values[0].value == "--junitxml="


@pytest.mark.parametrize("outcome", [None, "failure", "error", "skipped"])
def test_native_evidence_export_preserves_executed_results(tmp_path, outcome) -> None:
    import xml.etree.ElementTree as ET
    spec = importlib.util.spec_from_file_location("export_test_evidence", ROOT / "scripts/export_test_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = ET.Element("testsuite")
    case = ET.SubElement(root, "testcase", classname="tests.test_native.TestRestart", name="test_commit", time="1.25")
    if outcome:
        ET.SubElement(case, outcome, message="original failure detail").text = "unchanged trace"
    ET.SubElement(root, "testcase", classname="tests.test_native_extra", name="unrelated", time="9")
    source, output = tmp_path / "full.xml", tmp_path / "proof.xml"
    ET.ElementTree(root).write(source)
    assert module.export(source, output, ["tests/test_native.py"]) == int(outcome is not None)
    exported = ET.parse(output).getroot()
    assert exported.get("tests") == "1" and exported.get("time") == "1.25"
    assert ET.tostring(next(exported.iter("testcase"))) == ET.tostring(case)
    with pytest.raises(ValueError, match="No executed evidence"):
        module.export(source, tmp_path / "missing.xml", ["tests/test_missing.py"])


def test_ci_reuses_full_suite_for_native_proof_artifacts() -> None:
    import re
    workflow = (ROOT / ".github/workflows/ci.yml").read_text().split("\n  test:\n", 1)[1]
    proof_commands = re.findall(r"export_test_evidence.py ([^\n]+)", workflow)
    assert len(proof_commands) == 7
    for command in proof_commands:
        assert "--source output/d6a-after.xml" in command
    # A timing-gate failure still leaves executed JUnit evidence. Every native
    # export must override GitHub's implicit success() rather than skip that proof.
    for step in re.split(r"(?m)^      - name: ", workflow):
        if "python scripts/export_test_evidence.py" in step:
            assert "if: ${{ !cancelled() }}" in step, step.splitlines()[0]
    # The full measured run precedes every native export; only the conditional
    # old-code reproduction and the separately installed browser may rerun pytest.
    assert workflow.index("python scripts/measure_test_suite.py --output") < workflow.index("export_test_evidence.py")
    pytest_commands = re.findall(r"(?m)^          pytest ([^\n]+)", workflow)
    assert len(pytest_commands) == 2
    assert "a08-before.xml" in pytest_commands[0]
    assert "test_browser_knowledge_context.py" in pytest_commands[1]


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


def test_diff_filter_includes_deletions() -> None:
    preflight = _load()
    assert "D" in preflight.DIFF_FILTER
    for letter in "ACMRD":
        assert letter in preflight.DIFF_FILTER


def test_deleted_product_paths_still_require_their_category() -> None:
    item = _load().classify_paths(["src/review_ledger.py"])["opslag"]
    assert item["status"] == "required"
    assert "src/review_ledger.py" in item["paths"]


def test_discover_includes_deleted_product_paths(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "review_ledger.py").write_text("ledger = True\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "rm", "src/review_ledger.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "delete ledger"], cwd=repo, check=True, capture_output=True)
    preflight = _load()
    paths = preflight.discover_changed_paths(repo, "HEAD~1")
    assert "src/review_ledger.py" in paths
    assert preflight.classify_paths(paths)["opslag"]["status"] == "required"


def test_service_app_inspection_api_is_toegang() -> None:
    item = _load().classify_paths(["src/service_app.py"])["toegang"]
    assert item["status"] == "required"
    assert "src/service_app.py" in item["paths"]


def test_release_control_markers_are_not_live_release_evidence() -> None:
    """Markers/comments are metadata pointing at concrete checks, not live proof."""
    result = _load().evaluate_release_control(paths=TOOLING_PATHS, tests_root=ROOT / "tests")
    assert result["status"] == "PASS"
    assert result.get("live_release_evidence") is False
    report = result["report"]
    uncertainty = str(report["onzekerheid"]).lower()
    bewijs = str(report["bewijs"]).lower()
    assert "not live-release" in uncertainty or "niet als live-release" in uncertainty
    assert "marker" in uncertainty or "metadata" in uncertainty
    assert "live-release" not in bewijs or "not live-release" in uncertainty


def test_unresolved_base_fails_closed_instead_of_working_tree_passthrough() -> None:
    result = _run_cli(["--base", "definitely-not-a-ref", "--tests-root", str(ROOT / "tests")])
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "BLOCKED"
    errors = " ".join(payload.get("errors") or []).lower()
    assert "definitely-not-a-ref" in errors
    assert "unresolved" in errors


def test_discover_unresolved_base_raises(tmp_path: Path) -> None:
    preflight = _load()
    with pytest.raises(RuntimeError, match="unresolved"):
        preflight.discover_changed_paths(ROOT, "definitely-not-a-ref")
