"""Verify all recorded source blocks/mappings survive immutable-view roundtrip.

Reads evidence only. No PDF extraction, database writes or provider calls.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.vorming.prepared_source_views_v1 import prepare,PreparedSource
from src.vorming.pre_review_semantic_v1 import _candidate_fragments
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.semantic_replay_v1 import stable_json_hash
import src.vorming.source_reconstruction_v1 as reconstruction


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-zip',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    csv.field_size_limit(64000000)
    recorded_hash=None
    with ZipFile(args.evidence_zip) as archive:
        if 'validator_inputs.csv' in archive.namelist():
            rows=list(csv.DictReader(io.StringIO(archive.read('validator_inputs.csv').decode('utf-8-sig'))))
            data=json.loads(rows[0]['validator_input'])
            if 'attempt_diagnostics.csv' in archive.namelist():
                diagnostics=[json.loads(r['diagnostic']) for r in csv.DictReader(io.StringIO(archive.read('attempt_diagnostics.csv').decode('utf-8-sig')))]
                matching=next((d for d in diagnostics if (d.get('validator_input_ref') or {}).get('artifact_id')==rows[0]['artifact_id']),{})
                recorded_hash=((matching.get('semantic_identity') or {}).get('components') or {}).get('source_blocks_hash')
        else:
            rows=list(csv.DictReader(io.StringIO(archive.read('attempt_diagnostics.csv').decode('utf-8-sig'))))
            diagnostic=next(json.loads(row['diagnostic']) for row in rows if 'validator_input' in json.loads(row['diagnostic']))
            data=diagnostic['validator_input']
            recorded_hash=((diagnostic.get('semantic_identity') or {}).get('components') or {}).get('source_blocks_hash')
    expected={'source_blocks':semantic_source_blocks(_candidate_fragments(data['fragments'])),
              'evidence_blocks':semantic_source_blocks(data['evidence_fragments'])}
    root=prepare(data['evidence_fragments'])
    encoded=json.dumps(root.payload,ensure_ascii=False,separators=(',',':'))
    original=reconstruction._with_status
    def forbidden(*args,**kwargs):
        raise AssertionError('A verified source view may not reconstruct source again')
    reconstruction._with_status=forbidden
    try:
        restored=PreparedSource(data['evidence_fragments'],json.loads(encoded))
        actual={'source_blocks':semantic_source_blocks(restored.carriers['candidate']),
                'evidence_blocks':semantic_source_blocks(restored.carriers['evidence'])}
        assert actual==expected
        if recorded_hash is not None:
            assert stable_json_hash(actual)==recorded_hash
        assert list(restored.carriers['content'])==data['fragments']
    finally:
        reconstruction._with_status=original
    result={'fixture':'recorded Smetten validator input','validator_input_hash':stable_json_hash(data),
            'content_fragments':len(data['fragments']),'evidence_fragments':len(data['evidence_fragments']),
            'source_blocks_hash':stable_json_hash(actual),'historical_source_blocks_hash_verified':recorded_hash is not None,'source_blocks':len(actual['source_blocks']),
            'evidence_blocks':len(actual['evidence_blocks']),'all_source_blocks_and_mappings_equal':True,
            'roundtrip_with_reconstruction_forbidden':True,'derived_views_payload_bytes':len(encoded.encode()),
            'scope':'Recorded validator-source views, not raw PDF extraction, provider output or clinical acceptance'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
