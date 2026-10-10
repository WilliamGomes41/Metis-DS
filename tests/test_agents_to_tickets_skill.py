"""Pointer tests for the repository-native to-tickets agent skill."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs


def test_to_tickets_skill_is_wired_and_repository_native() -> None:
    skill = ROOT / ".agents/skills/to-tickets/SKILL.md"
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "name: to-tickets" in text
    assert "docs/agents/continuous-development.md" in text
    assert "docs/agents/issue-tracker.md" in text
    assert "Change class: A | B | C" in text
    assert "Rewrite risk: none | high" in text
    assert "Stateful Class B" in text
    assert "ready-for-agent" in text
    assert "needs-info" in text
    assert "native blocking dependencies" in text
    assert ".agents/skills/to-tickets/" in agents

    visible = "\n".join([text, agents]).lower()
    assert "mattpocock" not in visible
    assert "matt pocock" not in visible
