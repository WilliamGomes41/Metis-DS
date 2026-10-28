"""Source heading structure for pre-Review processing.

Headings are extraction structure: the extractor labels them, and this module
projects each extractor-labelled heading as one structural row in source
order. It makes no meaning decisions: it does not split, merge, reword, type
or select prose. Knowledge candidates are formed only by the semantic routes
through ``knowledge_materialisation_v1.materialise_knowledge_candidates``.

Only non-heading material is filtered: navigation chrome, strength stamps,
bare list numbers, timestamps and empty text are not headings of the source.
"""
from __future__ import annotations

from typing import Any, Iterable

from src.object_taxonomy_v1 import (
    extract_object_type,
    is_kennisplatform_chrome_text,
    is_list_number_only,
    is_raw_timestamp,
    is_strength_stamp,
    normalize_visible_prose,
)
from src.vorming.source_occurrence_authority_v1 import prefer_authoritative_exact_occurrences
from src.vorming.source_reconstruction_v1 import reconstruct_source_fragments, source_fragment_ids_for_text


def _not_a_heading(text: str) -> bool:
    blob = normalize_visible_prose(text)
    return (
        not blob
        or is_kennisplatform_chrome_text(blob)
        or is_strength_stamp(blob)
        or is_list_number_only(blob)
        or is_raw_timestamp(blob)
    )


def heading_structure_units(
    fragments: Iterable[dict[str, Any]],
    *,
    document_id: str,
) -> list[dict[str, Any]]:
    """Project extractor-labelled headings as structural rows, one per heading."""

    from src.vorming.prepared_source_views_v1 import filtered_view
    headings = filtered_view(fragments,"headings")
    if headings is None:
        headings = [fragment for fragment in fragments if extract_object_type(fragment)[0] == "heading"]
    rows: list[dict[str, Any]] = []
    for fragment in reconstruct_source_fragments(headings):
        text = (fragment.get("clean_text") or fragment.get("raw_text") or "").strip()
        if extract_object_type(fragment)[0] != "heading" or _not_a_heading(text):
            continue
        heading = fragment.get("heading")
        rows.append({
            "object_id": f"{document_id}-{fragment['fragment_id']}",
            "object_type": "heading",
            "text": text,
            "clean_text": text,
            "source_fragment_ids": list(dict.fromkeys(
                source_fragment_ids_for_text(fragment, start=0, end=len(text)) or [fragment["fragment_id"]])),
            "section_path": [
                part
                for part in (fragment.get("section_path") or [])
                if not is_strength_stamp(str(part)) and not is_kennisplatform_chrome_text(str(part))
            ],
            "heading": None
            if is_strength_stamp(str(heading or "")) or is_kennisplatform_chrome_text(str(heading or ""))
            else heading,
            "review_track": "clinical",
            "relations": [],
            "confirmed_relations": [],
            "proposed_object_type": "heading",
        })
    return prefer_authoritative_exact_occurrences(rows)
