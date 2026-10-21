#!/usr/bin/env python3
"""Deterministic lexical retrieval baseline for V&VN Data Services.

This engine is deliberately simple and auditable. It operates only on derived
retrieval projection records; it never reads or mutates canonical knowledge.

Ranking: BM25 over retrieval_text with a small exact-bigram bonus.
Abstention: the engine returns no result unless the top document passes BOTH a
minimum BM25 score and a minimum IDF-weighted query-coverage threshold.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ENGINE_VERSION = "lexical-bm25-v1.0.0"

# Function words and query boilerplate. Clinical/domain terms are deliberately
# not included here: they need to contribute to retrieval and abstention.
STOPWORDS = {
    "aan", "als", "bij", "dan", "dat", "de", "dit", "door", "een", "en", "er", "het",
    "hoe", "in", "is", "kan", "mag", "met", "moet", "naar", "niet", "nog", "of", "om",
    "op", "over", "te", "tot", "uit", "van", "voor", "wat", "welke", "wie", "wordt", "worden",
    "zijn", "haar", "hem", "hun", "ze", "zij", "deze", "die", "wel", "ieder", "iedere", "vanaf",
    "volgens", "specifieke", "pilotkennisset", "kennisset", "routinematig",
}

OPERATOR_REPLACEMENTS = {
    ">=": " gte ", "≤": " lte ", "<=": " lte ", "≥": " gte ",
    ">": " gt ", "<": " lt ", "=": " eq ",
}

TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    # Preserve comparison meaning as lexical tokens.
    for source, target in sorted(OPERATOR_REPLACEMENTS.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(source, target)
    text = text.replace("²", "2").replace("µ", "u")
    return text


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(normalize_text(text)) if t not in STOPWORDS and (len(t) > 1 or t.isdigit())]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int = 5
    k1: float = 1.35
    b: float = 0.72
    bigram_bonus: float = 0.35
    min_score: float = 2.0
    min_query_coverage: float = 0.48
    min_distinct_terms: int = 2

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetrievalConfig":
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})


class LexicalIndex:
    def __init__(self, records: list[dict[str, Any]], config: RetrievalConfig | None = None):
        self.records = records
        self.config = config or RetrievalConfig()
        self.doc_tokens: list[list[str]] = [tokenize(r.get("retrieval_text", "")) for r in records]
        self.term_freqs: list[Counter[str]] = [Counter(ts) for ts in self.doc_tokens]
        self.doc_lengths = [len(ts) for ts in self.doc_tokens]
        self.avgdl = (sum(self.doc_lengths) / len(self.doc_lengths)) if self.doc_lengths else 0.0
        df: dict[str, int] = defaultdict(int)
        for tokens in self.doc_tokens:
            for term in set(tokens):
                df[term] += 1
        self.df = dict(df)
        self.n = len(records)

    def idf(self, term: str) -> float:
        # BM25+ style positive IDF. Terms absent from the corpus get a high
        # weight in coverage, making unknown query concepts push toward abstain.
        n = max(self.n, 1)
        df = self.df.get(term, 0)
        return math.log(1.0 + (n - df + 0.5) / (df + 0.5))

    def _bm25(self, query_terms: list[str], doc_idx: int) -> float:
        if not self.n or not query_terms:
            return 0.0
        tf = self.term_freqs[doc_idx]
        dl = self.doc_lengths[doc_idx]
        score = 0.0
        for term in set(query_terms):
            freq = tf.get(term, 0)
            if not freq:
                continue
            denom = freq + self.config.k1 * (1 - self.config.b + self.config.b * dl / max(self.avgdl, 1e-9))
            score += self.idf(term) * (freq * (self.config.k1 + 1) / denom)
        return score

    def _bigram_bonus(self, query_terms: list[str], doc_idx: int) -> float:
        if len(query_terms) < 2:
            return 0.0
        doc = self.doc_tokens[doc_idx]
        doc_bigrams = set(zip(doc, doc[1:]))
        q_bigrams = set(zip(query_terms, query_terms[1:]))
        return self.config.bigram_bonus * sum(1 for bg in q_bigrams if bg in doc_bigrams)

    def _coverage(self, query_terms: list[str], doc_idx: int) -> tuple[float, int, list[str]]:
        unique = list(dict.fromkeys(query_terms))
        if not unique:
            return 0.0, 0, []
        doc_terms = set(self.doc_tokens[doc_idx])
        total_weight = sum(self.idf(t) for t in unique)
        matched = [t for t in unique if t in doc_terms]
        matched_weight = sum(self.idf(t) for t in matched)
        coverage = matched_weight / total_weight if total_weight else 0.0
        return coverage, len(matched), matched

    def search(self, query: str, top_k: int | None = None) -> dict[str, Any]:
        top_k = top_k or self.config.top_k
        qterms = tokenize(query)
        if not qterms or not self.records:
            return {
                "engine_version": ENGINE_VERSION,
                "query": query,
                "query_terms": qterms,
                "behavior": "abstain",
                "reason": "empty_query_or_corpus",
                "results": [],
            }

        scored: list[dict[str, Any]] = []
        for i, record in enumerate(self.records):
            bm25 = self._bm25(qterms, i)
            bonus = self._bigram_bonus(qterms, i)
            score = bm25 + bonus
            coverage, distinct, matched = self._coverage(qterms, i)
            if score <= 0:
                continue
            scored.append({
                "retrieval_id": record["retrieval_id"],
                "object_id": record["metadata"]["object_id"],
                "object_version": record["metadata"]["object_version"],
                "score": round(score, 6),
                "bm25_score": round(bm25, 6),
                "bigram_bonus": round(bonus, 6),
                "query_coverage": round(coverage, 6),
                "matched_distinct_terms": distinct,
                "matched_terms": matched,
                "projection_hash": record.get("projection_hash"),
            })
        scored.sort(key=lambda r: (-r["score"], -r["query_coverage"], r["retrieval_id"]))

        if not scored:
            return {
                "engine_version": ENGINE_VERSION,
                "query": query,
                "query_terms": qterms,
                "behavior": "abstain",
                "reason": "no_lexical_match",
                "results": [],
            }

        top = scored[0]
        reasons = []
        if top["score"] < self.config.min_score:
            reasons.append("top_score_below_threshold")
        if top["query_coverage"] < self.config.min_query_coverage:
            reasons.append("query_coverage_below_threshold")
        if top["matched_distinct_terms"] < self.config.min_distinct_terms:
            reasons.append("too_few_distinct_terms")
        if reasons:
            return {
                "engine_version": ENGINE_VERSION,
                "query": query,
                "query_terms": qterms,
                "behavior": "abstain",
                "reason": "+".join(reasons),
                "top_candidate": top,
                "results": [],
            }

        return {
            "engine_version": ENGINE_VERSION,
            "query": query,
            "query_terms": qterms,
            "behavior": "retrieve",
            "reason": "thresholds_passed",
            "results": scored[:top_k],
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--top-k", type=int)
    args = ap.parse_args()

    cfg_data = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    config = RetrievalConfig.from_dict(cfg_data)
    idx = LexicalIndex(read_jsonl(args.records), config)
    result = idx.search(args.query, args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
