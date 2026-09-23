"""Contract tests for Metis continuous-development and lifecycle-VSA governance.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _assert_terms(text: str, *terms: str) -> None:
    lowered = text.lower()
    for term in terms:
        assert term.lower() in lowered


def test_agent_entrypoints_route_through_continuous_development_model() -> None:
    agents = _read("AGENTS.md")
    execution = _read("docs/agents/execution-contract.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")

    model_ref = "docs/agents/continuous-development.md"
    assert model_ref in agents
    assert model_ref in execution
    assert model_ref in engineer

    # Prove each entrypoint routes work through the same A/B/C classifier without
    # requiring every document to spell each class name in the same editorial form.
    _assert_terms(agents, "Class A", "Class B", "Class C")
    _assert_terms(execution, "Class A", "Class B", "Class C")
    _assert_terms(engineer, "classify the issue", "Class A, B, or C", "before implementation")
    _assert_terms(engineer, "Class B or C", "stop", "reclassify")

    _assert_terms(agents, "lightest process", "safely proves the promise")
    _assert_terms(execution, "classifies the issue", "A, B, or C", "before implementation")
    _assert_terms(engineer, "stop", "reclassify")


def test_continuous_development_model_limits_heavy_governance_to_lifecycle_core() -> None:
    model = _read("docs/agents/continuous-development.md")

    assert "Class A — Lifecycle core" in model
    assert "Class B — Normal product behavior" in model
    assert "Class C — Cosmetic, copy, documentation, and non-semantic maintenance" in model
    _assert_terms(model, "lightest process", "safely proves the user promise")
    assert "Class A MUST follow `docs/agents/lifecycle-vsa.md` in full." in model
    _assert_terms(model, "do not create lifecycle paperwork", "lifecycle semantics are unchanged")

    # VSA governs promise completeness, not the size/count of implementation PRs.
    _assert_terms(model, "VSA means user-promise completeness, not PR size")
    _assert_terms(model, "multiple small PRs", "user promise", "proven end to end")

    assert "MUST NOT create a new architecture rule unless it prevents a named failure mode" in model
    assert "MUST NOT create a new durable source of truth" in model
    assert "Stop implementation and return to design" in model
    _assert_terms(model, "cost of proving a change", "proportional to the risk")


def test_rewrite_risk_is_mandatory_semantic_and_fail_closed() -> None:
    model = _read("docs/agents/continuous-development.md")

    assert "Rewrite risk: none | high" in model
    _assert_terms(model, "rewrite risk is semantic", "not a line-count threshold")
    _assert_terms(
        model,
        "durable authority",
        "persisted identity",
        "shared mutation",
        "migration/cutover",
        "restart/recovery",
    )
    for field in (
        "Rewrite target:",
        "Why local patching is insufficient:",
        "Current authority/writer/reader map:",
        "Supported runtime topologies:",
        "Persisted-state impact:",
        "Compatibility/migration plan:",
        "Rollback/recovery plan:",
        "Cutover trigger:",
        "Cleanup/decommission criteria:",
        "Failure blast radius:",
        "Adversarial proof matrix:",
    ):
        assert field in model

    _assert_terms(model, "big-bang replacement is forbidden by default")
    _assert_terms(model, "temporary dual-read or dual-write", "one authority", "reconciliation", "removal/expiry")
    _assert_terms(model, "destructive or irreversible migration", "explicit human approval", "backup/recovery")
    _assert_terms(model, "separate adversarial review pass", "green CI", "not by itself proof")
    _assert_terms(model, "rewrite risk is discovered after implementation started", "STOP")


def test_high_risk_rewrite_rules_reach_execution_and_pr_surfaces() -> None:
    agents = _read("AGENTS.md")
    execution = _read("docs/agents/execution-contract.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")
    template = _read(".github/pull_request_template.md")

    for text in (agents, execution, engineer, template):
        _assert_terms(text, "Rewrite risk", "high")

    _assert_terms(agents, "authority", "writer", "reader", "adversarial")
    _assert_terms(execution, "big-bang", "destructive or irreversible migration", "human approval")
    _assert_terms(engineer, "stop and rescope", "temporary dual-read/dual-write", "green CI")
    _assert_terms(
        template,
        "Current authority/writer/reader map",
        "rollback/recovery",
        "cutover trigger",
        "failure blast radius",
        "separate adversarial review",
    )


def test_lifecycle_entrypoints_require_same_normative_contract_for_class_a() -> None:
    agents = _read("AGENTS.md")
    execution = _read("docs/agents/execution-contract.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")

    contract_ref = "docs/agents/lifecycle-vsa.md"
    assert contract_ref in agents
    assert contract_ref in execution
    assert contract_ref in engineer

    assert "Class A issues MUST also follow `docs/agents/lifecycle-vsa.md` in full." in agents
    assert "is normative" in execution
    assert "read and apply `docs/agents/lifecycle-vsa.md` in full before implementation" in engineer
    assert "Do not fill the gap with a reasonable assumption" in engineer


def test_lifecycle_contract_defines_stable_entities_and_single_authorities() -> None:
    contract = _read("docs/agents/lifecycle-vsa.md")

    for entity in (
        "LogicalDocument",
        "SourceSnapshot",
        "WorkingRevision",
        "PublicationRelease",
    ):
        assert f"### {entity}" in contract

    assert "One LogicalDocument MUST have at most one active serving release." in contract
    assert "Source bytes: immutable source store." in contract
    assert "Working/review state: durable workflow PostgreSQL state." in contract
    assert "Historically published canonical object versions/releases: canonical publication store." in contract
    assert "Current serving eligibility: publication registry." in contract
    assert "UI/envelope state MUST NOT become a second serving authority." in contract


def test_lifecycle_contract_forbids_reopening_published_work_in_place() -> None:
    contract = _read("docs/agents/lifecycle-vsa.md")

    assert "A policy upgrade MUST NOT reopen or mutate a previously published WorkingRevision in place." in contract
    assert "Startup migrations MUST NOT silently turn a published revision back into current review work." in contract
    assert "The valid state `published v1 + working v2 in review` MUST be supported." in contract
    assert "the existing active release MUST remain active and immutable while the successor is processed or reviewed." in contract


def test_successor_publication_and_withdrawal_are_closed_lifecycle_transitions() -> None:
    contract = _read("docs/agents/lifecycle-vsa.md")

    assert "publication of W2 MUST be one atomic lifecycle transition." in contract
    assert "R2 serving state = `active`;" in contract
    assert "R1 release state = `superseded`;" in contract
    assert "R1 serving state = `inactive`;" in contract
    assert "There MUST be no observable successful intermediate state with both R1 and R2 active" in contract
    assert "On failure the transition MUST fail closed: R1 remains active and R2 does not become active." in contract

    assert "an authorized withdrawal MUST require an explicit reason" in contract
    assert "release state = `withdrawn`;" in contract
    assert "serving state = `inactive`;" in contract
    assert "Restart/recovery MUST NOT reactivate the release." in contract


def test_lifecycle_high_risk_rewrite_requires_surface_map_and_adversarial_proof() -> None:
    contract = _read("docs/agents/lifecycle-vsa.md")

    assert "## 13A. High-risk rewrite overlay" in contract
    _assert_terms(contract, "authority/writer/reader map", "inheritance/override", "storage backends")
    _assert_terms(contract, "rollback-capable", "temporary dual-read/dual-write", "one named authority")
    _assert_terms(contract, "separate adversarial review", "failed cutover", "green CI")
    _assert_terms(contract, "irreversible migration", "explicit human approval", "backup/recovery")


def test_lifecycle_slice_requires_exact_transition_and_black_box_proof() -> None:
    contract = _read("docs/agents/lifecycle-vsa.md")

    for field in (
        "Lifecycle entity:",
        "Lifecycle transition:",
        "Initial durable state:",
        "Trigger:",
        "Mutable entities:",
        "Immutable entities:",
        "Workflow state before:",
        "Workflow state after:",
        "Release state before:",
        "Release state after:",
        "Serving state before:",
        "Serving state after:",
        "Failure result:",
        "Restart result:",
        "Recovery result:",
        "Required black-box scenario:",
        "Explicit non-goals:",
        "Rewrite risk: none | high",
    ):
        assert field in contract

    assert "A relevant item with `FAIL`, `UNKNOWN`, or `NOT TESTED` means the slice is NOT DONE." in contract
    assert "The agent MUST NOT fill these gaps with a reasonable assumption." in contract
    assert "one black-box lifecycle closure scenario passes" in contract


def test_stateful_class_b_requires_domain_first_gate_before_vsa() -> None:
    agents = _read("AGENTS.md")
    model = _read("docs/agents/continuous-development.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")

    _assert_terms(agents, "Class B", "durable domain state", "Stateful Class B domain-first overlay", "before VSA")
    assert "#### Stateful Class B domain-first overlay" in model

    for field in (
        "Domain entity/aggregate:",
        "Invariant(s):",
        "Durable state before:",
        "Durable state after:",
        "Transaction boundary:",
        "Failure/recovery result:",
        "Duplicate execution / idempotency result:",
        "Concurrency result:",
        "Audit/evidence requirement:",
    ):
        assert field in model

    _assert_terms(
        engineer,
        "Class B",
        "creates or mutates durable domain state",
        "stateful Class B domain-first overlay",
        "before implementation",
    )
    _assert_terms(engineer, "stateful Class B", "domain-first overlay", "continuous-development.md")


def test_stateful_class_b_gate_is_lightweight_and_escalates_only_when_needed() -> None:
    agents = _read("AGENTS.md")
    model = _read("docs/agents/continuous-development.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")

    _assert_terms(model, "Apply this overlay only when a Class B change creates or mutates durable domain state")
    _assert_terms(model, "Do not apply it to stateless reads", "presentation-only behavior", "no durable state transition")
    _assert_terms(model, "not a second lifecycle contract", "publication lifecycle truth", "lifecycle-vsa.md")
    _assert_terms(model, "STOP", "reclassify to Class A", "before implementation")
    _assert_terms(agents, "document owns the criteria and escalation rule")
    _assert_terms(engineer, "stateful Class B", "before VSA")
