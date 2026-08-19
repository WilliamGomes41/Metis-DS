#!/usr/bin/env python3
"""Build deterministic retrieval text from approved knowledge objects.
No embedding provider is called in this preparatory step.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def retrieval_text(obj: dict[str, Any]) -> str:
    content = obj.get("content") or {}
    structure = obj.get("structure") or {}
    source = obj.get("source") or {}
    parts = []
    if source.get("title"):
        parts.append(f"Bron: {source['title']}")
    section_path = structure.get("section_path") or []
    if section_path:
        parts.append("Sectie: " + " > ".join(section_path))
    if structure.get("heading"):
        parts.append(f"Kop: {structure['heading']}")
    if content.get("context_text"):
        parts.append(f"Context: {content['context_text']}")
    if content.get("clean_text"):
        parts.append(content["clean_text"])
    logic = obj.get("logic")
    if logic:
        compact = {k: v for k, v in logic.items() if v not in (None, [], "")}
        if compact:
            parts.append("Logica: " + json.dumps(compact, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts).strip()


def build_record(obj: dict[str, Any]) -> dict[str, Any]:
    if (obj.get("governance") or {}).get("validation_status") != "approved":
        raise ValueError("Only approved objects may become retrieval records")
    return {
        "object_id": obj["object_id"],
        "document_id": obj["document_id"],
        "object_type": obj["object_type"],
        "retrieval_text": retrieval_text(obj),
        "metadata": {
            "source_url": (obj.get("source") or {}).get("source_url"),
            "source_page": (obj.get("source") or {}).get("source_page"),
            "version": (obj.get("source") or {}).get("version"),
            "topic": (obj.get("content") or {}).get("topic", []),
            "target_group": (obj.get("content") or {}).get("target_group", []),
            "care_setting": (obj.get("content") or {}).get("care_setting", []),
        },
    }
