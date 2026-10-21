#!/usr/bin/env python3
"""Check concrete Metis direct-import boundaries without importing product code."""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER_ONLY_PREFIXES = ("docling", "docling_core", "src.docling_worker_v1")
SDK_OWNER = "src/docling_worker_v1.py"
PROTECTED_MODULES = (
    "src/docling_contract_v1.py",
    "src/integrity_kernel.py",
    "src/candidate_eligibility_v1.py",
    "src/object_taxonomy_v1.py",
    "src/recommendation_semantics_v1.py",
)
INFRA_PREFIXES = (
    "fastapi", "starlette", "psycopg", "psycopg2", "sqlite3", "azure",
    "requests", "httpx", "urllib.request",
    "src.operations_console_app", "src.console_asgi", "src.service_app",
    "src.product_api_v1", "src.operations_console_v1",
    "src.durable_publication_console_v1", "src.azure_authoritative_publication_console_v1",
    "src.canonical_publication_postgres_v1", "src.g2_source_store", "src.workflows",
)


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


def _absolute(module: str, level: int, package: str) -> str:
    if not level:
        return module
    parts = package.split(".")
    base = parts[:len(parts) - level + 1]
    return ".".join([*base, *([module] if module else [])])


def _imports(tree: ast.AST, path: str):
    package = path.removesuffix(".py").replace("/", ".").rsplit(".", 1)[0]
    loaders = {"__import__"}
    importlibs = {"importlib"}
    # Collect common aliases first so local imports are checked too.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlibs.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            loaders.update(alias.asname or alias.name for alias in node.names
                           if alias.name == "import_module")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            module = _absolute(node.module or "", node.level, package)
            yield node.lineno, module
            for alias in node.names:
                if alias.name != "*":
                    yield node.lineno, module + "." + alias.name
        elif isinstance(node, ast.Call):
            fn = node.func
            loader = (isinstance(fn, ast.Name) and fn.id in loaders) or (
                isinstance(fn, ast.Attribute) and fn.attr == "import_module"
                and isinstance(fn.value, ast.Name) and fn.value.id in importlibs)
            name = node.args[0] if node.args else next(
                (kw.value for kw in node.keywords if kw.arg == "name"), None)
            if loader and isinstance(name, ast.Constant):
                module = name.value
                if isinstance(module, str):
                    if module.startswith("."):
                        anchor = node.args[1] if len(node.args) > 1 else next(
                            (kw.value for kw in node.keywords if kw.arg == "package"), None)
                        if isinstance(anchor, ast.Constant) and isinstance(anchor.value, str):
                            level = len(module) - len(module.lstrip("."))
                            module = _absolute(module.lstrip("."), level, anchor.value)
                    yield node.lineno, module


def check_boundaries(root: Path) -> list[str]:
    errors: list[str] = []
    source = root / "src"
    if not source.is_dir():
        return ["src/: source directory is missing"]
    for required in (SDK_OWNER, *PROTECTED_MODULES):
        if not (root / required).is_file():
            errors.append(f"{required}: boundary owner is missing; update the contract explicitly")
    for path in sorted(source.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors.append(f"{relative}: cannot inspect Python source: {exc}")
            continue
        violations = set()
        for line, module in _imports(tree, relative):
            if relative != SDK_OWNER and _matches(module, WORKER_ONLY_PREFIXES):
                violations.add((line, "docling-worker-only", module))
            if relative in PROTECTED_MODULES and _matches(module, INFRA_PREFIXES):
                violations.add((line, "contract-without-infrastructure", module))
        errors.extend(f"{relative}:{line}: {rule}: forbidden import {module}"
                      for line, rule, module in sorted(violations))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = check_boundaries(args.root)
    if errors:
        print("Architecture boundaries: BLOCKED")
        print("\n".join(errors))
        return 1
    print("Architecture boundaries: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
