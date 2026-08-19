#!/usr/bin/env python3
"""Local inspection API/UI for V&VN Data Services.

Safety model:
- REAL mode is the default and searches only derived records from the current
  published corpus. If nothing is published, retrieval abstains.
- FIXTURE mode is explicit test/demo mode and is visibly labelled synthetic.
- This service never approves, publishes, revises, embeds, or mutates canonical
  knowledge. It is a read-only inspection layer.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .hybrid_retrieval_v1 import HybridConfig, HybridIndex
from .lexical_retrieval_v1 import RetrievalConfig, read_jsonl as read_lexical_jsonl
from .semantic_vector_retrieval_v1 import VectorConfig

ROOT = Path(__file__).resolve().parents[1]
SERVICE_VERSION = "inspection-service-v1.0.0"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


@dataclass(frozen=True)
class ServicePaths:
    semantic_objects: Path
    real_records: Path
    fixture_records: Path
    real_published: Path
    source_manifest: Path
    source_registry: Path
    prepublication_report: Path
    lexical_config: Path
    vector_config: Path
    hybrid_config: Path

    @classmethod
    def defaults(cls, root: Path = ROOT) -> "ServicePaths":
        return cls(
            semantic_objects=root / "output/v2/fractuurpreventie_page15_semantic_v21.jsonl",
            real_records=root / "output/v2/retrieval/real_current_retrieval_records.jsonl",
            fixture_records=root / "output/v2/retrieval/baseline_fixture_records.jsonl",
            real_published=root / "output/v2/retrieval/real_current_published.jsonl",
            source_manifest=root / "data/source_manifest.v2.json",
            source_registry=root / "data/source_registry.json",
            prepublication_report=root / "output/v2/integrity_sprint/prepublication_current.json",
            lexical_config=root / "config/retrieval_baseline_v1.json",
            vector_config=root / "config/vector_retrieval_v1.json",
            hybrid_config=root / "config/hybrid_retrieval_v1.json",
        )


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class InspectionState:
    def __init__(self, mode: Literal["real", "fixture"], paths: ServicePaths):
        self.mode = mode
        self.paths = paths
        self.synthetic = mode == "fixture"
        self.semantic_objects = _read_jsonl(paths.semantic_objects)
        self.semantic_by_id = {o.get("object_id"): o for o in self.semantic_objects if o.get("object_id")}
        self.published_envelopes = _read_jsonl(paths.real_published) if mode == "real" else []
        self.real_published_ids = {
            e.get("knowledge_object", {}).get("object_id")
            for e in self.published_envelopes
            if isinstance(e.get("knowledge_object"), dict)
        }
        self.records = _read_jsonl(paths.real_records if mode == "real" else paths.fixture_records)
        self.record_by_object = {
            r.get("metadata", {}).get("object_id"): r
            for r in self.records
            if r.get("metadata", {}).get("object_id")
        }
        self.source_manifest = _read_json(paths.source_manifest, {})
        self.source_registry = _read_json(paths.source_registry, {"sources": []})
        self.prepublication = _read_json(paths.prepublication_report, {"status": "UNKNOWN", "errors": []})
        self.lexical_config = RetrievalConfig.from_dict(_read_json(paths.lexical_config, {}))
        self.vector_config = VectorConfig.from_dict(_read_json(paths.vector_config, {}))
        self.hybrid_config = HybridConfig.from_dict(_read_json(paths.hybrid_config, {}))
        self.hybrid = HybridIndex(self.records, self.hybrid_config, self.lexical_config, self.vector_config)

    def status(self) -> dict[str, Any]:
        validated = sum(1 for o in self.semantic_objects if (o.get("governance") or {}).get("validation_status") == "approved")
        high_risk = sum(1 for o in self.semantic_objects if (o.get("risk") or {}).get("requires_second_review"))
        verified_sources = len(self.source_registry.get("sources", []))
        return {
            "service_version": SERVICE_VERSION,
            "mode": self.mode,
            "synthetic_fixture_mode": self.synthetic,
            "warning": (
                "SYNTHETIC FIXTURE MODE - results are test data and are not published V&VN knowledge."
                if self.synthetic else None
            ),
            "prepublication_gate": self.prepublication.get("status", "UNKNOWN"),
            "semantic_object_count": len(self.semantic_objects),
            "approved_object_count": validated,
            "high_risk_object_count": high_risk,
            "verified_source_count": verified_sources,
            "published_envelope_count": len(self.published_envelopes),
            "retrieval_record_count": len(self.records),
            "hybrid_index_signature": self.hybrid.index_signature,
            "search_policy": "published_only" if not self.synthetic else "synthetic_fixture_only",
        }

    def sources(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "synthetic_fixture_mode": self.synthetic,
            "manifest": self.source_manifest,
            "verified_registry": self.source_registry,
        }

    def documents(self) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for obj in self.semantic_objects:
            did = obj.get("document_id")
            if not did:
                continue
            bucket = grouped.setdefault(did, {
                "document_id": did,
                "title": (obj.get("source") or {}).get("title"),
                "version": (obj.get("source") or {}).get("version"),
                "source_url": (obj.get("source") or {}).get("source_url"),
                "object_count": 0,
                "approved_count": 0,
                "published_count": 0,
                "high_risk_count": 0,
            })
            bucket["object_count"] += 1
            if (obj.get("governance") or {}).get("validation_status") == "approved":
                bucket["approved_count"] += 1
            if obj.get("object_id") in self.real_published_ids:
                bucket["published_count"] += 1
            if (obj.get("risk") or {}).get("requires_second_review"):
                bucket["high_risk_count"] += 1
        return sorted(grouped.values(), key=lambda x: x["document_id"])

    def releases(self) -> list[dict[str, Any]]:
        releases: dict[tuple[str, str], dict[str, Any]] = {}
        if self.synthetic:
            for record in self.records:
                md = record.get("metadata") or {}
                rid = md.get("release_id")
                rv = md.get("release_version")
                if not rid:
                    continue
                key = (rid, rv or "")
                bucket = releases.setdefault(key, {
                    "release_id": rid,
                    "release_version": rv,
                    "published_at": md.get("published_at"),
                    "object_count": 0,
                    "synthetic": True,
                })
                bucket["object_count"] += 1
        else:
            for env in self.published_envelopes:
                pub = env.get("publication") or {}
                rid = pub.get("release_id")
                rv = pub.get("release_version")
                if not rid:
                    continue
                key = (rid, rv or "")
                bucket = releases.setdefault(key, {
                    "release_id": rid,
                    "release_version": rv,
                    "published_at": pub.get("published_at"),
                    "object_count": 0,
                    "synthetic": False,
                })
                bucket["object_count"] += 1
        return sorted(releases.values(), key=lambda x: (x["release_id"], x.get("release_version") or ""))

    def knowledge(self, object_id: str) -> dict[str, Any]:
        if self.synthetic:
            record = self.record_by_object.get(object_id)
            if not record:
                raise KeyError(object_id)
            return {
                "mode": "fixture",
                "synthetic": True,
                "warning": "This object is exposed only as synthetic inspection data; it is not published V&VN knowledge.",
                "retrieval_record": record,
                "internal_canonical_preview": self.semantic_by_id.get(object_id),
            }
        if object_id not in self.real_published_ids:
            raise PermissionError("object_not_published")
        env = next(e for e in self.published_envelopes if e.get("knowledge_object", {}).get("object_id") == object_id)
        return {"mode": "real", "synthetic": False, **env}

    def _enrich_results(self, result: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(result)
        out: list[dict[str, Any]] = []
        for item in result.get("results", []):
            record = self.record_by_object.get(item.get("object_id")) or {}
            md = record.get("metadata") or {}
            out.append({
                **item,
                "source_title": md.get("source_title"),
                "source_version": md.get("source_version"),
                "source_url": md.get("source_url"),
                "source_page": md.get("source_page"),
                "object_type": md.get("object_type", item.get("object_type")),
                "risk_level": md.get("risk_level"),
                "retrieval_text": record.get("retrieval_text"),
                "structured_logic": record.get("structured_logic"),
            })
        enriched["results"] = out
        enriched["mode"] = self.mode
        enriched["synthetic_fixture_mode"] = self.synthetic
        if self.synthetic:
            enriched["warning"] = "SYNTHETIC FIXTURE MODE - not published V&VN knowledge."
        return enriched

    def search(self, query: str, top_k: int) -> dict[str, Any]:
        return self._enrich_results(self.hybrid.search(query, top_k))

    def explain(self, query: str, top_k: int) -> dict[str, Any]:
        hybrid = self.hybrid.search(query, top_k)
        lexical = self.hybrid.lexical.search(query, max(top_k, self.hybrid_config.candidate_k))
        vector = self.hybrid.vector.search(query, max(top_k, self.hybrid_config.candidate_k))
        return {
            "service_version": SERVICE_VERSION,
            "mode": self.mode,
            "synthetic_fixture_mode": self.synthetic,
            "warning": "SYNTHETIC FIXTURE MODE - not published V&VN knowledge." if self.synthetic else None,
            "query": query,
            "policy": {
                "search_scope": "published_only" if not self.synthetic else "synthetic_fixture_only",
                "hybrid_fusion": "reciprocal_rank_fusion",
                "abstention": "child engines gate first; both abstain => hybrid abstains",
                "lexical_thresholds": {
                    "min_score": self.lexical_config.min_score,
                    "min_query_coverage": self.lexical_config.min_query_coverage,
                    "min_distinct_terms": self.lexical_config.min_distinct_terms,
                },
                "vector_threshold": self.vector_config.min_similarity,
            },
            "hybrid": self._enrich_results(hybrid),
            "lexical": lexical,
            "vector": vector,
        }


HTML = r'''<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>V&VN Data Services Inspector</title>
<style>
:root{font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1f2937;background:#f6f7f9}
body{margin:0}.wrap{max-width:1120px;margin:0 auto;padding:28px}.panel{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:20px;margin-bottom:16px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
h1{margin:0 0 6px;font-size:28px}h2{font-size:18px;margin:0 0 14px}.muted{color:#6b7280}.banner{border-radius:10px;padding:12px 14px;margin:16px 0;font-weight:650}.real{background:#ecfdf5;border:1px solid #a7f3d0}.fixture{background:#fff7ed;border:1px solid #fdba74}.blocked{background:#fef2f2;border:1px solid #fecaca}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.stat{padding:12px;background:#f9fafb;border-radius:8px}.stat b{display:block;font-size:20px;margin-top:4px}
.search{display:flex;gap:8px}input{flex:1;border:1px solid #d1d5db;border-radius:8px;padding:12px;font-size:16px}button{border:0;border-radius:8px;padding:10px 16px;background:#111827;color:white;font-weight:650;cursor:pointer}button.secondary{background:#e5e7eb;color:#111827}
.result{border-top:1px solid #e5e7eb;padding:14px 0}.result:first-child{border-top:0}.chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{font-size:12px;padding:3px 7px;border-radius:999px;background:#eef2ff}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;overflow-wrap:anywhere}.score{font-variant-numeric:tabular-nums}pre{background:#111827;color:#e5e7eb;padding:14px;border-radius:8px;overflow:auto;max-height:430px;white-space:pre-wrap}.hidden{display:none}a{color:#1d4ed8}
</style>
</head>
<body><div class="wrap">
<div class="panel"><h1>V&VN Data Services Inspector</h1><div class="muted">Read-only inspectie van publicatiestatus, retrieval en bronherleidbaarheid.</div><div id="modeBanner" class="banner">Status laden...</div><div id="stats" class="grid"></div></div>
<div class="panel"><h2>Retrieval testen</h2><div class="search"><input id="q" placeholder="Bijv. Wanneer wordt bij een cliënt van 60 jaar de risicofactorenscore gebruikt?"><button onclick="search(false)">Zoeken</button><button class="secondary" onclick="search(true)">Uitleg</button></div><div id="decision" style="margin-top:14px"></div><div id="results"></div><pre id="explain" class="hidden"></pre></div>
<div class="panel"><h2>Bronnen en documenten</h2><div id="docs"></div></div>
</div>
<script>
const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
async function boot(){
 const st=await (await fetch('/system/status')).json();
 const b=document.getElementById('modeBanner');
 b.className='banner '+(st.synthetic_fixture_mode?'fixture':(st.prepublication_gate==='BLOCKED'?'blocked':'real'));
 b.textContent=st.synthetic_fixture_mode?'SYNTHETIC FIXTURE MODE — testdata, geen gepubliceerde V&VN-kennis.':`REAL MODE — pre-publication gate: ${st.prepublication_gate}`;
 document.getElementById('stats').innerHTML=[['Semantische objecten',st.semantic_object_count],['Approved',st.approved_object_count],['Published',st.published_envelope_count],['Retrieval records',st.retrieval_record_count],['High-risk',st.high_risk_object_count],['Verified bronnen',st.verified_source_count]].map(x=>`<div class=stat>${esc(x[0])}<b>${esc(x[1])}</b></div>`).join('');
 const docs=await (await fetch('/documents')).json();
 document.getElementById('docs').innerHTML=docs.length?docs.map(d=>`<div class=result><b>${esc(d.title||d.document_id)}</b><div class=muted>${esc(d.version||'')} · ${d.object_count} objecten · ${d.approved_count} approved · ${d.published_count} published</div><div class=mono>${esc(d.document_id)}</div></div>`).join(''):'Geen documenten.';
}
async function search(explain){
 const q=document.getElementById('q').value.trim(); if(!q)return;
 const endpoint=explain?'/retrieval/explain':'/search';
 const data=await (await fetch(endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({query:q,top_k:5})})).json();
 const main=explain?data.hybrid:data;
 document.getElementById('decision').innerHTML=`<b>${esc((main.behavior||'').toUpperCase())}</b> — ${esc(main.reason||'')}`;
 document.getElementById('results').innerHTML=(main.results||[]).map(r=>`<div class=result><b>${esc(r.source_title||r.object_id)}</b><div class=chips><span class=chip>${esc(r.object_type)}</span><span class=chip>pagina ${esc(r.source_page??'—')}</span><span class=chip>versie ${esc(r.source_version||r.object_version)}</span><span class=chip>risk ${esc(r.risk_level||'—')}</span></div><div class=mono>${esc(r.object_id)}</div><div class=score>RRF ${esc(r.rrf_score)} · lexical ${esc(r.lexical_score??'—')} · vector ${esc(r.vector_score??'—')}</div><p>${esc(r.retrieval_text||'')}</p>${r.source_url?`<a href="${esc(r.source_url)}" target=_blank rel=noopener>Bron openen</a>`:''}</div>`).join('');
 const pre=document.getElementById('explain');
 if(explain){pre.classList.remove('hidden');pre.textContent=JSON.stringify(data,null,2)}else{pre.classList.add('hidden');pre.textContent=''}
}
boot();
</script></body></html>'''


def create_app(mode: Literal["real", "fixture"] | None = None, *, paths: ServicePaths | None = None) -> FastAPI:
    selected = mode or os.getenv("VVN_SERVICE_MODE", "real").strip().lower()
    if selected not in {"real", "fixture"}:
        raise ValueError("VVN_SERVICE_MODE must be 'real' or 'fixture'")
    state = InspectionState(selected, paths or ServicePaths.defaults())
    app = FastAPI(
        title="V&VN Data Services Inspection API",
        version=SERVICE_VERSION,
        description="Read-only local inspection layer. REAL mode searches published objects only.",
    )
    app.state.inspection = state

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def ui() -> str:
        return HTML

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service_version": SERVICE_VERSION, "mode": state.mode, "synthetic_fixture_mode": state.synthetic}

    @app.get("/system/status")
    def system_status() -> dict[str, Any]:
        return state.status()

    @app.get("/sources")
    def sources() -> dict[str, Any]:
        return state.sources()

    @app.get("/documents")
    def documents() -> list[dict[str, Any]]:
        return state.documents()

    @app.get("/releases")
    def releases() -> list[dict[str, Any]]:
        return state.releases()

    @app.get("/knowledge/{object_id}")
    def knowledge(object_id: str) -> dict[str, Any]:
        try:
            return state.knowledge(object_id)
        except PermissionError:
            raise HTTPException(status_code=404, detail="object_not_published") from None
        except KeyError:
            raise HTTPException(status_code=404, detail="object_not_found") from None

    @app.post("/search")
    def search(req: SearchRequest) -> dict[str, Any]:
        return state.search(req.query, req.top_k)

    @app.post("/retrieval/explain")
    def explain(req: SearchRequest) -> dict[str, Any]:
        return state.explain(req.query, req.top_k)

    return app


app = create_app()
