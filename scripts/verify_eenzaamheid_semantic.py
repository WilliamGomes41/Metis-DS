#!/usr/bin/env python3
"""Read-only source/model acceptance; never writes Metis workflow or publication."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.extract_pdf_v2 import extract
from src.llm_provider_v1 import load_llm_provider_config
from src.operations_console_v1 import ConsoleError
from src.pre_review_semantic_v1 import (
    _candidate_fragments, _evidence_fragments, _post_json, semantic_spec_from_fragments,
)
from src.semantic_passage_v1 import semantic_source_blocks, SELECTION_ORIGIN_PROPOSAL
from src.semantic_replay_v1 import stable_json_hash
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate, admission_of, GATE_ALLOWED
from src.passage_register_v1 import apply_passage_register

SOURCE_HASH = '2185b6502a76b76e942db2352d746a5f1193645091844fd84241dfb94ac51064'
INPUT_HASH = '5b32b417da3efd05575cdf839375b6f97048a519f6ccfe9dc84e681c2e5213ff'
DOCUMENT_ID = 'console-eenzaamheid-eenzaamheid-bij-ouderen-1-5-2185b650'
FIELDS = ('source_sha256', 'block_id', 'start', 'end', 'text', 'source_fragment_ids',
          'section_path', 'expected_type', 'reviewed_by', 'reviewed_at', 'note')
KNOWLEDGE_TYPES = {'recommendation', 'definition', 'explanation', 'condition', 'exception'}
REFERENCE_TYPES = KNOWLEDGE_TYPES | {'context', 'label', 'non_knowledge'}


def source_input(pdf: Path):
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != SOURCE_HASH:
        raise ValueError('source_hash_mismatch')
    fragments = extract(pdf, document_id=DOCUMENT_ID, source_id='src-2185b6502a76b76e')
    source = semantic_source_blocks(_candidate_fragments(fragments))
    evidence = semantic_source_blocks(_evidence_fragments(fragments))
    payload = {'source_blocks': source, 'evidence_blocks': evidence}
    if stable_json_hash(payload) != INPUT_HASH:
        raise ValueError('reconstructed_input_mismatch')
    return fragments, payload


def write_draft(path: Path, payload: dict):
    # Every candidate remains explicitly unknown until a human reviews it.
    with path.open('x', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for block in payload['source_blocks']:
            writer.writerow({'source_sha256': SOURCE_HASH, 'block_id': block['block_id'],
                'start': 0, 'end': len(block['text']), 'text': block['text'],
                'source_fragment_ids': json.dumps(block['source_fragment_ids']),
                'section_path': json.dumps(block.get('section_path') or []),
                'expected_type': 'UNREVIEWED', 'reviewed_by': '', 'reviewed_at': '', 'note': ''})


def reviewed_reference(path: Path, payload: dict):
    blocks = {block['block_id']: block for block in payload['source_blocks']}
    with path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError('human_reference_empty')
    covered = {key: set() for key in blocks}
    for row in rows:
        block = blocks.get(row.get('block_id'))
        if (not block or row.get('source_sha256') != SOURCE_HASH
                or row.get('expected_type') not in REFERENCE_TYPES
                or not row.get('reviewed_by', '').strip() or not row.get('reviewed_at', '').strip()):
            raise ValueError('human_reference_incomplete_or_stale')
        start, end = int(row['start']), int(row['end'])
        if not 0 <= start < end <= len(block['text']) or row['text'] != block['text'][start:end]:
            raise ValueError('human_reference_not_literal')
        row['start'], row['end'] = start, end
        covered[row['block_id']].update(range(start, end))
    # Splitting a block is allowed, but dropping an unreviewed statement is not.
    if any(any(index not in covered[key] for index, char in enumerate(block['text']) if not char.isspace())
           for key, block in blocks.items()):
        raise ValueError('human_reference_coverage_incomplete')
    if not any(row['expected_type'] == 'recommendation' for row in rows):
        raise ValueError('human_reference_recommendations_required')
    return rows


def prepare_review_objects(spec: dict, fragments: list[dict]):
    manifest = {'canonical_source': {
        'source_id': 'src-2185b6502a76b76e', 'title': 'Eenzaamheid bij ouderen',
        'publisher': 'V&VN', 'source_url': 'urn:vvn:freeze:' + SOURCE_HASH,
        'source_type': 'pdf', 'source_level': 1, 'canonicality': 'canonical',
        'source_checksum': SOURCE_HASH, 'checksum_algorithm': 'sha256',
        'integrity_status': 'verified', 'publication_date': None, 'version': '1.5',
    }}
    production_spec = {key: value for key, value in spec.items() if key != '_semantic_replay'}
    objects = transform(production_spec, manifest, fragments)
    return apply_passage_register(apply_admission_gate(objects, klasse='richtlijn', fragments=fragments,
        document_version='1.5', source_hash=SOURCE_HASH))


def compare_reference(rows: list[dict], spec: dict, review_objects: list[dict]):
    selected = [obj for obj in spec['objects']
                if obj.get('semantic_passage', {}).get('selection_origin') == SELECTION_ORIGIN_PROPOSAL]
    outcomes = []
    by_id = {obj['object_id']: obj for obj in review_objects}
    for ref in rows:
        matching = [obj for obj in selected if any(span.get('block_id') == ref['block_id']
                    and span.get('start', -1) <= ref['start'] and span.get('end', -1) >= ref['end']
                    for span in obj.get('semantic_passage', {}).get('spans', []))]
        kind = ref['expected_type']
        if kind in KNOWLEDGE_TYPES:
            typed = [obj for obj in matching if obj.get('proposed_object_type') == kind]
            ok = any(admission_of(by_id.get(obj['object_id'], {})).get('gate_result') == GATE_ALLOWED for obj in typed)
            outcome = 'matched_and_admitted' if ok else 'blocked_by_admission' if typed else 'missing_or_wrong_type'
        else:
            # A label/context is not a standalone model-proposed knowledge item.
            ok = not matching
            outcome = 'retained_without_knowledge_proposal' if ok else 'nonknowledge_proposed_as_knowledge'
        outcomes.append({'block_id': ref['block_id'], 'start': ref['start'], 'end': ref['end'],
                         'expected_type': kind, 'outcome': outcome, 'passed': ok,
                         'matching_object_ids': [obj['object_id'] for obj in matching],
                         'admission': {obj['object_id']: admission_of(by_id.get(obj['object_id'], {})) for obj in matching}})
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('draft', 'run'))
    parser.add_argument('--pdf', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    fragments, payload = source_input(args.pdf)
    if args.action == 'draft':
        write_draft(args.reference, payload)
        print(json.dumps({'status': 'HUMAN_REVIEW_REQUIRED', 'source_blocks': len(payload['source_blocks']),
                          'evidence_blocks': len(payload['evidence_blocks']), 'mutation': 'local_reference_only'}))
        return 0
    reference = reviewed_reference(args.reference, payload)
    config = load_llm_provider_config()
    if not config.configured:
        raise ValueError('provider_configuration_required')
    if args.output is None:
        raise ValueError('output_directory_required')
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'BLOCKED', 'source_sha256': SOURCE_HASH, 'input_hash': INPUT_HASH,
              'human_reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
              'model': config.model, 'requested_at': datetime.now(timezone.utc).isoformat(),
              'production_mutation': 'none', 'publication_acceptance': 'NOT_TESTED'}

    def record_actual_call(url, headers, request, timeout):
        (args.output / 'request.json').write_text(json.dumps(request, ensure_ascii=False, indent=2), encoding='utf-8')
        response = _post_json(url, headers, request, timeout)
        # Keep only visible output, provider status and usage. No HTTP headers or reasoning.
        visible = {'id': response.get('id'), 'status': response.get('status'), 'usage': response.get('usage'),
                   'output': [row for row in response.get('output', []) if row.get('type') == 'message']}
        (args.output / 'provider-visible-response.json').write_text(json.dumps(visible, ensure_ascii=False, indent=2), encoding='utf-8')
        report['actual_provider_response_received'] = True
        return response

    try:
        spec = semantic_spec_from_fragments(document_id=DOCUMENT_ID, title='Eenzaamheid bij ouderen',
            family='eenzaamheid', class_='richtlijn', fragments=fragments, content_kind='pdf',
            api_key=config.api_key, model=config.model, field_contract_v2=True,
            formation_context={'snapshot_id': 'acceptance-eenzaamheid-2185b650', 'source_sha256': SOURCE_HASH},
            post_json=record_actual_call)
        (args.output / 'source-bound-spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
        objects = prepare_review_objects(spec, fragments)
        (args.output / 'review-objects.json').write_text(json.dumps(objects, ensure_ascii=False, indent=2), encoding='utf-8')
        outcomes = compare_reference(reference, spec, objects)
        report.update(status='PASS' if all(row['passed'] for row in outcomes) else 'FAIL',
                      source_bound_contract='validated', admission_pipeline='executed', reference_outcomes=outcomes,
                      passed=sum(row['passed'] for row in outcomes), total=len(outcomes))
    except (ConsoleError, ValueError) as exc:
        report['error'] = exc.code if isinstance(exc, ConsoleError) else str(exc)
    finally:
        (args.output / 'acceptance-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'reference_outcomes'}))
    return 0 if report['status'] == 'PASS' else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ValueError as exc:
        print(json.dumps({'status': 'BLOCKED', 'error': str(exc), 'production_mutation': 'none'}))
        sys.exit(2)
