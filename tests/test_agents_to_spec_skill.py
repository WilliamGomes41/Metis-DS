"""Pointer tests for the repository-native to-spec agent skill."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_to_spec_skill_is_wired_and_repository_native() -> None:
    skill = ROOT / ".agents/skills/to-spec/SKILL.md"
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    triage = (ROOT / "docs/agents/triage-labels.md").read_text(encoding="utf-8")

    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "name: to-spec" in text
    assert "docs/agents/continuous-development.md" in text
    assert "docs/agents/abstraction-boundaries.md" in text
    assert "ready-for-agent" in text
    assert "needs-info" in text
    assert "Stateful Class B" in text
    assert "Rewrite risk" in text
    assert ".agents/skills/to-spec/" in agents

    visible = "\n".join([text, agents, triage]).lower()
    assert "mattpocock" not in visible
    assert "matt pocock" not in visible
