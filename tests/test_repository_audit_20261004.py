"""Reproductions for the two non-semantic audit repairs.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
# No persistence writers change. Existing concurrency/stale regressions remain
# the behavioral evidence; the tests below cover the maintenance-only repairs.
import ast
from pathlib import Path
from typing import get_type_hints

from src.operations_console_app import ERROR_COPY
from src.workflows.workflow_identity_postgres_v1 import _PostgresIdentityMixin


def test_error_copy_has_no_silently_shadowed_literal_key():
    path = Path(__file__).resolve().parents[1] / "src/operations_console_app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mapping = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "ERROR_COPY" for t in node.targets))
    keys = [key.value for key in mapping.keys if isinstance(key, ast.Constant)]
    assert len(keys) == len(set(keys))
    assert ERROR_COPY["pre_review_llm_response_not_completed"].startswith(
        "De semantische verwerking is niet afgerond.")


def test_workflow_mirror_path_annotation_resolves():
    hints = get_type_hints(_PostgresIdentityMixin._startup_local_mirror_is_authority)
    assert hints["path"] is Path
    assert hints["return"] is bool
