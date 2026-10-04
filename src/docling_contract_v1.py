"""Translate official Docling JSON into Metis source fragments; no extraction.

Offsets index Python Unicode characters in the recorded Docling text field, not PDF
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
LAYOUT_PRESET = "layout_egret_large"
MODEL_REVISIONS = {
    "docling-project/docling-layout-egret-large": "fff417c78abd6bab338c87706c95a8d79dc68f1e",
    "docling-project/docling-models": "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
}


class DoclingError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class ExtractedFragments(list):
    """Transient prepared value. The existing envelope commit owns persistence."""
    def __init__(self, rows, record):
        super().__init__(rows)
        self.extraction_record = record


def top_left_box(box: dict, size: dict, *, intersect_page: bool = False) -> list[float]:
    try:
        left, right, top, bottom = (float(box[k]) for k in ("l", "r", "t", "b"))
        width, height = float(size["width"]), float(size["height"])
        if box["coord_origin"] == "BOTTOMLEFT":
            top, bottom = height - top, height - bottom
        elif box["coord_origin"] != "TOPLEFT":
            raise ValueError()
        if (not all(math.isfinite(v) for v in [left, top, right, bottom, width, height])
                or width <= 0 or height <= 0 or left >= right or top >= bottom):
            raise ValueError()
        if intersect_page:
            # A PDF glyph's bounds can extend beyond the visible page rectangle.
            # Locate the supplied geometry's visible intersection; retain the
            # unmodified SDK bbox in provenance. Never move disjoint geometry
            # onto a page or repair reversed/non-finite coordinates.
            left, top = max(0, left), max(0, top)
            right, bottom = min(width, right), min(height, bottom)
        values = [left, top, right, bottom]
        if not (0 <= left < right <= width and 0 <= top < bottom <= height):
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
    record["offsets"] = "unicode_codepoints_in_binding_text_field"
    record["raw_text_definition"] = "Docling text; not a verbatim digital-layer claim"
    record["coordinate_mapping"] = "docling_2_132_merged_first_page_origin_to_top_left_intersect_page"
    record["selected_pages"] = sorted(selected)
    extraction_id = stable_hash(record)
    out, bindings, exclusions, stack = [], [], [], []

    def emit(text: str, prov: dict, ref: str, *, heading=None, cell=None, text_field="text", origin_height=None):
        page = prov["page_no"]
        if type(page) is not int or str(page) not in page_data:
            raise DoclingError("docling_page_invalid")
        geometry = prov["bbox"]
        if origin_height is not None:
            # Pinned SDK 2.132.0 ReadingOrderModel._merge_elements serializes
            # ALL merged bboxes with the first element's page height. Translate
            # that declared origin; do not guess a new box or alter SDK output.
            if geometry.get("coord_origin") != "BOTTOMLEFT":
                raise DoclingError("docling_geometry_invalid")
            geometry = {**geometry, "t": origin_height - geometry["t"],
                        "b": origin_height - geometry["b"], "coord_origin": "TOPLEFT"}
        box = top_left_box(geometry, page_data[str(page)]["size"], intersect_page=True)
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
                         "charspan_text_field": text_field,
                         "text_origin": origin, "geometry_precision": "item_bbox",
                         "docling_origin_height": origin_height,
                         "geometry_mapping": "intersect_original_page"})

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
        text_field = "text"
        # Official ListItemMarkerProcessor strips the declared marker from text
        # without changing the full-original provenance span. Retain orig only
        # when that exact transformation is proven; do not clamp/guess offsets.
        original = item.get("orig")
        marker = item.get("marker")
        if (label == "list_item" and isinstance(original, str) and text
                and isinstance(marker, str) and marker and len(provenance) == 1
                and provenance[0].get("charspan") == [0, len(original)]
                and len(original) > len(text) and original.endswith(text)
                and original[:-len(text)].strip() == marker):
            text, text_field = original, "orig"
        ranges = []
        for prov in provenance:
            start, end = prov["charspan"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise DoclingError("docling_charspan_invalid")
            ranges.append((start, end))
            origin_height = None
            first_page = provenance[0]["page_no"]
            if prov["page_no"] != first_page:
                if type(first_page) is not int or str(first_page) not in page_data:
                    raise DoclingError("docling_page_invalid")
                origin_height = page_data[str(first_page)]["size"]["height"]
            emit(text[start:end], prov, ref, heading=heading, text_field=text_field,
                 origin_height=origin_height)
        # Docling merged paragraphs may have a separator between page spans.
        covered = set(i for lo, hi in ranges for i in range(lo, hi))
        if any(not ch.isspace() and i not in covered for i, ch in enumerate(text)):
            raise DoclingError("docling_text_coverage_incomplete")
    if not out:
        raise DoclingError("docling_no_source_text")
    # OCR is disabled. A missing page may be blank, scanned, or missed by the
    # model; none of those possibilities proves complete source extraction.
    if selected - {row["source_page"] for row in out}:
        raise DoclingError("docling_page_text_unverified")
    record.update(extraction_id=extraction_id, bindings=bindings, exclusions=exclusions,
                  selected_pages=sorted(selected), metrics=deepcopy(result.get("metrics", {})))
    return ExtractedFragments(out, record)


def stored_fragments(envelope: dict):
    """Read the accepted representation, never reconvert on review/repair."""
    from src.integrity_kernel import stable_hash
    runs = envelope.get("quality_processing_runs") or []
    # Classification and blocked attempts can append a run without producing
    # a new extraction. Keep the latest accepted producer, not the latest event.
    for run in reversed(runs):
        if run.get("outcome") != "succeeded":
            continue
        if "document_extraction" in run:
            record = run["document_extraction"]
            break
        versions = run.get("extractor_versions") or []
        if any(str(version).startswith(CONTRACT + "/") for version in versions):
            raise DoclingError("docling_stored_evidence_invalid")
        if versions or run.get("source_fragments"):
            # An explicitly accepted native extraction supersedes older
            # Docling work. Historical native readers retain their own route.
            return None
    else:
        return None
    if not isinstance(record, dict):
        raise DoclingError("docling_stored_evidence_invalid")
    rows = record.get("prepared_fragments")
    if (record.get("source_sha256") != envelope.get("sha256") or not isinstance(rows, list)
            or record.get("prepared_fragments_hash") != stable_hash(rows)
            or record.get("record_hash") != stable_hash({k: v for k, v in record.items() if k != "record_hash"})):
        raise DoclingError("docling_stored_evidence_invalid")
    return ExtractedFragments(deepcopy(rows), deepcopy(record))
