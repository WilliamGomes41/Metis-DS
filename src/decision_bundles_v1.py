"""Keep literal bullet units separately reviewable under their source result bundle."""
from copy import deepcopy
import re

from src.integrity_kernel import stable_hash

BULLET = re.compile(r"(?m)^\s*[•·*\-]\s+")


def split_bundles(fragments):
    output = []
    for original in fragments:
        text = original["clean_text"]
        markers = list(BULLET.finditer(text))
        if len(markers) < 2 or original.get("bundle_role"):
            output.append(original)
            continue
        container = deepcopy(original)
        container["bundle_id"] = original["fragment_id"]
        container["bundle_role"] = "container"
        container["boom_kind"] = "path"
        output.append(container)
        for i, marker in enumerate(markers):
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            member = deepcopy(original)
            member["fragment_id"] += f"-bullet-{i + 1}"
            member["boom_id"] += f"-bullet-{i + 1}"
            member["raw_text"] = member["clean_text"] = text[marker.start():end].strip()
            member["boom_kind"] = "outcome"
            member["bundle_id"] = original["fragment_id"]
            member["bundle_role"] = "member"
            member["parser_version"] = "decision-source-bullets-v1"
            member["fragment_hash"] = stable_hash({k: v for k, v in member.items() if k != "fragment_hash"})
            output.append(member)
    return output


def stamp_bundles(fragments, objects):
    by_fragment = {f["fragment_id"]: f for f in fragments}
    by_source = {r["raw_object_id"]: o["object_id"] for o in objects
                 for r in o.get("provenance", {}).get("source_fragments", [])}
    for obj in objects:
        for ref in obj.get("provenance", {}).get("source_fragments", []):
            fragment = by_fragment.get(ref["raw_object_id"], {})
            if fragment.get("bundle_id"):
                obj.setdefault("metadata", {})["result_bundle"] = {
                    "object_id": by_source[fragment["bundle_id"]], "role": fragment["bundle_role"]}


def bundle_evidence(fragment):
    return ({"bundle_id": fragment["bundle_id"], "bundle_role": fragment["bundle_role"]}
            if fragment.get("bundle_id") else {})


def bundle_issues(nodes, objects, evidence):
    issues = []
    by_source = {r["raw_object_id"]: oid for oid, obj in objects.items()
                 for r in obj.get("provenance", {}).get("source_fragments", [])}
    for oid, obj in objects.items():
        expected = None
        for ref in obj.get("provenance", {}).get("source_fragments", []):
            row = evidence.get(ref["raw_object_id"], {})
            if row.get("bundle_id"):
                expected = {"object_id": by_source.get(row["bundle_id"]), "role": row["bundle_role"]}
        actual = obj.get("metadata", {}).get("result_bundle")
        if actual != expected:
            issues.append("decision_graph_bundle_evidence_mismatch")
        if expected and expected["role"] == "member":
            if (nodes.get(oid, {}).get("mode") != "context" or
                    nodes.get(expected["object_id"], {}).get("mode") not in {"continue", "terminal"}):
                issues.append("decision_graph_bundle_context_missing")
    return issues
