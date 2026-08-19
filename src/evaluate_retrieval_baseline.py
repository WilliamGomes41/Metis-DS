#!/usr/bin/env python3
"""Evaluate the deterministic lexical baseline against a V&VN golden set.

This evaluator separates retrieval quality from abstention safety. It does not
turn the preliminary golden set into clinical truth; it only measures behavior
against the expectations encoded in that set.
"""
from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Any

from lexical_retrieval_v1 import LexicalIndex, RetrievalConfig, read_jsonl

EVALUATOR_VERSION = "retrieval-eval-v1.0.0"


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
    # score_points may be attached at the logic level while operator/threshold
    # live in a predicate.
    for c in candidates:
        combined = dict(c)
        if logic.get("score_points") is not None:
            combined.setdefault("score_points", logic["score_points"])
        ok = True
        for k, v in expected.items():
            if k not in combined:
                ok = False
                break
            if isinstance(v, str):
                ok = _norm(combined[k]) == _norm(v)
            else:
                ok = combined[k] == v
            if not ok:
                break
        if ok:
            return True
    return False


def evaluate(records: list[dict[str, Any]], golden: dict[str, Any], config: RetrievalConfig) -> dict[str, Any]:
    index = LexicalIndex(records, config)
    record_by_object = {r["metadata"]["object_id"]: r for r in records}
    details: list[dict[str, Any]] = []

    retrieve_questions = 0
    retrieve_any_hits = 0
    expected_total = 0
    expected_found = 0
    abstain_questions = 0
    abstain_correct = 0
    content_checks_total = 0
    content_checks_pass = 0
    retrieve_abstained = 0
    retrieve_abstained_correct_top_candidate = 0

    for q in golden.get("questions", []):
        if q.get("execution_mode") != "published_corpus":
            continue
        result = index.search(q["question"], config.top_k)
        returned_ids = [x["object_id"] for x in result.get("results", [])]
        expected_ids = q.get("expected_object_ids") or []
        detail = {
            "id": q["id"],
            "class": q["class"],
            "question": q["question"],
            "expected_behavior": q["expected_behavior"],
            "actual_behavior": result["behavior"],
            "returned_object_ids": returned_ids,
            "expected_object_ids": expected_ids,
            "reason": result.get("reason"),
        }

        if q["expected_behavior"] == "retrieve":
            retrieve_questions += 1
            expected_total += len(expected_ids)
            found = [x for x in expected_ids if x in returned_ids]
            expected_found += len(found)
            any_hit = bool(found)
            retrieve_any_hits += int(any_hit)
            detail["any_expected_in_top_k"] = any_hit
            detail["expected_found"] = found

            # Integrity/content checks are evaluated against the expected source
            # record(s), independent from whether ranking found them. This lets us
            # distinguish projection loss from ranking loss.
            checks: list[dict[str, Any]] = []
            phrases = (q.get("must_contain") or []) + (q.get("must_preserve") or [])
            for phrase in phrases:
                content_checks_total += 1
                present = any(
                    _norm(phrase) in _norm(record_by_object.get(oid, {}).get("retrieval_text") or "")
                    for oid in expected_ids
                )
                content_checks_pass += int(present)
                checks.append({"type": "phrase", "expected": phrase, "pass": present})
            for expected_logic in q.get("expected_logic") or []:
                content_checks_total += 1
                matched = any(
                    _logic_match(expected_logic, (record_by_object.get(oid) or {}).get("structured_logic"))
                    for oid in expected_ids
                )
                content_checks_pass += int(matched)
                checks.append({"type": "logic", "expected": expected_logic, "pass": matched})
            detail["content_integrity_checks"] = checks
            if result["behavior"] == "abstain":
                retrieve_abstained += 1
                if result.get("top_candidate"):
                    detail["top_candidate"] = result["top_candidate"]
                    if result["top_candidate"].get("object_id") in expected_ids:
                        retrieve_abstained_correct_top_candidate += 1
        elif q["expected_behavior"] == "abstain":
            abstain_questions += 1
            correct = result["behavior"] == "abstain"
            abstain_correct += int(correct)
            detail["abstention_correct"] = correct
            if result.get("top_candidate"):
                detail["top_candidate"] = result["top_candidate"]
        details.append(detail)

    metrics = {
        "published_corpus_questions": retrieve_questions + abstain_questions,
        "retrieve_questions": retrieve_questions,
        "retrieve_any_hit_at_5": round(retrieve_any_hits / retrieve_questions, 6) if retrieve_questions else None,
        "micro_expected_object_recall_at_5": round(expected_found / expected_total, 6) if expected_total else None,
        "abstain_questions": abstain_questions,
        "abstention_accuracy": round(abstain_correct / abstain_questions, 6) if abstain_questions else None,
        "projection_content_integrity": round(content_checks_pass / content_checks_total, 6) if content_checks_total else None,
        "retrieve_questions_abstained": retrieve_abstained,
        "abstained_retrieve_with_correct_top_candidate": retrieve_abstained_correct_top_candidate,
        "content_checks": {"passed": content_checks_pass, "total": content_checks_total},
    }
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "engine_version": "lexical-bm25-v1.0.0",
        "golden_set_id": golden.get("golden_set_id"),
        "golden_set_status": golden.get("status"),
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
    args = ap.parse_args()

    records = read_jsonl(args.records)
    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    cfg = RetrievalConfig.from_dict(json.loads(args.config.read_text(encoding="utf-8")))
    report = evaluate(records, golden, cfg)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
