"""G1 strengthening preserves existing protections and rejects false completion.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from scripts.check_github_merge_policy import plan_ruleset, validate_ruleset

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "config/github_merge_policy.v1.json").read_text())


def current_g1():
    return {
        "id": 21686159, "source": "WilliamGomes41/Metis-DS", "source_type": "Repository",
        "name": "G1 main", "target": "branch", "enforcement": "active",
        "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
        "bypass_actors": [],
        "rules": [
            {"type": "deletion"}, {"type": "non_fast_forward"},
            {"type": "required_status_checks", "parameters": {
                "strict_required_status_checks_policy": True,
                "do_not_enforce_on_create": False,
                "required_status_checks": [{"context": "test (3.12)"}, {"context": "test (3.13)"}],
            }},
            {"type": "pull_request", "parameters": {
                "required_approving_review_count": 0,
                "dismiss_stale_reviews_on_push": True,
                "required_reviewers": [], "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_review_thread_resolution": False,
                "allowed_merge_methods": ["merge", "squash", "rebase"],
            }},
        ],
    }


def before_test_cutover():
    snapshot = current_g1()
    checks = snapshot["rules"][2]["parameters"]["required_status_checks"]
    for check in checks:
        check["integration_id"] = 15368
    checks.append({"context": "handoff-contract", "integration_id": 15368})
    snapshot["rules"][3]["parameters"]["required_review_thread_resolution"] = True
    return snapshot


def planned_snapshot():
    snapshot = before_test_cutover()
    snapshot.update(plan_ruleset(snapshot, POLICY, retire_legacy_test_checks=True))
    return snapshot


def test_earlier_baseline_exposes_missing_consolidated_check_handoff_and_threads():
    assert validate_ruleset(current_g1(), POLICY) == [
        "missing required check: test",
        "missing required check: handoff-contract",
        "retired check is still required: test (3.12)",
        "retired check is still required: test (3.13)",
        "review threads must be resolved",
    ]


@pytest.mark.parametrize("name", ["test", "handoff-contract"])
def test_missing_required_context_fails(name):
    snapshot = planned_snapshot()
    checks = snapshot["rules"][2]["parameters"]["required_status_checks"]
    checks[:] = [c for c in checks if c["context"] != name]
    assert f"missing required check: {name}" in validate_ruleset(snapshot, POLICY)


@pytest.mark.parametrize("field,value,message", [
    ("strict_required_status_checks_policy", False, "up-to-date"),
    ("do_not_enforce_on_create", True, "branch creation"),
])
def test_weakened_check_requirements_fail(field, value, message):
    snapshot = planned_snapshot()
    snapshot["rules"][2]["parameters"][field] = value
    assert any(message in e for e in validate_ruleset(snapshot, POLICY))


def test_unresolved_threads_fail():
    snapshot = planned_snapshot()
    snapshot["rules"][3]["parameters"]["required_review_thread_resolution"] = False
    assert validate_ruleset(snapshot, POLICY) == ["review threads must be resolved"]


def test_planner_is_pure_idempotent_and_preserves_stronger_and_unrelated_settings():
    snapshot = before_test_cutover()
    snapshot["rules"].append({"type": "required_linear_history"})
    snapshot["rules"][2]["parameters"]["required_status_checks"].append(
        {"context": "security", "integration_id": 42}
    )
    snapshot["rules"][3]["parameters"].update(
        required_approving_review_count=2, require_code_owner_review=True,
        require_last_push_approval=True,
    )
    original = deepcopy(snapshot)
    planned = plan_ruleset(snapshot, POLICY, retire_legacy_test_checks=True)
    assert snapshot == original
    assert planned["rules"][4] == original["rules"][4]
    assert {
        "context": "security", "integration_id": 42,
    } in planned["rules"][2]["parameters"]["required_status_checks"]
    original_review = original["rules"][3]["parameters"]
    assert planned["rules"][3]["parameters"] == {
        **original_review, "required_review_thread_resolution": True,
    }
    snapshot.update(planned)
    assert validate_ruleset(snapshot, POLICY) == []
    assert plan_ruleset(snapshot, POLICY) == planned
    assert "id" not in planned and "source" not in planned


def test_only_explicit_cutover_retires_exact_legacy_checks():
    snapshot = before_test_cutover()
    before = {c["context"] for c in snapshot["rules"][2]["parameters"]["required_status_checks"]}
    staged = plan_ruleset(snapshot, POLICY)
    assert {c["context"] for c in staged["rules"][2]["parameters"]["required_status_checks"]} == before | {"test"}
    assert validate_ruleset({**snapshot, **staged}, POLICY) == [
        "retired check is still required: test (3.12)",
        "retired check is still required: test (3.13)",
    ]
    cutover = plan_ruleset(snapshot, POLICY, retire_legacy_test_checks=True)
    assert {c["context"] for c in cutover["rules"][2]["parameters"]["required_status_checks"]} == {
        "test", "handoff-contract",
    }
    assert validate_ruleset({**snapshot, **cutover}, POLICY) == []


def test_cutover_refuses_an_unexpected_legacy_provider():
    snapshot = before_test_cutover()
    snapshot["rules"][2]["parameters"]["required_status_checks"][0]["integration_id"] = 42
    with pytest.raises(ValueError, match="unexpected legacy check integration"):
        plan_ruleset(snapshot, POLICY, retire_legacy_test_checks=True)


def test_solo_owner_does_not_gain_impossible_approval_requirements():
    review = planned_snapshot()["rules"][3]["parameters"]
    assert review["required_approving_review_count"] == 0
    assert review["require_last_push_approval"] is False
    assert review["require_code_owner_review"] is False


@pytest.mark.parametrize("field,value", [
    ("id", 1), ("source", "someone/else"), ("source_type", "Organization"),
    ("target", "tag"), ("enforcement", "disabled"),
    ("bypass_actors", [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]),
    ("conditions", {"ref_name": {"include": ["refs/heads/main"], "exclude": ["refs/heads/main"]}}),
])
def test_unsafe_scope_refuses_both_validation_and_planning(field, value):
    snapshot = current_g1()
    snapshot[field] = value
    for operation in (validate_ruleset, plan_ruleset):
        with pytest.raises(ValueError):
            operation(snapshot, POLICY)


@pytest.mark.parametrize("kind", ["deletion", "non_fast_forward", "required_status_checks", "pull_request"])
@pytest.mark.parametrize("duplicate", [True, False])
def test_missing_or_duplicate_protection_is_not_silently_replaced(kind, duplicate):
    snapshot = current_g1()
    rule = next(r for r in snapshot["rules"] if r["type"] == kind)
    if duplicate:
        snapshot["rules"].append(deepcopy(rule))
    else:
        snapshot["rules"].remove(rule)
    with pytest.raises(ValueError, match="exactly one"):
        plan_ruleset(snapshot, POLICY)


def test_wrong_check_provider_requires_explicit_reconciliation():
    snapshot = planned_snapshot()
    snapshot["rules"][2]["parameters"]["required_status_checks"][0]["integration_id"] = 42
    assert "GitHub Actions" in validate_ruleset(snapshot, POLICY)[0]
    with pytest.raises(ValueError, match="unexpected check integration"):
        plan_ruleset(snapshot, POLICY)


def test_duplicate_context_is_ambiguous():
    snapshot = current_g1()
    snapshot["rules"][2]["parameters"]["required_status_checks"].append({"context": "test (3.12)"})
    with pytest.raises(ValueError, match="duplicate"):
        plan_ruleset(snapshot, POLICY)


def test_cli_rejects_drift_prints_only_plan_json_and_checks_readback(tmp_path):
    path = tmp_path / "ruleset.json"
    path.write_text(json.dumps(current_g1()))
    command = [sys.executable, str(ROOT / "scripts/check_github_merge_policy.py"), "--ruleset", str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1 and "missing required check: handoff-contract" in result.stderr
    snapshot = before_test_cutover()
    path.write_text(json.dumps(snapshot))
    result = subprocess.run([*command, "--plan", "--retire-legacy-test-checks"], capture_output=True, text=True)
    assert result.returncode == 0 and "PLAN ONLY" in result.stderr
    snapshot.update(json.loads(result.stdout))
    path.write_text(json.dumps(snapshot))
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0 and "supplied ruleset snapshot" in result.stdout
    path.write_text("{}")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1 and "invalid ruleset" in result.stderr


def test_required_handoff_has_one_unconditional_pr_job_including_body_edits():
    workflows = {
        path.name: yaml.safe_load(path.read_text())
        for path in (ROOT / ".github/workflows").glob("*.y*ml")
    }
    owners = [name for name, workflow in workflows.items() if "handoff-contract" in workflow.get("jobs", {})]
    assert owners == ["pr-handoff.yml"]
    workflow = workflows[owners[0]]
    events = workflow.get("on", workflow.get(True))
    assert events == {"pull_request": {"types": ["opened", "synchronize", "reopened", "edited"]}}
    assert workflow["permissions"] == {"contents": "read"}
    job = workflow["jobs"]["handoff-contract"]
    assert "if" not in job and "permissions" not in job and "continue-on-error" not in job
    assert all("if" not in s and "continue-on-error" not in s for s in job["steps"])
    checkout = next(s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["persist-credentials"] is False
    validation = next(s for s in job["steps"] if "--validate-event" in s.get("run", ""))
    assert validation["run"] == 'python scripts/linear_github_sync.py --validate-event "$GITHUB_EVENT_PATH"'
    assert "secrets." not in json.dumps(workflow)


@pytest.mark.parametrize(
    ("results", "exit_code"),
    [
        ("success,success,success,success", 0),
        ("success,success,skipped,success", 1),
        ("success,success,failure,success", 1),
        ("success,success,cancelled,success", 1),
        ("success,success,success", 1),
        ("", 1),
    ],
)
def test_actual_ci_gate_refuses_incomplete_proof(results, exit_code):
    jobs = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]
    gate = jobs["test"]
    assert gate["if"] == "${{ always() }}"
    assert gate["needs"] == ["preflight", "suite", "browser", "characterization-evidence"]
    assert "strategy" not in gate
    evidence_step = gate["steps"][0]
    assert evidence_step["env"] == {"REQUIRED_RESULTS": "${{ join(needs.*.result, ',') }}"}
    assert "if" not in evidence_step and "continue-on-error" not in evidence_step
    run = subprocess.run(
        ["bash", "-c", evidence_step["run"]],
        env={"REQUIRED_RESULTS": results},
        capture_output=True,
        text=True,
    )
    assert run.returncode == exit_code


def test_transition_names_report_the_same_test_result_without_rerunning_tests():
    legacy = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]["legacy-test-status"]
    assert legacy["name"] == "test (${{ matrix.python-version }})"
    assert legacy["strategy"]["matrix"] == {"python-version": ["3.12", "3.13"]}
    assert legacy["if"] == "${{ always() }}" and legacy["needs"] == "test"
    step, = legacy["steps"]
    assert step["env"] == {"TEST_RESULT": "${{ needs.test.result }}"}
    for result in ("success", "skipped", "failure", "cancelled", ""):
        exit_code = subprocess.run(["bash", "-c", step["run"]], env={"TEST_RESULT": result}).returncode
        assert exit_code == (0 if result == "success" else 1)
