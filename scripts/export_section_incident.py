#!/usr/bin/env python3
"""Join a browser probe with normalized JSON arrays or JSONL diagnostic events."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

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
    parser.add_argument('--browser', required=True)
    parser.add_argument('--application')
    parser.add_argument('--platform')
    parser.add_argument('--output', required=True, help='New output directory; never overwritten')
    args = parser.parse_args()
    hashes = {}
    probe, hashes['browser'] = read(args.browser)
    app, platform = [], []
    if args.application:
        app, hashes['application'] = read(args.application, events=True)
    if args.platform:
        platform, hashes['platform'] = read(args.platform, events=True)
    result = build_incident(probe, app, platform)
    result['input_sha256'] = hashes
    result['snapshot_consistency'] = 'independent_observations_not_atomic'
    output = Path(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / 'incident.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    (output / 'summary.txt').write_text(summary(result))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, TypeError):
        # Paths and parser exception text can contain private source material.
        print('Incident export failed: check input schema, size and new output directory.', file=sys.stderr)
        sys.exit(2)
