"""Bounded geometric proposals, never authority for PDF route interpretation."""
from __future__ import annotations

from collections import deque
from math import hypot
from typing import Any


def propose_routes(fragments: list[dict[str, Any]], objects: list[dict[str, Any]],
                   inventory: dict[str, Any]) -> list[dict[str, Any]]:
    object_for = {r["raw_object_id"]: o["object_id"] for o in objects if o["object_type"] != "document"
                  for r in o["provenance"]["source_fragments"]}
    proposals = []
    for page in sorted({f["source_page"] for f in fragments}):
        texts = [f for f in fragments if f["source_page"] == page and f["fragment_id"] in object_for
                 and f.get("bundle_role") != "member"]
        segments = [(a, b, eid) for eid, e in inventory["items"].items()
                    if e["kind"] == "graphic" and e["page"] == page for a, b in e["segments"]]
        for eid, e in inventory["items"].items():
            if e["kind"] == "graphic" and e["page"] == page:
                for curve in e.get("curves", []):
                    sampled = [_bezier(curve, i / 8) for i in range(9)]
                    segments.extend((a, b, eid) for a, b in zip(sampled, sampled[1:]))
        # Complex pages remain manual; avoid unbounded graph/path enumeration.
        if len(segments) > 2000:
            continue
        points, adjacency = [], {}
        def vertex(point):
            for i, prior in enumerate(points):
                if hypot(point[0] - prior[0], point[1] - prior[1]) <= 2:
                    return i
            points.append(point)
            adjacency[len(points) - 1] = {}
            return len(points) - 1
        for a, b, eid in segments:
            left, right = vertex(a), vertex(b)
            if left != right:
                adjacency[left].setdefault(right, set()).add(eid)
                adjacency[right].setdefault(left, set()).add(eid)
        tips, wings = set(), set()
        for v, neighbors in adjacency.items():
            short = [n for n in neighbors if len(adjacency[n]) == 1 and
                     2 <= hypot(points[v][0] - points[n][0], points[v][1] - points[n][1]) <= 15]
            long = [n for n in neighbors if n not in short]
            if len(short) == 2 and len(long) == 1:
                shaft = [points[long[0]][j] - points[v][j] for j in (0, 1)]
                vectors = [[points[n][j] - points[v][j] for j in (0, 1)] for n in short]
                cross = [shaft[0] * w[1] - shaft[1] * w[0] for w in vectors]
                if cross[0] * cross[1] < 0 and all(sum(shaft[j] * w[j] for j in (0, 1)) > 0 for w in vectors):
                    tips.add(v)
                    wings.update(short)
        anchors = {}
        for v, neighbors in adjacency.items():
            if v in wings or len([n for n in neighbors if n not in wings]) != 1:
                continue
            x, y = points[v]
            distances = sorted((hypot(max(f["bbox"][0] - x, 0, x - f["bbox"][2]),
                                      max(f["bbox"][1] - y, 0, y - f["bbox"][3])), f["fragment_id"])
                               for f in texts)
            if distances and distances[0][0] <= 35:
                anchors[v] = (distances[0][1], len(distances) > 1 and distances[1][0] - distances[0][0] < 6)
        if len(anchors) > 100:
            continue
        pairs = set()
        for start in anchors:
            pending, seen = deque([(start, [], set())]), {start}
            while pending:
                v, path, evidence = pending.popleft()
                if v != start and v in anchors:
                    evidence |= set().union(*(adjacency[v][w] for w in adjacency[v] if w in wings))
                    pair = tuple(sorted((start, v)))
                    if pair in pairs or anchors[start][0] == anchors[v][0]:
                        continue
                    pairs.add(pair)
                    uncertainties = ["human_route_confirmation_required"]
                    if any(inventory["items"][eid].get("curves") for eid in evidence):
                        uncertainties.append("curved_path_approximation")
                    src, dst = start, v
                    if (start in tips) != (v in tips):
                        if start in tips:
                            src, dst = v, start
                    else:
                        src, dst = sorted((start, v), key=lambda n: (points[n][1], points[n][0]))
                        uncertainties.append("direction_unverified")
                    if anchors[start][1] or anchors[v][1]:
                        uncertainties.append("endpoint_ambiguous")
                    endpoint_ids = {anchors[start][0], anchors[v][0]}
                    labels = []
                    for f in texts:
                        if f["fragment_id"] in endpoint_ids or len(f["clean_text"]) > 60:
                            continue
                        box = f["bbox"]
                        corners = [(x, y) for x in (box[0], box[2]) for y in (box[1], box[3])]
                        if path and min(_point_segment_distance(p, points[a], points[b]) for a, b in path for p in corners) <= 18:
                            labels.append(f)
                    label = labels[0] if len(labels) == 1 else None
                    if label:
                        evidence.add(label["fragment_id"])
                    else:
                        uncertainties.append("label_ambiguous" if labels else "route_kind_unverified")
                    proposals.append({"id": f"pdf-route-{len(proposals) + 1}",
                        "from": object_for[anchors[src][0]], "to": object_for[anchors[dst][0]],
                        "kind": "answer" if label else "continue", "label": label["clean_text"] if label else "",
                        "evidence_ids": sorted(evidence), "uncertainties": uncertainties})
                    continue
                for n, ids in adjacency[v].items():
                    if n not in seen and n not in wings:
                        seen.add(n)
                        arrow_evidence = set().union(*(adjacency[v][w] for w in adjacency[v] if w in wings))
                        pending.append((n, path + [(v, n)], evidence | ids | arrow_evidence))
    return proposals


def _point_segment_distance(point, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    t = max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length)) if length else 0
    return hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def _bezier(points, t):
    return [sum(weight * point[axis] for weight, point in zip(
        ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3), points)) for axis in (0, 1)]
