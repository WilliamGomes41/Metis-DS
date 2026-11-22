"""Keep README links usable as documentation entry points.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from pathlib import Path
import re


def test_entry_documentation_links_resolve():
    filename = "README.md"
    root = Path(__file__).resolve().parents[1]
    document = (root / filename).read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document)
    local_links = [link for link in links if not link.startswith(("https://", "http://", "#"))]
    assert local_links, f"{filename} must point readers to repository documentation"
    missing = [link for link in local_links if not (root / link.split("#", 1)[0]).exists()]
    assert not missing, f"Broken {filename} links: {missing}"



def test_repository_does_not_have_a_handoff_layer():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "HANDOFF.md").exists()
