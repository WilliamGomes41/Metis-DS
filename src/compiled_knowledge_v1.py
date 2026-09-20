"""Post-publication compiled-knowledge input boundary.

This module deliberately contains no LLM executor. It reads only the active
publication registry and proves its immutable source bytes before exposing input
to a future compiled-knowledge/wiki build. The future executor must use
src.llm_provider_v1 rather than introducing another provider key or model.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.canonical_publication_postgres_v1 import CanonicalPublicationStoreError
from src.product_source_authority_v1 import (
    ProductSourceAuthorityError,
    verify_active_publication_sources,
)


class CompiledKnowledgeInputError(RuntimeError):
    """Raised when the published input authority cannot be proven."""


def compiled_knowledge_inputs(
    *,
    canonical_store: Any,
    source_store: Any,
) -> list[dict[str, Any]]:
    try:
        authority_rows = canonical_store.active_publication_rows()
    except CanonicalPublicationStoreError as exc:
        raise CompiledKnowledgeInputError("compiled_knowledge_publication_authority_unavailable") from exc
    except Exception as exc:
        raise CompiledKnowledgeInputError("compiled_knowledge_publication_authority_unavailable") from exc

    try:
        verify_active_publication_sources(
            authority_rows,
            canonical_store=canonical_store,
            source_store=source_store,
        )
    except ProductSourceAuthorityError as exc:
        raise CompiledKnowledgeInputError(str(exc)) from exc

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in authority_rows:
        if not isinstance(row, dict):
            raise CompiledKnowledgeInputError("compiled_knowledge_publication_row_invalid")
        obj = row.get("knowledge_object")
        publication = row.get("publication")
        if not isinstance(obj, dict) or not isinstance(publication, dict):
            raise CompiledKnowledgeInputError("compiled_knowledge_publication_row_invalid")
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
