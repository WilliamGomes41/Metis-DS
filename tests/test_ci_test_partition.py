"""Excluded CI modules must already have a complete run in the same job.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from collections import Counter
from pathlib import Path
import re
import shlex


ROOT = Path(__file__).resolve().parents[1]


def _assert_prior_runs_cover_exclusions(workflow: str) -> None:
    # This deliberately checks the executable pytest commands, not step names
    # or a second list of expected module filenames.
    workflow = re.sub(
        r"(?m)^        run: >-\n((?:          [^\n]*\n)+)",
        lambda match: "        run: " + " ".join(line.strip() for line in match[1].splitlines()) + "\n",
        workflow,
    )
    test_job = workflow.split("\n  test:\n", 1)[1]
    prior_runs: Counter[str] = Counter()
    checked = False
    for step in re.split(r"(?m)^      - ", test_job)[1:]:
        for command in re.findall(r"(?m)^(?:        run: |          )(?:python -m )?pytest ([^\n]+)", step):
            args = shlex.split(command)
            ignored = [arg.split("=", 1)[1] for arg in args if arg.startswith("--ignore=")]
            if ignored:
                assert len(ignored) == len(set(ignored)), "Repeated CI exclusion"
                for module in ignored:
                    assert (ROOT / module).is_file(), f"Missing excluded module: {module}"
                    assert prior_runs[module] == 1, f"Excluded module lacks exactly one prior full run: {module}"
                checked = True
                continue
            condition = re.search(r"(?m)^        if: (.+)$", step)
            if condition and condition[1] != "${{ !cancelled() }}":
                continue  # A branch-specific reproduction is not a full run.
            if any(arg.startswith(("-k", "-m", "--deselect", "--ignore")) for arg in args):
                continue
            prior_runs.update(arg for arg in args if arg.startswith("tests/") and arg.endswith(".py"))
    assert checked, "Missing CI partition"


def test_ci_exclusions_have_prior_complete_pytest_runs() -> None:
    _assert_prior_runs_cover_exclusions((ROOT / ".github/workflows/ci.yml").read_text())
