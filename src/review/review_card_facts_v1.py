"""Verified intrinsic inputs for Review cards, never command/publication input.

The workflow store seals these against current object histories and the retained
source identity. Current approvals, policy, actor routes and source closure are
deliberately absent: their existing owners still derive those at read time.
"""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
import hashlib

from src.integrity_kernel import exact_review_snapshot_hash, stable_hash
from src.vorming.prepared_source_views_v1 import freeze, preserve_fragments

CONTRACT = 'review-card-facts-v1'


def producer_contract():
    from src.vorming.prepared_source_views_v1 import contract
    from src.review.source_context_review_v1 import CONTRACT as context
    from src.vorming.source_containers_v1 import VERSION as containers
    from src.vorming.source_bound_fields_v2 import VERSION as bound_context
    from src.vorming.decision_unit_construction_v1 import CONTRACT as unit
    return {'version': CONTRACT, 'source_views': contract(), 'context': context,
            'containers': containers, 'bound_context': bound_context, 'unit': unit}


class ReviewObjectFacts(Mapping):
    """An immutable, non-JSON-serializable projection, not a KnowledgeObject."""

    def __init__(self, record):
        if (not isinstance(record, dict) or record.get('contract') != CONTRACT
                or not isinstance(record.get('fields'), dict)
                or not isinstance(record.get('proof'), dict)
                or record['proof'].get('producer') != producer_contract()
                or not record.get('exact_hash')):
            raise ValueError('review_card_facts_invalid')
        self._record = freeze(deepcopy(record))

    def __getitem__(self, key):
        return self._record['fields'][key]

    def __iter__(self):
        return iter(self._record['fields'])

    def __len__(self):
        return len(self._record['fields'])

    def __deepcopy__(self, memo):
        return self

    @property
    def exact_hash(self):
        return self._record['exact_hash']

    @property
    def proof(self):
        return self._record['proof']


@dataclass(frozen=True)
class ReviewFactSources:
    """Checked source primitives for one exact captured object set; no bytes."""
    objects: tuple
    _by_id: Mapping = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        rows = {obj['object_id']: obj for obj in self.objects}
        if len(rows) != len(self.objects) or any(not isinstance(obj, ReviewObjectFacts) for obj in self.objects):
            raise ValueError('review_card_facts_invalid')
        object.__setattr__(self, '_by_id', MappingProxyType(rows))

    def proof_for(self, obj):
        if self._by_id.get(obj.get('object_id')) is not obj:
            raise ValueError('review_card_source_capture_mismatch')
        return obj.proof


def preserve_review_sources(fragments):
    return fragments if isinstance(fragments, ReviewFactSources) else preserve_fragments(fragments)


def projection_hash(obj):
    return obj.exact_hash if isinstance(obj, ReviewObjectFacts) else exact_review_snapshot_hash(obj)


def source_input(obj):
    """Complete primitive dependencies; no policy/governance or approval state."""
    md = obj.get('metadata') or {}
    return {k: deepcopy(obj.get(k)) for k in ('object_id', 'source', 'content', 'semantic_passage')} | {
        'source_fragments': deepcopy((obj.get('provenance') or {}).get('source_fragments')),
        'metadata': {k: deepcopy(md.get(k)) for k in ('semantic_passage', 'source_accountability',
                    'source_bound_context', 'decision_unit_construction', 'result_bundle')},
    }


def prepare_source_proof(obj, fragments):
    """Run existing primitive validators on complete inputs at the writer/prep boundary."""
    from src.review.knowledge_path_v1 import source_lineage_resolves
    from src.review.source_context_review_v1 import literal_identity, verify_literal_source
    from src.vorming.source_accountability_v1 import evidence_of
    from src.vorming.source_containers_v1 import accounting_reason, bound_context_valid
    from src.vorming.decision_unit_construction_v1 import unit_issues

    evidence = evidence_of(obj)
    literal = False
    if fragments is not None:
        try:
            literal = verify_literal_source(obj, fragments, (obj.get('source') or {}).get('source_checksum'))
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
    return {
        'producer': producer_contract(),
        'input_hash': stable_hash(source_input(obj)),
        'lineage': source_lineage_resolves(obj, fragments=fragments),
        'literal': literal,
        'literal_identity': literal_identity(obj),
        'literal_text_hash': stable_hash(str((obj.get('content') or {}).get('clean_text') or '')),
        'source_refs_hash': _refs_equality_hash((obj.get('provenance') or {}).get('source_fragments')),
        'bound_context': bound_context_valid(obj, fragments=fragments),
        'evidence': {k: deepcopy(v) for k, v in evidence.items() if k not in {'text', 'binding_hash'}},
        'metadata_reason': accounting_reason(evidence['text']) if evidence else None,
        'unit_issues': unit_issues(obj),
    }


def prepare_object_facts(obj, *, proof):
    from src.review.four_eyes_v1 import HIGH_RISK_FIELDS
    if proof['input_hash'] != stable_hash(source_input(obj)):
        raise ValueError('review_card_source_input_mismatch')
    keys = ('object_id', 'object_version', 'document_id', 'parent_object_id', 'object_type',
            'proposed_object_type', 'confirmed_object_type', 'structure', 'risk', 'uncertainty',
            'logic', 'relations', 'confirmed_relations', 'proposed_knowledge_relations',
            'confirmed_knowledge_relations', 'no_action', 'governance', 'source')
    fields = {k: deepcopy(obj[k]) for k in keys if k in obj}
    prov = obj.get('provenance') or {}
    fields['provenance'] = {k: deepcopy(prov[k]) for k in ('canonical_object_hash', 'previous_object_version',
        'revision_reason', 'revision_patch_hash') if k in prov}
    if 'source_fragments' in prov:
        fields['provenance']['source_fragments'] = [
            {'raw_object_id': row.get('raw_object_id')} if isinstance(row, dict) else deepcopy(row)
            for row in prov['source_fragments']]
    md = obj.get('metadata') or {}
    selected = ('admission', 'passage_register', 'review_policy',
                'revision_lineage', 'source_role_review', 'result_bundle', 'risk_level', *HIGH_RISK_FIELDS)
    metadata = {k: deepcopy(md[k]) for k in selected if k in md}
    if isinstance(metadata.get('admission'), dict):
        metadata['admission'] = {k: deepcopy(md['admission'][k]) for k in
            ('gate_result', 'source_hash', 'document_version', 'section_path') if k in md['admission']}
    semantic = md.get('semantic_passage')
    if isinstance(semantic, dict):
        metadata['semantic_passage'] = {k: deepcopy(semantic[k]) for k in
            ('version', 'selection_origin', 'structural', 'formation_mode', 'spans') if k in semantic}
    elif 'semantic_passage' in md:
        metadata['semantic_passage'] = deepcopy(semantic)
    if 'source_accountability' in md:
        metadata['source_accountability'] = None  # Retain damaged/valid source discriminator.
    if 'decision_unit_construction' in md:
        metadata['decision_unit_construction'] = bool(md['decision_unit_construction'])
    if 'source_bound_context' in md:
        raw = md['source_bound_context']
        entries = raw.get('entries') if isinstance(raw, dict) else None
        metadata['source_bound_context'] = {'entries': [
            {k: deepcopy(row[k]) for k in ('span', 'unresolved_reason') if k in row}
            if isinstance(row, dict) else deepcopy(row) for row in entries
        ] if isinstance(entries, list) else deepcopy(entries)} if isinstance(raw, dict) else deepcopy(raw)
    if 'confirmed_source_context' in md:
        raw = md['confirmed_source_context']
        metadata['confirmed_source_context'] = [
            {**{k: deepcopy(v) for k, v in row.items() if k not in {'text', 'source_fragments'}},
             'literal_text_hash': stable_hash(row.get('text')),
             'source_refs_hash': _refs_equality_hash(row.get('source_fragments'))}
            if isinstance(row, dict) else deepcopy(row) for row in raw
        ] if isinstance(raw, list) else deepcopy(raw)
    fields['metadata'] = metadata
    return {'contract': CONTRACT, 'fields': fields, 'exact_hash': exact_review_snapshot_hash(obj), 'proof': deepcopy(proof)}


def literal_link_matches(target, link, source):
    if isinstance(target, ReviewObjectFacts) and isinstance(source, ReviewObjectFacts):
        return link.get('literal_text_hash') == source.proof['literal_text_hash']
    return link.get('text') == str((source.get('content') or {}).get('clean_text') or '')


def _refs_equality_hash(value):
    """Preserve existing JSON/Python reference equality, including 1 == 1.0.

    This is solely an equality primitive; canonical review/source hashes retain
    their exact numeric representation and continue using the integrity kernel.
    """
    def normalize(item):
        if isinstance(item, bool) or isinstance(item, float) and item.is_integer():
            return int(item)
        if isinstance(item, dict):
            return {key: normalize(part) for key, part in item.items()}
        if isinstance(item, list):
            return [normalize(part) for part in item]
        return item
    return stable_hash(normalize(value))


def literal_refs_match(target, link, source):
    if isinstance(target, ReviewObjectFacts) and isinstance(source, ReviewObjectFacts):
        return link.get('source_refs_hash') == source.proof['source_refs_hash']
    return link.get('source_fragments') == (source.get('provenance') or {}).get('source_fragments')


class ReviewGraphInventory(Mapping):
    """Compact intrinsic graph evidence, never evidence for source opening."""
    def __init__(self, inventory):
        if not isinstance(inventory, dict):
            raise ValueError('review_card_graph_evidence_invalid')
        self._inventory = freeze(inventory)

    def __getitem__(self, key):
        return self._inventory[key]

    def __iter__(self):
        return iter(self._inventory)

    def __len__(self):
        return len(self._inventory)

    def label_matches(self, evidence_ids, label):
        digest = hashlib.sha256(label.encode('utf8')).hexdigest()
        evidence = self.get('items') or {}
        return any(evidence[i].get('literal_text_hash') == digest for i in evidence_ids)
