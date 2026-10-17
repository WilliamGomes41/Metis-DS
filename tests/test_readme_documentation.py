"""Keep the README and roadmap links usable as documentation entry points.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from pathlib import Path
import re

import pytest


@pytest.mark.parametrize("filename", ["README.md", "ROADMAP.md"])
def test_entry_documentation_links_resolve(filename):
    root = Path(__file__).resolve().parents[1]
    document = (root / filename).read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document)
    local_links = [link for link in links if not link.startswith(("https://", "http://", "#"))]
    assert local_links, f"{filename} must point readers to repository documentation"
    missing = [link for link in local_links if not (root / link.split("#", 1)[0]).exists()]
    assert not missing, f"Broken {filename} links: {missing}"


def test_roadmap_current_state_is_a_pointer_not_a_handoff_layer():
    root = Path(__file__).resolve().parents[1]
    roadmap = (root / "ROADMAP.md").read_text(encoding="utf-8")
    assert re.search(r"\*\*Gecontroleerde main:\*\* \[`[0-9a-f]{40}`\]", roadmap)
    section_start = roadmap.index("## Actuele stand")
    assert section_start < roadmap.index("## R4.1")
    section = roadmap[section_start:roadmap.index("## R4.1")]
    assert "GitHub-issues blijven de voortgangsbron" in section
    assert "geen tweede statusadministratie" in section
    assert not (root / "HANDOFF.md").exists()
