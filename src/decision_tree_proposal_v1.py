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
        ids = row["evidence_ids"]
        if not isinstance(ids, list) or len(set(map(str, ids))) != len(ids) or any(
                not isinstance(i, str) or i not in evidence for i in ids):
            _fail("decision_proposal_evidence_unknown", ref=ref)
        # An answer label is literal source text: a selected span, or the label
        # of an explicit export relation that the connection cites.
        exported = any(evidence[i].get("kind") == "export_edge" for i in ids)
        if row["label_span"] is not None:
            if row["kind"] != "answer":
                _fail("decision_proposal_label_invalid", ref=ref)
            _span(row["label_span"], by_block)
        elif row["kind"] == "answer" and not exported:
            _fail("decision_proposal_label_invalid", ref=ref)
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
                      inventory: dict[str, Any],
                      fragments_by_id: dict[str, dict[str, Any]]) -> list[str]:
    """Check that cited evidence supports this relation; an empty list confirms nothing."""
    items = inventory.get("items") or {}
    ids = connection["evidence_ids"]
    kinds = {items[i]["kind"] for i in ids}
    source, target = connection["from"], connection["to"]
    findings: list[str] = []
    if target is None:
        return ["target_unknown"]
    if connection["kind"] == "answer" and "export_edge" not in kinds:
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
    routes = _Routes([items[i] for i in ids if items[i]["kind"] == "graphic"])
    joining = routes.joining(endpoint_fragments[source], endpoint_fragments[target])
    if not joining:
        return [*findings, "graphic_not_bound_to_endpoints"]
    if connection["kind"] == "answer" and not routes.labelled(
            joining, [fragments_by_id.get(i) or {} for i in label_fragment_ids]):
        findings.append("label_not_on_route")
    tips = routes.tips(joining)
    at_target = routes.touching(tips, endpoint_fragments[target])
    at_source = routes.touching(tips, endpoint_fragments[source])
    if at_source and not at_target:
        findings.append("direction_conflict")
    elif at_target == at_source:
        findings.append("direction_unverified")
    return findings


LABEL_DISTANCE = 18
ANCHOR_DISTANCE = 35
VERTEX_TOLERANCE = 2
WING_MIN, WING_MAX = 2, 15


def _bezier(points, t):
    return [sum(weight * point[axis] for weight, point in zip(
        ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3), points)) for axis in (0, 1)]


def _point_segment_distance(point, a, b) -> float:
    from math import hypot
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0
    return hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def _rect_distance(point, box) -> float:
    from math import hypot
    x, y = point
    return hypot(max(box[0] - x, 0, x - box[2]), max(box[1] - y, 0, y - box[3]))


class _Routes:
    """Connected line components of the cited drawings only; geometry is evidence, not meaning."""

    def __init__(self, graphics: list[dict[str, Any]]) -> None:
        from math import hypot
        self.points: list[tuple[float, float, Any]] = []
        self.parent: list[int] = []
        self.adjacent: dict[int, set[int]] = {}
        self.segments: list[tuple[int, int]] = []
        for item in graphics:
            page = item.get("page")
            lines = [tuple(map(tuple, seg)) for seg in item.get("segments", [])]
            for curve in item.get("curves", []):
                sampled = [tuple(_bezier(curve, i / 8)) for i in range(9)]
                lines.extend(zip(sampled, sampled[1:]))
            for a, b in lines:
                left, right = self._vertex(a, page, hypot), self._vertex(b, page, hypot)
                if left != right:
                    self.segments.append((left, right))
                    self.adjacent[left].add(right)
                    self.adjacent[right].add(left)
                    self.parent[self._root(left)] = self._root(right)

    def _vertex(self, point, page, hypot) -> int:
        for index, (x, y, p) in enumerate(self.points):
            if p == page and hypot(point[0] - x, point[1] - y) <= VERTEX_TOLERANCE:
                return index
        self.points.append((point[0], point[1], page))
        self.parent.append(len(self.parent))
        self.adjacent[len(self.points) - 1] = set()
        return len(self.points) - 1

    def _root(self, index: int) -> int:
        while self.parent[index] != index:
            index = self.parent[index]
        return index

    def touching(self, vertices, fragments) -> set[int]:
        boxes = [(f["bbox"], f.get("source_page")) for f in fragments if f.get("bbox")]
        return {v for v in vertices for box, page in boxes
                if self.points[v][2] == page and _rect_distance(self.points[v][:2], box) <= ANCHOR_DISTANCE}

    def joining(self, source, target) -> set[int]:
        """Vertices of components that touch both endpoints."""
        everything = range(len(self.points))
        roots = ({self._root(v) for v in self.touching(everything, source)}
                 & {self._root(v) for v in self.touching(everything, target)})
        return {v for v in everything if self._root(v) in roots}

    def labelled(self, component: set[int], labels: list[dict[str, Any]]) -> bool:
        if not labels:
            return False
        for label in labels:
            box = label.get("bbox")
            if not box or len(box) != 4:
                return False
            corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
            if not any(a in component and self.points[a][2] == label.get("source_page")
                       and _point_segment_distance(p, self.points[a][:2], self.points[b][:2]) <= LABEL_DISTANCE
                       for a, b in self.segments for p in corners):
                return False
        return True

    def tips(self, component: set[int]) -> set[int]:
        """Arrow tips: two short symmetric wings beside one shaft."""
        from math import hypot
        found = set()
        for v in component:
            x, y, _ = self.points[v]
            short = [n for n in self.adjacent[v] if len(self.adjacent[n]) == 1
                     and WING_MIN <= hypot(self.points[n][0] - x, self.points[n][1] - y) <= WING_MAX]
            shaft = [n for n in self.adjacent[v] if n not in short]
            if len(short) != 2 or len(shaft) != 1:
                continue
            axis = [self.points[shaft[0]][j] - self.points[v][j] for j in (0, 1)]
            wings = [[self.points[n][j] - self.points[v][j] for j in (0, 1)] for n in short]
            cross = [axis[0] * w[1] - axis[1] * w[0] for w in wings]
            if cross[0] * cross[1] < 0 and all(axis[0] * w[0] + axis[1] * w[1] > 0 for w in wings):
                found.add(v)
        return found
