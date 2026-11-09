"""Shared structural envelope for already materialised candidate units."""
from typing import Any


def document_spec(*, document_id, title, family, class_, content_kind, units):
    """Structural envelope shared by producers; candidate units come from their owner."""
    objects: list[dict[str, Any]] = [
        {
            "object_id": f"{document_id}-document",
            "object_type": "document",
            "text": title,
            "review_track": "technical",
        }
    ]
    objects.extend(units)
    spec = {
        "spec_version": "console-ingest-1.0",
        "document_id": document_id,
        "object_version": "1.0",
        "target_group": [],
        "care_setting": [],
        "topic": [family, f"class:{class_}", f"source-kind:{content_kind}"],
        "objects": objects,
    }
    return spec
