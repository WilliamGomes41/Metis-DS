"""Existing PDF fragment identity/locator format, independent of extractor."""
from typing import Any


def fragment_payload(x: dict[str, Any]) -> dict[str, Any]:
    return {k: x[k] for k in ["fragment_id", "document_id", "source_id", "source_page", "bbox",
                             "source_locator", "raw_text", "clean_text", "section_path", "heading",
                             "sequence", "parser_version"]}


def page_bbox_locator(page_no: int, bbox: list[float]) -> dict[str, str]:
    coordinates = ",".join(f"{value:.6f}" for value in bbox)
    return {"locator_type": "page_bbox", "locator_value": f"page:{page_no};bbox:{coordinates}"}
