"""Integrity and discovery contract for the pinned Emil Kowalski design skills.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import hashlib
import json


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ("emil-design-eng", "break-ui", "mobile-native")


def _manifest():
    return json.loads((ROOT / "config/emil_design_skills.v1.json").read_text())


def test_snapshot_is_complete_and_matches_pinned_hashes():
    manifest = _manifest()
    assert manifest["repository"] == "https://github.com/emilkowalski/skills"
    assert len(manifest["commit"]) == 40
    assert tuple(manifest["skills"]) == SKILLS
    files = manifest["files"]
    for relative, digest in files.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == digest, relative
    installed = {
        path.relative_to(ROOT).as_posix()
        for name in SKILLS for path in (ROOT / ".agents/skills" / name).rglob("*") if path.is_file()
    }
    assert installed == {path for path in files if path.startswith(".agents/skills/")}
    assert ".agents/licenses/emil-skills-MIT.txt" in files


def test_adapters_repeat_upstream_metadata_and_link_to_the_canonical_skill():
    for name in SKILLS:
        canonical = (ROOT / ".agents/skills" / name / "SKILL.md").read_text()
        header = canonical.split("---", 2)[1]
        for provider in (".claude", ".cursor"):
            adapter = ROOT / provider / "skills" / name / "SKILL.md"
            text = adapter.read_text()
            for line in header.splitlines():
                if line.startswith(("name:", "description:")):
                    assert line in text, (provider, name)
            assert (adapter.parent / f"../../../.agents/skills/{name}/SKILL.md").resolve().is_file()
            assert "docs/agents/emil-design-skills.md" in text


def test_impeccable_stays_the_mandatory_workflow_and_the_toggle_stays_out():
    agents = (ROOT / "AGENTS.md").read_text()
    section = agents.split("### Frontend interaction craft — Emil Kowalski skills", 1)[1].split("\n### ", 1)[0]
    assert "docs/agents/emil-design-skills.md" in section
    assert "Impeccable remains the mandatory" in section
    document = (ROOT / "docs/agents/emil-design-skills.md").read_text()
    assert _manifest()["commit"] in document
    assert "Do not add that toggle" in document
    assert "do not add a frontend\n  framework" in document
    for name in SKILLS:
        assert f".agents/skills/{name}/SKILL.md" in document
