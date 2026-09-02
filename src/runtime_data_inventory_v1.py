"""Inventory, export, restore and --clean true proof for console runtime data.

Protocol v2.22 wave D. Runtime data lives under ``/home/data/metis-console``.
A clean deploy of wwwroot MUST NOT delete that tree. No large database
migration. Path members are allowlisted before any filesystem join.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DATA_ROOT = Path("/home/data/metis-console")

INVENTORY_CATEGORIES = (
    "accounts_roles",
    "document_snapshots",
    "review_ledger",
    "canonical_objects",
    "derived_projections",
)

_CATEGORY_PATHS: dict[str, tuple[str, ...]] = {
    "accounts_roles": ("output/runtime/operations-console/accounts.json",),
    "document_snapshots": (
        "output/runtime/operations-console/envelopes.json",
        "sources/private",
    ),
    "review_ledger": ("output/runtime/operations-console/review_ledger.jsonl",),
    "canonical_objects": ("output/runtime/operations-console/objects",),
    "derived_projections": ("output/runtime/operations-console/published_projection.jsonl",),
}

_SAFE_PART = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")


class RuntimeDataError(RuntimeError):
    """Fail-closed inventory / backup / restore error."""


class CleanDeployError(RuntimeError):
    """Fail-closed --clean true error."""


def _has_path_escape(value: str) -> bool:
    return (not value) or value in {".", ".."} or "/" in value or "\\" in value or ".." in value


def safe_backup_member(name: str) -> str:
    """Allowlist a zip/backup member before any filesystem join."""
    raw = "" if name is None else str(name).replace("\\", "/")
    if raw.startswith("/") or raw.startswith("\\"):
        raise RuntimeDataError("unsafe_backup_member")
    if not raw or raw.endswith("/"):
        raise RuntimeDataError("unsafe_backup_member")
    parts = [part for part in raw.split("/") if part != ""]
    if not parts:
        raise RuntimeDataError("unsafe_backup_member")
    for part in parts:
        if _has_path_escape(part) or part in {".", ".."}:
            raise RuntimeDataError("unsafe_backup_member")
        if any(ch not in _SAFE_PART for ch in part):
            raise RuntimeDataError("unsafe_backup_member")
    return "/".join(parts)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_category_files(data_root: Path, relative_paths: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for relative in relative_paths:
        token = safe_backup_member(relative)
        path = data_root.joinpath(*token.split("/"))
        resolved_root = Path(os.path.realpath(os.fspath(data_root)))
        resolved = Path(os.path.realpath(os.fspath(path)))
        if resolved != resolved_root and not str(resolved).startswith(str(resolved_root) + os.sep):
            raise RuntimeDataError("unsafe_backup_member")
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    files.append(item)
    return files


def inventory_runtime_data(data_root: Path | None = None) -> dict[str, Any]:
    root = Path(data_root or os.environ.get("CONSOLE_DATA_ROOT") or DEFAULT_DATA_ROOT)
    categories: list[dict[str, Any]] = []
    for name in INVENTORY_CATEGORIES:
        files = _iter_category_files(root, _CATEGORY_PATHS[name])
        ids: list[str] = []
        count = len(files)
        if name == "accounts_roles":
            accounts_path = root / "output" / "runtime" / "operations-console" / "accounts.json"
            if accounts_path.is_file():
                payload = json.loads(accounts_path.read_text(encoding="utf-8"))
                count = len(payload)
                ids = [str(row.get("username") or key) for key, row in payload.items()]
        elif name == "document_snapshots":
            envelopes_path = root / "output" / "runtime" / "operations-console" / "envelopes.json"
            if envelopes_path.is_file():
                payload = json.loads(envelopes_path.read_text(encoding="utf-8"))
                ids = list(payload)
                count = len(payload)
        elif name == "canonical_objects":
            count = len(files)
            ids = [path.stem for path in files]
        elif name == "review_ledger":
            ledger = root / "output" / "runtime" / "operations-console" / "review_ledger.jsonl"
            if ledger.is_file():
                count = sum(1 for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip())
        categories.append(
            {
                "category": name,
                "present": bool(files) or bool(ids) or count > 0,
                "count": count,
                "ids": ids,
                "files": [str(path.relative_to(root).as_posix()) for path in files],
            }
        )
    return {"data_root": str(root), "categories": categories}


def export_runtime_data(data_root: Path, archive: Path) -> dict[str, Any]:
    root = Path(data_root)
    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    report = inventory_runtime_data(root)
    files: dict[str, str] = {}
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        for category in report["categories"]:
            for relative in category["files"]:
                member = safe_backup_member(relative)
                path = root.joinpath(*member.split("/"))
                digest = _sha256_file(path)
                files[member] = digest
                zipf.write(path, member)
        manifest = {
            "ok": True,
            "categories": [item["category"] for item in report["categories"]],
            "file_count": len(files),
            "files": files,
        }
        zipf.writestr("inventory_manifest.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


def restore_runtime_data(archive: Path, dest: Path, *, allow_nonempty: bool = False) -> dict[str, Any]:
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()) and not allow_nonempty:
        raise RuntimeDataError("restore_target_not_clean")
    dest.mkdir(parents=True, exist_ok=True)
    restored: list[str] = []
    with zipfile.ZipFile(archive) as zipf:
        names = zipf.namelist()
        if "inventory_manifest.json" not in names:
            raise RuntimeDataError("backup_manifest_missing")
        manifest = json.loads(zipf.read("inventory_manifest.json").decode("utf-8"))
        for name in names:
            if name.endswith("/") or name == "inventory_manifest.json":
                continue
            member = safe_backup_member(name)
            target = dest.joinpath(*member.split("/"))
            resolved_dest = Path(os.path.realpath(os.fspath(dest)))
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipf.open(name) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            resolved_target = Path(os.path.realpath(os.fspath(target)))
            if resolved_target != resolved_dest and not str(resolved_target).startswith(
                str(resolved_dest) + os.sep
            ):
                target.unlink(missing_ok=True)
                raise RuntimeDataError("unsafe_backup_member")
            restored.append(member)
    return {"ok": True, "restored": restored, "manifest": manifest}


def integrity_check(data_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    root = Path(data_root)
    missing: list[str] = []
    mismatch: list[str] = []
    for relative, expected in (manifest.get("files") or {}).items():
        member = safe_backup_member(relative)
        path = root.joinpath(*member.split("/"))
        if not path.is_file():
            missing.append(member)
            continue
        if _sha256_file(path) != expected:
            mismatch.append(member)
    return {"ok": not missing and not mismatch, "missing": missing, "mismatch": mismatch}


def apply_clean_wwwroot(
    *,
    wwwroot: Path,
    runtime_data_root: Path,
    clean: bool,
) -> dict[str, Any]:
    """Model ``az webapp deploy --clean true``: wipe wwwroot, never /home/data."""
    wwwroot = Path(wwwroot)
    runtime_data_root = Path(runtime_data_root)
    resolved_www = Path(os.path.realpath(os.fspath(wwwroot)))
    resolved_data = Path(os.path.realpath(os.fspath(runtime_data_root)))
    if resolved_data == resolved_www or str(resolved_data).startswith(str(resolved_www) + os.sep):
        raise CleanDeployError("runtime_data_must_not_live_in_wwwroot")
    if not clean:
        return {"wwwroot_wiped": False, "runtime_data_deleted": False}
    if wwwroot.exists():
        for item in wwwroot.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    return {
        "wwwroot_wiped": True,
        "runtime_data_deleted": False,
        "runtime_data_present": runtime_data_root.exists(),
    }
