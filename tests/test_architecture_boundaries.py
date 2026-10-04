"""Executable agent dependency rules, including deliberately injected bypasses.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from scripts.check_architecture_boundaries import (
    PROTECTED_MODULES, SDK_OWNER, check_boundaries, main,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repository(tmp_path):
    for relative in (SDK_OWNER, *PROTECTED_MODULES):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return tmp_path


def test_current_repository_satisfies_boundaries():
    assert check_boundaries(ROOT) == []


@pytest.mark.parametrize("code", [
    "import docling as sdk",
    "def convert():\n    from docling.document_converter import DocumentConverter",
    "if False:\n    import docling_core.types.doc",
    "import importlib as loader\nloader.import_module('docling.document_converter')",
    "from importlib import import_module as load\nload('docling_core.types.doc')",
    "__import__('docling')",
    "import importlib\nimportlib.import_module(name='docling_core.types.doc')",
    "from .docling_worker_v1 import main",
    "import importlib\nimportlib.import_module('src.docling_worker_v1')",
])
def test_sdk_cannot_bypass_worker(repository, code):
    (repository / "src/new_route.py").write_text(code, encoding="utf-8")
    errors = check_boundaries(repository)
    assert errors and all("docling-worker-only" in error for error in errors)
    assert all("src/new_route.py:" in error for error in errors)


@pytest.mark.parametrize("code", [
    "import psycopg",
    "from azure.identity import DefaultAzureCredential",
    "from fastapi import FastAPI",
    "from .operations_console_app import create_console_app",
    "from . import workflows",
    "from src import canonical_publication_postgres_v1",
    "import importlib\nimportlib.import_module('.operations_console_app', package='src')",
    "from importlib import import_module\nimport_module('httpx')",
])
def test_contract_cannot_depend_on_infrastructure(repository, code):
    (repository / PROTECTED_MODULES[0]).write_text(code, encoding="utf-8")
    errors = check_boundaries(repository)
    assert errors and all("contract-without-infrastructure" in error for error in errors)


def test_worker_and_composition_root_keep_legitimate_dependencies(repository):
    (repository / SDK_OWNER).write_text("from docling.document_converter import DocumentConverter")
    (repository / "src/console_asgi.py").write_text("import fastapi\nimport psycopg")
    (repository / PROTECTED_MODULES[0]).write_text(
        "from src.docling_contract_v1 import DoclingError\nimport docling_unrelated")
    assert check_boundaries(repository) == []


def test_invalid_source_or_missing_owner_fails_closed(repository):
    path = repository / SDK_OWNER
    path.write_text("def incomplete(")
    assert "cannot inspect Python source" in "\n".join(check_boundaries(repository))
    path.unlink()
    assert "boundary owner is missing" in "\n".join(check_boundaries(repository))


def test_cli_blocks_invalid_repository(tmp_path, capsys):
    assert main(["--root", str(tmp_path)]) == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_agents_and_ci_use_executable_boundary_contract():
    guide = "docs/agents/abstraction-boundaries.md"
    command = "python scripts/check_architecture_boundaries.py"
    for relative in ("AGENTS.md", ".github/agents/metis-engineer.agent.md", "CONTRIBUTING.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert guide in text and command in text
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert command in ci
    assert "needs: [change-contract, architecture-boundaries]" in ci


def test_contract_map_points_to_existing_code_and_proofs():
    guide = (ROOT / "docs/agents/abstraction-boundaries.md").read_text(encoding="utf-8")
    owners = re.findall(r"`(src/[^`]+\.py)::([\w.]+)`", guide)
    assert owners
    for relative, symbol in owners:
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        for part in symbol.split("."):
            tree = next(node for node in tree.body
                        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name == part)
    proofs = re.findall(r"`(tests/[^`]+\.py)`", guide)
    assert proofs and all((ROOT / path).is_file() for path in proofs)
