"""Project human selections on frozen source into a decision-tree proposal."""
from copy import deepcopy

from src.vorming.decision_tree_proposal_v1 import (
    CONTRACT as PROPOSAL_CONTRACT,
    MAX_UNITS,
    DecisionTreeProposalError,
    validate_proposal,
)
from src.vorming.knowledge_materialisation_v1 import (
    resolve_source_selection,
    selection_source_blocks,
    source_reconstruction_scope,
)

INPUT_CONTRACT = "decision-tree-annotation-input-v1"


def proposal_from_entries(entries, *, fragments, inventory):
    """Resolve literal quotes on the server before validating the complete graph."""
    if not isinstance(entries, dict) or entries.get("contract") != INPUT_CONTRACT:
        raise DecisionTreeProposalError("decision_annotation_contract_unsupported")
    units = entries.get("units")
    if not isinstance(units, list) or not 0 < len(units) <= MAX_UNITS:
        raise DecisionTreeProposalError("decision_proposal_size_invalid")
    proposal = deepcopy(entries)
    proposal["contract"] = PROPOSAL_CONTRACT
    with source_reconstruction_scope(reuse_existing=True):
        for unit in proposal["units"]:
            if not isinstance(unit, dict) or "quoted_text" in unit:
                raise DecisionTreeProposalError("decision_annotation_unit_invalid")
            selection = resolve_source_selection(unit.get("spans"), fragments=fragments)
            unit["quoted_text"] = selection["source_text"]
        try:
            return validate_proposal(proposal, blocks=selection_source_blocks(fragments), inventory=inventory)
        except TypeError as exc:
            raise DecisionTreeProposalError("decision_proposal_shape_invalid") from exc


ROUTE = "decision-tree-annotation-v1"


def empty_entries():
    return {"contract": INPUT_CONTRACT, "units": [], "connections": [],
            "context_bindings": [], "result_bundles": [], "unresolved": []}


def export_entries(fragments, inventory):
    """Seed the graph with the items, branches and bundles stated by the source."""
    entries = empty_entries()
    blocks = {fid: block for block in selection_source_blocks(fragments)
              for fid in block["source_fragment_ids"]}
    refs = {}
    members = {}
    containers = {}
    for fragment in fragments:
        text = " ".join(fragment["clean_text"].split())
        if not text:
            continue
        fid = fragment["fragment_id"]
        block = blocks[fid]
        if block["source_fragment_ids"] != [fid] or block["text"] != text:
            raise DecisionTreeProposalError("decision_export_node_not_preserved")
        ref = f"u{len(refs) + 1}"
        refs[str(fragment["boom_id"])] = ref
        role = {"path": "start", "outcome": "outcome"}.get(fragment.get("boom_kind"), "action")
        if fragment.get("bundle_role") == "member":
            role = "context"
            members.setdefault(fragment["bundle_id"], []).append(ref)
        if fragment.get("bundle_role") == "container":
            containers[fid] = ref
        entries["units"].append({"ref": ref, "role": role, "selection": None, "entry": False,
                                 "spans": [{"block_id": block["block_id"], "start": 0, "end": len(text)}]})
    for key, item in sorted(inventory["items"].items()):
        if item["kind"] == "export_edge":
            branch = item["record"]
            if branch["from"] in refs and branch["to"] in refs:
                entries["connections"].append({"ref": f"c{len(entries['connections']) + 1}",
                    "from": refs[branch["from"]], "to": refs[branch["to"]],
                    "kind": "answer" if branch.get("label") else "continue",
                    "label_span": None, "evidence_ids": [key]})
    for fid, ref in containers.items():
        entries["result_bundles"].append({"ref": f"b{len(entries['result_bundles']) + 1}",
                                           "container": ref, "members": members.get(fid, [])})
    return entries


def validate_export_choices(graph, fragments, inventory):
    """Only node semantics and entrypoint selection are writable on an export."""
    expected = export_entries(fragments, inventory)
    if len(expected["units"]) != len(graph["units"]):
        raise DecisionTreeProposalError("decision_export_node_not_preserved")
    incoming = {edge["to"] for edge in expected["connections"]}
    for source, chosen in zip(expected["units"], graph["units"]):
        if source["role"] == "action" and chosen["role"] == "question":
            source.update(role="question", selection=chosen["selection"])
        if chosen["entry"] and chosen["ref"] in incoming:
            raise DecisionTreeProposalError("decision_export_route_not_preserved")
        source["entry"] = chosen["entry"]
    if graph != expected:
        raise DecisionTreeProposalError("decision_export_structure_not_preserved")


def build_graph(seal, entries, fragments):
    """Reproduce the formation from its seal, including its immutable source evidence."""
    import json
    from src.integrity_kernel import stable_hash
    from src.operations_console_v1 import canonical_source_manifest, transform_generic
    from src.review.review_policy_v1 import project_policy
    from src.vorming import decision_tree_route_v1 as route
    from src.vorming.admission_gate_v1 import apply_admission_gate
    from src.vorming.decision_tree_construction_v1 import construct

    context = seal["context"]
    if not context.get("review_policy"):
        raise DecisionTreeProposalError("decision_annotation_review_policy_required")
    source = seal["tree_source"]
    inventory = source["inventory"]
    entry, = entries
    proposal = proposal_from_entries(entry["payload"]["graph"], fragments=fragments, inventory=inventory)
    exported = context["content_kind"] == "boom"
    identity = {"actor": entry["author_id"], "annotation_seal_id": stable_hash(seal)}
    construction = construct(proposal, document_id=context["document_id"], title=context["title"],
        family=context["family"], class_=context["class"], content_kind=context["content_kind"],
        fragments=fragments, inventory=inventory, model=None, annotation=identity,
        proposed_types=route.export_types(proposal, fragments) if exported else None)
    if exported:
        data = json.dumps({"branches": source["branches"]}).encode()
        route.verify_export_preserved(construction, data, fragments)
        valid = {item["locator"]["json_pointer"] for item in inventory["items"].values()
                 if item["kind"] == "export_edge"}
        construction["graph_plan"]["unresolved"].extend(f"invalid_export_branch:{i}"
            for i in range(len(source["branches"])) if f"/branches/{i}" not in valid)
        route._export_enrichment(construction, fragments, context["document_id"])
    objects = transform_generic(construction["spec"], canonical_source_manifest(context), fragments)
    objects = apply_admission_gate(objects, klasse=context["class"], fragments=fragments,
                                   document_version=context["version"], source_hash=context["sha256"])
    if context.get("review_policy"):
        project_policy(objects, context["review_policy"])
    record = {"construction": construction, "inventory": inventory,
              "formation": {"route": ROUTE, "model": None, **identity,
                            "policy_version": route.POLICY_VERSION, "proposal_contract": PROPOSAL_CONTRACT,
                            "construction_contract": construction["contract"], "proposal_hash": construction["proposal_hash"]}}
    for obj in objects:
        if obj["object_type"] != "document":
            obj["metadata"]["human_annotation"] = {key: entry[key] for key in ("annotation_id", "revision", "payload_hash")}
    fields = route.finalize(record, objects, fragments, context["sha256"], actor=entry["author_id"],
                            with_graph=True)
    return objects, fields
