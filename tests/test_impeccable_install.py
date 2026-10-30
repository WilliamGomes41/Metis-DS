"""Integrity and discovery contract for mandatory frontend design guidance.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]


def test_impeccable_snapshot_is_complete_and_matches_pinned_hashes():
    manifest = json.loads((ROOT / "config/impeccable.v1.json").read_text())
    assert manifest["repository"] == "https://github.com/pbakaus/impeccable"
    assert len(manifest["commit"]) == 40
    files = manifest["files"]
    for relative, digest in files.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
    base = ROOT / manifest["distribution"]
    installed = {str(p.relative_to(ROOT)) for p in base.rglob("*") if p.is_file()}
    assert installed == {p for p in files if p.startswith(manifest["distribution"] + "/")}
    for relative in ("SKILL.md", "reference/craft-floor.md", "scripts/impeccable",
                     "scripts/impeccable.cmd", "scripts/engine-checksums.txt"):
        assert (base / relative).is_file()


def test_frontend_trigger_and_provider_entrypoints_resolve_to_canonical_skill():
    agents = (ROOT / "AGENTS.md").read_text()
    section = agents.split("### Frontend design — Impeccable (mandatory)", 1)[1].split("\n### ", 1)[0]
    assert "agents MUST read and apply" in section
    assert "without\nrequiring the user to name the skill" in section
    assert ".agents/skills/impeccable/SKILL.md" in section
    assert "docs/agents/impeccable.md" in section
    for provider in (".claude", ".cursor"):
        adapter = ROOT / provider / "skills/impeccable/SKILL.md"
        text = adapter.read_text()
        assert (adapter.parent / "../../../.agents/skills/impeccable/SKILL.md").resolve().is_file()
        assert "skill base directory is `.agents/skills/impeccable`" in text
    for entry in ("CLAUDE.md", ".github/copilot-instructions.md"):
        assert "AGENTS.md" in (ROOT / entry).read_text()
