"""Explicit online BUILD operation. Never called by a request or application boot."""
from __future__ import annotations
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if version("docling-slim") != "2.132.0":
        raise SystemExit("docling_dependency_version_invalid")
    from docling.utils.model_downloader import download_models
    download_models(args.output, with_layout=True, with_tableformer=True,
                    with_code_formula=False, with_picture_classifier=False,
                    with_rapidocr=False, with_easyocr=False, progress=True)
    files = {}
    for path in sorted(args.output.rglob("*")):
        if path.is_file() and path.name != "metis-model-manifest.json":
            with path.open("rb") as handle:
                files[path.relative_to(args.output).as_posix()] = hashlib.file_digest(handle, "sha256").hexdigest()
    manifest = {"docling_version": version("docling-slim"), "files": files,
                "purpose": "official CPU layout and TableFormer; OCR disabled"}
    (args.output / "metis-model-manifest.json").write_text(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
