"""Read-only semantic contract and proposal validation, independent of execution."""
from typing import Any
from src.operations_console_v1 import ConsoleError
from src.vorming.semantic_passage_v1 import ALLOWED_PROPOSED_TYPES, SEMANTIC_PASSAGE_VERSION, STRENGTH_BINDING_VERSION, V3_STRENGTH_VOCABULARY_VERSION
from src.vorming.source_bound_fields_v2 import MODE as SEMANTIC_V2_MODE, evidence_schema, context_evidence_schema, CONTEXT_VERSION
from src.vorming.source_bound_fields_v3 import MODE as SEMANTIC_V3_MODE, VERSION as FIELDS_V3_VERSION
from src.vorming.source_occurrence_authority_v1 import SOURCE_OCCURRENCE_AUTHORITY_VERSION
from src.vorming.source_evidence_resolution_v1 import VERSION as EVIDENCE_RESOLUTION_VERSION, V3_VERSION as V3_EVIDENCE_RESOLUTION_VERSION


def semantic_contract_version(*, field_contract_v2=False, field_contract_v3=False):
    """The one semantic contract string; replay identity and reservation MOETEN share it."""
    return ("source-accountability-v2/bounded-formation-v1/" if field_contract_v3 else "source-accountability-v1/") + (f"recoverable-formation-v1/relation-object-index-v1/target-via-relation-v1/scope-list-introduction-v1/predicate-contiguous-v1/{FIELDS_V3_VERSION}/{CONTEXT_VERSION}/condition-context-and-timing-list-v2/recommendation-core-admission-v3/recommendation-coverage-v1/{V3_STRENGTH_VOCABULARY_VERSION}/{SEMANTIC_PASSAGE_VERSION}/{V3_EVIDENCE_RESOLUTION_VERSION}" if field_contract_v3 else f"source-bound-fields-v2/{CONTEXT_VERSION}/{SEMANTIC_PASSAGE_VERSION}/{EVIDENCE_RESOLUTION_VERSION}" if field_contract_v2 else f"{SEMANTIC_PASSAGE_VERSION}/{EVIDENCE_RESOLUTION_VERSION}") + f"/{STRENGTH_BINDING_VERSION}/{SOURCE_OCCURRENCE_AUTHORITY_VERSION}"

def semantic_contract_version_for_mode(mode):
    """Read-only mapping from a stored processing mode; non-semantic modes have no contract."""
    from src.vorming.passage_formation_policy_v1 import SEMANTIC_MODE
    if mode == SEMANTIC_V3_MODE:
        return semantic_contract_version(field_contract_v3=True)
    if mode == SEMANTIC_V2_MODE:
        return semantic_contract_version(field_contract_v2=True)
    if mode == SEMANTIC_MODE:
        return semantic_contract_version()
    return None

def _proposal_schema(field_contract_v2: bool = False, field_contract_v3: bool = False) -> dict[str, Any]:
    span = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "block_id": {"type": "string"},
            "literal": {"type": "string", "minLength": 1},
            "occurrence": {"type": ["integer", "null"], "minimum": 0},
        },
        "required": ["block_id", "literal", "occurrence"],
    }
    nullable_span = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": dict(span["properties"]),
        "required": list(span["required"]),
    }
    recommendation_semantics = {
        "type": ["object", "null"],
        "additionalProperties": False,
        "properties": {
            "direction": {"type": "string", "enum": ["for", "against"]},
            "direction_evidence": span,
            "strength": {
                "type": ["string", "null"],
                "enum": ["strong", "weak", None],
            },
            "strength_status": {
                "type": "string",
                "enum": ["explicit", "not_stated", "unmapped"],
            },
            "strength_evidence": nullable_span,
        },
        "required": [
            "direction",
            "direction_evidence",
            "strength",
            "strength_status",
            "strength_evidence",
        ],
    }
    relation = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_spans": {"type": "array", "minItems": 1, "items": span},
            "relation_type": {
                "type": "string",
                "enum": [
                    "applies_if",
                    "except_if",
                    "defines",
                    "explains",
                    "supported_by",
                    "supersedes",
                ],
            },
            "target_spans": {"type": "array", "minItems": 1, "items": span},
            "evidence_spans": {"type": "array", "minItems": 1, "items": span},
        },
        "required": [
            "source_spans",
            "relation_type",
            "target_spans",
            "evidence_spans",
        ],
    }
    obj = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "spans": {"type": "array", "minItems": 1, "items": span},
            "proposed_object_type": {
                "type": "string",
                "enum": sorted(ALLOWED_PROPOSED_TYPES),
            },
            "recommendation_semantics": recommendation_semantics,
        },
        "required": [
            "spans",
            "proposed_object_type",
            "recommendation_semantics",
        ],
    }
    if field_contract_v3:
        # B5-h: a v3 relation names its endpoints by object index; the producer
        # boundary (recoverable_formation_v1.prepare) maps them to the objects'
        # own selections, so repeated span literals cannot miss an endpoint.
        props = relation["properties"]
        del props["source_spans"], props["target_spans"]
        props["source_object"] = {"type": "integer", "minimum": 0}
        props["target_object"] = {"type": "integer", "minimum": 0}
        relation["required"] = ["source_object", "relation_type", "target_object", "evidence_spans"]
    if field_contract_v2 or field_contract_v3:
        from src.vorming.source_bound_fields_v3 import evidence_schema as schema_v3
        obj["properties"]["field_evidence"] = schema_v3(span) if field_contract_v3 else evidence_schema(span)
        obj["required"].append("field_evidence")
        obj["properties"]["context_evidence"] = context_evidence_schema(span)
        obj["required"].append("context_evidence")
    result = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "objects": {"type": "array", "items": obj},
            "relations": {"type": "array", "items": relation},
            "abstain_reason": {"type": ["string", "null"]},
        },
        "required": ["objects", "relations", "abstain_reason"],
    }
    if field_contract_v2 or field_contract_v3:
        from src.vorming.source_accountability_v1 import assessment_schema
        result["properties"]["source_assessments"] = assessment_schema(span)
        result["required"].append("source_assessments")
    return result

def validate_provider_proposal(proposal, *, field_contract_v2=False, field_contract_v3=False):
    """Pure proposal gates shared with read-only diagnostic reproduction."""
    if not isinstance(proposal, dict):
        raise ConsoleError("pre_review_llm_response_invalid")
    if str(proposal.get("abstain_reason") or "").strip():
        raise ConsoleError("pre_review_llm_abstained")
    if (field_contract_v2 or field_contract_v3) and isinstance(proposal.get("objects"), list):
        for index, row in enumerate(proposal["objects"]):
            if not isinstance(row, dict) or "context_evidence" not in row:
                error = ConsoleError("pre_review_llm_proposal_rejected", "source_bound_context_required")
                error.validation_finding = {"candidate_index": index, "field": "context_evidence",
                    "proposed_object": row, "reason_code": "source_bound_context_required"}
                raise error
