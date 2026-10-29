"""Pure exact positioning of model-selected literals in canonical source blocks.

The wire reference is not authoritative evidence. Only the resolved span, after
the existing semantic validators accept it, may enter the existing run commit.
Offset-only legacy references are left to those validators, never repaired.
"""
from __future__ import annotations

from copy import deepcopy
import re

from src.vorming.semantic_passage_v1 import SemanticPassageError
from src.vorming.recommendation_semantics_v1 import adjacent_source_strength_span

VERSION = "source-evidence-resolution-v1"
V3_VERSION = "source-evidence-resolution-v1/v3-adjacent-strength-v2/owner-scoped-fields-v2"


def resolve_proposal_evidence(proposal, *, blocks, evidence_blocks, field_contract_v3=False):
    """Resolve all literal references without changing input or domain state.

    Occurrence is zero-based, counting exact (including overlapping) matches.
    A null/absent occurrence requires uniqueness, except for v3 directional
    strength stamps exactly adjacent to a uniquely selected recommendation and
    v3 fields that occur exactly once inside the owners bind_fields admits (B5-e).
    Offsets alongside a literal are non-authoritative hints.
    """
    texts = {}
    for block in [*blocks, *evidence_blocks]:
        block_id, text = block["block_id"], block["text"]
        if block_id in texts and texts[block_id] != text:
            raise SemanticPassageError("semantic_evidence_block_conflict")
        texts[block_id] = text

    def fail(code, path, ref):
        error = SemanticPassageError(code)
        error.finding.update(field=path, evidence_ref=deepcopy(ref))
        if code == "semantic_evidence_literal_ambiguous" and path.endswith(".recommendation_semantics.strength_evidence"):
            error.finding["strength_applicability"] = {"outcome": "uncertain"}
        if path.startswith("objects."):
            error.finding["candidate_index"] = int(path.split(".")[1])
        raise error

    def adjacent_strength(path, ref, text):
        # Only an exact directional stamp immediately following a uniquely
        # selected core may disambiguate v3 evidence. Never pick the first or
        # nearest match, cross blocks, or infer association across other prose.
        if not field_contract_v3 or not re.fullmatch(
            r"objects\.\d+\.recommendation_semantics\.strength_evidence", path
        ) or not re.fullmatch(r"(?:Sterk|Zwak)\s*[-–—:]\s*(?:voor|tegen)", ref["literal"], re.I):
            return None
        index = int(path.split(".")[1])
        obj = proposal["objects"][index]
        if obj.get("proposed_object_type") != "recommendation" or len(obj.get("spans") or []) != 1:
            return None
        core_ref = ((obj.get("field_evidence") or {}).get("recommendation_evidence_span") or {}).get("span")
        if not isinstance(core_ref, dict):
            return None
        candidate = resolve(obj["spans"][0], f"objects.{index}.spans.0")
        selected = resolve(core_ref, f"objects.{index}.field_evidence.recommendation_evidence_span.span")
        if (set(selected) != {"block_id", "start", "end"}
                or selected["block_id"] != ref["block_id"]
                or type(selected["start"]) is not int or type(selected["end"]) is not int
                or not 0 <= selected["start"] < selected["end"] <= len(text)):
            return None
        if (not isinstance(candidate, dict) or set(candidate) != {"block_id", "start", "end"}
                or candidate["block_id"] != selected["block_id"]
                or type(candidate["start"]) is not int or type(candidate["end"]) is not int
                or not 0 <= candidate["start"] <= selected["start"] < selected["end"] <= candidate["end"] <= len(text)):
            return None
        span = adjacent_source_strength_span(text, selected["end"])
        if span and text[span[0]:span[1]] == ref["literal"]:
            return span[0]
        return None

    def candidate_scoped(path, ref, text):
        # B5-e: a v3 field may only bind inside the owners bind_fields admits:
        # a core field inside its own candidate; a context field inside its
        # candidate or an explicitly supplied, resolved context entry with an
        # admissible role. Exactly one admissible match resolves; zero or
        # several stay ambiguous. Never picks the first or nearest match.
        from src.vorming.source_bound_fields_v3 import CONTEXT_FIELDS
        shape = re.fullmatch(r"objects\.(\d+)\.field_evidence\.(\w+)\.span(?:\.\d+)?", path)
        if not field_contract_v3 or not shape:
            return None
        index, field = int(shape.group(1)), shape.group(2)
        obj = proposal["objects"][index]
        if not isinstance(obj, dict) or not isinstance(obj.get("spans"), list):
            return None
        refs = [(span, f"objects.{index}.spans.{n}") for n, span in enumerate(obj["spans"])]
        if field in CONTEXT_FIELDS:
            context = obj.get("context_evidence", [])
            if not isinstance(context, list):
                return None
            refs += [(row["span"], f"objects.{index}.context_evidence.{n}.span") for n, row in enumerate(context)
                     if isinstance(row, dict) and row.get("role") in CONTEXT_FIELDS[field]
                     and row.get("span") and not row.get("unresolved_reason")]
        try:
            owners = [resolve(span, owner_path) for span, owner_path in refs]
        except SemanticPassageError:
            return None
        literal, matches, start = ref["literal"], [], 0
        while (match := text.find(literal, start)) >= 0:
            if any(isinstance(c, dict) and c.get("block_id") == ref["block_id"]
                   and type(c.get("start")) is int and type(c.get("end")) is int
                   and c["start"] <= match and match + len(literal) <= c["end"] for c in owners):
                matches.append(match)
            start = match + 1
        return matches[0] if len(matches) == 1 else None

    def resolve(value, path):
        if isinstance(value, list):
            return [resolve(row, f"{path}.{index}" if path else str(index))
                    for index, row in enumerate(value)]
        if not isinstance(value, dict):
            return value
        if "block_id" in value and "literal" in value:
            if (set(value) - {"block_id", "literal", "occurrence", "start", "end"}
                    or ("start" in value) != ("end" in value)):
                fail("semantic_evidence_reference_invalid", path, value)
            block_id, literal = value["block_id"], value["literal"]
            if not isinstance(block_id, str) or block_id not in texts:
                fail("semantic_evidence_unknown_block", path, value)
            if not isinstance(literal, str) or not literal:
                fail("semantic_evidence_literal_invalid", path, value)
            occurrence = value.get("occurrence")
            if occurrence is not None and (type(occurrence) is not int or occurrence < 0):
                fail("semantic_evidence_occurrence_invalid", path, value)
            text = texts[block_id]
            # Only the first two matches are needed to reject ambiguity. Explicit
            # occurrence resolution also stops as soon as its match is found.
            start, count, found = 0, 0, None
            while True:
                match = text.find(literal, start)
                if match < 0:
                    break
                if occurrence is not None and count == occurrence:
                    found = match
                    break
                if occurrence is None:
                    if count:
                        found = adjacent_strength(path, value, text)
                        if found is None:
                            found = candidate_scoped(path, value, text)
                        if found is None:
                            fail("semantic_evidence_literal_ambiguous", path, value)
                        break
                    found = match
                count += 1
                start = match + 1
            if found is None:
                fail("semantic_evidence_literal_not_found" if count == 0
                     else "semantic_evidence_occurrence_invalid", path, value)
            return {"block_id": block_id, "start": found, "end": found + len(literal)}
        return {key: resolve(row, f"{path}.{key}" if path else key)
                for key, row in value.items()}

    return resolve(proposal, "")
