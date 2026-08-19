#!/usr/bin/env python3
"""Protocol v2.1 safe retrieval: hybrid candidates + answerability gate."""
from __future__ import annotations

from typing import Any

try:
    from .answerability_gate_v1 import AnswerabilityConfig, evaluate_answerability
    from .hybrid_retrieval_v1 import HybridConfig, HybridIndex
    from .lexical_retrieval_v1 import RetrievalConfig
    from .semantic_vector_retrieval_v1 import VectorConfig
except ImportError:
    from answerability_gate_v1 import AnswerabilityConfig, evaluate_answerability
    from hybrid_retrieval_v1 import HybridConfig, HybridIndex
    from lexical_retrieval_v1 import RetrievalConfig
    from semantic_vector_retrieval_v1 import VectorConfig

ENGINE_VERSION = "safe-retrieval-v1.0.0"


class SafeRetrievalIndex:
    def __init__(
        self,
        records: list[dict[str, Any]],
        hybrid_config: HybridConfig | None = None,
        lexical_config: RetrievalConfig | None = None,
        vector_config: VectorConfig | None = None,
        answerability_config: AnswerabilityConfig | None = None,
    ):
        self.records = records
        self.hybrid = HybridIndex(records, hybrid_config, lexical_config, vector_config)
        self.answerability_config = answerability_config or AnswerabilityConfig()
        self.record_by_object = {r["metadata"]["object_id"]: r for r in records}
        self.index_signature = self.hybrid.index_signature

    def search(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        raw = self.hybrid.search(query, top_k)
        gated = evaluate_answerability(query, raw, self.record_by_object, self.answerability_config)
        return {
            "engine_version": ENGINE_VERSION,
            "candidate_engine_version": raw.get("engine_version"),
            "index_signature": self.index_signature,
            "query": query,
            "behavior": gated["behavior"],
            "answerability": gated["answerability"],
            "reason": gated["reason"],
            "false_positive_class": gated.get("false_positive_class"),
            "query_spec": gated.get("query_spec"),
            "candidate_decision": {
                "behavior": raw.get("behavior"),
                "reason": raw.get("reason"),
                "child_decisions": raw.get("child_decisions"),
            },
            "candidate_evidence": gated.get("candidate_evidence", []),
            "evidence_clusters": gated.get("evidence_clusters", []),
            "results": gated.get("results", []),
        }
