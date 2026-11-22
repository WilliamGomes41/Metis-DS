"""Check the runtime that CI proves and which workflow can report its result.

# release-control-evidence: scope/belofte slop releasebewijs
"""
import itertools
import json
from pathlib import Path
import re
import shlex

import yaml

from src.azure_deploy_package import AZURE_PYTHON_ABI, AZURE_PYTHON_VERSION


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name):
    return yaml.safe_load((WORKFLOWS / name).read_text())


def _setup_python(job):
    setup, = [step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@")]
    return setup["with"]["python-version"]


def _image_python(recipe, target=None):
    stages = {}
    version = None
    for image, alias in re.findall(r"(?im)^FROM\s+(\S+)(?:\s+AS\s+(\S+))?\s*$", recipe.read_text()):
        base = re.fullmatch(r"python:(\d+\.\d+)-slim", image)
        version = base.group(1) if base else stages[image]
        if alias:
            stages[alias] = version
    return stages[target] if target else version


def test_release_runtimes_match_the_ci_suite():
    jobs = _workflow("ci.yml")["jobs"]
    expected = _setup_python(jobs["suite"])
    release = (ROOT / "scripts" / "build_azure_release_image.sh").read_text().replace("\\\n", " ")
    build = shlex.split(next(line for line in release.splitlines() if line.startswith("az acr build ")))
    recipe = ROOT / build[build.index("--file") + 1]
    target = build[build.index("--target") + 1]
    production = _workflow("deploy-production.yml")["jobs"]["deploy"]["steps"]
    zip_runtime, = re.findall(r"'PYTHON\|(\d+\.\d+)'\)", "\n".join(step.get("run", "") for step in production))
    versions = {
        "test job": _setup_python(jobs["test"]),
        f"{recipe.name}:{target}": _image_python(recipe, target),
        f"{recipe.name}:acceptance": _image_python(recipe, "acceptance"),
        "Dockerfile.docling-acceptance": _image_python(ROOT / "Dockerfile.docling-acceptance"),
        "Docling acceptance host": _setup_python(_workflow("docling-acceptance.yml")["jobs"]["real-pdf"]),
        "Dockerfile.product-api": _image_python(ROOT / "Dockerfile.product-api"),
        "ZIP runtime gate": zip_runtime,
        "ZIP package job": _setup_python(jobs["package"]),
        "ZIP wheel target": AZURE_PYTHON_VERSION,
    }
    assert {name: version for name, version in versions.items() if version != expected} == {}, (
        f"CI suite requires Python {expected}"
    )
    assert AZURE_PYTHON_ABI == "cp" + zip_runtime.replace(".", "")


def test_documented_g1_check_names_match_target_and_temporary_policy():
    policy = json.loads((ROOT / "config" / "github_merge_policy.v1.json").read_text())
    for file in ("TEST_AND_RELEASE_RUNBOOK.md", "REPOSITORY_CONVENTIONS.md", "STACK_SETUP_BASELINE.md"):
        docs = (ROOT / "docs" / file).read_text()
        for label, key in (("G1-doelchecks", "required_status_checks"),
                           ("Tijdelijke G1-checks", "retired_status_checks")):
            lines = [line for line in docs.splitlines() if line.startswith(f"**{label}**")]
            assert len(lines) == 1, (file, label)
            assert re.findall(r"`([^`]+)`", lines[0]) == [row["context"] for row in policy[key]], (file, label)


def test_trace_retry_check_invariant_links_to_its_explicit_successor():
    path = ROOT / "docs" / "change-contracts" / "1107-playwright-trace-on-failure.md"
    invariant, = [line for line in path.read_text().splitlines() if line.startswith("| I6 |")]
    assert "(1135-single-required-test.md)" in invariant


def _matrix_names(job_id, job):
    name = job.get("name", job_id)
    matrix = job.get("strategy", {}).get("matrix", {})
    if not isinstance(matrix, dict):
        return {name}
    axes = {key: values if isinstance(values, list) else [values]
            for key, values in matrix.items() if key not in {"include", "exclude"}}
    bases = [dict(zip(axes, combination)) for combination in itertools.product(*axes.values())] if axes else []
    bases = [row for row in bases if not any(
        all(row.get(key) == value for key, value in excluded.items()) for excluded in matrix.get("exclude", [])
    )]
    rows = [row.copy() for row in bases]
    for included in matrix.get("include", []):
        compatible = [i for i, row in enumerate(bases)
                      if all(key not in included or included[key] == row[key] for key in axes)]
        for i in compatible:
            rows[i].update(included)
        if not compatible:
            rows.append(included)
    expression = re.compile(r"\$\{\{\s*matrix(?:\.([\w-]+)|\[['\"]([\w-]+)['\"]\])\s*\}\}")
    return {expression.sub(lambda match: str(row.get(match[1] or match[2], match[0])), name)
            for row in rows or [{}]}


def test_only_ci_owns_the_consolidated_and_temporary_test_check_names():
    reserved = {"test", "test (3.12)", "test (3.13)"}
    violations = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        if path.name == "ci.yml":
            continue
        for job_id, job in _workflow(path.name).get("jobs", {}).items():
            candidates = {job_id} | _matrix_names(job_id, job)
            patterns = [".*".join(map(re.escape, re.split(r"\$\{\{.*?\}\}", candidate, flags=re.S)))
                        for candidate in candidates]
            collisions = {check for check in reserved if any(re.fullmatch(pattern, check) for pattern in patterns)}
            if collisions:
                violations[f"{path.name}:{job_id}"] = sorted(collisions)
    assert violations == {}
