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
from datetime import datetime, timezone
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CONSOLE_REQUIREMENTS_NAME = "requirements-console.txt"
DEPLOY_COMMIT_MARKER = "config/deployed_commit.txt"
AZURE_MANYLINUX_PLATFORM = "manylinux2014_x86_64"
AZURE_ABI3_PLATFORM = "manylinux_2_28_x86_64"
AZURE_PYTHON_VERSION = "3.12"
AZURE_PYTHON_ABI = "cp312"
INCLUDE_DIRS = (
    "src",
    "scripts",
    "db",
    "config",
    "schemas",
    "assets",
)
INCLUDE_FILES = (
    CONSOLE_REQUIREMENTS_NAME,
    "requirements.txt",
    "pyproject.toml",
)
INCLUDE_STATIC_FILES = (
    "data/audit/semantic_passage_safety_v1.json",
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


def requirement_specs(path: Path, *, _seen: set[Path] | None = None) -> list[str]:
    """Return installable requirement lines, following ``-r`` includes."""

    resolved = Path(path).resolve()
    seen = _seen if _seen is not None else set()
    if resolved in seen or not resolved.is_file():
        return []
    seen.add(resolved)
    specs: list[str] = []
    for raw in resolved.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        include = _INCLUDE_RE.match(line)
        if include:
            specs.extend(requirement_specs(resolved.parent / include.group(1), _seen=seen))
            continue
        if line.startswith("-"):
            continue
        specs.append(line)
    return specs


def _python_executable() -> str:
    return os.environ.get("PYTHON") or shutil.which("python") or shutil.which("python3") or "python3"


def _pip_download_target(
    *,
    python: str,
    wheelhouse: Path,
    specs: list[str],
    platform: str,
    cwd: Path,
    no_deps: bool = False,
) -> None:
    command = [
        python,
        "-m",
        "pip",
        "download",
        "--only-binary=:all:",
        "--platform",
        platform,
        "--implementation",
        "cp",
        "--python-version",
        AZURE_PYTHON_VERSION,
        "--abi",
        AZURE_PYTHON_ABI,
        "--abi",
        "abi3",
        "--dest",
        str(wheelhouse),
    ]
    if no_deps:
        command.append("--no-deps")
    command.extend(specs)
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployPackageError(
            "azure_target_download_failed:"
            + ",".join(specs)
            + "\n"
            + result.stderr[-2000:]
        )


def _wheel_distribution_identity(wheel: Path) -> tuple[str, str]:
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [
            name
            for name in archive.namelist()
            if name.endswith(".dist-info/METADATA")
        ]
        if len(metadata_names) != 1:
            raise DeployPackageError(f"wheel_metadata_invalid:{wheel.name}")
        payload = archive.read(metadata_names[0]).decode("utf-8")
    parsed = Parser().parsestr(payload)
    name = str(parsed.get("Name") or "").strip().lower().replace("_", "-")
    version = str(parsed.get("Version") or "").strip()
    if not name or not version:
        raise DeployPackageError(f"wheel_metadata_incomplete:{wheel.name}")
    return name, version


def _validate_unique_wheel_versions(wheelhouse: Path) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for wheel in sorted(wheelhouse.glob("*.whl")):
        name, version = _wheel_distribution_identity(wheel)
        prior = seen.get(name)
        if prior is not None and prior[0] != version:
            raise DeployPackageError(
                f"duplicate_distribution_versions:{name}:{prior[0]}:{version}"
            )
        seen[name] = (version, wheel.name)


def _pip_install_one_wheel(
    *,
    python: str,
    wheel: Path,
    target: Path,
    cwd: Path,
) -> None:
    command = [
        python,
        "-m",
        "pip",
        "install",
        "--no-compile",
        "--no-deps",
        "--only-binary=:all:",
        "--platform",
        AZURE_MANYLINUX_PLATFORM,
        "--implementation",
        "cp",
        "--python-version",
        AZURE_PYTHON_VERSION,
        "--abi",
        AZURE_PYTHON_ABI,
        "--abi",
        "abi3",
        "-t",
        str(target),
        str(wheel),
    ]
    result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if result.returncode == 0:
        return

    # PyMuPDF currently ships an abi3 wheel at manylinux_2_28 rather than
    # manylinux2014. The wheel was already resolved against the allowed fallback
    # platform, so retry only the isolated wheel install against that platform.
    command[command.index(AZURE_MANYLINUX_PLATFORM)] = AZURE_ABI3_PLATFORM
    fallback = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    if fallback.returncode != 0:
        raise DeployPackageError(
            f"azure_target_wheel_install_failed:{wheel.name}\n{fallback.stderr[-2000:]}"
        )


def _merge_resolved_wheels(
    *,
    python: str,
    wheelhouse: Path,
    vendor: Path,
    cwd: Path,
) -> None:
    wheels = sorted(wheelhouse.glob("*.whl"))
    if not wheels:
        raise DeployPackageError("azure_target_wheels_missing")
    for index, wheel in enumerate(wheels):
        with tempfile.TemporaryDirectory(prefix=f"metis-wheel-{index}-") as raw_target:
            isolated = Path(raw_target)
            _pip_install_one_wheel(
                python=python,
                wheel=wheel,
                target=isolated,
                cwd=cwd,
            )
            _copy_tree(isolated, vendor)


def _validate_vendor_record_completeness(vendor: Path) -> None:
    import csv

    for record in sorted(vendor.glob("*.dist-info/RECORD")):
        with record.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.reader(handle):
                if not row:
                    continue
                rel = str(row[0]).replace("\\", "/")
                if not rel or rel.startswith("../") or rel.startswith("/"):
                    continue
                if not (vendor / rel).is_file():
                    raise DeployPackageError(
                        f"vendor_record_missing:{record.parent.name}:{rel}"
                    )


def _validate_vendor_distribution_versions(vendor: Path) -> None:
    seen: dict[str, tuple[str, str]] = {}
    for metadata in sorted(vendor.glob("*.dist-info/METADATA")):
        parsed = Parser().parsestr(metadata.read_text(encoding="utf-8"))
        name = str(parsed.get("Name") or "").strip().lower().replace("_", "-")
        version = str(parsed.get("Version") or "").strip()
        if not name or not version:
            raise DeployPackageError(f"vendor_metadata_incomplete:{metadata.parent.name}")
        prior = seen.get(name)
        if prior is not None:
            raise DeployPackageError(
                f"duplicate_vendor_distribution:{name}:{prior[0]}:{version}"
            )
        seen[name] = (version, metadata.parent.name)


def _install_azure_dependency_graph(
    *,
    python: str,
    vendor: Path,
    requirements: Path,
    cwd: Path,
) -> None:
    """Resolve once, then merge wheels without clobbering namespace siblings.

    Directly installing multiple target wheels into one --target directory can
    leave dist-info metadata behind while replacing package subdirectories such
    as azure.identity. Resolve the graph first, then install every wheel in an
    isolated target and merge files recursively into the final vendor tree.
    """

    specs = requirement_specs(requirements)
    pymupdf_specs = [
        spec
        for spec in specs
        if _REQ_NAME_RE.match(spec)
        and _REQ_NAME_RE.match(spec).group(1).lower().replace("_", "-") == "pymupdf"
    ]
    primary_specs = [spec for spec in specs if spec not in pymupdf_specs]

    with tempfile.TemporaryDirectory(prefix="metis-wheelhouse-") as raw_wheelhouse:
        wheelhouse = Path(raw_wheelhouse)
        if primary_specs:
            _pip_download_target(
                python=python,
                wheelhouse=wheelhouse,
                specs=primary_specs,
                platform=AZURE_MANYLINUX_PLATFORM,
                cwd=cwd,
            )
        if pymupdf_specs:
            _pip_download_target(
                python=python,
                wheelhouse=wheelhouse,
                specs=pymupdf_specs,
                platform=AZURE_ABI3_PLATFORM,
                cwd=cwd,
                no_deps=True,
            )
        _validate_unique_wheel_versions(wheelhouse)
        _merge_resolved_wheels(
            python=python,
            wheelhouse=wheelhouse,
            vendor=vendor,
            cwd=cwd,
        )

    _validate_vendor_distribution_versions(vendor)
    _validate_vendor_record_completeness(vendor)


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


def pinned_requirement(path: Path, package: str) -> str:
    """Return the exact pinned requirement, following requirement includes."""
    resolved = Path(path).resolve()
    wanted = package.lower().replace("_", "-")
    for raw in resolved.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        include = _INCLUDE_RE.match(line)
        if include:
            try:
                return pinned_requirement(resolved.parent / include.group(1), package)
            except DeployPackageError:
                continue
        match = _REQ_NAME_RE.match(line)
        if match and match.group(1).lower().replace("_", "-") == wanted:
            if "==" not in line:
                raise DeployPackageError(f"azure_native_requirement_must_be_pinned:{wanted}")
            return line
    raise DeployPackageError(f"azure_native_requirement_missing:{wanted}")


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


def git_head_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeployPackageError("deploy_commit_unavailable") from exc
    commit = result.stdout.strip().lower()
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise DeployPackageError("deploy_commit_invalid")
    return commit



def git_head_zip_datetime(root: Path) -> tuple[int, int, int, int, int, int]:
    """Stable ZIP timestamp derived from HEAD, so successive releases are distinguishable."""
    try:
        result = subprocess.run(
            ["git", "show", "-s", "--format=%ct", "HEAD"],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
        )
        stamp = int(result.stdout.strip())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise DeployPackageError("deploy_commit_timestamp_unavailable") from exc
    value = datetime.fromtimestamp(stamp, tz=timezone.utc)
    if value.year < 1980:
        raise DeployPackageError("deploy_commit_timestamp_invalid")
    # ZIP stores seconds with 2-second granularity.
    return (value.year, value.month, value.day, value.hour, value.minute, value.second - value.second % 2)


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
        for filename in INCLUDE_STATIC_FILES:
            src = root / filename
            if not src.is_file():
                raise DeployPackageError(f"required_static_file_missing:{filename}")
            if package_contains_runtime_data(filename):
                raise DeployPackageError(f"required_static_file_is_runtime_data:{filename}")
            dest = stage / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        marker = stage / DEPLOY_COMMIT_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(git_head_commit(root) + "\n", encoding="utf-8")
        vendor = stage / ".python_packages"
        vendor.mkdir(parents=True, exist_ok=True)
        _install_azure_dependency_graph(
            python=_python_executable(),
            vendor=vendor,
            requirements=requirements,
            cwd=root,
        )
        if not any(vendor.iterdir()):
            raise DeployPackageError("dependencies_missing")
        _refuse_fat_vendor_tree(vendor)
        zip_datetime = git_head_zip_datetime(root)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for item in stage.rglob("*"):
                if not item.is_file():
                    continue
                rel = item.relative_to(stage).as_posix()
                if package_contains_runtime_data(rel):
                    raise DeployPackageError("runtime_data_in_package")
                info = zipfile.ZipInfo(rel)
                info.date_time = zip_datetime
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
