"""Translate official Docling JSON into Metis source fragments; no extraction.

Offsets index Python Unicode characters in Docling's derived text, not PDF
bytes or the digital text layer. Original Docling text, tables, relationships,
OCR observations and excluded furniture remain in the immutable result record.
"""
from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

CONTRACT = "metis-docling-source-v1"
DOCLING_VERSION = "2.132.0"
CORE_VERSION = "2.99.0"


class DoclingError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ExtractedFragments(list):
    """Transient prepared value. The existing envelope commit owns persistence."""
    def __init__(self, rows, record):
        super().__init__(rows)
        self.extraction_record = record


def top_left_box(box: dict, size: dict) -> list[float]:
    try:
        left, right, top, bottom = (float(box[k]) for k in ("l", "r", "t", "b"))
        width, height = float(size["width"]), float(size["height"])
        if box["coord_origin"] == "BOTTOMLEFT":
            top, bottom = height - top, height - bottom
        elif box["coord_origin"] != "TOPLEFT":
            raise ValueError()
        values = [left, top, right, bottom]
        if (not all(math.isfinite(v) for v in [*values, width, height])
                or not (0 <= left < right <= width and 0 <= top < bottom <= height)):
            raise ValueError()
        return values
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise DoclingError("docling_geometry_invalid") from error


def translate(result: dict, *, document_id: str, source_id: str, source_sha256: str,
              pages: list[int] | None = None) -> ExtractedFragments:
    """Validate before building any prepared domain input. No Markdown export."""
    from src.integrity_kernel import stable_hash
    from src.pdf_fragment_contract_v1 import fragment_payload, page_bbox_locator
    from src.source_layout_v1 import text_view
    if (result.get("contract") != CONTRACT or result.get("source_sha256") != source_sha256
            or result.get("versions", {}).get("docling-slim") != DOCLING_VERSION
            or result.get("versions", {}).get("docling-core") != CORE_VERSION):
        raise DoclingError("docling_result_identity_invalid")
    doc = result["document"]
    page_data = doc["pages"]
    selected = set(pages) if pages is not None else {int(p) for p in page_data}
    if not selected or not selected.issubset({int(p) for p in page_data}):
        raise DoclingError("docling_page_selection_invalid")
    items = {item["self_ref"]: item for key in ("texts", "tables", "pictures", "key_value_items", "form_items")
             for item in doc.get(key, [])}
    ordered = result["reading_order"]
    if len(set(ordered)) != len(ordered) or any(ref not in items for ref in ordered):
        raise DoclingError("docling_reading_order_invalid")
    # Detect unvisited text: do not silently trust a body-only iterator.
    if set(items) - set(ordered):
        raise DoclingError("docling_inventory_incomplete")
    record = deepcopy(result)
    record.pop("metrics", None)
    record["offsets"] = "unicode_codepoints_in_docling_derived_text"
    record["raw_text_definition"] = "Docling text; not a verbatim digital-layer claim"
    record["selected_pages"] = sorted(selected)
    extraction_id = stable_hash(record)
    out, bindings, exclusions, stack = [], [], [], []

    def emit(text: str, prov: dict, ref: str, *, heading=None, cell=None):
        page = prov["page_no"]
        if type(page) is not int or str(page) not in page_data:
            raise DoclingError("docling_page_invalid")
        box = top_left_box(prov["bbox"], page_data[str(page)]["size"])
        if page not in selected or not text.strip():
            return
        sequence = len(out) + 1
        row = {"fragment_id": f"{document_id}-dx-{extraction_id[:16]}-f{sequence:06d}",
               "document_id": document_id, "source_id": source_id, "source_page": page,
               "bbox": box, "source_locator": page_bbox_locator(page, box),
               "raw_text": text, "clean_text": text_view(text, [])["text"],
               "source_text_view": text_view(text, []), "section_path": [x[1] for x in stack],
               "heading": heading, "sequence": sequence, "parser_version": CONTRACT + "/" + DOCLING_VERSION}
        row["fragment_hash"] = stable_hash(fragment_payload(row))
        out.append(row)
        # Conservatively classify at page level, retaining exact cell observations.
        observations = result.get("page_text_origins", {}).get(str(page), [])
        origin = ("ocr_or_mixed" if True in observations else "digital_text_layer"
                  if observations and all(v is False for v in observations) else "unknown")
        bindings.append({"fragment_id": row["fragment_id"], "fragment_hash": row["fragment_hash"],
                         "item_ref": ref, "provenance": deepcopy(prov), "table_cell": cell,
                         "text_origin": origin, "geometry_precision": "item_bbox"})

    for ref in ordered:
        item = items[ref]
        provenance = item.get("prov") or []
        label = item.get("label")
        if item.get("content_layer") == "furniture" or label in {"page_header", "page_footer"}:
            exclusions.append({"item_ref": ref, "reason": "docling_furniture", "provenance": provenance})
            continue
        if label == "table":
            cells = item["data"]["table_cells"]
            for index, cell in enumerate(cells):
                text = cell.get("text", "")
                if not text.strip():
                    continue
                # Docling cells have no independent page number. Never guess on
                # a table crossing pages; keep the raw structure but block use.
                if len(provenance) != 1:
                    raise DoclingError("docling_multipage_table_mapping_unresolved")
                cp = deepcopy(provenance[0])
                if cell.get("bbox") is not None:
                    cp["bbox"] = cell["bbox"]
                emit(text, cp, ref, cell=index)
            continue
        if "text" not in item:
            exclusions.append({"item_ref": ref, "reason": "non_text_item_preserved_in_document", "provenance": provenance})
            continue
        text = item["text"]
        if not isinstance(text, str) or (text.strip() and not provenance):
            raise DoclingError("docling_text_provenance_missing")
        heading = text_view(text, [])["text"] if label in {"section_header", "title"} else None
        if heading:
            level = item.get("level", 1)
            if type(level) is not int or not 1 <= level <= 20:
                raise DoclingError("docling_heading_level_invalid")
            stack = [x for x in stack if x[0] < level] + [(level, heading)]
        ranges = []
        for prov in provenance:
            start, end = prov["charspan"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise DoclingError("docling_charspan_invalid")
            ranges.append((start, end))
            emit(text[start:end], prov, ref, heading=heading)
        # Docling merged paragraphs may have a separator between page spans.
        covered = set(i for lo, hi in ranges for i in range(lo, hi))
        if any(not ch.isspace() and i not in covered for i, ch in enumerate(text)):
            raise DoclingError("docling_text_coverage_incomplete")
    if not out:
        raise DoclingError("docling_no_source_text")
    record.update(extraction_id=extraction_id, bindings=bindings, exclusions=exclusions,
                  selected_pages=sorted(selected), metrics=deepcopy(result.get("metrics", {})))
    return ExtractedFragments(out, record)


def stored_fragments(envelope: dict):
    """Read the accepted representation, never reconvert on review/repair."""
    from src.integrity_kernel import stable_hash
    runs = envelope.get("quality_processing_runs") or []
    if not runs or "document_extraction" not in runs[-1]:
        return None
    record = runs[-1]["document_extraction"]
    rows = record.get("prepared_fragments")
    if (record.get("source_sha256") != envelope.get("sha256") or not isinstance(rows, list)
            or record.get("prepared_fragments_hash") != stable_hash(rows)
            or record.get("record_hash") != stable_hash({k: v for k, v in record.items() if k != "record_hash"})):
        raise DoclingError("docling_stored_evidence_invalid")
    return ExtractedFragments(deepcopy(rows), deepcopy(record))
