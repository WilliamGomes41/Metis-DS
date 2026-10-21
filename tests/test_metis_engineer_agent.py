from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def _contains_all(text: str, *terms: str) -> bool:
    lowered = text.lower()
    return all(term.lower() in lowered for term in terms)


def test_metis_engineer_agent_is_explicit_and_fail_closed() -> None:
    profile_path = ROOT / ".github/agents/metis-engineer.agent.md"
    execution_path = ROOT / "docs/agents/execution-contract.md"
    agents_path = ROOT / "AGENTS.md"

    assert profile_path.is_file()
    assert execution_path.is_file()

    profile = profile_path.read_text(encoding="utf-8")
    execution = execution_path.read_text(encoding="utf-8")
    agents = agents_path.read_text(encoding="utf-8")

    assert "name: Metis Engineer" in profile
    assert "target: github-copilot" in profile
    assert "disable-model-invocation: true" in profile
    assert "user-invocable: true" in profile
    assert "ready-for-agent" in profile
    assert "Work on exactly one issue per run" in profile
    assert "Do not deploy" in profile
    assert "merge your own pull request" in profile.lower()

    # Check the behavioral contract rather than one editorial sentence.
    assert "vertical slice" in profile.lower()
    assert _contains_all(profile, "user promise", "crosses layers")
    assert _contains_all(profile, "promise", "not complete", "end-to-end evidence")

    assert "does **not** start an agent by itself" in execution
    assert "explicitly assigns one issue" in execution
    assert "must stop without modifying code" in execution
    assert "must not merge its own PR" in execution
    assert "## Vertical-slice completeness" in execution
    assert "trigger -> authorization -> validation -> domain transition" in execution
    assert "frontend-only, API-only, backend-only, or storage-only" in execution
    assert _contains_all(execution, "layers", "required by", "promise")

    assert ".github/agents/metis-engineer.agent.md" in agents
    assert "docs/agents/execution-contract.md" in agents
