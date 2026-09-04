"""Protocol v2.24 code wave: console vs retrieval package boundary."""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.azure_deploy_package import (
    CONSOLE_REQUIREMENTS_NAME,
    FORBIDDEN_CONSOLE_PACKAGES,
    DeployPackageError,
    default_console_requirements,
    requirement_package_names,
    requirements_contain_forbidden_packages,
    vendor_tree_forbidden_packages,
    write_deploy_zip,
)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

RETRIEVAL_RUNTIME_MODULES = frozenset(
    {
        "embedding_provider_v1.py",
        "semantic_vector_retrieval_v1.py",
        "hybrid_retrieval_v1.py",
        "provider_vector_retrieval_v1.py",
        "product_api_v1.py",
        "service_app.py",
        "safe_retrieval_v1.py",
        "evaluate_vector_retrieval.py",
        "evaluate_hybrid_retrieval.py",
        "evaluate_retrieval_baseline.py",
    }
)
CONSOLE_ENTRYPOINTS = (
    SRC / "console_asgi.py",
    SRC / "operations_console_v1.py",
    SRC / "operations_console_app.py",
)
FORBIDDEN_RETRIEVAL_MODULES = frozenset(
    {
        "embedding_provider_v1",
        "semantic_vector_retrieval_v1",
        "hybrid_retrieval_v1",
        "provider_vector_retrieval_v1",
        "product_api_v1",
        "safe_retrieval_v1",
    }
)
ALLOWED_CONSOLE_PACKAGES = frozenset(
    {
        "jsonschema",
        "rfc3987",
        "pymupdf",
        "fastapi",
        "uvicorn",
        "python-multipart",
        "gunicorn",
        "azure-identity",
        "azure-storage-blob",
        "cryptography",
    }
)


def _imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0] if module else ""
            if root:
                names.add(root)
            if module:
                names.add(module)
                names.add(module.split(".")[-1])
            if root == "src" and module.startswith("src."):
                names.add(module.split(".", 1)[1].split(".")[0])
    return names


def _walk_console_import_graph() -> tuple[set[str], set[Path]]:
    seen_files: set[Path] = set()
    names: set[str] = set()
    queue = list(CONSOLE_ENTRYPOINTS)
    while queue:
        path = queue.pop()
        if path in seen_files or not path.is_file():
            continue
        seen_files.add(path)
        imported = _imported_names(path)
        names.update(imported)
        for raw in imported:
            candidate = raw.split(".")[-1]
            local = SRC / f"{candidate}.py"
            if local.is_file() and local not in seen_files:
                queue.append(local)
    return names, seen_files


def test_v224_console_requirements_exclude_sklearn_stack() -> None:
    console = ROOT / CONSOLE_REQUIREMENTS_NAME
    names = requirement_package_names(console)
    assert names
    assert names <= ALLOWED_CONSOLE_PACKAGES
    assert requirements_contain_forbidden_packages(console) == frozenset()
    assert requirements_contain_forbidden_packages(ROOT / "requirements.txt") == frozenset()
    assert default_console_requirements(ROOT) == console


def test_v224_console_pins_azure_linux_compatible_cryptography() -> None:
    requirements = (ROOT / CONSOLE_REQUIREMENTS_NAME).read_text(encoding="utf-8")
    assert "cryptography==44.0.3" in requirements.splitlines()


def test_v224_retrieval_extra_keeps_sklearn_stack() -> None:
    retrieval = ROOT / "requirements-retrieval.txt"
    names = requirement_package_names(retrieval)
    assert "scikit-learn" in names
    assert "numpy" in names
    assert "scipy" in names
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'retrieval = [' in pyproject
    assert "scikit-learn==1.8.0" in pyproject
    assert "numpy==2.3.5" in pyproject
    assert "scipy==1.17.0" in pyproject
    assert "scikit-learn==1.8.0" not in (ROOT / CONSOLE_REQUIREMENTS_NAME).read_text(encoding="utf-8")
    assert "-r requirements-retrieval.txt" in (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")


def test_v224_keeps_two_products_and_retrieval_modules_in_repo() -> None:
    for name in (
        "service_app.py",
        "product_api_v1.py",
        "embedding_provider_v1.py",
        "semantic_vector_retrieval_v1.py",
        "hybrid_retrieval_v1.py",
        "provider_vector_retrieval_v1.py",
        "console_asgi.py",
        "operations_console_v1.py",
        "operations_console_app.py",
    ):
        assert (SRC / name).is_file(), name
    assert not (ROOT / "HANDOFF.md").exists()


def test_v224_console_import_graph_excludes_forbidden_and_retrieval() -> None:
    names, files = _walk_console_import_graph()
    hits = sorted(
        name
        for name in names
        if name.split(".")[0] in FORBIDDEN_CONSOLE_PACKAGES or name in FORBIDDEN_CONSOLE_PACKAGES
    )
    assert hits == [], f"console import graph includes forbidden packages: {hits}"
    retrieval_hits = sorted(FORBIDDEN_RETRIEVAL_MODULES.intersection(names))
    assert retrieval_hits == [], f"console import graph includes retrieval modules: {retrieval_hits}"
    for path in files:
        imported = _imported_names(path)
        for name in imported:
            root = name.split(".")[0]
            assert root not in FORBIDDEN_CONSOLE_PACKAGES, f"{path.name} imported {name}"


def test_v224_shared_kernel_modules_must_not_import_sklearn_stack() -> None:
    for path in sorted(SRC.glob("*.py")):
        if path.name in RETRIEVAL_RUNTIME_MODULES:
            continue
        imported = _imported_names(path)
        hits = [
            name
            for name in imported
            if name.split(".")[0] in FORBIDDEN_CONSOLE_PACKAGES or name in FORBIDDEN_CONSOLE_PACKAGES
        ]
        assert hits == [], f"shared kernel {path.name} imported forbidden packages: {hits}"


def test_v224_console_process_start_does_not_load_sklearn_or_retrieval(tmp_path: Path) -> None:
    probe = tmp_path / "probe_console_asgi.py"
    probe.write_text(
        "\n".join(
            [
                "import sys",
                "from src.console_asgi import build_app",
                "build_app()",
                "loaded = set(sys.modules)",
                "forbidden = {",
                "    'numpy', 'sklearn', 'scipy', 'scikit-learn',",
                "    'src.embedding_provider_v1', 'src.semantic_vector_retrieval_v1',",
                "    'src.hybrid_retrieval_v1', 'src.provider_vector_retrieval_v1',",
                "    'src.product_api_v1', 'src.safe_retrieval_v1', 'src.service_app',",
                "}",
                "hits = sorted(name for name in loaded if name in forbidden or name.split('.')[0] in forbidden)",
                "if hits:",
                "    raise SystemExit('loaded forbidden: ' + ','.join(hits))",
                "print('console_process_start_clean')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "CONSOLE_DATA_ROOT": str(tmp_path / "console-data"),
        "PYTHONPATH": str(ROOT),
    }
    env.pop("CONSOLE_IMMUTABLE_SOURCE_STORE", None)
    env.pop("WEBSITE_SITE_NAME", None)
    result = subprocess.run(
        [sys.executable, str(probe)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "console_process_start_clean" in result.stdout


def test_v224_packer_refuses_fat_console_requirements(tmp_path: Path) -> None:
    fat = tmp_path / "fat-requirements.txt"
    fat.write_text("scikit-learn==1.8.0\nnumpy==2.3.5\n", encoding="utf-8")
    with pytest.raises(DeployPackageError, match="console_requirements_must_not_vendor_sklearn_stack"):
        write_deploy_zip(tmp_path / "fat.zip", root=ROOT, requirements=fat)


def test_v224_vendor_tree_helper_detects_sklearn(tmp_path: Path) -> None:
    vendor = tmp_path / "vendor"
    (vendor / "sklearn").mkdir(parents=True)
    (vendor / "numpy-2.3.5.dist-info").mkdir()
    hits = vendor_tree_forbidden_packages(vendor)
    assert "sklearn" in hits
    assert "numpy" in hits


def test_v224_changelog_records_implementation_under_v224() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Protocol v2.24 console vs retrieval requirements split" in changelog
    assert "Runtime-scheiding mag veranderen; protocol- en publicatiegrenzen niet." in changelog
    assert "MUST NOT vendor numpy, sklearn, scipy, or scikit-learn" in changelog
    assert "requirements-console.txt" in changelog
    assert "requirements-retrieval.txt" in changelog
    assert "this split does not open publish() or G2" in changelog
    assert "MUST NOT implement the requirements split in this PR" in changelog
