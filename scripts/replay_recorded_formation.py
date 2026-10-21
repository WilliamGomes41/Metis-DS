#!/usr/bin/env python3
"""Offline replay of recorded provider outputs; no network or workflow writes."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import time
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.pre_review_semantic_v1 import semantic_spec_from_fragments
from src.semantic_transform_generic_v1 import transform
from src.admission_gate_v1 import apply_admission_gate
from src.source_accountability_v1 import evidence_of


def replay(path):
    csv.field_size_limit(32_000_000)
    with ZipFile(path) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read('attempt_diagnostics.csv').decode('utf-8-sig'))))
    diagnostic = next(json.loads(r['diagnostic']) for r in rows if r['state'] == 'failed')
    recorded = diagnostic['provider_evidence']
    calls = [recorded, *recorded.get('supplementary_calls', [])]
    invoked = []
    def provider(_url, _headers, payload, _timeout):
        if len(invoked) >= len(calls):
            raise AssertionError('Replay requested an unrecorded model response')
        response = calls[len(invoked)]['response']
        invoked.append(payload)
        return {'id': response['id'], 'status': response['status'], 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': response['output_text']}]}]}
    started = time.monotonic()
    data = diagnostic['validator_input']
    spec = semantic_spec_from_fragments(document_id=data['document_id'], title='Recorded source',
        family='recorded', class_='richtlijn', fragments=data['evidence_fragments'], content_kind='pdf',
        api_key='offline-recorded-response', model=diagnostic['model'], post_json=provider,
        field_contract_v3=True, formation_context={'snapshot_id': 'offline-replay', 'source_sha256': diagnostic['source_hash']})
    record = spec['_semantic_replay']
    manifest = {'canonical_source': {'source_id': data['evidence_fragments'][0]['source_id'], 'title': 'Recorded source',
        'source_type': 'pdf', 'source_url': 'urn:recorded:source', 'source_level': 1,
        'canonicality': 'canonical', 'integrity_status': 'verified',
        'source_checksum': diagnostic['source_hash'], 'version': diagnostic['source_version']}}
    objects = apply_admission_gate(transform(spec, manifest, data['evidence_fragments']), klasse='richtlijn',
        fragments=data['evidence_fragments'], document_version=diagnostic['source_version'], source_hash=diagnostic['source_hash'])
    candidates = [o for o in objects if (o.get('metadata') or {}).get('source_bound_fields')]
    evidence = record['provider_evidence']
    return {'proof_kind': 'offline_recorded_responses_not_live_or_clinical_acceptance',
        'evidence_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'source_sha256': diagnostic['source_hash'],
        'original_deployed_commit': diagnostic['deployed_commit'], 'original_failure': diagnostic['reason_code'],
        'provider_calls_replayed': len(invoked), 'source_fragments': len(data['evidence_fragments']),
        'validated_proposals': len(record['proposal']['objects']),
        'proposal_types': dict(Counter(o['proposed_object_type'] for o in record['proposal']['objects'])),
        'candidate_admission': dict(Counter(o['metadata']['admission']['gate_result'] for o in candidates)),
        'admission_block_reasons': dict(Counter(code for o in candidates for code in o['metadata']['admission']['reason_codes'])),
        'source_accountability_records': sum(bool(evidence_of(o)) for o in objects),
        'formation_incomplete': evidence['formation_incomplete'],
        'open_formation_reasons': dict(Counter(r['reason_code'] for r in evidence['pending_rejections'])),
        'elapsed_seconds': round(time.monotonic() - started, 3)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence_zip', type=Path)
    print(json.dumps(replay(parser.parse_args().evidence_zip), indent=2))
