"""Versioned, pure measurements over committed workflow evidence.

No model calls, canonical writes or inferred clinical correctness. The input is
an authorized, frozen document cohort. Activity and current inventory are
separate: cohort filters are not event-time filters.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from src.integrity_kernel import stable_hash
from src.quality_evidence_v1 import RUNS, VERSION, route_of
from src.review_interaction_v1 import review_burden_projection
from src.review_disposition_v1 import definitive_review_disposition
from src.review_duty_v1 import review_stage, authoritative_review_type
from src.beslisboom_path_v1 import review_path_for_klasse

DEFINITION_VERSION = "quality-workprocess-v1.0.0"
ROUTES = ("deterministic", "semantic", "remainder", "unknown")
DEFINITIONS = {
    "direct": "Eerste inhoudelijke besluiten over oorspronkelijke kandidaten; uitstel en structuur uitgesloten. Onbekende vergelijking is geen succes.",
    "interactions": "Unieke opgeslagen beslisinteracties; batchleden tellen afzonderlijk als objectbesluiten. Geen werktijdmeting.",
    "repairs": "Expliciet opgeslagen correcties; herstelverzoeken worden afzonderlijk geteld. Geen veronderstelde afstamming.",
    "open": "Huidige onafgehandelde bronpassages binnen het ingestcohort. Geen historische werkvoorraad.",
    "duration": "Ingest tot vastgelegde publicatie; gereedheid wordt alleen als eerste waarneming gerapporteerd.",
    "problems": "Ontdekte, expliciet geregistreerde inhoudelijke problemen; geen maat voor alle aanwezige fouten.",
}


def parse_time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def coverage(known: int, total: int) -> str:
    return "not_measurable" if not total or not known else "measurable" if known == total else "partial"


def document_route(envelope: dict[str, Any], objects: list[dict[str, Any]]) -> str:
    runs = envelope.get(RUNS) or []
    if runs and runs[-1].get("outcome") == "succeeded":
        origins = [r["origin"]["route"] for r in runs[-1].get("candidates", []) if not r.get("structural")]
    else:
        origins = [route_of(o)["route"] for o in objects
                   if o.get("object_type") not in {"document", "heading", "path"}]
    kinds = set(origins)
    return next(iter(kinds)) if len(kinds) == 1 else "mixed" if kinds else "unknown"


def select_cohort(documents: list[dict[str, Any]], filters: dict[str, str]) -> list[dict[str, Any]]:
    selected = []
    for doc in documents:
        env = doc["envelope"]
        timestamp = parse_time(env.get("acquired_at"))
        if filters.get("from") and (timestamp is None or timestamp.date().isoformat() < filters["from"]):
            continue
        if filters.get("to") and (timestamp is None or timestamp.date().isoformat() > filters["to"]):
            continue
        if filters.get("kind") and env.get("content_kind") != filters["kind"]:
            continue
        if filters.get("ingest") and env.get("ingest_kind") != filters["ingest"]:
            continue
        if filters.get("route") and document_route(env, doc["objects"]) != filters["route"]:
            continue
        selected.append(doc)
    return selected


def build_report(documents: list[dict[str, Any]], *, as_of: str,
                 filters: dict[str, str] | None = None) -> dict[str, Any]:
    filters = filters or {}
    cohort = select_cohort(documents, filters)
    events = []
    seen = set()
    first = {}
    per_route = {route: {"first_decisions": 0, "known_comparisons": 0, "direct": 0,
                         "repair_requests": 0, "rejections": 0, "corrections": 0, "corrections_after_approval": 0, "changed_fields": Counter()} for route in ROUTES}
    details = []
    publications = []
    pending_age = []
    pending_total = 0
    correction_unknown = 0
    processing = Counter()
    versions = {}
    for doc in cohort:
        env, objects = doc["envelope"], doc["objects"]
        sid = env["snapshot_id"]
        rows = []
        for event in doc["events"]:
            identity = event.get("event_hash") or stable_hash(event)
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(event)
            events.append(event)
        run_by_id = {r["run_id"]: r for r in env.get(RUNS) or []}
        candidate_keys = {(r["run_id"], c["object_id"]): c for r in run_by_id.values() for c in r.get("candidates", [])}
        for run in run_by_id.values():
            processing[run.get("outcome", "unknown")] += 1
            identity = run.get("semantic_identity") or {}
            if identity.get("hash"):
                versions[identity["hash"]] = identity.get("components", {})
        published = False
        approved_ids = set()
        for event in rows:
            kind = str(event.get("event_type") or "")
            payload = event.get("details") or {}
            evidence = payload.get("quality_evidence") or {}
            valid = (evidence.get("version") == VERSION and
                     (evidence.get("run_id"), event.get("object_id")) in candidate_keys and
                     evidence.get("after_version") == event.get("object_version") and
                     evidence.get("origin") == candidate_keys.get((evidence.get("run_id"), event.get("object_id")), {}).get("origin"))
            origin = (evidence.get("origin") or {}).get("route") if valid else "unknown"
            route = origin if origin in ROUTES else "unknown"
            if kind == "quality_object_corrected":
                per_route[route]["corrections"] += 1
                per_route[route]["corrections_after_approval"] += int(event.get("object_id") in approved_ids)
                if valid:
                    per_route[route]["changed_fields"].update(evidence.get("changed_fields") or [])
                continue
            if kind == "revision_created":
                correction_unknown += 1
            if kind == "release_published" and not published:
                begin, end = parse_time(env.get("acquired_at")), parse_time(event.get("occurred_at"))
                if begin and end and end >= begin:
                    publications.append((end - begin).total_seconds())
                    published = True
            if kind.endswith(("_review_approve", "_review_revise", "_review_reject")) and kind != "second_review_approve":
                interaction = payload.get("review_interaction") or {}
                if evidence.get("structural") or interaction.get("interaction_kind") == "structure":
                    continue
                if kind.endswith("_approve"):
                    approved_ids.add(event.get("object_id"))
                if kind.endswith("_reject"):
                    per_route[route]["rejections"] += 1
                if kind.endswith("_revise"):
                    per_route[route]["repair_requests"] += 1
                key = (sid, evidence.get("run_id") if valid else "unknown", event.get("object_id"))
                if key in first:
                    continue
                first[key] = True
                metric = per_route[route]
                metric["first_decisions"] += 1
                # A rejected/revise proposal is known not to be directly usable.
                known = not kind.endswith("_approve") or (valid and evidence.get("unchanged_proposal") is not None)
                metric["known_comparisons"] += int(known)
                metric["direct"] += int(kind.endswith("_approve") and valid and evidence.get("unchanged_proposal") is True)
                if valid:
                    metric["changed_fields"].update(evidence.get("changed_fields") or [])
        dispositions = Counter()
        open_ids = []
        for obj in objects:
            if obj.get("object_type") == "document":
                continue
            disposition = (obj.get("metadata") or {}).get("passage_register") or obj.get("passage_register") or {}
            dispositions[disposition.get("status", "unknown")] += 1
            if authoritative_review_type(obj) in {"heading", "path"}:
                continue
            stage = review_stage(obj, review_path=review_path_for_klasse(env.get("class", "richtlijn")), bindings=doc.get("bindings"), fragments=doc.get("fragments"))
            disposition_state = definitive_review_disposition(obj)
            pending_approval = (disposition_state["register_status"] == "selected_as_candidate"
                                and disposition_state["review_status"] == "approved" and stage is not None)
            if not disposition_state["final"] or pending_approval:
                open_ids.append(obj.get("object_id"))
        pending_total += len(open_ids)
        acquired, now = parse_time(env.get("acquired_at")), parse_time(as_of)
        # This is age of an unfinished source, not invented task-creation time.
        age = (now - acquired).total_seconds() / 86400 if open_ids and now and acquired and now >= acquired else None
        if age is not None:
            pending_age.append(age)
        burden = review_burden_projection(rows)
        details.append({"snapshot_id": sid, "title": env.get("title", sid),
                        "source_hash": env.get("sha256"), "kind": env.get("content_kind"),
                        "ingest_kind": env.get("ingest_kind"), "route": document_route(env, objects),
                        "object_count": sum(o.get("object_type") != "document" for o in objects),
                        "high_risk_objects": sum(bool((o.get("risk") or {}).get("requires_second_review")) for o in objects),
                        "open_passages": len(open_ids), "source_age_days": age,
                        "dispositions": dict(dispositions),
                        "interactions": burden["review_interactions"], "object_decisions": burden["object_decisions"],
                        "run_count": len(run_by_id), "ready_observed": doc.get("ready_observed"),
                        "processing_blocker": env.get("processing_blocker")})
    burden = review_burden_projection(events)
    # No reviewer identifiers or per-person rankings in the report.
    burden.pop("interactions", None)
    for row in per_route.values():
        row["changed_fields"] = dict(row["changed_fields"])
        row["coverage"] = coverage(row["known_comparisons"], row["first_decisions"])
        row["direct_rate"] = row["direct"] / row["first_decisions"] if row["coverage"] == "measurable" else None
    durations = sorted(publications)
    return {"definition_version": DEFINITION_VERSION, "definitions": DEFINITIONS,
            "as_of": as_of, "filters": filters, "scope": [d["snapshot_id"] for d in details],
            "cohort_size": len(details), "source_count_before_filters": len(documents),
            "routes": per_route, "burden": burden, "documents": details,
            "processing_runs": dict(processing), "semantic_configurations": list(versions.values()),
            "open_passages": pending_total,
            "oldest_unfinished_source_days": max(pending_age) if pending_age else None,
            "publication_duration_seconds": {"samples": len(durations),
                "median": ((durations[(len(durations)-1)//2] + durations[len(durations)//2]) / 2) if durations else None,
                "p90": durations[max(0, (9 * len(durations) + 9)//10 - 1)] if durations else None},
            "readiness_duration": {"coverage": "not_measurable", "reason": "Exact overgangstijdstip naar publicatiegereed ontbreekt; deze doorlooptijd is niet meetbaar."},
            "clinical_errors": {"coverage": "not_measurable", "reason": "Reviewafwijzing is geen bewezen klinische fout; bestaande redenen zijn niet uniform gecodeerd."},
            "limitations": ["Vergelijking betreft een ingestcohort; gebeurtenissen beslaan het werk aan deze bronnen tot de gegevensgrens.",
                "Open werk is een momentopname. Ouderdom betreft de bron, niet het ontstaan van een individuele taak.",
                "Veldverschillen tellen per vastgelegd besluit of correctie; dit is geen telling van unieke inhoudelijke fouten.",
                "Onbekende herkomst/vergelijking blijft zichtbaar. Geen werktijdmeting of bewijs van klinische correctheid.",
                "Gemengde bronnen worden niet volledig aan één route toegeschreven. Verschillen bewijzen geen causaliteit.",
                "Afstamming bij splitsen/samenvoegen wordt niet geraden; niet-gekoppelde besluiten blijven onbekend."],
            "legacy_revision_events": correction_unknown}
