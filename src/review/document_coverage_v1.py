"""Compare one audited guideline with its exact, current candidate set."""
from functools import lru_cache
import json
from pathlib import Path

from src.integrity_kernel import exact_review_snapshot_hash, stable_hash
from src.review.knowledge_path_v1 import content_reviewable, source_lineage_resolves
from src.review.source_context_review_v1 import links_of, role_of
from src.vorming.knowledge_materialisation_v1 import _read_source_blocks
from src.vorming.source_accountability_v1 import evidence_of, uncovered_ranges
from src.vorming.source_bound_fields_v2 import validated_context

REFERENCE = Path(__file__).resolve().parents[2] / 'config/smetten_document_coverage_v1.json'
RETIRED = {'rejected', 'revise', 'superseded'}


@lru_cache(maxsize=1)
def _reference():
    return json.loads(REFERENCE.read_text(encoding='utf-8'))


def _ranges(spans, block_id):
    return [(span['start'], span['end']) for span in spans if span['block_id'] == block_id]


def _covers(block, ranges):
    return not uncovered_ranges(len(block['text']), ranges)


def _object_version(obj):
    return (obj['object_id'], obj['object_version'], exact_review_snapshot_hash(obj))


def _context_spans(obj, fragments, source_hash):
    try:
        return validated_context(obj, fragments, source_hash)
    except (ValueError, TypeError, KeyError):
        return []


def assess(envelope, objects, revision, fragments, accountability):
    """Return a read projection, without retaining or replaying older assessments.

    Objects must come from the document snapshot captured together with revision.
    The audit reference is independent of object selection and identifies the
    complete synthetic source by bytes and the reviewed extraction by text and
    location. Block identifiers are resolved from the current verified extract.
    """
    reference = _reference()
    source_hash = envelope['sha256']
    if source_hash != reference['source_sha256']:
        return None

    captured = _read_source_blocks(fragments, include_headings=True) if fragments is not None else {}
    locations = [(source.get('source_locator') or {}).get('locator_value') for _, source in captured.values()]
    blocks = [block for block, _ in captured.values()]
    if [[location, block['text']] for location, block in zip(locations, blocks)] != reference['blocks']:
        return {'scope': reference['scope'], 'status': 'unavailable'}

    binding = {
        'snapshot_id': envelope['snapshot_id'],
        'source_sha256': source_hash,
        'extraction_hash': stable_hash(getattr(fragments, 'extraction_record', None) or fragments),
        'set_revision': revision,
        'reference_hash': stable_hash(reference),
    }
    sources, recommendations = {}, []
    for obj in objects:
        oid = obj['object_id']
        source = obj.get('source') or {}
        usage = accountability.get(oid) or {}
        if (source.get('source_checksum') != source_hash or source.get('source_id') != envelope['source_id']
                or usage.get('role') == 'invalid_evidence'):
            continue
        evidence = evidence_of(obj)
        if evidence:
            if (obj.get('governance') or {}).get('validation_status') != 'superseded':
                sources[oid] = (obj, evidence['spans'], role_of(obj), usage)
            continue
        kind = obj.get('confirmed_object_type') or obj.get('proposed_object_type')
        if (kind == 'recommendation' and (obj.get('governance') or {}).get('validation_status') not in RETIRED
                and content_reviewable(obj) and source_lineage_resolves(obj, fragments=fragments)):
            recommendations.append((obj, obj['metadata']['semantic_passage']['spans'],
                                    _context_spans(obj, fragments, source_hash)))

    findings = []
    for provision in reference['provisions']:
        index = provision['block']
        kind = provision['kind']
        block = blocks[index]
        block_id = block['block_id']
        contributors = {}
        fully_covered = False
        for obj, core, context in recommendations:
            if kind == 'recommendation':
                ranges = _ranges(core, block_id)
            else:
                anchor = blocks[provision['recommendation']]
                if not _covers(anchor, _ranges(core, anchor['block_id'])):
                    continue
                ranges = _ranges([row['span'] for row in context
                                  if row['role'] == kind and row['span'] and not row['unresolved_reason']], block_id)
                for link in links_of(obj):
                    source_row = sources.get(link['source_object_id'])
                    if (source_row and source_row[2].get('role') == 'context'
                            and source_row[3]['role'] == 'linked_context'):
                        source_ranges = _ranges(source_row[1], block_id)
                        if source_ranges:
                            ranges.extend(source_ranges)
                            contributors[source_row[0]['object_id']] = source_row[0]
            if ranges:
                contributors[obj['object_id']] = obj
                fully_covered |= _covers(block, ranges)

        source_rows = [(obj, _ranges(spans, block_id), role, usage)
                       for obj, spans, role, usage in sources.values()]
        source_ids = [obj['object_id'] for obj, ranges, _, _ in source_rows if ranges]
        exclusions = [(obj, ranges, role['reason']) for obj, ranges, role, usage in source_rows
                      if ranges and role.get('role') == 'excluded' and role.get('reason')
                      and usage.get('reason') == 'excluded_with_reason']
        reason = ''
        if fully_covered:
            status = 'covered'
        elif not contributors and _covers(block, [span for _, ranges, _ in exclusions for span in ranges]):
            status = 'excluded'
            reason = ' · '.join(dict.fromkeys(reason for _, _, reason in exclusions))
            contributors.update((obj['object_id'], obj) for obj, _, _ in exclusions)
        else:
            status = 'partial' if contributors else 'missing'
        findings.append({
            'kind': kind, 'status': status, 'text': block['text'], 'location': locations[index],
            'span': {'block_id': block_id, 'start': 0, 'end': len(block['text'])},
            'reason': reason, 'source_object_ids': source_ids,
            'objects': [_object_version(obj) for obj in contributors.values()],
        })
    return {'scope': reference['scope'], 'status': 'current', 'binding': binding, 'findings': findings}
