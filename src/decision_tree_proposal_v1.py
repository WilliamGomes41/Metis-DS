"""Versioned semantic proposal for a decision tree; never candidate authority.

A proposal names exact source selections under temporary references, proposed
roles, connections between those references, literal label selections, context
bindings, result bundles and explicit uncertainty. It assigns no object
identity and carries no canonical text: quoted text is only a claim that the
deterministic materialiser verifies against the frozen source.

Three checks stay separate:

1. ``validate_proposal`` enforces the closed shape (fail closed as a whole);
2. ``relation_findings`` checks that cited source evidence is attached to the
   proposed relation itself (findings, never confirmation);
3. a named reviewer confirms the interpretation in the existing graph review.
"""
from __future__ import annotations

import re
from typing import Any

CONTRACT = "decision-tree-proposal-v1"
ROLES = ("start", "question", "action", "outcome", "context")
SELECTIONS = ("single", "multiple")
CONNECTION_KINDS = ("answer", "continue", "page_transition")
UNRESOLVED_CODES = (
    "role_ambiguous",
    "route_ambiguous",
    "target_unknown",
    "label_ambiguous",
    "direction_unverified",
    "evidence_missing",
)
MAX_UNITS = 512
MAX_CONNECTIONS = 2048
_REF = re.compile(r"[a-z][a-z0-9_-]{0,39}")

_TOP = {"contract", "units", "connections", "context_bindings", "result_bundles", "unresolved"}
_UNIT = {"ref", "role", "selection", "entry", "spans", "quoted_text"}
_SPAN = {"block_id", "start", "end"}
_CONNECTION = {"ref", "from", "to", "kind", "label_span", "evidence_ids"}
_BINDING = {"ref", "context", "applies_to"}
_BUNDLE = {"ref", "container", "members"}
_UNRESOLVED = {"ref", "subject", "code"}


class DecisionTreeProposalError(ValueError):
    """Closed proposal rejection with one stable reason code."""

    def __init__(self, code: str, **details: Any) -> None:
        self.code = code
        self.finding = {"reason_code": code, **details}
        super().__init__(code)


def _fail(code: str, **details: Any) -> None:
    raise DecisionTreeProposalError(code, **details)


def _exact_keys(row: Any, keys: set[str], code: str) -> None:
    if not isinstance(row, dict) or set(row) != keys:
        _fail(code)


def _ref(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _REF.fullmatch(value):
        _fail(code)
    return value


def _span(span: Any, blocks: dict[str, dict[str, Any]]) -> None:
    _exact_keys(span, _SPAN, "decision_proposal_span_invalid")
    block = blocks.get(span["block_id"]) if isinstance(span["block_id"], str) else None
    start, end = span["start"], span["end"]
    if block is None:
        _fail("decision_proposal_unknown_block")
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(block["text"]):
        _fail("decision_proposal_span_invalid")


def proposal_schema() -> dict[str, Any]:
    """Strict provider schema; every field required, absence is an explicit null."""
    span = {"type": "object", "additionalProperties": False, "required": sorted(_SPAN),
            "properties": {"block_id": {"type": "string"}, "start": {"type": "integer"},
                           "end": {"type": "integer"}}}
    refs = {"type": "array", "items": {"type": "string"}}
    return {"type": "object", "additionalProperties": False, "required": sorted(_TOP), "properties": {
        "contract": {"type": "string", "enum": [CONTRACT]},
        "units": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": sorted(_UNIT), "properties": {
                "ref": {"type": "string"}, "role": {"type": "string", "enum": list(ROLES)},
                "selection": {"type": ["string", "null"], "enum": [*SELECTIONS, None]},
                "entry": {"type": "boolean"}, "spans": {"type": "array", "items": span},
                "quoted_text": {"type": "string"}}}},
        "connections": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": sorted(_CONNECTION), "properties": {
                "ref": {"type": "string"}, "from": {"type": "string"}, "to": {"type": ["string", "null"]},
                "kind": {"type": "string", "enum": list(CONNECTION_KINDS)},
                "label_span": {"anyOf": [span, {"type": "null"}]}, "evidence_ids": refs}}},
        "context_bindings": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": sorted(_BINDING), "properties": {
                "ref": {"type": "string"}, "context": {"type": "string"}, "applies_to": refs}}},
        "result_bundles": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": sorted(_BUNDLE), "properties": {
                "ref": {"type": "string"}, "container": {"type": "string"}, "members": refs}}},
        "unresolved": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": sorted(_UNRESOLVED), "properties": {
                "ref": {"type": "string"}, "subject": {"type": ["string", "null"]},
                "code": {"type": "string", "enum": list(UNRESOLVED_CODES)}}}},
    }}


def validate_proposal(proposal: Any, *, blocks: list[dict[str, Any]],
                      inventory: dict[str, Any]) -> dict[str, Any]:
    """Validate shape and references only; no text, identity or route is decided here."""
    _exact_keys(proposal, _TOP, "decision_proposal_shape_invalid")
    if proposal["contract"] != CONTRACT:
        _fail("decision_proposal_contract_unsupported")
    for key in _TOP - {"contract"}:
        if not isinstance(proposal[key], list):
            _fail("decision_proposal_shape_invalid")
    by_block = {b["block_id"]: b for b in blocks}
    evidence = inventory.get("items") or {}
    if not proposal["units"] or len(proposal["units"]) > MAX_UNITS or len(proposal["connections"]) > MAX_CONNECTIONS:
        _fail("decision_proposal_size_invalid")
    refs: set[str] = set()

    def fresh(value: Any) -> str:
        ref = _ref(value, "decision_proposal_ref_invalid")
        if ref in refs:
            _fail("decision_proposal_ref_duplicate", ref=ref)
        refs.add(ref)
        return ref

    units: dict[str, dict[str, Any]] = {}
    for unit in proposal["units"]:
        _exact_keys(unit, _UNIT, "decision_proposal_unit_invalid")
        ref = fresh(unit["ref"])
        if unit["role"] not in ROLES or type(unit["entry"]) is not bool:
            _fail("decision_proposal_unit_invalid", ref=ref)
        if (unit["role"] == "question") != (unit["selection"] in SELECTIONS) or (
                unit["role"] != "question" and unit["selection"] is not None):
            _fail("decision_proposal_selection_invalid", ref=ref)
        if not isinstance(unit["spans"], list) or not unit["spans"]:
            _fail("decision_proposal_span_invalid", ref=ref)
        for span in unit["spans"]:
            _span(span, by_block)
        if not isinstance(unit["quoted_text"], str) or not unit["quoted_text"].strip():
            _fail("decision_proposal_unit_invalid", ref=ref)
        units[ref] = unit
    for row in proposal["connections"]:
        _exact_keys(row, _CONNECTION, "decision_proposal_connection_invalid")
        ref = fresh(row["ref"])
        if row["from"] not in units or (row["to"] is not None and row["to"] not in units):
            _fail("decision_proposal_endpoint_unknown", ref=ref)
        if row["kind"] not in CONNECTION_KINDS:
            _fail("decision_proposal_connection_invalid", ref=ref)
        if (row["kind"] == "answer") != (row["label_span"] is not None):
            _fail("decision_proposal_label_invalid", ref=ref)
        if row["label_span"] is not None:
            _span(row["label_span"], by_block)
        ids = row["evidence_ids"]
        if not isinstance(ids, list) or len(set(map(str, ids))) != len(ids) or any(
                not isinstance(i, str) or i not in evidence for i in ids):
            _fail("decision_proposal_evidence_unknown", ref=ref)
    for row in proposal["context_bindings"]:
        _exact_keys(row, _BINDING, "decision_proposal_binding_invalid")
        ref = fresh(row["ref"])
        targets = row["applies_to"]
        if (units.get(row["context"], {}).get("role") != "context" or not isinstance(targets, list) or not targets
                or len(set(targets)) != len(targets)
                or any(t not in units or units[t]["role"] == "context" for t in targets)):
            _fail("decision_proposal_binding_invalid", ref=ref)
    for row in proposal["result_bundles"]:
        _exact_keys(row, _BUNDLE, "decision_proposal_bundle_invalid")
        ref = fresh(row["ref"])
        members = row["members"]
        if (row["container"] not in units or not isinstance(members, list) or not members
                or len(set(members)) != len(members) or row["container"] in members
                or any(m not in units for m in members)):
            _fail("decision_proposal_bundle_invalid", ref=ref)
    for row in proposal["unresolved"]:
        _exact_keys(row, _UNRESOLVED, "decision_proposal_unresolved_invalid")
        fresh(row["ref"])
        if row["code"] not in UNRESOLVED_CODES or (row["subject"] is not None and row["subject"] not in refs):
            _fail("decision_proposal_unresolved_invalid", ref=row["ref"])
    return proposal


def relation_findings(connection: dict[str, Any], *, endpoint_fragments: dict[str, list[dict[str, Any]]],
                      label_fragment_ids: list[str], label_text: str | None,
                      inventory: dict[str, Any], geometric: list[dict[str, Any]],
                      fragments_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Check that cited evidence supports this relation; an empty list confirms nothing.

    ``geometric`` are the existing bounded route proposals between the same
    temporary references (``pdf_route_proposals_v1``), reused as evidence only.
    """
    items = inventory.get("items") or {}
    ids = connection["evidence_ids"]
    kinds = {items[i]["kind"] for i in ids}
    source, target = connection["from"], connection["to"]
    findings: list[str] = []
    if target is None:
        return ["target_unknown"]
    if connection["kind"] == "answer":
        if not label_text or not set(label_fragment_ids) <= set(ids) or not any(
                items[i].get("text") == label_text for i in label_fragment_ids):
            findings.append("label_not_bound_to_relation")
    if connection["kind"] == "page_transition":
        pages = {ref: {f.get("source_page") for f in endpoint_fragments[ref]} for ref in (source, target)}
        texts = [i for i in ids if items[i]["kind"] == "text"]
        target_pages = {str(p) for p in pages[target] if p is not None}
        if (len(pages[source]) != 1 or pages[source] == pages[target] or not texts or not any(
                (fragments_by_id.get(i) or {}).get("source_page") in pages[source]
                and target_pages & set(re.findall(r"\d+", str(items[i].get("text") or ""))) for i in texts)):
            findings.append("page_transition_unverified")
        return findings
    if "export_edge" in kinds:
        boom = {ref: {str(f.get("boom_id")) for f in endpoint_fragments[ref]} for ref in (source, target)}
        if not any(items[i]["kind"] == "export_edge"
                   and str(items[i]["record"].get("from")) in boom[source]
                   and str(items[i]["record"].get("to")) in boom[target]
                   and (connection["kind"] != "answer" or items[i]["record"].get("label") == label_text)
                   for i in ids):
            findings.append("export_relation_not_bound_to_endpoints")
        return findings
    if "graphic" not in kinds:
        return [*findings, "relation_evidence_missing"]
    cited = {i for i in ids if items[i]["kind"] == "graphic"}
    if connection["kind"] == "answer" and not _label_on_route(
            [fragments_by_id.get(i) or {} for i in label_fragment_ids], [items[i] for i in cited],
            endpoint_fragments[source], endpoint_fragments[target]):
        findings.append("label_not_on_route")
    matches = [p for p in geometric if {p["from"], p["to"]} == {source, target}
               and cited & set(p["evidence_ids"])]
    if not matches:
        findings.append("graphic_not_bound_to_endpoints")
    elif all("direction_unverified" in p["uncertainties"] for p in matches):
        findings.append("direction_unverified")
    elif not any(p["from"] == source and p["to"] == target for p in matches
                 if "direction_unverified" not in p["uncertainties"]):
        findings.append("direction_conflict")
    return findings



LABEL_DISTANCE = 18  # Same bounds as the existing geometric route proposal.
ANCHOR_DISTANCE = 35
VERTEX_TOLERANCE = 2


def _rect_distance(point, box) -> float:
    from math import hypot
    x, y = point
    return hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - y, 0, y - box[3]))


def _label_on_route(labels: list[dict[str, Any]], graphics: list[dict[str, Any]],
                    source: list[dict[str, Any]], target: list[dict[str, Any]]) -> bool:
    """A literal label lies on a connected line touching both endpoints; nearness is not meaning."""
    from math import hypot
    from src.pdf_route_proposals_v1 import _bezier, _point_segment_distance
    if not labels:
        return False
    for label in labels:
        box = label.get("bbox")
        if not box or len(box) != 4:
            return False
        page = label.get("source_page")
        segments = []
        for item in graphics:
            if item.get("page") != page:
                continue
            segments.extend(tuple(map(tuple, seg)) for seg in item.get("segments", []))
            for curve in item.get("curves", []):
                sampled = [tuple(_bezier(curve, i / 8)) for i in range(9)]
                segments.extend(zip(sampled, sampled[1:]))
        points: list[tuple] = []
        parent: list[int] = []

        def vertex(point):
            for index, prior in enumerate(points):
                if hypot(point[0] - prior[0], point[1] - prior[1]) <= VERTEX_TOLERANCE:
                    return index
            points.append(point)
            parent.append(len(parent))
            return len(points) - 1

        def root(index):
            while parent[index] != index:
                index = parent[index]
            return index
        ends = [(vertex(a), vertex(b)) for a, b in segments]
        for a, b in ends:
            parent[root(a)] = root(b)
        boxes = {side: [f["bbox"] for f in rows if f.get("bbox") and f.get("source_page") == page]
                 for side, rows in (("source", source), ("target", target))}

        def touches(component, side):
            return any(root(i) == component and _rect_distance(points[i], b) <= ANCHOR_DISTANCE
                       for i in range(len(points)) for b in boxes[side])
        corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
        if not any(touches(root(a), "source") and touches(root(a), "target")
                   and any(_point_segment_distance(p, seg[0], seg[1]) <= LABEL_DISTANCE for p in corners)
                   for seg, (a, _b) in zip(segments, ends)):
            return False
    return True
