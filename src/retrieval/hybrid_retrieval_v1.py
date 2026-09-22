#!/usr/bin/env python3
"""Hybrid lexical + local-vector retrieval for V&VN Data Services.

Fusion uses Reciprocal Rank Fusion (RRF), avoiding incompatible raw-score
normalization between BM25 and vector cosine similarity.

Safety:
- consumes derived retrieval projection records only;
- never mutates canonical knowledge;
- each child engine applies its own abstention policy first;
- if both child engines abstain, hybrid abstains;
- only result lists from child engines that passed their own gate contribute;
- source/object/version/projection metadata remain attached to every result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    from .lexical_retrieval_v1 import LexicalIndex, RetrievalConfig
    from .semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl
except ImportError:  # direct script execution
    from lexical_retrieval_v1 import LexicalIndex, RetrievalConfig
    from semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl

ENGINE_VERSION = "hybrid-rrf-v1.0.0"


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class HybridConfig:
    top_k: int = 5
    candidate_k: int = 10
    rrf_k: int = 60
    lexical_weight: float = 1.0
    vector_weight: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HybridConfig":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in allowed})


class HybridIndex:
    def __init__(
        self,
        records: list[dict[str, Any]],
        hybrid_config: HybridConfig | None = None,
        lexical_config: RetrievalConfig | None = None,
        vector_config: VectorConfig | None = None,
    ):
        self.records = records
        self.hybrid_config = hybrid_config or HybridConfig()
        self.lexical_config = lexical_config or RetrievalConfig()
        self.vector_config = vector_config or VectorConfig()
        self.lexical = LexicalIndex(records, self.lexical_config)
        self.vector = LocalVectorIndex(records, self.vector_config)
        self.record_by_object = {r["metadata"]["object_id"]: r for r in records}
        self.index_signature = _hash({
            "engine": ENGINE_VERSION,
            "hybrid_config": asdict(self.hybrid_config),
            "lexical_engine": getattr(__import__(LexicalIndex.__module__, fromlist=['ENGINE_VERSION']), 'ENGINE_VERSION', 'unknown'),
            "vector_signature": self.vector.index_signature,
            "projection_hashes": sorted(r.get("projection_hash") for r in records if r.get("projection_hash")),
        })

    def _rrf_add(self, fused: dict[str, dict[str, Any]], result: dict[str, Any], source: str, weight: float) -> None:
        if result.get("behavior") != "retrieve":
            return
        for rank, item in enumerate(result.get("results", []), start=1):
            oid = item["object_id"]
            bucket = fused.setdefault(oid, {
                "object_id": oid,
                "rrf_score": 0.0,
                "lexical_rank": None,
                "vector_rank": None,
                "lexical_score": None,
                "vector_score": None,
            })
            bucket["rrf_score"] += weight / (self.hybrid_config.rrf_k + rank)
            bucket[f"{source}_rank"] = rank
            bucket[f"{source}_score"] = item.get("score")

    def search(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        top_k = top_k or self.hybrid_config.top_k
        if not self.records:
            return {
                "engine_version": ENGINE_VERSION,
                "index_signature": self.index_signature,
                "query": query,
                "behavior": "abstain",
                "reason": "empty_published_corpus",
                "results": [],
            }

        lr = self.lexical.search(query, self.hybrid_config.candidate_k)
        vr = self.vector.search(query, self.hybrid_config.candidate_k)

        if lr.get("behavior") == "abstain" and vr.get("behavior") == "abstain":
            return {
                "engine_version": ENGINE_VERSION,
                "index_signature": self.index_signature,
                "query": query,
                "behavior": "abstain",
                "reason": "all_child_engines_abstained",
                "child_decisions": {
                    "lexical": {"behavior": lr.get("behavior"), "reason": lr.get("reason")},
                    "vector": {"behavior": vr.get("behavior"), "reason": vr.get("reason")},
                },
                "results": [],
            }

        fused: dict[str, dict[str, Any]] = {}
        self._rrf_add(fused, lr, "lexical", self.hybrid_config.lexical_weight)
        self._rrf_add(fused, vr, "vector", self.hybrid_config.vector_weight)

        ranked = sorted(
            fused.values(),
            key=lambda x: (-x["rrf_score"], x["object_id"]),
        )[:top_k]
        out: list[dict[str, Any]] = []
        for item in ranked:
            record = self.record_by_object[item["object_id"]]
            md = record["metadata"]
            out.append({
                "retrieval_id": record["retrieval_id"],
                "object_id": item["object_id"],
                "object_version": md["object_version"],
                "document_id": md.get("document_id"),
                "object_type": md.get("object_type"),
                "release_id": md.get("release_id"),
                "release_version": md.get("release_version"),
                "rrf_score": round(item["rrf_score"], 12),
                "lexical_rank": item["lexical_rank"],
                "vector_rank": item["vector_rank"],
                "lexical_score": item["lexical_score"],
                "vector_score": item["vector_score"],
                "projection_hash": record.get("projection_hash"),
            })

        return {
            "engine_version": ENGINE_VERSION,
            "index_signature": self.index_signature,
            "query": query,
            "behavior": "retrieve",
            "reason": "at_least_one_child_engine_passed_then_rrf_fused",
            "child_decisions": {
                "lexical": {"behavior": lr.get("behavior"), "reason": lr.get("reason")},
                "vector": {"behavior": vr.get("behavior"), "reason": vr.get("reason")},
            },
            "results": out,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--hybrid-config", type=Path, required=True)
    ap.add_argument("--lexical-config", type=Path, required=True)
    ap.add_argument("--vector-config", type=Path, required=True)
    ap.add_argument("--top-k", type=int)
    args = ap.parse_args()

    records = read_jsonl(args.records)
    hcfg = HybridConfig.from_dict(json.loads(args.hybrid_config.read_text(encoding="utf-8")))
    lcfg = RetrievalConfig.from_dict(json.loads(args.lexical_config.read_text(encoding="utf-8")))
    vcfg = VectorConfig.from_dict(json.loads(args.vector_config.read_text(encoding="utf-8")))
    result = HybridIndex(records, hcfg, lcfg, vcfg).search(args.query, args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
