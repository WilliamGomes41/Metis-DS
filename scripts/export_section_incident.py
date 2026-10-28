#!/usr/bin/env python3
"""Join a browser probe with normalized JSON arrays or JSONL diagnostic events."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from zipfile import BadZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.section_incident_v1 import build_incident, summary

MAX_BYTES = 8 * 1024 * 1024


def read(path, *, events=False):
    with Path(path).open('rb') as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError('input_exceeds_8_mib')
    text = raw.decode('utf-8')
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        if not events:
            raise ValueError('invalid_probe_json') from None
        data = [json.loads(line.removeprefix('metis_diagnostic '))
                for line in text.splitlines() if line.strip()]
    if events and (not isinstance(data, list) or any(not isinstance(r, dict) for r in data)):
        raise ValueError('events_must_be_json_array_or_jsonl')
    if events:
        data = [row.get('d', row) for row in data]
        if any(not isinstance(row, dict) for row in data):
            raise ValueError('invalid_event_object')
    return data, hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser')
    parser.add_argument('--processing')
    parser.add_argument('--publication', help='Authorized publication observation JSON')
    parser.add_argument('--publication-route', help='Captured browser/readiness/product route evidence')
    parser.add_argument('--publication-after-restart', help='Observation from a later process')
    parser.add_argument('--evidence', help='Existing processing-evidence ZIP; read recorded tables only')
    parser.add_argument('--attempt-id')
    parser.add_argument('--request-id')
    parser.add_argument('--application')
    parser.add_argument('--platform')
    parser.add_argument('--output', required=True, help='New output directory; never overwritten')
    args = parser.parse_args()
    hashes = {}
    if not args.browser and not args.processing and not args.evidence and not args.publication:
        parser.error('Supply --browser, --processing, --evidence or --publication')
    if (args.publication_after_restart or args.publication_route) and not args.publication:
        parser.error('--publication-after-restart requires --publication')
    probe = None
    if args.browser:
        probe, hashes['browser'] = read(args.browser)
    app, platform = [], []
    if args.application:
        app, hashes['application'] = read(args.application, events=True)
    if args.platform:
        platform, hashes['platform'] = read(args.platform, events=True)
    result = build_incident(probe, app, platform) if probe is not None else {'schema':'processing-incident-bundle-v1'}
    if args.processing:
        from src.vorming.processing_trace_v1 import processing_incident
        processing, hashes['processing'] = read(args.processing)
        result['processing'] = processing_incident(processing, app, selected_attempt=args.attempt_id, selected_request=args.request_id)
    if args.evidence:
        from src.vorming.blockage_diagnostics_v1 import read_blockage_zip, blockage_report
        tables = read_blockage_zip(args.evidence)
        with Path(args.evidence).open('rb') as source:
            hashes['evidence'] = hashlib.file_digest(source, 'sha256').hexdigest()
        result['blockage'] = blockage_report(tables, selected_attempt=args.attempt_id)
        if 'processing' in result:
            trace = result['processing']['trace']
            context = result['blockage']['context']
            result['processing_context_match'] = all(trace.get(key) and trace.get(key) == context.get(key)
                                                     for key in ('snapshot_id', 'source_hash'))
    if args.publication:
        from src.publication.publication_evidence_v1 import publication_report
        publication, hashes['publication'] = read(args.publication)
        after = None
        if args.publication_after_restart:
            after, hashes['publication_after_restart'] = read(args.publication_after_restart)
        route = None
        if args.publication_route:
            route, hashes['publication_route'] = read(args.publication_route)
        if args.application:
            from src.publication.publication_evidence_v1 import publication_route_from_events
            boundary = publication_route_from_events(publication, app, request_id=args.request_id)
            route = {**(route or {}), **boundary}
        if route is not None and probe is not None:
            route = {**route, 'browser_incident':{key:value for key,value in result.items() if key in ('schema','browser','application','platform','correlation','missing_evidence','contradictions')}}
        result['publication'] = publication_report(publication, after_restart=after, route_evidence=route)
        for name in ('processing', 'blockage'):
            if name in result:
                context = result[name]['trace' if name == 'processing' else 'context']
                matches = all(context.get(key) and context.get(key) == publication.get(key)
                              for key in ('snapshot_id', 'source_hash'))
                result['publication'][name + '_context_matches'] = bool(matches)
                if not matches:
                    result['publication']['identity_conflicts'].append(name + '_context_not_bound')
                    result['publication']['end_to_end_proven'] = False
    result['input_sha256'] = hashes
    result['snapshot_consistency'] = 'independent_observations_not_atomic'
    output = Path(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / 'incident.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    report = summary(result) if probe is not None else 'Metis processing incident\nDomain completion: not assessed.\n'
    if 'processing' in result:
        item = result['processing']
        report += '\nStored processing state: ' + str(item['assessment']['stored_state'])
        report += '\nLast recorded checkpoint: ' + str(item['assessment']['last_recorded_checkpoint'])
        report += '\nMissing evidence: ' + ', '.join(item['missing_evidence'])
        report += '\nNext check: ' + item['assessment']['next_check'] + '\n'
    if 'blockage' in result:
        from src.vorming.blockage_diagnostics_v1 import blockage_summary
        report += '\n' + blockage_summary(result['blockage'])
    if 'publication' in result:
        item = result['publication']
        report += '\nPublicatie: duurzaam waargenomen=' + str(item['canonical_release_observed'])
        report += '; exact actief=' + str(item['exact_release_active'])
        report += '; na procesherstart=' + str(item['same_release_after_process_restart'])
        report += '\nOntbrekend bewijs: ' + ', '.join(item['missing_evidence'])
        report += '\nConflicten: ' + ', '.join(item['identity_conflicts']) + '\n'
    (output / 'summary.txt').write_text(report)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError, BadZipFile, csv.Error, RuntimeError):
        # Paths and parser exception text can contain private source material.
        print('Incident export failed: check input schema, size and new output directory.', file=sys.stderr)
        sys.exit(2)
