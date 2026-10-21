"""Pointer tests for improve-codebase-architecture agent skill install.

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


def test_improve_codebase_architecture_skill_wired() -> None:
    skill = ROOT / ".agents/skills/improve-codebase-architecture/SKILL.md"
    report = ROOT / ".agents/skills/improve-codebase-architecture/HTML-REPORT.md"
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert skill.is_file()
    assert report.is_file()
    text = skill.read_text(encoding="utf-8")
    assert "improve-codebase-architecture" in text
    assert "deepening" in text.lower() or "deep module" in text.lower() or "depth" in text.lower()
    assert ".agents/skills/improve-codebase-architecture" in agents
