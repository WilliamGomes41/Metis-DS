"""Explicit online BUILD operation. Never called by a request or application boot."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.docling_contract_v1 import DOCLING_VERSION, MODEL_REVISIONS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if version("docling-slim") != DOCLING_VERSION:
        raise SystemExit("docling_dependency_version_invalid")
    from docling.models.utils.hf_model_download import download_hf_model
    for repo, revision in MODEL_REVISIONS.items():
        download_hf_model(repo_id=repo, revision=revision,
                          local_dir=args.output / repo.replace("/", "--"), progress=True)
    files = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and ".cache" not in path.parts and path.name != "metis-model-manifest.json":
            with path.open("rb") as handle:
                files[path.relative_to(args.output).as_posix()] = hashlib.file_digest(handle, "sha256").hexdigest()
    manifest = {"docling_version": version("docling-slim"), "files": files,
                "repositories": MODEL_REVISIONS,
                "purpose": "official CPU Egret-large and TableFormer; OCR disabled"}
    (args.output / "metis-model-manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
