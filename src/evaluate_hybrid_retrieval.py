#!/usr/bin/env python3
"""Evaluate hybrid retrieval against the unchanged V&VN golden set."""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

try:
    from .hybrid_retrieval_v1 import HybridIndex, HybridConfig
    from .lexical_retrieval_v1 import RetrievalConfig
    from .semantic_vector_retrieval_v1 import VectorConfig, read_jsonl
except ImportError:
    from hybrid_retrieval_v1 import HybridIndex, HybridConfig
    from lexical_retrieval_v1 import RetrievalConfig
    from semantic_vector_retrieval_v1 import VectorConfig, read_jsonl

EVALUATOR_VERSION = "hybrid-retrieval-eval-v1.0.0"


def _norm(value: Any) -> str:
    text = str(value).casefold().replace("≥", ">=").replace("≤", "<=")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _logic_match(expected: dict[str, Any], logic: dict[str, Any] | None) -> bool:
    if not logic:
        return False
    candidates = list(logic.get("predicates") or [])
    if logic.get("result_threshold"):
        candidates.append(dict(logic["result_threshold"]))
    for c in candidates:
        combined = dict(c)
        if logic.get("score_points") is not None:
            combined.setdefault("score_points", logic["score_points"])
        if all((k in combined) and (_norm(combined[k]) == _norm(v) if isinstance(v, str) else combined[k] == v) for k, v in expected.items()):
            return True
    return False


def evaluate(records: list[dict[str, Any]], golden: dict[str, Any], hcfg: HybridConfig, lcfg: RetrievalConfig, vcfg: VectorConfig) -> dict[str, Any]:
    index = HybridIndex(records, hcfg, lcfg, vcfg)
    by_object = {r["metadata"]["object_id"]: r for r in records}
    details = []
    rq = rah = et = ef = aq = ac = ctotal = cpass = 0
    for q in golden.get("questions", []):
        if q.get("execution_mode") != "published_corpus":
            continue
        result = index.search(q["question"], hcfg.top_k)
        returned = [x["object_id"] for x in result.get("results", [])]
        expected = q.get("expected_object_ids") or []
        detail = {
            "id": q["id"], "class": q["class"], "question": q["question"],
            "expected_behavior": q["expected_behavior"], "actual_behavior": result["behavior"],
            "returned_object_ids": returned, "expected_object_ids": expected,
            "reason": result.get("reason"), "child_decisions": result.get("child_decisions"),
        }
        if result.get("results"):
            detail["top_candidate"] = result["results"][0]
        if q["expected_behavior"] == "retrieve":
            rq += 1; et += len(expected)
            found = [oid for oid in expected if oid in returned]
            ef += len(found); rah += int(bool(found))
            detail["any_expected_in_top_k"] = bool(found); detail["expected_found"] = found
            checks = []
            for phrase in (q.get("must_contain") or []) + (q.get("must_preserve") or []):
                ctotal += 1
                ok = any(_norm(phrase) in _norm((by_object.get(oid) or {}).get("retrieval_text") or "") for oid in expected)
                cpass += int(ok); checks.append({"type": "phrase", "expected": phrase, "pass": ok})
            for el in q.get("expected_logic") or []:
                ctotal += 1
                ok = any(_logic_match(el, (by_object.get(oid) or {}).get("structured_logic")) for oid in expected)
                cpass += int(ok); checks.append({"type": "logic", "expected": el, "pass": ok})
            detail["content_integrity_checks"] = checks
        else:
            aq += 1
            ok = result["behavior"] == "abstain"
            ac += int(ok); detail["abstention_correct"] = ok
        details.append(detail)
    metrics = {
        "published_corpus_questions": rq + aq,
        "retrieve_questions": rq,
        "retrieve_any_hit_at_5": round(rah / rq, 6) if rq else None,
        "micro_expected_object_recall_at_5": round(ef / et, 6) if et else None,
        "abstain_questions": aq,
        "abstention_accuracy": round(ac / aq, 6) if aq else None,
        "projection_content_integrity": round(cpass / ctotal, 6) if ctotal else None,
        "content_checks": {"passed": cpass, "total": ctotal},
    }
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "engine_version": "hybrid-rrf-v1.0.0",
        "index_signature": index.index_signature,
        "golden_set_id": golden.get("golden_set_id"),
        "evaluation_status": "preliminary_same_set_child_thresholds_not_independent_holdout",
        "corpus_records": len(records),
        "hybrid_config": hcfg.__dict__,
        "metrics": metrics,
        "details": details,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--hybrid-config", type=Path, required=True)
    ap.add_argument("--lexical-config", type=Path, required=True)
    ap.add_argument("--vector-config", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--lexical-report", type=Path)
    ap.add_argument("--vector-report", type=Path)
    args = ap.parse_args()

    records = read_jsonl(args.records)
    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    hcfg = HybridConfig.from_dict(json.loads(args.hybrid_config.read_text(encoding="utf-8")))
    lcfg = RetrievalConfig.from_dict(json.loads(args.lexical_config.read_text(encoding="utf-8")))
    vcfg = VectorConfig.from_dict(json.loads(args.vector_config.read_text(encoding="utf-8")))
    report = evaluate(records, golden, hcfg, lcfg, vcfg)
    comparisons = {}
    for label, path in [("lexical", args.lexical_report), ("vector", args.vector_report)]:
        if path and path.exists():
            comparisons[label] = json.loads(path.read_text(encoding="utf-8"))["metrics"]
    if comparisons:
        hm = report["metrics"]
        report["comparison"] = {
            "hybrid": hm,
            "lexical_retrieve_any_hit_at_5": comparisons.get("lexical", {}).get("retrieve_any_hit_at_5"),
            "vector_retrieve_any_hit_at_5": comparisons.get("vector", {}).get("retrieve_any_hit_at_5"),
            "hybrid_delta_vs_lexical": round(hm["retrieve_any_hit_at_5"] - comparisons.get("lexical", {}).get("retrieve_any_hit_at_5", 0), 6),
            "hybrid_delta_vs_vector": round(hm["retrieve_any_hit_at_5"] - comparisons.get("vector", {}).get("retrieve_any_hit_at_5", 0), 6),
            "safety_preserved_vs_both": hm["abstention_accuracy"] >= max(
                comparisons.get("lexical", {}).get("abstention_accuracy", 0),
                comparisons.get("vector", {}).get("abstention_accuracy", 0),
            ),
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": report["metrics"], "comparison": report.get("comparison")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
