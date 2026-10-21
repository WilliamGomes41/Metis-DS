"""Reproducible shared skills and repository instruction contracts (#777)."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/sync_shared_agent_skills.py"


class SharedSkillSyncTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.source = self.base / "source"
        self.source.mkdir()
        self.checkout = self.base / "metis"
        (self.checkout / "scripts").mkdir(parents=True)
        shutil.copyfile(SCRIPT, self.checkout / "scripts" / SCRIPT.name)
        self.original = b'---\nname: fixture\ndescription: "Verify a fixture claim."\n---\n\nCompare the evidence.\n'
        (self.source / "SKILL.md").write_bytes(self.original)
        (self.source / "LICENSE").write_text("MIT fixture notice\n")
        self.git("init", "-q")
        self.commit()
        self.lock = {
            "version": 1, "repository": "fixture", "commit": self.git("rev-parse", "HEAD"),
            "files": [
                {"source": "SKILL.md", "destination": ".agents/skills/fixture/SKILL.md",
                 "sha256": hashlib.sha256(self.original).hexdigest()},
                {"source": "LICENSE", "destination": ".agents/licenses/fixture.txt",
                 "sha256": hashlib.sha256(b"MIT fixture notice\n").hexdigest()},
            ],
        }
        self.write_lock()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.source), *args], text=True).strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "-c", "user.name=Fixture",
                 "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture")

    def write_lock(self):
        (self.checkout / "config").mkdir(exist_ok=True)
        (self.checkout / "config/shared_agent_skills.v1.json").write_text(json.dumps(self.lock))

    def run_sync(self, *args):
        return subprocess.run([sys.executable, str(self.checkout / "scripts" / SCRIPT.name), *args],
                              capture_output=True, text=True, timeout=30)

    def install(self):
        result = self.run_sync("--source", str(self.source))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_reproduce_and_check_offline_with_same_claude_procedure(self):
        self.install()
        canonical = self.checkout / ".agents/skills/fixture/SKILL.md"
        self.assertEqual(canonical.read_bytes(), self.original)
        adapter = self.checkout / ".claude/skills/fixture/SKILL.md"
        self.assertIn("../../../.agents/skills/fixture/SKILL.md", adapter.read_text())
        self.assertIn("AGENTS.md", adapter.read_text())
        shutil.rmtree(self.source)
        result = self.run_sync("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_upstream_worktree_and_head_do_not_upgrade_the_pin(self):
        (self.source / "SKILL.md").write_bytes(self.original + b"Unreviewed change\n")
        self.commit()
        self.install()
        self.assertEqual((self.checkout / ".agents/skills/fixture/SKILL.md").read_bytes(), self.original)

    def test_bad_source_checksum_writes_nothing(self):
        self.lock["files"][1]["sha256"] = "0" * 64
        self.write_lock()
        result = self.run_sync("--source", str(self.source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum mismatch", result.stderr)
        self.assertFalse((self.checkout / ".agents").exists())

    def test_local_edits_are_detected_and_not_overwritten(self):
        self.install()
        canonical = self.checkout / ".agents/skills/fixture/SKILL.md"
        canonical.write_bytes(b"Local work\n")
        self.assertNotEqual(self.run_sync("--check").returncode, 0)
        self.assertNotEqual(self.run_sync("--source", str(self.source)).returncode, 0)
        self.assertEqual(canonical.read_bytes(), b"Local work\n")

    def test_drifted_or_missing_claude_adapter_fails_the_check(self):
        self.install()
        adapter = self.checkout / ".claude/skills/fixture/SKILL.md"
        adapter.write_text("Different workflow\n")
        self.assertNotEqual(self.run_sync("--check").returncode, 0)
        adapter.unlink()
        self.assertNotEqual(self.run_sync("--check").returncode, 0)

    def test_escape_path_and_empty_selection_are_rejected(self):
        self.lock["files"][0]["destination"] = "../escape.md"
        self.write_lock()
        self.assertNotEqual(self.run_sync("--source", str(self.source)).returncode, 0)
        self.assertFalse((self.base / "escape.md").exists())
        self.lock["files"] = []
        self.write_lock()
        self.assertNotEqual(self.run_sync("--check").returncode, 0)


class SharedInstructionContractTests(unittest.TestCase):
    def test_checksummed_files_have_stable_checkout_line_endings(self):
        lock = json.loads((ROOT / "config/shared_agent_skills.v1.json").read_text())
        paths = [item["destination"] for item in lock["files"]]
        paths += [".claude/skills/verify-this/SKILL.md", ".claude/skills/make-pr-easy-to-review/SKILL.md"]
        for path in paths:
            attribute = subprocess.check_output(["git", "check-attr", "eol", "--", path], cwd=ROOT, text=True)
            self.assertTrue(attribute.strip().endswith(": lf"), attribute)

    def test_real_selection_and_all_adapters_are_valid_offline(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--check"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lock = json.loads((ROOT / "config/shared_agent_skills.v1.json").read_text())
        self.assertEqual(lock["repository"], "https://github.com/WilliamGomes41/plugins.git")
        names = {Path(item["destination"]).parent.name for item in lock["files"]
                 if item["destination"].endswith("/SKILL.md")}
        self.assertEqual(names, {"verify-this", "make-pr-easy-to-review"})

    def test_agent_entrypoints_retain_metis_authority(self):
        for relative in ("CLAUDE.md", ".github/copilot-instructions.md"):
            text = (ROOT / relative).read_text()
            self.assertIn("AGENTS.md", text)
            self.assertIn("docs/agents/shared-skills.md", text)
        index = (ROOT / "docs/agents/shared-skills.md").read_text()
        self.assertIn("not execution, merge, deployment, or\npublication authority", index)
        self.assertIn("do not add a duplicate mandatory verification pass", index)
        for relative in (".agents/skills/verify-this/SKILL.md", ".agents/skills/make-pr-easy-to-review/SKILL.md"):
            header = (ROOT / relative).read_text().split("---", 2)[1]
            self.assertNotIn("allowed-tools:", header)
            self.assertNotIn("hooks:", header)


if __name__ == "__main__":
    unittest.main()
