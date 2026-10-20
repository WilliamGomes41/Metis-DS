"""Acceptance proof for the optional Bend workspace experiment (#773)."""

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


EXPERIMENT = Path(__file__).resolve().parents[1] / "experiments" / "bend"
BEND = shutil.which("bend")


@unittest.skipUnless(BEND, "Optional Bend toolchain is not installed")
class BendExperimentTests(unittest.TestCase):
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
