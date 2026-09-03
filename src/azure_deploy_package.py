"""Build a fully deployable Azure ZIP with vendored dependencies.

Protocol v2.22 wave C: git-archive-only is not enough. Live Oryx-during-deploy
caused HTTP_504 on B1. MUST NOT ship runtime data. MUST NOT overwrite /home/data.

Protocol v2.24: pack the console requirements, not the retrieval/ML extra.
MUST NOT vendor numpy, sklearn, scipy, or scikit-learn into vvn-metis-console.
Oryx output.tar.zst of a fat vendor tree on B1 is refused.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONSOLE_REQUIREMENTS_NAME = "requirements-console.txt"
INCLUDE_DIRS = (
    "src",
    "scripts",
    "config",
    "schemas",
    "assets",
)
INCLUDE_FILES = (
    CONSOLE_REQUIREMENTS_NAME,
    "requirements.txt",
    "pyproject.toml",
)
FORBIDDEN_CONSOLE_PACKAGES = frozenset({"numpy", "sklearn", "scipy", "scikit-learn"})
_REQ_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)")
_INCLUDE_RE = re.compile(r"^(?:-r|--requirement)\s+(\S+)")
_VENDOR_TOP_RE = re.compile(
    r"^(numpy|sklearn|scipy|scikit-learn|scikit_learn)(?:[.-]|$)",
    re.IGNORECASE,
)
RUNTIME_DATA_MARKERS = (
    "home/data",
    "/home/data",
    "output/runtime",
    "operations-console/accounts.json",
    "operations-console/sessions.json",
    "operations-console/envelopes.json",
    "operations-console/review_ledger.jsonl",
    "operations-console/published_projection.jsonl",
    "sources/private",
    ".env",
)
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".python_packages",
    "output",
    "home",
}


class DeployPackageError(RuntimeError):
    """Fail-closed packaging error."""


def default_console_requirements(root: Path) -> Path:
    return Path(root) / CONSOLE_REQUIREMENTS_NAME


def requirement_package_names(path: Path, *, _seen: set[Path] | None = None) -> set[str]:
    """Return declared requirement names, following ``-r`` includes."""
    resolved = Path(path).resolve()
    seen = _seen if _seen is not None else set()
    if resolved in seen:
        return set()
    seen.add(resolved)
    names: set[str] = set()
    if not resolved.is_file():
        return names
    for raw in resolved.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        include = _INCLUDE_RE.match(line)
        if include:
            names.update(requirement_package_names(resolved.parent / include.group(1), _seen=seen))
            continue
        if line.startswith("-"):
            continue
        match = _REQ_NAME_RE.match(line)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def requirements_contain_forbidden_packages(path: Path) -> frozenset[str]:
    names = requirement_package_names(path)
    return frozenset(name for name in names if name in FORBIDDEN_CONSOLE_PACKAGES)


def vendor_tree_forbidden_packages(vendor: Path) -> frozenset[str]:
    hits: set[str] = set()
    if not vendor.is_dir():
        return frozenset()
    for child in vendor.iterdir():
        if _VENDOR_TOP_RE.match(child.name):
            root = child.name.split("-", 1)[0].split(".", 1)[0].lower().replace("_", "-")
            if root == "scikit-learn":
                hits.add("scikit-learn")
                hits.add("sklearn")
            else:
                hits.add(root)
    return frozenset(hits)


def _refuse_fat_console_requirements(requirements: Path) -> None:
    hits = requirements_contain_forbidden_packages(requirements)
    if hits:
        raise DeployPackageError("console_requirements_must_not_vendor_sklearn_stack")


def _refuse_fat_vendor_tree(vendor: Path) -> None:
    hits = vendor_tree_forbidden_packages(vendor)
    if hits:
        raise DeployPackageError("console_vendor_must_not_include_sklearn_stack")


def package_contains_runtime_data(name: str) -> bool:
    normalized = name.replace("\\", "/").lstrip("./")
    if normalized.startswith(".env") or normalized == ".env":
        return True
    return any(marker in normalized for marker in RUNTIME_DATA_MARKERS)


def _refuse_home_data_output(output: Path) -> None:
    resolved = Path(os.path.realpath(os.fspath(output)))
    parts = set(resolved.parts)
    if "home" in parts and "data" in parts:
        home_data = Path("/home/data")
        try:
            resolved.relative_to(home_data)
        except ValueError:
            # Also refuse a test-constructed .../home/data/... path
            posix = resolved.as_posix()
            if "/home/data/" in posix or posix.endswith("/home/data"):
                raise DeployPackageError("must_not_write_home_data")
        else:
            raise DeployPackageError("must_not_write_home_data")
    posix = resolved.as_posix()
    if "/home/data/" in posix or posix.endswith("/home/data"):
        raise DeployPackageError("must_not_write_home_data")


def _copy_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if not item.is_file():
            continue
        rel = item.relative_to(src)
        if any(part in SKIP_DIR_NAMES for part in rel.parts):
            continue
        if package_contains_runtime_data(rel.as_posix()):
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)


def write_deploy_zip(
    output: Path,
    *,
    root: Path | None = None,
    requirements: Path | None = None,
) -> Path:
    root = Path(root or os.environ.get("METIS_PACKAGE_ROOT") or ROOT)
    output = Path(output)
    _refuse_home_data_output(output)
    requirements = Path(
        requirements
        or os.environ.get("METIS_PACKAGE_REQUIREMENTS")
        or default_console_requirements(root)
    )
    if not requirements.is_file():
        raise DeployPackageError("requirements_missing")
    _refuse_fat_console_requirements(requirements)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="metis-azure-zip-") as raw_stage:
        stage = Path(raw_stage)
        for dirname in INCLUDE_DIRS:
            src = root / dirname
            if src.is_dir():
                _copy_tree(src, stage / dirname)
        for filename in INCLUDE_FILES:
            src = root / filename
            if src.is_file() and not package_contains_runtime_data(filename):
                shutil.copy2(src, stage / filename)
        vendor = stage / ".python_packages"
        vendor.mkdir(parents=True, exist_ok=True)
        command = [
            os.environ.get("PYTHON") or shutil.which("python") or shutil.which("python3") or "python3",
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-compile",
            "-r",
            str(requirements),
            "-t",
            str(vendor),
        ]
        subprocess.run(command, check=True, cwd=root)
        if not any(vendor.iterdir()):
            raise DeployPackageError("dependencies_missing")
        _refuse_fat_vendor_tree(vendor)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in stage.rglob("*"):
                if not item.is_file():
                    continue
                rel = item.relative_to(stage).as_posix()
                if package_contains_runtime_data(rel):
                    raise DeployPackageError("runtime_data_in_package")
                info = zipfile.ZipInfo(rel)
                info.date_time = (2026, 1, 1, 0, 0, 0)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, item.read_bytes())
    return output


def main() -> int:
    parser = argparse.ArgumentParser(prog="create-azure-deploy-package")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--requirements", type=Path, default=None)
    args = parser.parse_args()
    write_deploy_zip(args.output, root=args.root, requirements=args.requirements)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
