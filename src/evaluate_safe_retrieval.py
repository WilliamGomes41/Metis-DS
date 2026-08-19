#!/usr/bin/env python3
"""Evaluate protocol-v2.1 safe retrieval on a development/golden set.

This evaluator is intentionally labelled development-only. Independent holdout
acceptance is a separate workflow and must not be used for tuning.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .answerability_gate_v1 import AnswerabilityConfig
    from .hybrid_retrieval_v1 import HybridConfig
    from .lexical_retrieval_v1 import RetrievalConfig
    from .safe_retrieval_v1 import SafeRetrievalIndex
    from .semantic_vector_retrieval_v1 import VectorConfig, read_jsonl
except ImportError:
    from answerability_gate_v1 import AnswerabilityConfig
    from hybrid_retrieval_v1 import HybridConfig
    from lexical_retrieval_v1 import RetrievalConfig
    from safe_retrieval_v1 import SafeRetrievalIndex
    from semantic_vector_retrieval_v1 import VectorConfig, read_jsonl

EVALUATOR_VERSION = "safe-retrieval-development-eval-v1.0.0"


def evaluate(records: list[dict[str, Any]], golden: dict[str, Any], hcfg, lcfg, vcfg, acfg) -> dict[str, Any]:
    index = SafeRetrievalIndex(records, hcfg, lcfg, vcfg, acfg)
    details = []
    retrieve = hit = abstain = abstain_correct = false_answers = 0
    for q in golden.get("questions", []):
        if q.get("execution_mode") != "published_corpus":
            continue
        result = index.search(q["question"], hcfg.top_k)
        ids = [x["object_id"] for x in result.get("results", [])]
        d = {
            "id": q["id"], "class": q["class"], "question": q["question"],
            "expected_behavior": q["expected_behavior"], "actual_behavior": result["behavior"],
            "answerability": result.get("answerability"), "reason": result.get("reason"),
            "false_positive_class": result.get("false_positive_class"), "returned_object_ids": ids,
        }
        if q["expected_behavior"] == "retrieve":
            retrieve += 1
            ok = any(x in ids for x in q.get("expected_object_ids") or [])
            hit += int(ok); d["expected_hit"] = ok
        else:
            abstain += 1
            ok = result["behavior"] == "abstain"
            abstain_correct += int(ok)
            false_answers += int(not ok)
            d["abstention_correct"] = ok
        details.append(d)
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "evaluation_status": "development_only_tuning_allowed_not_independent_acceptance",
        "golden_set_id": golden.get("golden_set_id"),
        "metrics": {
            "retrieve_questions": retrieve,
            "retrieve_any_hit_at_5": round(hit / retrieve, 6) if retrieve else None,
            "no_answer_questions": abstain,
            "abstention_accuracy": round(abstain_correct / abstain, 6) if abstain else None,
            "false_answer_rate": round(false_answers / abstain, 6) if abstain else None,
        },
        "details": details,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--hybrid-config", type=Path, required=True)
    ap.add_argument("--lexical-config", type=Path, required=True)
    ap.add_argument("--vector-config", type=Path, required=True)
    ap.add_argument("--answerability-config", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    report = evaluate(
        read_jsonl(args.records), json.loads(args.golden.read_text(encoding="utf-8")),
        HybridConfig.from_dict(json.loads(args.hybrid_config.read_text())),
        RetrievalConfig.from_dict(json.loads(args.lexical_config.read_text())),
        VectorConfig.from_dict(json.loads(args.vector_config.read_text())),
        AnswerabilityConfig.from_dict(json.loads(args.answerability_config.read_text())),
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
