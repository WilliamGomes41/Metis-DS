"""Researcher source selections, before candidate creation or review.

The workflow database owns every saved choice. Quotes are transient witnesses;
this module never creates candidate text, identities, review or publication.
"""
import hashlib
import json
from copy import deepcopy
from uuid import UUID

import regex

from src.integrity_kernel import stable_hash
from src.operations_console_v1 import ConsoleError
from src.object_taxonomy_v1 import CLOSED_OBJECT_TYPES
from src.vorming.semantic_passage_v1 import semantic_source_blocks
from src.vorming.source_preparation_context_v1 import SourceIdentity, extraction_record, extractor_contract, stored_extraction
from src.vorming.source_selection_v1 import authorize
from src.workflows.formation_task_store_v1 import FormationTaskStore
from src.workflows.workflow_documents_postgres_v1 import _json_text
from src.workflows.workflow_transaction_v1 import workflow_transaction

NORMALIZATION = 'metis-visible-prose-codepoints-v1'
ROLES = ('core', 'population', 'context', 'condition', 'exception', 'explanation', 'evidence',
         'actor','scope','timing','list_introduction','row_header','column_header')
EVIDENCE_FUNCTIONS = ('supported_by', 'explains')
STATUSES = ('draft', 'ready', 'uncertain', 'withdrawn')

# Source input names the designated core group, never inferred semantic fields.
CORE_FIELDS = frozenset({'type_evidence_spans','recommendation_evidence_span','factual_claim_span',
                         'support_span','condition_span','exception_span'})
TYPE_CORE_FIELDS = {'recommendation':'recommendation_evidence_span','factual_finding':'factual_claim_span',
                    'explanation':'support_span','condition':'condition_span','exception':'exception_span'}


def fail(code):
    raise ConsoleError(code)


def owns_source(console, snapshot_id):
    if not snapshot_id:
        return False
    with console.workflow_document_store._connect() as con:
        return con.execute('SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=%s', (snapshot_id,)).fetchone() is not None


def _identity(envelope):
    from dataclasses import asdict
    return asdict(SourceIdentity.from_envelope(envelope))


def _locked(console, con, actor_id, snapshot_id):
    # Same authorization-before-document lock order as publication/reprocessing.
    console.workflow_review_store._lock_authorizations(con)
    source = con.execute('SELECT snapshot_id,source_id,document_id,source_sha256 AS sha256,source_version AS version,'
        'content_kind,working_revision_id,logical_document_id FROM workflow.documents WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,)).fetchone()
    if source is None:
        fail('unknown_snapshot')
    envelope = console.workflow_document_store.get_envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    console._require_mutable_working_revision(snapshot_id, current=True)
    if any(value != envelope.get(key) for key,value in source.items()):
        fail('annotation_representation_stale')
    return envelope


def prepare(console, *, actor_id, snapshot_id, expected_revision):
    envelope = console._envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    console._require_mutable_working_revision(snapshot_id)
    if envelope['class'] == 'beslisboom':
        fail('annotation_prose_required')
    if owns_source(console, snapshot_id):
        return overview(console, actor_id=actor_id, snapshot_id=snapshot_id)
    if console.objects_revision(snapshot_id) != expected_revision:
        fail('annotation_objects_stale')
    source_path, _ = console._verified_source_bytes(envelope)
    # Long source/extractor I/O stays outside the shared PostgreSQL transaction.
    full = console._legacy_review_source_envelope(envelope)
    fragments = stored_extraction(full)
    if fragments is None:
        fragments = console._extract(envelope['content_kind'], source_path,
            document_id=envelope['document_id'], source_id=envelope['source_id'])
    record = full.get('prepared_source_extraction') or extraction_record(envelope, fragments, extractor_contract(envelope['content_kind']))
    semantic_source_blocks(fragments)  # Validate reconstruction before admitting input.
    store = console.workflow_document_store
    with workflow_transaction(store) as con:
        current = _locked(console, con, actor_id, snapshot_id)
        if (_identity(current) != _identity(envelope)
                or current['working_revision_id'] != envelope['working_revision_id']
                or current['logical_document_id'] != envelope['logical_document_id']
                or store.objects_revision(snapshot_id) != expected_revision):
            fail('annotation_objects_stale')
        if con.execute('SELECT 1 FROM workflow.annotation_sets WHERE snapshot_id=%s', (snapshot_id,)).fetchone():
            pass  # Another identical prepare won; use the authoritative pin.
        else:
            if store.current_document_objects(snapshot_id):
                fail('annotation_existing_work_requires_takeover')
            attempts = console._processing_history_envelope(snapshot_id).get('processing_attempts') or []
            if any(a.get('state') == 'running' for a in attempts):
                fail('annotation_processing_in_progress')
            FormationTaskStore(store)._immutable(con, 'prepared_extraction_versions', 'record_hash', record['record_hash'],
                ['snapshot_id'], [snapshot_id], record)
            con.execute('INSERT INTO workflow.annotation_sets(snapshot_id,working_revision_id,extraction_hash,source_identity,objects_revision,normalization,created_by) '
                'VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s)',
                (snapshot_id, current['working_revision_id'], record['record_hash'], _json_text(_identity(current)), expected_revision, NORMALIZATION, actor_id))
    return overview(console, actor_id=actor_id, snapshot_id=snapshot_id)


def _read_set(console, snapshot_id):
    with console.workflow_document_store._connect() as con:
        row = con.execute('SELECT s.*,e.payload AS extraction FROM workflow.annotation_sets s '
            'JOIN workflow.prepared_extraction_versions e ON e.record_hash=s.extraction_hash WHERE s.snapshot_id=%s', (snapshot_id,)).fetchone()
    if row is None:
        fail('annotation_source_not_prepared')
    fragments = stored_extraction({**row['source_identity'], 'prepared_source_extraction': row['extraction']})
    if row['extraction']['record_hash'] != row['extraction_hash'] or fragments is None:
        fail('annotation_representation_stale')
    return row, fragments


def _validate(selection, blocks):
    if not isinstance(selection, dict) or set(selection) - {'status','object_type','ranges','evidence_not_applicable','pending_range','field_evidence','recommendation_semantics','selection_version','disposition','required_links'}:
        fail('annotation_selection_invalid')
    status, kind = selection.get('status'), selection.get('object_type')
    disposition=selection.get('disposition')
    if disposition is not None:
        from src.vorming.source_accountability_v1 import ROLES as SOURCE_ROLES
        if not isinstance(disposition,dict) or set(disposition)!={'role','reason'} or kind is not None:
            fail('annotation_source_disposition_invalid')
        if any(disposition[key] is not None and not isinstance(disposition[key],str) for key in ('role','reason')):
            fail('annotation_source_disposition_invalid')
        if (disposition['role'] is not None and disposition['role'] not in SOURCE_ROLES
                or disposition['reason'] is not None and disposition['reason'] not in SOURCE_ROLES.get(disposition['role'],())):
            fail('annotation_source_disposition_invalid')
        if 'field_evidence' in selection or selection.get('recommendation_semantics') is not None or selection.get('evidence_not_applicable'):
            fail('annotation_source_disposition_invalid')
    if status not in STATUSES or (kind is not None and kind not in tuple(t for t in CLOSED_OBJECT_TYPES if t!='heading')):
        fail('annotation_selection_invalid')
    ranges = selection.get('ranges', [])
    if not isinstance(ranges, list) or len(ranges)>256:
        fail('annotation_selection_invalid')
    if type(selection.get('evidence_not_applicable', False)) is not bool:
        fail('annotation_selection_invalid')
    result, seen = [], set()
    for anchor in ranges:
        if not isinstance(anchor, dict) or set(anchor) - {'block_id','start','end','quote','role','required_for_meaning','evidence_function','relationship_id'}:
            fail('annotation_anchor_invalid')
        if not isinstance(anchor.get('block_id'),str):
            fail('annotation_anchor_invalid')
        block = blocks.get(anchor['block_id'])
        start, end, role = anchor.get('start'), anchor.get('end'), anchor.get('role')
        if block is None or type(start) is not int or type(end) is not int or not 0<=start<end<=len(block['text']):
            fail('annotation_anchor_invalid')
        boundaries = {0, *(match.end() for match in regex.finditer(r'\X', block['text']))}
        if start not in boundaries or end not in boundaries:
            fail('annotation_grapheme_boundary_invalid')
        exact = block['text'][start:end]
        if anchor.get('quote') != exact:
            fail('annotation_anchor_mismatch')
        if role not in ROLES or type(anchor.get('required_for_meaning', False)) is not bool:
            fail('annotation_role_invalid')
        function = anchor.get('evidence_function')
        if (role == 'evidence' and function not in EVIDENCE_FUNCTIONS) or (role != 'evidence' and function is not None):
            fail('annotation_evidence_function_required')
        key = (block['block_id'],start,end,role)
        if key in seen:
            fail('annotation_range_duplicate')
        seen.add(key)
        result.append({'block_id':block['block_id'],'start':start,'end':end,'role':role,
            'required_for_meaning': anchor.get('required_for_meaning',False), 'evidence_function':function,
            'quote_sha256':hashlib.sha256(exact.encode('utf-8')).hexdigest()})
        if 'relationship_id' in anchor:
            if role=='core' or not isinstance(anchor['relationship_id'],str) or len(anchor['relationship_id'])>1024:
                fail('annotation_relationship_invalid')
            result[-1]['relationship_id']=anchor['relationship_id']
    if status == 'ready':
        if selection.get('pending_range') is not None:
            fail('annotation_pending_range')
        if (kind is None and disposition is None) or not any(a['role']=='core' for a in result):
            fail('annotation_core_required')
        evidence = any(a['role']=='evidence' for a in result)
        if disposition is None and evidence == selection.get('evidence_not_applicable',False):
            fail('annotation_evidence_required')
        if disposition is not None and (disposition['role'] not in {'metadata','structure'} or not disposition['reason']
                or any(a['role']!='core' for a in result)):
            fail('annotation_source_disposition_unresolved')
    pending = selection.get('pending_range')
    if pending is not None:
        pending = _validate({'status':'draft','ranges':[pending]},blocks)['ranges'][0]
    payload={'status':status,'object_type':kind,'ranges':result,'pending_range':pending,
             'evidence_not_applicable':selection.get('evidence_not_applicable',False)}
    if any(a['role'] in ROLES[7:] or 'relationship_id' in a for a in [*result,*([pending] if pending else [])]):
        payload['selection_version']='human-annotation-input-v2'
    if 'required_links' in selection:
        links=selection['required_links']
        if not isinstance(links,list) or len(links)>256:
            fail('annotation_relationship_invalid')
        for link in links:
            if (not isinstance(link,dict) or set(link)!={'relationship_id','role','evidence_function','required_for_meaning','withdrawal_reason'}
                    or not isinstance(link['relationship_id'],str) or len(link['relationship_id'])>1024
                    or link['role'] not in ROLES[1:] or type(link['required_for_meaning']) is not bool
                    or link['role']=='evidence' and link['evidence_function'] not in EVIDENCE_FUNCTIONS
                    or link['role']!='evidence' and link['evidence_function'] is not None):
                fail('annotation_relationship_invalid')
            reason=link['withdrawal_reason']
            if link['required_for_meaning']:
                if reason is not None:
                    fail('annotation_relationship_invalid')
                if status=='ready':
                    fail('annotation_required_relationship_missing')
            elif not isinstance(reason,str) or not 1<=len(reason.strip())<=1000:
                fail('annotation_relationship_withdrawal_required')
        payload.update(required_links=[dict(link) for link in links],selection_version='human-annotation-input-v2')
    if disposition is not None:
        payload.update(disposition=dict(disposition),selection_version='human-annotation-input-v2')
    if 'field_evidence' in selection:
        from src.vorming.source_bound_fields_v3 import FIELDS
        from src.vorming.source_bound_fields_v3 import MISSING,TARGET_FIELDS,VIA_RELATION
        raw=selection['field_evidence']
        if not isinstance(raw,dict) or set(raw)!=set(FIELDS):
            fail('source_bound_fields_invalid')
        fields={}
        for field,evidence in raw.items():
            if isinstance(evidence,dict) and set(evidence)=={'core'} and evidence['core'] is True:
                if field not in CORE_FIELDS:
                    fail('human_field_core_not_allowed')
                fields[field]={'core':True}
            elif isinstance(evidence,dict) and set(evidence)<={'span','missing_reason','quote'} and set(evidence)>={'span','missing_reason'}:
                if evidence['span'] is None:
                    if evidence['missing_reason'] not in MISSING and not (field in TARGET_FIELDS and evidence['missing_reason']==VIA_RELATION):
                        fail('source_bound_missing_reason_required')
                    fields[field]={'span':None,'missing_reason':evidence['missing_reason']}
                else:
                    if evidence['missing_reason'] is not None:
                        fail('source_bound_field_invalid')
                    fields[field]={'span':_field_span(evidence['span'],evidence.get('quote'),blocks),'missing_reason':None}
            else:
                fail('source_bound_field_invalid')
        payload['selection_version']='human-annotation-input-v2'
        payload['field_evidence']=fields
    if 'recommendation_semantics' in selection:
        raw=selection['recommendation_semantics']
        if raw is not None:
            if not isinstance(raw,dict) or set(raw)!={'direction','direction_evidence','strength_status','strength','strength_evidence'}:
                fail('recommendation_semantics_invalid')
            if (kind not in {None,'recommendation'} or raw['direction'] not in (None,'for','against')
                    or raw['strength_status'] not in (None,'explicit','not_stated','unmapped')
                    or raw['strength'] not in (None,'strong','weak')):
                fail('recommendation_semantics_invalid')
            raw=dict(raw)
            for field in ('direction_evidence','strength_evidence'):
                if raw[field] is not None:
                    witness=raw[field]
                    if not isinstance(witness,dict) or set(witness)!={'span','quote'}:
                        fail('recommendation_semantics_invalid')
                    raw[field]=_field_span(witness['span'],witness['quote'],blocks)
        payload['selection_version']='human-annotation-input-v2'
        payload['recommendation_semantics']=raw
    if 'selection_version' in selection and selection['selection_version']!=payload.get('selection_version'):
        fail('annotation_client_contract_stale')
    return payload


def _field_span(span, quote, blocks):
    if not isinstance(span,dict) or set(span)!={'block_id','start','end'}:
        fail('annotation_anchor_invalid')
    anchor=_validate({'status':'draft','ranges':[{**span,'quote':quote,'role':'core'}]},blocks)['ranges'][0]
    return {key:anchor[key] for key in ('block_id','start','end')}


def relationship_id(annotation_id, anchor):
    return 'link-v1:'+json.dumps([annotation_id,anchor['role'],anchor['block_id'],anchor['start'],anchor['end']],ensure_ascii=False,separators=(',',':'))


def _relationship_history(previous, payload, annotation_id):
    if (previous and previous.get('field_evidence') is not None
            and payload['status']!='withdrawn' and payload.get('disposition') is None
            and 'field_evidence' not in payload):
        fail('annotation_client_contract_stale')
    def identity(anchor):
        return anchor.get('relationship_id') or relationship_id(annotation_id,anchor)
    ranges=[a for a in payload['ranges'] if a['role']!='core']
    if payload.get('selection_version'):
        for anchor in ranges:
            anchor.setdefault('relationship_id',identity(anchor))
    links=payload.get('required_links') or []
    bound={identity(a):a for a in ranges}
    open_links={a['relationship_id']:a for a in links}
    if len(bound)!=len(ranges) or len(open_links)!=len(links):
        fail('annotation_relationship_duplicate')
    identities=[*bound.items(),*open_links.items()]
    pending=payload.get('pending_range')
    if pending and 'relationship_id' in pending:
        identities.append((pending['relationship_id'],pending))
    for key,link in identities:
        try:
            parts=json.loads(key.removeprefix('link-v1:'))
            if (not key.startswith('link-v1:') or not isinstance(parts,list) or len(parts)!=5
                    or parts[0]!=annotation_id or parts[1]!=link['role'] or not isinstance(parts[2],str)
                    or type(parts[3]) is not int or type(parts[4]) is not int or not 0<=parts[3]<parts[4]):
                fail('annotation_relationship_invalid')
            if key!='link-v1:'+json.dumps(parts,ensure_ascii=False,separators=(',',':')):
                fail('annotation_relationship_invalid')
        except (ValueError,TypeError):
            fail('annotation_relationship_invalid')
    for key,link in open_links.items():
        if key in bound and (link['required_for_meaning'] or bound[key]['required_for_meaning']):
            fail('annotation_relationship_duplicate')
    if previous and payload['status']!='withdrawn':
        needed={identity(a) for a in previous['ranges'] if a['role']!='core' and a['required_for_meaning']}
        needed.update(a['relationship_id'] for a in previous.get('required_links') or [] if a['required_for_meaning'])
        retained={key for key,a in bound.items() if a['required_for_meaning']} | set(open_links)
        if not needed<=retained:
            fail('annotation_required_relationship_missing')


def save(console, *, actor_id, snapshot_id, command_id, annotation_id, expected_revision,
         expected_generation, extraction_hash, normalization, selection):
    if not isinstance(snapshot_id,str) or not 1<=len(snapshot_id)<=512 or '\x00' in snapshot_id:
        fail('annotation_command_invalid')
    authorize(console, actor_id, console._envelope(snapshot_id))
    if (not isinstance(command_id,str) or not 1<=len(command_id)<=128 or '\x00' in command_id
            or type(expected_revision) is not int or expected_revision<0
            or type(expected_generation) is not int or expected_generation<0):
        fail('annotation_command_invalid')
    try:
        if str(UUID(annotation_id)) != annotation_id:
            fail('annotation_command_invalid')
    except (ValueError,TypeError,AttributeError):
        fail('annotation_command_invalid')
    row, fragments = _read_set(console, snapshot_id)
    if extraction_hash != row['extraction_hash'] or normalization != NORMALIZATION:
        fail('annotation_representation_stale')
    payload = _validate(selection, {b['block_id']:b for b in semantic_source_blocks(fragments)})
    _relationship_history(None,payload,annotation_id)
    core = [{k:a[k] for k in ('block_id','start','end')} for a in payload['ranges'] if a['role']=='core']
    if core and payload.get('disposition') is None:
        from src.vorming.knowledge_materialisation_v1 import resolve_source_selection, MaterialisationError
        try:
            resolve_source_selection(core, fragments=fragments)
        except MaterialisationError as exc:
            raise ConsoleError('annotation_core_source_invalid') from exc
    request_hash = stable_hash({'actor_id':actor_id,'annotation_id':annotation_id,'expected_revision':expected_revision,
        'expected_generation':expected_generation,'extraction_hash':extraction_hash,'normalization':normalization,'selection':payload})
    with workflow_transaction(console.workflow_document_store) as con:
        current = _locked(console, con, actor_id, snapshot_id)
        active = con.execute('SELECT * FROM workflow.annotation_sets WHERE snapshot_id=%s FOR UPDATE', (snapshot_id,)).fetchone()
        if _identity(current) != active['source_identity'] or current['working_revision_id'] != active['working_revision_id']:
            fail('annotation_representation_stale')
        if console.workflow_document_store.objects_revision(snapshot_id) != active['objects_revision']:
            fail('annotation_objects_stale')
        receipt = con.execute('SELECT request_hash,result FROM workflow.annotation_commands WHERE snapshot_id=%s AND command_id=%s', (snapshot_id,command_id)).fetchone()
        if receipt:
            if receipt['request_hash'] != request_hash:
                fail('annotation_command_conflict')
            return receipt['result']
        head = con.execute('SELECT h.revision,h.position,v.payload FROM workflow.annotation_heads h JOIN workflow.annotation_versions v '
            'USING(snapshot_id,annotation_id,revision) WHERE h.snapshot_id=%s AND h.annotation_id=%s', (snapshot_id,annotation_id)).fetchone()
        if active['generation'] != expected_generation or (head['revision'] if head else 0) != expected_revision:
            fail('annotation_write_conflict')
        if head and head['payload'].get('selection_version') and payload.get('selection_version')!=head['payload']['selection_version']:
            fail('annotation_client_contract_stale')
        _relationship_history(head['payload'] if head else None,payload,annotation_id)
        revision, generation = expected_revision+1, expected_generation+1
        con.execute('INSERT INTO workflow.annotation_versions(snapshot_id,annotation_id,revision,status,author_id,payload,payload_hash) '
            'VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s)',
            (snapshot_id,annotation_id,revision,payload['status'],actor_id,_json_text(payload),stable_hash(payload)))
        con.execute('INSERT INTO workflow.annotation_heads(snapshot_id,annotation_id,revision,position) VALUES(%s,%s,%s,%s) '
            'ON CONFLICT(snapshot_id,annotation_id) DO UPDATE SET revision=EXCLUDED.revision',
            (snapshot_id,annotation_id,revision,head['position'] if head else generation))
        con.execute('UPDATE workflow.annotation_sets SET generation=%s WHERE snapshot_id=%s', (generation,snapshot_id))
        result = {'annotation_id':annotation_id,'revision':revision,'generation':generation,'status':payload['status']}
        con.execute('INSERT INTO workflow.annotation_commands(snapshot_id,command_id,actor_id,request_hash,result) VALUES(%s,%s,%s,%s,%s::jsonb)',
            (snapshot_id,command_id,actor_id,request_hash,_json_text(result)))
    return result


def validate_stored_selection(payload, *, fragments, annotation_id=None):
    """Check imported immutable input with the same source/role rules as save.

    Recovery has no live author decision to repeat. Rebuilding transient quote
    witnesses only validates the retained exact anchor; it never reanchors it.
    """
    blocks = {b['block_id']:b for b in semantic_source_blocks(fragments)}
    selection = deepcopy(payload)
    for anchor in [*selection['ranges'], *([selection['pending_range']] if selection.get('pending_range') else [])]:
        block = blocks.get(anchor['block_id'])
        if block is None:
            fail('annotation_representation_stale')
        anchor['quote'] = block['text'][anchor['start']:anchor['end']]
        anchor.pop('quote_sha256')
    for field in (selection.get('field_evidence') or {}).values():
        if field.get('span'):
            span=field['span'];field['quote']=blocks[span['block_id']]['text'][span['start']:span['end']]
    if selection.get('recommendation_semantics'):
        for key in ('direction_evidence','strength_evidence'):
            span=selection['recommendation_semantics'][key]
            if span:
                selection['recommendation_semantics'][key]={'span':span,'quote':blocks[span['block_id']]['text'][span['start']:span['end']]}
    if _validate(selection, blocks) != payload:
        fail('annotation_integrity_failed')
    if annotation_id is not None:
        rebuilt=deepcopy(payload)
        _relationship_history(None,rebuilt,annotation_id)
        if rebuilt!=payload:
            fail('annotation_integrity_failed')
    core = [{k:a[k] for k in ('block_id','start','end')} for a in payload['ranges'] if a['role']=='core']
    if core and payload.get('disposition') is None:
        from src.vorming.knowledge_materialisation_v1 import resolve_source_selection
        resolve_source_selection(core, fragments=fragments)


def overview(console, *, actor_id, snapshot_id):
    envelope = console._envelope(snapshot_id)
    authorize(console, actor_id, envelope)
    row, fragments = _read_set(console, snapshot_id)
    if _identity(envelope) != row['source_identity'] or envelope['working_revision_id'] != row['working_revision_id']:
        fail('annotation_representation_stale')
    blocks = semantic_source_blocks(fragments)
    raw = {f['fragment_id']:f for f in fragments}
    for block in blocks:
        block['locations'] = [{'page':raw[f].get('source_page'),'locator':raw[f].get('source_locator')}
            for f in block['source_fragment_ids'] if f in raw]
    by_id = {b['block_id']:b for b in blocks}
    # One statement captures heads and generation together, including two-tab writes.
    with console.workflow_document_store._connect() as con:
        capture = con.execute('SELECT s.generation,COALESCE(jsonb_agg(jsonb_build_object('
            "'annotation_id',v.annotation_id,'revision',v.revision,'author_id',v.author_id,'payload',v.payload,'payload_hash',v.payload_hash) "
            "ORDER BY h.position) FILTER (WHERE v.annotation_id IS NOT NULL),'[]'::jsonb) AS entries "
            'FROM workflow.annotation_sets s LEFT JOIN workflow.annotation_heads h USING(snapshot_id) '
            'LEFT JOIN workflow.annotation_versions v ON (v.snapshot_id,v.annotation_id,v.revision)=(h.snapshot_id,h.annotation_id,h.revision) '
            'WHERE s.snapshot_id=%s GROUP BY s.generation', (snapshot_id,)).fetchone()
    entries = capture['entries']
    for entry in entries:
        if stable_hash(entry['payload']) != entry.pop('payload_hash'):
            fail('annotation_integrity_failed')
        entry.update(entry.pop('payload'))
        for anchor in [*entry['ranges'], *([entry['pending_range']] if entry.get('pending_range') else [])]:
            block = by_id.get(anchor['block_id'])
            if block is None:
                fail('annotation_representation_stale')
            text = block['text'][anchor['start']:anchor['end']]
            if hashlib.sha256(text.encode('utf-8')).hexdigest()!=anchor['quote_sha256']:
                fail('annotation_integrity_failed')
            anchor['quote'] = text
    summary = {'snapshot_id':snapshot_id,'working_revision_id':row['working_revision_id'],
        'source_identity':row['source_identity'],'extraction_hash':row['extraction_hash'],
        'normalization':row['normalization'],'generation':capture['generation'],'entries':entries}
    summary['overview_hash'] = stable_hash(summary)
    return {**summary,'title':envelope['title'],'blocks':blocks,'objects_revision':console.objects_revision(snapshot_id)}
