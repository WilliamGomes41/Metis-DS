"""Keep the README usable as an entry point to repository documentation.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""

from pathlib import Path
import re


def test_readme_documentation_links_resolve():
    root = Path(__file__).resolve().parents[1]
    document = (root / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", document)
    local_links = [link for link in links if not link.startswith(("https://", "http://", "#"))]
    assert local_links, "README must point readers to repository documentation"
    missing = [link for link in local_links if not (root / link.split("#", 1)[0]).exists()]
    assert not missing, f"Broken README links: {missing}"
