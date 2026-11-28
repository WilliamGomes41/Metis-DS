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
        return validate_proposal(proposal, blocks=selection_source_blocks(fragments), inventory=inventory)
