from pathlib import Path
import re


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


def test_dispatcher_is_discoverable_and_preserves_selection_boundaries() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    relative_path = ".agents/skills/skill-dispatcher/SKILL.md"
    assert f"[skill-dispatcher]({relative_path})" in agents
    skill = (ROOT / relative_path).read_text(encoding="utf-8")
    assert skill.startswith("---\nname: skill-dispatcher\ndescription: ")
    assert "gearchiveerde" in skill
    assert "expliciet" in skill
    assert "geen extra toestemming" in skill
    assert "routeer niet recursief" in skill
    interface = (ROOT / relative_path).parent / "agents/openai.yaml"
    assert "$skill-dispatcher" in interface.read_text(encoding="utf-8")


def test_dispatcher_examples_use_current_names_and_explicit_only_boundaries() -> None:
    skill = (ROOT / ".agents/skills/skill-dispatcher/SKILL.md").read_text(encoding="utf-8")
    rows = [line for line in skill.splitlines() if line.startswith("| ")]
    examples = "\n".join(rows)
    assert "`decision-oriented-writing`" in examples
    assert "`literature-review`" in examples
    for name in (
        "codebase-architecture-review",
        "agent-authorization-and-completion-gates",
        "assumption-testing-interview",
    ):
        row = next(line for line in rows if f"`{name}`" in line)
        assert "expliciet" in row
    obsolete = {
        "external-agent-gates", "grill-me", "minto", "via-negativa-redacteur",
        "heldere-uitleg", "literature-review-suite", "concise-text-editor", "clear-explanation",
    }
    assert not obsolete.intersection(re.findall(r"`([^`]+)`", examples))
def test_agents_requires_one_deterministic_candidate_creator_before_review():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = agents.split("### Hard invariant: one deterministic candidate creator before human review", 1)[1].split("\n### ", 1)[0]
    for obligation in (
        "deterministic materialisation MUST be the sole KnowledgeCandidate creator",
        "src/knowledge_materialisation_v1.py::materialise_knowledge_candidates",
        "They MUST NOT independently assign candidate identity",
        "they MUST NOT independently create, rewrite, split, merge, or silently repair a candidate",
        "Rejection MUST preserve source work and recovery findings",
        "every supported pre-review route uses the same creator",
        "This pre-review invariant grants no additional review or publication authority",
        "agents MUST NOT weaken or bypass it autonomously",
    ):
        assert obligation in section
