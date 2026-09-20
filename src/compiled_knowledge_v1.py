"""Post-publication compiled-knowledge input boundary.

This module deliberately contains no LLM executor. It defines the only allowed
input shape for a future compiled-knowledge/wiki build: active publication
authority rows that already contain a canonical knowledge object and publication
binding. The future executor must use src.llm_provider_v1 rather than
introducing another provider key or model setting.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


class CompiledKnowledgeInputError(ValueError):
    """Raised when compiled knowledge is asked to consume non-publication input."""


def compiled_knowledge_inputs(
    authority_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in authority_rows:
        if not isinstance(row, dict):
            raise CompiledKnowledgeInputError("compiled_knowledge_publication_row_required")
        obj = row.get("knowledge_object")
        publication = row.get("publication")
        if not isinstance(obj, dict) or not isinstance(publication, dict):
            raise CompiledKnowledgeInputError("compiled_knowledge_publication_row_required")
        object_id = str(obj.get("object_id") or "").strip()
        if not object_id:
            raise CompiledKnowledgeInputError("compiled_knowledge_object_id_required")
        if object_id in seen:
            raise CompiledKnowledgeInputError("compiled_knowledge_duplicate_object")
        seen.add(object_id)
        out.append(
            {
                "knowledge_object": deepcopy(obj),
                "publication": deepcopy(publication),
            }
        )
    return out
