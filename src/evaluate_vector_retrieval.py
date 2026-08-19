#!/usr/bin/env python3
"""Evaluate local vector retrieval on the same V&VN golden set as lexical baseline."""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

try:
    from .semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl
except ImportError:  # direct script execution
    from semantic_vector_retrieval_v1 import LocalVectorIndex, VectorConfig, read_jsonl

EVALUATOR_VERSION = "vector-retrieval-eval-v1.0.0"


def _norm(value: Any) -> str:
    text = str(value).casefold().replace("≥", ">=").replace("≤", "<=")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _logic_match(expected: dict[str, Any], logic: dict[str, Any] | None) -> bool:
    if not logic:
        return False
    candidates: list[dict[str, Any]] = list(logic.get("predicates") or [])
    if logic.get("result_threshold"):
        candidates.append(dict(logic["result_threshold"]))
    for c in candidates:
        combined = dict(c)
        if logic.get("score_points") is not None:
            combined.setdefault("score_points", logic["score_points"])
        if all((k in combined) and (_norm(combined[k]) == _norm(v) if isinstance(v, str) else combined[k] == v) for k, v in expected.items()):
            return True
    return False


def evaluate(records: list[dict[str, Any]], golden: dict[str, Any], config: VectorConfig) -> dict[str, Any]:
    index = LocalVectorIndex(records, config)
    record_by_object = {r["metadata"]["object_id"]: r for r in records}
    details: list[dict[str, Any]] = []
    retrieve_questions = retrieve_any_hits = expected_total = expected_found = 0
    abstain_questions = abstain_correct = 0
    content_checks_total = content_checks_pass = 0

    for q in golden.get("questions", []):
        if q.get("execution_mode") != "published_corpus":
            continue
        result = index.search(q["question"], config.top_k)
        returned_ids = [x["object_id"] for x in result.get("results", [])]
        expected_ids = q.get("expected_object_ids") or []
        detail = {
            "id": q["id"], "class": q["class"], "question": q["question"],
            "expected_behavior": q["expected_behavior"], "actual_behavior": result["behavior"],
            "returned_object_ids": returned_ids, "expected_object_ids": expected_ids,
            "reason": result.get("reason"),
        }
        if result.get("top_candidate"):
            detail["top_candidate"] = result["top_candidate"]
        elif result.get("results"):
            detail["top_candidate"] = result["results"][0]

        if q["expected_behavior"] == "retrieve":
            retrieve_questions += 1
            expected_total += len(expected_ids)
            found = [oid for oid in expected_ids if oid in returned_ids]
            expected_found += len(found)
            any_hit = bool(found)
            retrieve_any_hits += int(any_hit)
            detail["any_expected_in_top_k"] = any_hit
            detail["expected_found"] = found
            checks = []
            for phrase in (q.get("must_contain") or []) + (q.get("must_preserve") or []):
                content_checks_total += 1
                present = any(_norm(phrase) in _norm((record_by_object.get(oid) or {}).get("retrieval_text") or "") for oid in expected_ids)
                content_checks_pass += int(present)
                checks.append({"type": "phrase", "expected": phrase, "pass": present})
            for expected_logic in q.get("expected_logic") or []:
                content_checks_total += 1
                matched = any(_logic_match(expected_logic, (record_by_object.get(oid) or {}).get("structured_logic")) for oid in expected_ids)
                content_checks_pass += int(matched)
                checks.append({"type": "logic", "expected": expected_logic, "pass": matched})
            detail["content_integrity_checks"] = checks
        elif q["expected_behavior"] == "abstain":
            abstain_questions += 1
            correct = result["behavior"] == "abstain"
            abstain_correct += int(correct)
            detail["abstention_correct"] = correct
        details.append(detail)

    metrics = {
        "published_corpus_questions": retrieve_questions + abstain_questions,
        "retrieve_questions": retrieve_questions,
        "retrieve_any_hit_at_5": round(retrieve_any_hits / retrieve_questions, 6) if retrieve_questions else None,
        "micro_expected_object_recall_at_5": round(expected_found / expected_total, 6) if expected_total else None,
        "abstain_questions": abstain_questions,
        "abstention_accuracy": round(abstain_correct / abstain_questions, 6) if abstain_questions else None,
        "projection_content_integrity": round(content_checks_pass / content_checks_total, 6) if content_checks_total else None,
        "content_checks": {"passed": content_checks_pass, "total": content_checks_total},
    }
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "engine_version": "local-char-tfidf-vector-v1.0.0",
        "index_signature": index.index_signature,
        "golden_set_id": golden.get("golden_set_id"),
        "golden_set_status": golden.get("status"),
        "evaluation_status": "preliminary_same_set_threshold_calibration_not_independent_holdout",
        "corpus_records": len(records),
        "config": config.__dict__,
        "metrics": metrics,
        "details": details,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--golden", type=Path, required=True)
    ap.add_argument("--config", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--lexical-report", type=Path)
    args = ap.parse_args()
    records = read_jsonl(args.records)
    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    cfg = VectorConfig.from_dict(json.loads(args.config.read_text(encoding="utf-8")))
    report = evaluate(records, golden, cfg)
    if args.lexical_report and args.lexical_report.exists():
        lexical = json.loads(args.lexical_report.read_text(encoding="utf-8"))
        lm = lexical["metrics"]; vm = report["metrics"]
        report["comparison_to_lexical"] = {
            "lexical_retrieve_any_hit_at_5": lm.get("retrieve_any_hit_at_5"),
            "vector_retrieve_any_hit_at_5": vm.get("retrieve_any_hit_at_5"),
            "delta_retrieve_any_hit_at_5": round(vm.get("retrieve_any_hit_at_5", 0) - lm.get("retrieve_any_hit_at_5", 0), 6),
            "lexical_abstention_accuracy": lm.get("abstention_accuracy"),
            "vector_abstention_accuracy": vm.get("abstention_accuracy"),
            "safety_preserved": vm.get("abstention_accuracy") >= lm.get("abstention_accuracy"),
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metrics": report["metrics"], "comparison": report.get("comparison_to_lexical")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
