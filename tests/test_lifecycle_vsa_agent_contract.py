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


def test_agent_entrypoints_route_through_continuous_development_model() -> None:
    agents = _read("AGENTS.md")
    execution = _read("docs/agents/execution-contract.md")
    engineer = _read(".github/agents/metis-engineer.agent.md")

    model_ref = "docs/agents/continuous-development.md"
    assert model_ref in agents
    assert model_ref in execution
    assert model_ref in engineer

    assert "Class A" in agents and "Class B" in agents and "Class C" in agents
    assert "Apply the lightest process that safely proves the promise" in agents
    assert "classify the issue as A, B, or C" in execution
    assert "classify the issue as Class A, B, or C before implementation" in engineer
    assert "stop and reclassify" in engineer.lower()


def test_continuous_development_model_limits_heavy_governance_to_lifecycle_core() -> None:
    model = _read("docs/agents/continuous-development.md")

    assert "Class A — Lifecycle core" in model
    assert "Class B — Normal product behavior" in model
    assert "Class C — Cosmetic, copy, documentation, and non-semantic maintenance" in model
    assert "apply the lightest process that safely proves the user promise" in model.lower()
    assert "Class A MUST follow `docs/agents/lifecycle-vsa.md` in full." in model
    assert "do not create lifecycle paperwork when lifecycle semantics are unchanged" in model
    assert "Vertical slicing defines promise completeness, not mandatory PR size." in model
    assert "MUST NOT create a new architecture rule unless it prevents a named failure mode" in model
    assert "MUST NOT create a new durable source of truth" in model
    assert "Stop implementation and return to design" in model
    assert "the cost of proving a change is proportional to the risk of the change" in model


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
    ):
        assert field in contract

    assert "A relevant item with `FAIL`, `UNKNOWN`, or `NOT TESTED` means the slice is NOT DONE." in contract
    assert "The agent MUST NOT fill these gaps with a reasonable assumption." in contract
    assert "one black-box lifecycle closure scenario passes" in contract
