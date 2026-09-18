from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def test_agent_skill_wayfinding_docs_are_present_and_linked() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    expected_docs = (
        "docs/agents/issue-tracker.md",
        "docs/agents/triage-labels.md",
        "docs/agents/domain.md",
    )
    for relative_path in expected_docs:
        assert relative_path in agents
        assert (ROOT / relative_path).is_file()

    issue_tracker = (ROOT / "docs/agents/issue-tracker.md").read_text(encoding="utf-8")
    assert "Issues and specs for this repo live as GitHub issues" in issue_tracker

    triage_labels = (ROOT / "docs/agents/triage-labels.md").read_text(encoding="utf-8")
    for label in (
        "needs-triage",
        "needs-info",
        "ready-for-agent",
        "ready-for-human",
        "wontfix",
    ):
        assert label in triage_labels


def test_class_b_program_design_gate_requires_existing_path_before_code() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    required_contract = (
        "### Class B program-design gate",
        "trace the existing execution path",
        "the existing mechanism and authority",
        "the affected functions, types, and call path",
        "which state may mutate and which state must remain unchanged",
        "the smallest observable proof of the change",
        "before editing production code",
        "investigate first instead of patching",
        "MUST NOT be expanded into lifecycle-grade paperwork",
    )
    for phrase in required_contract:
        assert phrase in agents
