"""Local command construction protects existing source fields and relationship identity.

The card links nothing as essential; the dead repair path for essential links is gone (#1060, slice 5).

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from pathlib import Path
import subprocess


def test_context_binding_preserves_existing_fields_and_relationship_identity():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', str(root / 'tests/annotation_binding_task_check.mjs')],
                   cwd=root, check=True, capture_output=True, text=True)
