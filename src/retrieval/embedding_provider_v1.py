#!/usr/bin/env python3
"""Embedding provider contract for derived V&VN retrieval indexes.

Providers are infrastructure adapters only. They must never receive canonical
objects directly; callers pass published retrieval projection text.

Secrets are deliberately not part of this contract/config. Remote providers
should resolve credentials via environment/managed identity in their own
adapter implementation.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

PROVIDER_CONTRACT_VERSION = "embedding-provider-v1.0.0"


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def normalize_clinical_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    for source, target in [(">=", " gte "), ("≤", " lte "), ("<=", " lte "), ("≥", " gte "), (">", " gt "), ("<", " lt ")]:
        text = text.replace(source, target)
    text = text.replace("²", "2").replace("µ", "u")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


class EmbeddingProvider(ABC):
    """Provider interface used by vector indexes.

    fit() exists because deterministic local providers may learn a vocabulary.
    Hosted embedding APIs can implement it as a no-op.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str: ...

    @property
    @abstractmethod
    def deterministic(self) -> bool: ...

    @property
    @abstractmethod
    def fitted(self) -> bool: ...

    @abstractmethod
    def fit(self, texts: Sequence[str]) -> None: ...

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    @abstractmethod
    def embed_query(self, text: str) -> np.ndarray: ...

    @abstractmethod
    def metadata(self) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LocalCharTfidfProviderConfig:
    ngram_min: int = 3
    ngram_max: int = 5
    sublinear_tf: bool = True
    dtype: str = "float64"


class LocalCharTfidfEmbeddingProvider(EmbeddingProvider):
    """Deterministic local adapter matching the step-8 vector baseline."""

    def __init__(self, config: LocalCharTfidfProviderConfig | None = None):
        self.config = config or LocalCharTfidfProviderConfig()
        if self.config.dtype != "float64":
            raise ValueError("unsupported_dtype")
        self._vectorizer: TfidfVectorizer | None = None
        self._fitted = False
        self._corpus_signature: str | None = None

    @property
    def provider_id(self) -> str:
        return "local-char-tfidf-v1"

    @property
    def deterministic(self) -> bool:
        return True

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, texts: Sequence[str]) -> None:
        texts = list(texts)
        if not texts:
            self._vectorizer = None
            self._fitted = True
            self._corpus_signature = canonical_hash([])
            return
        self._vectorizer = TfidfVectorizer(
            preprocessor=normalize_clinical_text,
            analyzer="char_wb",
            ngram_range=(self.config.ngram_min, self.config.ngram_max),
            sublinear_tf=self.config.sublinear_tf,
            lowercase=False,
            dtype=np.float64,
        )
        self._vectorizer.fit(texts)
        self._fitted = True
        self._corpus_signature = canonical_hash(texts)

    def _require(self) -> TfidfVectorizer:
        if not self._fitted:
            raise RuntimeError("provider_not_fitted")
        if self._vectorizer is None:
            raise RuntimeError("provider_fitted_on_empty_corpus")
        return self._vectorizer

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        vectorizer = self._require()
        return vectorizer.transform(list(texts)).toarray()

    def embed_query(self, text: str) -> np.ndarray:
        vectorizer = self._require()
        return vectorizer.transform([text]).toarray()[0]

    def metadata(self) -> dict[str, Any]:
        dim = len(self._vectorizer.vocabulary_) if self._vectorizer is not None else 0
        return {
            "contract_version": PROVIDER_CONTRACT_VERSION,
            "provider_id": self.provider_id,
            "deterministic": self.deterministic,
            "config": asdict(self.config),
            "fitted": self.fitted,
            "dimension": dim,
            "corpus_signature": self._corpus_signature,
            "credentials_in_config": False,
        }


def build_provider(config: dict[str, Any]) -> EmbeddingProvider:
    forbidden = {"api_key", "secret", "client_secret", "password", "token"}
    if forbidden.intersection(k.casefold() for k in config):
        raise ValueError("secret_material_not_allowed_in_provider_config")
    kind = config.get("provider")
    if kind == "local_char_tfidf":
        params = config.get("parameters") or {}
        allowed = set(LocalCharTfidfProviderConfig.__dataclass_fields__)
        return LocalCharTfidfEmbeddingProvider(LocalCharTfidfProviderConfig(**{k: v for k, v in params.items() if k in allowed}))
    raise ValueError(f"embedding_provider_not_implemented:{kind}")
