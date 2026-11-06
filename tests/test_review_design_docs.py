"""Integrity of the approved review design handoff; no runtime claims."""
import hashlib
import json
from pathlib import Path
import re
import unittest

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
ROOT = Path(__file__).resolve().parents[1]


class ReviewDesignArtifacts(unittest.TestCase):
    def test_approved_images_remain_identifiable_and_unchanged(self):
        folder = ROOT / "docs/design/review-card-receipt"
        provenance = json.loads((folder / "provenance.json").read_text())
        self.assertEqual(len(provenance["images"]), 2)
        for image in provenance["images"]:
            with self.subTest(image=image["file"]):
                content = (folder / image["file"]).read_bytes()
                self.assertTrue(content.startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertEqual(hashlib.sha256(content).hexdigest(), image["sha256"])

    def test_architecture_handoff_links_resolve(self):
        for name in (
            "docs/architecture/review-card-receipt.md",
            "docs/change-contracts/995-review-card-receipt-design.md",
        ):
            path = ROOT / name
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                if "://" not in target:
                    with self.subTest(document=name, target=target):
                        self.assertTrue((path.parent / target.split("#")[0]).exists())
        program = (ROOT / "docs/plans/ko-statechart-program.md").read_text()
        self.assertIn("../architecture/review-card-receipt.md", program)


if __name__ == "__main__":
    unittest.main()
