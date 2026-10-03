"""Disposable official Docling converter. Never writes kernel/workflow state."""
from __future__ import annotations

import ctypes
import hashlib
from importlib.metadata import version, distributions, PackageNotFoundError
from io import BytesIO
import json
import os
from pathlib import Path
import resource
import signal
import sys
import time

from src.docling_contract_v1 import CONTRACT, DOCLING_VERSION, CORE_VERSION, DoclingError


def verified_models(path: Path) -> dict:
    try:
        manifest = json.loads((path / "metis-model-manifest.json").read_text())
        if manifest["docling_version"] != DOCLING_VERSION or not manifest["files"]:
            raise ValueError()
        for name, digest in manifest["files"].items():
            target = (path / name).resolve()
            if not target.is_relative_to(path.resolve()) or not target.is_file():
                raise ValueError()
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError()
        return manifest
    except (OSError, KeyError, ValueError) as error:
        raise DoclingError("docling_model_artifacts_invalid") from error


def convert(data: bytes, config: dict) -> dict:
    # Imports stay in this isolated interpreter, out of console memory/deps.
    if version("docling-slim") != DOCLING_VERSION or version("docling-core") != CORE_VERSION:
        raise DoclingError("docling_dependency_version_invalid")
    models = verified_models(Path(config["artifacts_path"]))
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat, ConversionStatus
    from docling.datamodel.pipeline_options import PdfPipelineOptions, HeadingHierarchyOptions
    from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
    from docling_core.types.io import DocumentStream
    from docling_core.types.doc import ContentLayer

    options = PdfPipelineOptions(
        artifacts_path=Path(config["artifacts_path"]), document_timeout=config["timeout"],
        enable_remote_services=False, allow_external_plugins=False,
        do_ocr=False, do_table_structure=True, generate_parsed_pages=True,
        generate_page_images=False, generate_picture_images=False,
        do_picture_classification=False, do_picture_description=False,
        do_code_enrichment=False, do_formula_enrichment=False,
        layout_batch_size=1, table_batch_size=1, ocr_batch_size=1, queue_max_size=2,
        heading_hierarchy_options=HeadingHierarchyOptions(enabled=True),
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=2))
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    started = time.monotonic()
    result = converter.convert(DocumentStream(name="source.pdf", stream=BytesIO(data)),
                               raises_on_error=True, max_num_pages=config["max_pages"],
                               max_file_size=config["max_bytes"])
    if result.status != ConversionStatus.SUCCESS:
        raise DoclingError("docling_conversion_incomplete")
    doc = result.document
    order = [item.self_ref for item, _ in doc.iterate_items(
        traverse_pictures=True, included_content_layers=set(ContentLayer))]
    # Furniture uses a separate tree. Preserve its actual order, no text sorting.
    order += [item.self_ref for item, _ in doc.iterate_items(root=doc.furniture,
        traverse_pictures=True, included_content_layers=set(ContentLayer)) if item.self_ref not in order]
    origins = {str(page.page_no): [getattr(cell, "from_ocr", None) for cell in page.cells]
               for page in result.pages}
    return {"contract": CONTRACT, "source_sha256": hashlib.sha256(data).hexdigest(),
            "versions": {d.metadata["Name"].lower().replace("_", "-"): d.version for d in distributions()},
            "models": models, "settings": options.model_dump(mode="json"),
            "document": doc.export_to_dict(), "reading_order": order,
            "page_text_origins": origins,
            "metrics": {"conversion_seconds": time.monotonic() - started,
                        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}}


def main() -> int:
    config_fd, input_fd, result_fd, parent_pid = map(int, sys.argv[1:])
    if sys.platform != "linux":
        return 2
    # SIGKILL on parent loss; no OCR subprocesses in this first digital-PDF slice.
    if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL) != 0 or os.getppid() != parent_pid:
        return 2
    with os.fdopen(config_fd) as handle:
        config = json.load(handle)
    resource.setrlimit(resource.RLIMIT_FSIZE, (config["max_output_bytes"], config["max_output_bytes"]))
    with os.fdopen(input_fd, "rb") as handle:
        data = handle.read(config["max_bytes"] + 1)
    try:
        if len(data) > config["max_bytes"]:
            raise DoclingError("docling_input_limit_exceeded")
        payload = {"result": convert(data, config)}
    except DoclingError as error:
        payload = {"error_code": error.code}
    except (ImportError, PackageNotFoundError):
        payload = {"error_code": "docling_dependency_missing"}
    except Exception:
        # No library exception prose/source bytes/paths/secrets in diagnostics.
        payload = {"error_code": "docling_conversion_failed"}
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(encoded) > config["max_output_bytes"]:
        encoded = b'{"error_code":"docling_output_limit_exceeded"}'
    with os.fdopen(result_fd, "wb") as handle:
        handle.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
