#!/usr/bin/env python3
"""Deterministic local vector retrieval baseline for V&VN Data Services.

This is deliberately *not* a pretrained semantic embedding model. It is a
reproducible character n-gram TF-IDF vector index used to validate the vector
retrieval architecture and establish a comparator before an external embedding
provider is introduced.

Safety properties:
- consumes derived retrieval projection records only;
- never reads or mutates canonical knowledge;
- empty published corpus => abstain;
- similarity below a configured threshold => abstain;
- index signature is deterministic for the same records + configuration;
- source/object/version metadata are preserved in every result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ENGINE_VERSION = "local-char-tfidf-vector-v1.0.0"


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    # Make comparison operators explicit so small symbol differences do not
    # silently disappear in vectorization.
    replacements = [(">=", " gte "), ("≤", " lte "), ("<=", " lte "), ("≥", " gte "), (">", " gt "), ("<", " lt ")]
    for source, target in replacements:
        text = text.replace(source, target)
    text = text.replace("²", "2").replace("µ", "u")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass(frozen=True)
class VectorConfig:
    top_k: int = 5
    ngram_min: int = 3
    ngram_max: int = 5
    min_similarity: float = 0.23
    sublinear_tf: bool = True
    threshold_status: str = "preliminary_calibrated_on_golden_v0.1"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VectorConfig":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in value.items() if k in allowed})


class LocalVectorIndex:
    def __init__(self, records: list[dict[str, Any]], config: VectorConfig | None = None):
        self.config = config or VectorConfig()
        self.records = sorted(records, key=lambda r: r.get("retrieval_id", ""))
        self._validate_records()
        signature_input = {
            "engine_version": ENGINE_VERSION,
            "config": asdict(self.config),
            "records": [
                {
                    "retrieval_id": r.get("retrieval_id"),
                    "projection_hash": r.get("projection_hash"),
                }
                for r in self.records
            ],
        }
        self.index_signature = _canonical_hash(signature_input)
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        if self.records:
            self.vectorizer = TfidfVectorizer(
                preprocessor=normalize_text,
                analyzer="char_wb",
                ngram_range=(self.config.ngram_min, self.config.ngram_max),
                sublinear_tf=self.config.sublinear_tf,
                lowercase=False,  # handled by preprocessor
                dtype=np.float64,
            )
            self.matrix = self.vectorizer.fit_transform([r["retrieval_text"] for r in self.records])

    def _validate_records(self) -> None:
        seen: set[str] = set()
        for r in self.records:
            rid = r.get("retrieval_id")
            if not rid or rid in seen:
                raise ValueError("retrieval_id_missing_or_duplicate")
            seen.add(rid)
            if not r.get("retrieval_text"):
                raise ValueError(f"retrieval_text_missing:{rid}")
            meta = r.get("metadata") or {}
            for field in ("object_id", "object_version", "content_hash", "release_id", "release_version"):
                if not meta.get(field):
                    raise ValueError(f"metadata_{field}_missing:{rid}")
            if not r.get("projection_hash"):
                raise ValueError(f"projection_hash_missing:{rid}")

    @staticmethod
    def _matches_filters(record: dict[str, Any], filters: dict[str, Any] | None) -> bool:
        if not filters:
            return True
        meta = record.get("metadata") or {}
        for key, expected in filters.items():
            actual = meta.get(key)
            if isinstance(expected, (list, tuple, set)):
                if actual not in expected:
                    return False
            elif actual != expected:
                return False
        return True

    def search(self, query: str, top_k: int | None = None, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        k = top_k or self.config.top_k
        if not self.records or self.vectorizer is None or self.matrix is None:
            return {
                "engine_version": ENGINE_VERSION,
                "index_signature": self.index_signature,
                "behavior": "abstain",
                "reason": "empty_published_corpus",
                "results": [],
            }
        candidates = [i for i, r in enumerate(self.records) if self._matches_filters(r, filters)]
        if not candidates:
            return {
                "engine_version": ENGINE_VERSION,
                "index_signature": self.index_signature,
                "behavior": "abstain",
                "reason": "no_records_after_filter",
                "results": [],
            }
        qv = self.vectorizer.transform([query])
        sims = cosine_similarity(qv, self.matrix[candidates])[0]
        order_local = np.argsort(-sims, kind="stable")
        ranked: list[dict[str, Any]] = []
        for local_pos in order_local[:k]:
            idx = candidates[int(local_pos)]
            r = self.records[idx]
            meta = r["metadata"]
            ranked.append({
                "retrieval_id": r["retrieval_id"],
                "object_id": meta["object_id"],
                "object_version": meta["object_version"],
                "document_id": meta.get("document_id"),
                "object_type": meta.get("object_type"),
                "release_id": meta.get("release_id"),
                "release_version": meta.get("release_version"),
                "score": round(float(sims[int(local_pos)]), 9),
                "projection_hash": r["projection_hash"],
            })
        top = ranked[0]
        if top["score"] < self.config.min_similarity:
            return {
                "engine_version": ENGINE_VERSION,
                "index_signature": self.index_signature,
                "behavior": "abstain",
                "reason": "similarity_below_threshold",
                "threshold": self.config.min_similarity,
                "top_candidate": top,
                "results": [],
            }
        return {
            "engine_version": ENGINE_VERSION,
            "index_signature": self.index_signature,
            "behavior": "retrieve",
            "reason": "threshold_passed",
            "threshold": self.config.min_similarity,
            "results": ranked,
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--config", type=Path)
    ap.add_argument("--top-k", type=int)
    args = ap.parse_args()
    cfg = VectorConfig.from_dict(json.loads(args.config.read_text(encoding="utf-8"))) if args.config else VectorConfig()
    idx = LocalVectorIndex(read_jsonl(args.records), cfg)
    print(json.dumps(idx.search(args.query, args.top_k), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
