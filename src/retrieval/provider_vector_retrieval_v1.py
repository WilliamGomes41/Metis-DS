#!/usr/bin/env python3
"""Vector retrieval index backed by the pluggable embedding-provider contract."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

try:
    from .embedding_provider_v1 import EmbeddingProvider, canonical_hash
except ImportError:
    from embedding_provider_v1 import EmbeddingProvider, canonical_hash

ENGINE_VERSION = "provider-vector-index-v1.0.0"


@dataclass(frozen=True)
class ProviderVectorConfig:
    top_k: int = 5
    min_similarity: float = 0.23


def _cosine(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    qn = np.linalg.norm(query)
    dn = np.linalg.norm(matrix, axis=1)
    denom = dn * qn
    out = np.zeros(len(matrix), dtype=float)
    mask = denom > 0
    if np.any(mask):
        out[mask] = (matrix[mask] @ query) / denom[mask]
    return out


class ProviderVectorIndex:
    def __init__(self, records: list[dict[str, Any]], provider: EmbeddingProvider, config: ProviderVectorConfig | None = None):
        self.records = sorted(records, key=lambda r: r.get("retrieval_id", ""))
        self.provider = provider
        self.config = config or ProviderVectorConfig()
        self._validate_records()
        self.matrix = np.empty((0, 0), dtype=float)
        if self.records:
            texts = [r["retrieval_text"] for r in self.records]
            self.provider.fit(texts)
            self.matrix = self.provider.embed_documents(texts)
        else:
            self.provider.fit([])
        self.index_signature = canonical_hash({
            "engine": ENGINE_VERSION,
            "config": asdict(self.config),
            "provider": self.provider.metadata(),
            "records": [{"retrieval_id": r.get("retrieval_id"), "projection_hash": r.get("projection_hash")} for r in self.records],
        })

    def _validate_records(self) -> None:
        seen = set()
        for r in self.records:
            rid = r.get("retrieval_id")
            if not rid or rid in seen:
                raise ValueError("retrieval_id_missing_or_duplicate")
            seen.add(rid)
            if not r.get("retrieval_text"):
                raise ValueError(f"retrieval_text_missing:{rid}")
            md = r.get("metadata") or {}
            for field in ("object_id", "object_version", "content_hash", "release_id", "release_version"):
                if not md.get(field):
                    raise ValueError(f"metadata_{field}_missing:{rid}")
            if not r.get("projection_hash"):
                raise ValueError(f"projection_hash_missing:{rid}")

    def search(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        k = top_k or self.config.top_k
        if not self.records:
            return {"engine_version": ENGINE_VERSION, "index_signature": self.index_signature, "behavior": "abstain", "reason": "empty_published_corpus", "results": []}
        q = self.provider.embed_query(query)
        sims = _cosine(q, self.matrix)
        order = np.argsort(-sims, kind="stable")[:k]
        ranked = []
        for idx in order:
            r = self.records[int(idx)]; md = r["metadata"]
            ranked.append({
                "retrieval_id": r["retrieval_id"], "object_id": md["object_id"], "object_version": md["object_version"],
                "document_id": md.get("document_id"), "object_type": md.get("object_type"),
                "release_id": md.get("release_id"), "release_version": md.get("release_version"),
                "score": round(float(sims[int(idx)]), 9), "projection_hash": r["projection_hash"],
            })
        if ranked[0]["score"] < self.config.min_similarity:
            return {"engine_version": ENGINE_VERSION, "index_signature": self.index_signature, "behavior": "abstain", "reason": "similarity_below_threshold", "threshold": self.config.min_similarity, "top_candidate": ranked[0], "results": []}
        return {"engine_version": ENGINE_VERSION, "index_signature": self.index_signature, "behavior": "retrieve", "reason": "threshold_passed", "threshold": self.config.min_similarity, "results": ranked}
