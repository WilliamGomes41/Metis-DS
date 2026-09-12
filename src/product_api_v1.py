#!/usr/bin/env python3
"""External Product API v1 for V&VN Data Services.

REAL mode reads the active publication registry from PostgreSQL and proves every
referenced source snapshot against Azure Blob before building the retrieval
projection. Local JSONL files are never a REAL-mode corpus source or fallback.
Fixture mode remains file-backed and explicitly synthetic.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .abstain_catalog_v1 import sentence_for
from .answerability_gate_v1 import AnswerabilityConfig
from .canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from .g2_source_store import AzureBlobSourceStore
from .hybrid_retrieval_v1 import HybridConfig
from .lexical_retrieval_v1 import RetrievalConfig
from .object_taxonomy_v1 import serving_block_reason
from .product_security_v1 import SlidingWindowRateLimiter, TenantPolicy, TenantRegistry
from .product_source_authority_v1 import ProductSourceAuthorityError, verify_active_publication_sources
from .retrieval_projection_v2 import build_projection
from .safe_retrieval_v1 import SafeRetrievalIndex
from .semantic_vector_retrieval_v1 import VectorConfig
from .serving_relations_v1 import applies_if_targets, except_if_targets, historical_type_must_not_serve
from .usage_ledger_v1 import UsageLedger

ROOT = Path(__file__).resolve().parents[1]
API_VERSION = "v1"
SERVICE_VERSION = "product-api-v1.3.0"


class ProductCorpusError(RuntimeError):
    """Fail-closed error for the REAL published corpus."""


class RetrieveFilters(BaseModel):
    document_ids: list[str] = Field(default_factory=list, max_length=50)
    topics: list[str] = Field(default_factory=list, max_length=50)


class RetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    filters: RetrieveFilters = Field(default_factory=RetrieveFilters)


@dataclass(frozen=True)
class ProductPaths:
    real_records: Path
    fixture_records: Path
    real_published: Path
    lexical_config: Path
    vector_config: Path
    hybrid_config: Path
    tenant_config: Path
    usage_db: Path

    @classmethod
    def defaults(cls, root: Path = ROOT) -> "ProductPaths":
        return cls(
            real_records=root / "output/v2/retrieval/real_current_retrieval_records.jsonl",
            fixture_records=root / "data/fixtures/baseline_v0_1/baseline_fixture_records.jsonl",
            real_published=root / "output/v2/retrieval/real_current_published.jsonl",
            lexical_config=root / "config/retrieval_baseline_v1.json",
            vector_config=root / "config/vector_retrieval_v1.json",
            hybrid_config=root / "config/hybrid_retrieval_v1.json",
            tenant_config=Path(os.getenv("VVN_TENANT_CONFIG", str(root / "config/tenants.v1.json"))),
            usage_db=Path(os.getenv("VVN_USAGE_DB", str(root / "output/runtime/product_api_usage.sqlite"))),
        )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _extract_api_key(authorization: str | None, x_api_key: str | None) -> str | None:
    if authorization:
        prefix = "Bearer "
        if authorization.startswith(prefix) and authorization[len(prefix):].strip():
            return authorization[len(prefix):].strip()
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    return None


def _corpus_revision(records: list[dict[str, Any]]) -> str:
    identity = [
        (
            str((row.get("metadata") or {}).get("object_id") or ""),
            str((row.get("metadata") or {}).get("object_version") or ""),
            str((row.get("metadata") or {}).get("release_id") or ""),
            str(row.get("projection_hash") or ""),
        )
        for row in records
    ]
    payload = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ProductState:
    def __init__(
        self,
        mode: Literal["real", "fixture"],
        paths: ProductPaths,
        tenant_registry: TenantRegistry,
        *,
        canonical_publication_store: Any | None = None,
        immutable_source_store: Any | None = None,
        usage_ledger: UsageLedger | None = None,
        rate_limiter: SlidingWindowRateLimiter | None = None,
    ):
        self.mode = mode
        self.synthetic = mode == "fixture"
        self.paths = paths
        self.canonical_publication_store = canonical_publication_store
        self.immutable_source_store = immutable_source_store
        self.records_path = paths.fixture_records if mode == "fixture" else None
        self._records_mtime_ns: int | None = None
        self._corpus_revision: str | None = None
        self.records: list[dict[str, Any]] = []
        self.record_by_object: dict[str, dict[str, Any]] = {}
        self.tenant_registry = tenant_registry
        self.ledger = usage_ledger or UsageLedger(paths.usage_db)
        self.rate_limiter = rate_limiter or SlidingWindowRateLimiter()
        self.lexical_config = RetrievalConfig.from_dict(_read_json(paths.lexical_config, {}))
        self.vector_config = VectorConfig.from_dict(_read_json(paths.vector_config, {}))
        self.hybrid_config = HybridConfig.from_dict(_read_json(paths.hybrid_config, {}))
        self.answerability_config = AnswerabilityConfig.from_dict(_read_json(paths.hybrid_config.parent / "answerability_gate_v1.json", {}))
        self._index_cache: dict[tuple[Any, ...], SafeRetrievalIndex] = {}
        self._reload_records(force=True)

    def _install_records(self, records: list[dict[str, Any]], *, revision: str) -> bool:
        records = [row for row in records if not historical_type_must_not_serve((row.get("metadata") or {}).get("object_type"))]
        if revision == self._corpus_revision:
            return False
        self.records = records
        self.record_by_object = {r.get("metadata", {}).get("object_id"): r for r in records if (r.get("metadata") or {}).get("object_id")}
        self._corpus_revision = revision
        self._index_cache = {}
        return True

    def _reload_fixture_records(self, *, force: bool = False) -> bool:
        assert self.records_path is not None
        try:
            mtime = self.records_path.stat().st_mtime_ns
        except FileNotFoundError:
            mtime = None
        if not force and mtime == self._records_mtime_ns:
            return False
        records = _read_jsonl(self.records_path)
        revision = "fixture:" + str(mtime) + ":" + _corpus_revision(records)
        changed = self._install_records(records, revision=revision)
        self._records_mtime_ns = mtime
        return changed

    def _reload_real_records(self) -> bool:
        store = self.canonical_publication_store
        if store is None:
            raise ProductCorpusError("canonical_publication_store_required")
        try:
            authority_rows = store.active_publication_rows()
        except CanonicalPublicationStoreError as exc:
            raise ProductCorpusError("canonical_publication_store_unavailable") from exc
        except Exception as exc:
            raise ProductCorpusError("canonical_publication_store_unavailable") from exc

        try:
            verify_active_publication_sources(
                authority_rows,
                canonical_store=store,
                source_store=self.immutable_source_store,
            )
        except ProductSourceAuthorityError as exc:
            raise ProductCorpusError(str(exc)) from exc

        envelopes = [{"knowledge_object": dict(row["knowledge_object"]), "publication": dict(row["publication"])} for row in authority_rows]
        records, blocked = build_projection(envelopes)
        if blocked:
            raise ProductCorpusError("canonical_publication_projection_invalid:" + json.dumps(blocked, ensure_ascii=False, sort_keys=True))
        if len({str((row.get("metadata") or {}).get("object_id") or "") for row in records}) != len(records):
            raise ProductCorpusError("canonical_publication_projection_duplicate_object")
        return self._install_records(records, revision="postgres+blob:" + _corpus_revision(records))

    def _reload_records(self, *, force: bool = False) -> bool:
        if self.mode == "real":
            return self._reload_real_records()
        return self._reload_fixture_records(force=force)

    def refresh(self) -> bool:
        return self._reload_records(force=False)

    def auth(self, api_key: str | None) -> TenantPolicy:
        if not api_key:
            raise HTTPException(status_code=401, detail={"code": "missing_api_key"}, headers={"WWW-Authenticate": "Bearer"})
        tenant = self.tenant_registry.authenticate(api_key)
        if tenant is None:
            raise HTTPException(status_code=401, detail={"code": "invalid_api_key"}, headers={"WWW-Authenticate": "Bearer"})
        allowed, retry_after = self.rate_limiter.allow(tenant.tenant_id, tenant.requests_per_minute)
        if not allowed:
            raise HTTPException(status_code=429, detail={"code": "rate_limit_exceeded"}, headers={"Retry-After": str(retry_after)})
        return tenant

    def require_scope(self, tenant: TenantPolicy, scope: str) -> None:
        if not tenant.has_scope(scope):
            raise HTTPException(status_code=403, detail={"code": "scope_denied", "required_scope": scope})

    def _tenant_records(self, tenant: TenantPolicy, filters: RetrieveFilters | None = None) -> list[dict[str, Any]]:
        self.refresh()
        requested_docs = set(filters.document_ids) if filters else set()
        requested_topics = set(filters.topics) if filters else set()
        for did in requested_docs:
            if not tenant.allows_document(did):
                raise HTTPException(status_code=403, detail={"code": "document_not_entitled", "document_id": did})
        if requested_topics and "*" not in tenant.allowed_topics:
            denied = sorted(t for t in requested_topics if t not in tenant.allowed_topics)
            if denied:
                raise HTTPException(status_code=403, detail={"code": "topic_not_entitled", "topics": denied})
        rows: list[dict[str, Any]] = []
        for r in self.records:
            md = r.get("metadata") or {}
            if not tenant.allows_document(md.get("document_id")) or not tenant.allows_topics(md.get("topic") or []):
                continue
            if requested_docs and md.get("document_id") not in requested_docs:
                continue
            if requested_topics and not requested_topics.intersection(set(md.get("topic") or [])):
                continue
            rows.append(r)
        return rows

    def _safe_index(self, records: list[dict[str, Any]]) -> SafeRetrievalIndex:
        key = (self._corpus_revision, tuple((r.get("metadata") or {}).get("object_id") for r in records))
        engine = self._index_cache.get(key)
        if engine is None:
            engine = SafeRetrievalIndex(records, self.hybrid_config, self.lexical_config, self.vector_config, self.answerability_config)
            self._index_cache = {key: engine}
        return engine

    def _bound_payload(self, record: dict[str, Any]) -> dict[str, Any]:
        md = record.get("metadata") or {}
        return {"knowledge_object_id": md.get("object_id"), "object_version": md.get("object_version"), "object_type": md.get("object_type") or md.get("confirmed_object_type"), "content": record.get("retrieval_text"), "advice_weight": False, "labels": ["V", "VN"]}

    def _attach_advice_bounds(self, results: list[dict[str, Any]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id = {(row.get("metadata") or {}).get("object_id"): row for row in records}
        out: list[dict[str, Any]] = []
        for item in results:
            record = by_id.get(item.get("knowledge_object_id")) or {}
            md = record.get("metadata") or {}
            applies_ids = list(md.get("applies_if_object_ids") or applies_if_targets(record) or applies_if_targets(md))
            except_ids = list(md.get("except_if_object_ids") or except_if_targets(record) or except_if_targets(md))
            item["applies_if"] = []
            item["except_if"] = []
            if item.get("object_type") != "recommendation" or not (applies_ids or except_ids):
                out.append(item)
                continue
            applies, excepts = [], []
            missing = False
            for oid in applies_ids:
                target = by_id.get(oid)
                if not target:
                    missing = True
                    break
                applies.append(self._bound_payload(target))
            if not missing:
                for oid in except_ids:
                    target = by_id.get(oid)
                    if not target:
                        missing = True
                        break
                    excepts.append(self._bound_payload(target))
            if missing:
                continue
            item["applies_if"] = applies
            item["except_if"] = excepts
            out.append(item)
        return out

    def retrieve(self, tenant: TenantPolicy, req: RetrieveRequest) -> dict[str, Any]:
        self.require_scope(tenant, "retrieve")
        if req.top_k > tenant.max_top_k:
            raise HTTPException(status_code=400, detail={"code": "top_k_exceeds_tenant_limit", "max_top_k": tenant.max_top_k})
        records = self._tenant_records(tenant, req.filters)
        raw = self._safe_index(records).search(req.query, req.top_k)
        results: list[dict[str, Any]] = []
        for item in raw.get("results", []):
            record = next((r for r in records if (r.get("metadata") or {}).get("object_id") == item.get("object_id")), None)
            if not record:
                continue
            md = record.get("metadata") or {}
            results.append({"knowledge_object_id": item["object_id"], "object_version": item.get("object_version"), "document_id": md.get("document_id"), "object_type": item.get("object_type") or md.get("object_type"), "content": record.get("retrieval_text"), "structured_logic": record.get("structured_logic"), "source": {"title": md.get("source_title"), "url": md.get("source_url"), "page": md.get("source_page"), "version": md.get("source_version"), "locator": md.get("source_locator")}, "release": {"release_id": md.get("release_id"), "release_version": md.get("release_version"), "published_at": md.get("published_at")}, "scores": {"hybrid_rrf": item.get("rrf_score"), "lexical": item.get("lexical_score"), "vector": item.get("vector_score")}, "content_hash": md.get("content_hash"), "projection_hash": record.get("projection_hash"), "chunk_readiness": md.get("chunk_readiness"), "advice_weight": bool(item.get("advice_weight")), "labels": item.get("labels") or (["V", "VN"] if raw.get("answerability") == "supported" else [])})
        results = self._attach_advice_bounds(results, records)
        if raw.get("answerability") == "supported" and not results:
            return {"api_version": API_VERSION, "service_version": SERVICE_VERSION, "synthetic_fixture": self.synthetic, "status": "abstain", "answerability": "insufficient_evidence", "reason": "advice_bounds_missing", "false_positive_class": "relation_mismatch", "labels": [], "advice_weight": False, "abstain_sentence": raw.get("abstain_sentence"), "results": [], "result_count": 0}
        return {"api_version": API_VERSION, "service_version": SERVICE_VERSION, "synthetic_fixture": self.synthetic, "status": raw.get("behavior"), "answerability": raw.get("answerability"), "reason": raw.get("reason"), "false_positive_class": raw.get("false_positive_class"), "labels": raw.get("labels") or [], "advice_weight": bool(raw.get("advice_weight")), "abstain_sentence": raw.get("abstain_sentence"), "results": results, "result_count": len(results)}

    def knowledge(self, tenant: TenantPolicy, object_id: str) -> dict[str, Any]:
        self.require_scope(tenant, "knowledge:read")
        self.refresh()
        record = self.record_by_object.get(object_id)
        if not record:
            raise HTTPException(status_code=404, detail={"code": "knowledge_object_not_found"})
        md = record.get("metadata") or {}
        if not tenant.allows_document(md.get("document_id")) or not tenant.allows_topics(md.get("topic") or []):
            raise HTTPException(status_code=404, detail={"code": "knowledge_object_not_found"})
        blocked = serving_block_reason(record)
        if blocked:
            raise HTTPException(status_code=404, detail={"code": "knowledge_object_not_servable", "reason": blocked, "status": "abstain", "answerability": "insufficient_evidence", "abstain_sentence": sentence_for(blocked)})
        return {"api_version": API_VERSION, "synthetic_fixture": self.synthetic, "knowledge_object_id": object_id, "object_version": md.get("object_version"), "document_id": md.get("document_id"), "object_type": md.get("confirmed_object_type") or md.get("object_type"), "content": record.get("retrieval_text"), "structured_logic": record.get("structured_logic"), "source": {"title": md.get("source_title"), "url": md.get("source_url"), "page": md.get("source_page"), "version": md.get("source_version")}, "release": {"release_id": md.get("release_id"), "release_version": md.get("release_version"), "published_at": md.get("published_at")}, "content_hash": md.get("content_hash"), "projection_hash": record.get("projection_hash"), "chunk_readiness": md.get("chunk_readiness")}

    def documents(self, tenant: TenantPolicy) -> list[dict[str, Any]]:
        self.require_scope(tenant, "documents:read")
        rows = self._tenant_records(tenant)
        grouped: dict[str, dict[str, Any]] = {}
        for r in rows:
            md = r.get("metadata") or {}
            did = md.get("document_id")
            if not did:
                continue
            bucket = grouped.setdefault(did, {"document_id": did, "title": md.get("source_title"), "version": md.get("source_version"), "source_url": md.get("source_url"), "published_at": md.get("published_at"), "knowledge_object_count": 0})
            bucket["knowledge_object_count"] += 1
        return sorted(grouped.values(), key=lambda x: x["document_id"])

    def updates(self, tenant: TenantPolicy) -> list[dict[str, Any]]:
        self.require_scope(tenant, "updates:read")
        rows = self._tenant_records(tenant)
        releases: dict[tuple[str, str], dict[str, Any]] = {}
        for r in rows:
            md = r.get("metadata") or {}
            rid, rv = md.get("release_id"), md.get("release_version")
            if not rid:
                continue
            key = (str(rid), str(rv or ""))
            bucket = releases.setdefault(key, {"release_id": rid, "release_version": rv, "published_at": md.get("published_at"), "documents": set(), "knowledge_object_count": 0})
            if md.get("document_id"):
                bucket["documents"].add(md["document_id"])
            bucket["knowledge_object_count"] += 1
        return sorted(({**x, "documents": sorted(x["documents"])} for x in releases.values()), key=lambda x: (x.get("published_at") or "", x["release_id"]), reverse=True)


def _default_real_store() -> PostgresCanonicalPublicationStore:
    store = PostgresCanonicalPublicationStore()
    store.verify_schema()
    return store


def create_product_app(
    mode: Literal["real", "fixture"] = "real",
    *,
    paths: ProductPaths | None = None,
    tenant_registry: TenantRegistry | None = None,
    canonical_publication_store: Any | None = None,
    immutable_source_store: Any | None = None,
    usage_ledger: UsageLedger | None = None,
    rate_limiter: SlidingWindowRateLimiter | None = None,
    allow_fixture: bool = False,
) -> FastAPI:
    if mode == "fixture" and not allow_fixture:
        raise ValueError("fixture mode is disabled for Product API unless allow_fixture=True")
    p = paths or ProductPaths.defaults()
    registry = tenant_registry or TenantRegistry.from_path(p.tenant_config)
    store = canonical_publication_store
    source_store = immutable_source_store
    if mode == "real":
        if store is None:
            store = _default_real_store()
        if source_store is None and canonical_publication_store is None:
            source_store = AzureBlobSourceStore()
    state = ProductState(mode, p, registry, canonical_publication_store=store, immutable_source_store=source_store, usage_ledger=usage_ledger, rate_limiter=rate_limiter)
    app = FastAPI(title="V&VN Data Services API", version=SERVICE_VERSION, description="Machine-to-machine access to published V&VN knowledge. This API does not generate clinical answers.")
    app.state.product = state
    bearer = HTTPBearer(auto_error=False, scheme_name="VVNApiKeyBearer", description="Tenant API key as Bearer token")

    def current_tenant(credentials: HTTPAuthorizationCredentials | None = Security(bearer), x_api_key: str | None = Header(default=None, alias="X-API-Key", include_in_schema=False)) -> TenantPolicy:
        authorization = f"Bearer {credentials.credentials}" if credentials else None
        return state.auth(_extract_api_key(authorization, x_api_key))

    def logged_response(*, request_id: str, tenant: TenantPolicy, endpoint: str, started: float, status_code: int, behavior: str | None = None, query: str | None = None, object_ids: list[str] | None = None) -> None:
        state.ledger.record(request_id=request_id, tenant_id=tenant.tenant_id, endpoint=endpoint, status_code=status_code, behavior=behavior, result_count=len(object_ids or []), query=query, result_object_ids=object_ids, latency_ms=(time.perf_counter() - started) * 1000.0, synthetic_fixture=state.synthetic)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-VVN-API-Version"] = API_VERSION
        return response

    @app.get("/v1/health")
    def health() -> dict[str, Any]:
        state.refresh()
        return {"status": "ok", "api_version": API_VERSION, "service_version": SERVICE_VERSION, "mode": state.mode, "synthetic_fixture": state.synthetic, "published_retrieval_records": len(state.records) if state.synthetic else None, "published_corpus_ready": bool(state.records), "corpus_reload_policy": "postgres_active_registry_plus_blob_readback" if state.mode == "real" else "reload_fixture_on_file_change", "published_corpus_authority": "postgres+azure_blob" if state.mode == "real" else "fixture_jsonl", "generation_enabled": False}

    @app.post("/v1/retrieve")
    def retrieve(req: RetrieveRequest, request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); result = state.retrieve(tenant, req); result["request_id"] = request.state.request_id; result["tenant_id"] = tenant.tenant_id
        ids = [x["knowledge_object_id"] for x in result["results"]]; logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/retrieve", started=started, status_code=200, behavior=result["status"], query=req.query, object_ids=ids); return result

    @app.get("/v1/knowledge/{object_id}")
    def knowledge(object_id: str, request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); result = state.knowledge(tenant, object_id); result["request_id"] = request.state.request_id; logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/knowledge/{id}", started=started, status_code=200, behavior="read", object_ids=[object_id]); return result

    @app.get("/v1/documents")
    def documents(request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); docs = state.documents(tenant); logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/documents", started=started, status_code=200, behavior="read", object_ids=[]); return {"api_version": API_VERSION, "request_id": request.state.request_id, "tenant_id": tenant.tenant_id, "documents": docs}

    @app.get("/v1/documents/{document_id}")
    def document(document_id: str, request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); docs = [d for d in state.documents(tenant) if d["document_id"] == document_id]
        if not docs: raise HTTPException(status_code=404, detail={"code": "document_not_found"})
        logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/documents/{id}", started=started, status_code=200, behavior="read", object_ids=[]); return {"api_version": API_VERSION, "request_id": request.state.request_id, "tenant_id": tenant.tenant_id, **docs[0]}

    @app.get("/v1/updates")
    def updates(request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); rows = state.updates(tenant); logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/updates", started=started, status_code=200, behavior="read", object_ids=[]); return {"api_version": API_VERSION, "request_id": request.state.request_id, "tenant_id": tenant.tenant_id, "updates": rows}

    @app.get("/v1/usage")
    def usage(request: Request, tenant: TenantPolicy = Depends(current_tenant)) -> dict[str, Any]:
        started = time.perf_counter(); state.require_scope(tenant, "usage:read"); summary = state.ledger.summary(tenant.tenant_id); logged_response(request_id=request.state.request_id, tenant=tenant, endpoint="/v1/usage", started=started, status_code=200, behavior="read", object_ids=[]); return {"api_version": API_VERSION, "request_id": request.state.request_id, **summary}

    return app
