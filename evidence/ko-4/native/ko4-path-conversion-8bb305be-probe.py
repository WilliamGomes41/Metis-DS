"""One bounded native reachability probe, independent of the implementation owner."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from src.operations_console_v1 import ConsoleError
from src.review.knowledge_object_state_v1 import is_knowledge_object
from src.review.review_duty_v1 import authoritative_review_type
from tests.test_v225_beslisboom_path import _console, _accounts, _ingest_boom
from tests.ko4_native_adversary_tmp import state


def test_real_boom_path_to_node_missing_answers(tmp_path, production_console):
    console = _console(tmp_path, production_console=production_console)
    accounts = _accounts(console)
    sid = _ingest_boom(console, accounts)['snapshot_id']
    target = next(o for o in console.snapshot_objects(sid) if authoritative_review_type(o) == 'path')
    assert not is_knowledge_object(target, 'boom')
    revision = console.objects_revision(sid)
    before = state(console, sid)
    output = {'sha': '8bb305be63e95712a51d2a719f95cd431978ce66', 'before_type': target['object_type'], 'before_authoritative_type': authoritative_review_type(target),
              'before_version': target['object_version'], 'input_assessment': None, 'input_na': False}
    try:
        console.review_object(actor_id=accounts['reviewer']['account_id'], snapshot_id=sid,
            object_id=target['object_id'], decision='approve', confirmed_object_type='node',
            type_action='type_wijzigen', expected_revision=revision)
    except ConsoleError as refused:
        output.update(result='REFUSED', code=refused.code, message=str(refused), unchanged=state(console, sid) == before)
        Path('/tmp/ko4-path-conversion-result.json').write_text(json.dumps(output, indent=2))
        assert output['unchanged'] is True
        print(json.dumps(output))
        return
    saved = next(o for o in console.snapshot_objects(sid) if o['object_id'] == target['object_id'])
    binding = [b for b in console.object_review_bindings(sid) if b['object_id'] == target['object_id'] and b.get('valid')]
    output.update(result='APPROVED', after_type=saved['object_type'], after_version=saved['object_version'],
        after_is_ko=is_knowledge_object(saved, 'boom'), governance=saved['governance'], bindings=binding,
        events_added=len(state(console, sid)['events'])-len(before['events']))
    Path('/tmp/ko4-path-conversion-result.json').write_text(json.dumps(output, indent=2))
    print(json.dumps(output))
    assert not (saved['governance']['validation_status'] == 'approved' and is_knowledge_object(saved, 'boom')), \
        'Native path-to-node approval bypassed required answers/evidence by checking only current non-KO'
