"""Local command construction protects existing source fields and essential duties."""
from pathlib import Path
import subprocess


def test_context_binding_preserves_existing_fields_and_relationship_identity():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', str(root / 'tests/annotation_binding_task_check.mjs')],
                   cwd=root, check=True, capture_output=True, text=True)
