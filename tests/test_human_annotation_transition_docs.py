"""Check that the HA-4 inventory remains navigable; no runtime acceptance claim."""
from pathlib import Path
import re
import unittest

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = (
    "docs/change-contracts/1017-human-annotation-transition.md",
    "docs/plans/human-annotation-practice-acceptance.md",
)


class HumanAnnotationTransitionReferences(unittest.TestCase):
    def test_relative_document_links_resolve(self):
        for name in DOCUMENTS:
            document = ROOT / name
            for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                with self.subTest(document=name, target=target):
                    self.assertTrue(
                        (document.parent / target.split("#", 1)[0]).is_file(),
                        f"Broken local link in {name}: {target}",
                    )

    def test_inventory_source_and_script_paths_resolve(self):
        inventory = (ROOT / DOCUMENTS[0]).read_text(encoding="utf-8")
        paths = re.findall(r"`((?:src|scripts)/[^`\s]+\.py)`", inventory)
        self.assertTrue(paths, "Inventory must identify inspectable source paths")
        for name in paths:
            with self.subTest(path=name):
                self.assertTrue((ROOT / name).is_file(), f"Stale inventory path: {name}")


if __name__ == "__main__":
    unittest.main()
