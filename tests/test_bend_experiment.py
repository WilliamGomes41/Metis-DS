"""Acceptance proof for the optional Bend workspace experiment (#773)."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "bend"
BEND = shutil.which("bend")


@unittest.skipUnless(BEND, "Optional Bend toolchain is not installed")
class BendExperimentTests(unittest.TestCase):
    def run_import_audit(self, root: Path, *args):
        result = subprocess.run(
            [sys.executable, str(EXPERIMENT / "pr-d3" / "audit.py"), "--root", str(root), *args],
            capture_output=True, text=True, timeout=90,
            env={**os.environ, "BEND_NO_TELEMETRY": "1"},
        )
        return result, json.loads(result.stdout)

    def test_d3_source_derived_import_boundary(self):
        result, report = self.run_import_audit(EXPERIMENT.parents[1])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(report["python_boundary_pass"])
        self.assertIn("ALL PROOFS CHECK", report["bend_output"])
        self.assertFalse(any(row["target_paths"] for row in report["roots"].values()))

    def test_d3_python_and_bend_reject_same_live_relative_import(self):
        with tempfile.TemporaryDirectory(prefix="metis-d3-import-negative-") as directory:
            target = Path(directory)
            for name in ("src", "scripts"):
                shutil.copytree(EXPERIMENT.parents[1] / name, target / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
            entry = target / "src" / "service_app.py"
            with entry.open("a") as stream:
                stream.write("\nfrom .retrieval import provider_vector_retrieval_v1\n")
            ordinary, ordinary_report = self.run_import_audit(target, "--python-only")
            result, report = self.run_import_audit(target)
            self.assertNotEqual(ordinary.returncode, 0)
            self.assertFalse(ordinary_report["python_boundary_pass"])
            self.assertTrue(ordinary_report["roots"]["src.service_app"]["target_paths"])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SOME PROOFS FAIL", report["bend_output"])
            self.assertIn("no_external_import_into_removed_route", report["bend_output"])
            self.assertIn("expected : False{}", report["bend_output"])
            self.assertIn("observed : True{}", report["bend_output"])

    def run_bend(self, path: Path, entry: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [BEND, entry], cwd=path, capture_output=True, text=True,
            env={**os.environ, "BEND_NO_TELEMETRY": "1"}, timeout=60,
        )

    def test_example_and_standard_proof(self):
        example = self.run_bend(EXPERIMENT, "Demo.bend")
        self.assertEqual(example.returncode, 0, example.stdout + example.stderr)
        self.assertEqual(example.stdout.strip(), "42n")
        proof = self.run_bend(EXPERIMENT, "PROOF.bend")
        self.assertEqual(proof.returncode, 0, proof.stdout + proof.stderr)
        self.assertIn("ALL PROOFS CHECK", proof.stdout)

    def test_law_rejects_incorrect_implementation(self):
        with tempfile.TemporaryDirectory(prefix="metis-bend-negative-") as directory:
            target = Path(directory)
            for name in ("Demo.bend", "LAWS.bend", "PROOF.bend"):
                shutil.copyfile(EXPERIMENT / name, target / name)
            # Well-typed, terminating, but fails preservation for n != 0.
            (target / "Demo.bend").write_text(
                "import Base\n\ndef identity(n: Nat) -> Nat:\n  0n\n",
                encoding="utf-8",
            )
            result = self.run_bend(target, "PROOF.bend")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SOME PROOFS FAIL", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
