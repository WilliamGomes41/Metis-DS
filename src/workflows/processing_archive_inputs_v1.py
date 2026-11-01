"""Indexed intrinsic inputs from an exact retained archive, under its owner.

The complete original stays immutable. These are source inputs, never computed
human closure, authority or a substitute for current review/publication rules.
"""
from dataclasses import dataclass
from copy import deepcopy
import json

from src.workflows.processing_archives_v1 import encoded, digest, source_binding, TREE_FIELDS
from src.workflows.workflow_documents_postgres_v1 import WorkflowDocumentStoreError
from src.workflows.workflow_transaction_v1 import workflow_transaction_active


def fail(reason):
    raise WorkflowDocumentStoreError('processing_input_' + reason)


@dataclass(frozen=True)
class FormationAssessmentInput:
    replay: dict
    archive_id: str
    payload_hash: str
    source: dict

    def __post_init__(self):
        from src.vorming.prepared_source_views_v1 import freeze
        object.__setattr__(self, 'replay', freeze(deepcopy(self.replay)))
        object.__setattr__(self, 'source', freeze(deepcopy(self.source)))


def tree_card_inventory(inventory):
    if not isinstance(inventory,dict):
        return {'source_sha256':None,'items':None}
    items=inventory.get('items')
    if isinstance(items,dict):
        items={key:{**{k:value[k] for k in ('kind','bundle_id','bundle_role') if k in value},
            'literal_text_hash':digest(value['text']) if isinstance(value.get('text'),str) else None}
            for key,value in items.items()}
    return {'source_sha256':inventory.get('source_sha256'),'items':items}


def _parts(kind, value):
    if kind == 'semantic_replay':
        from src.vorming.semantic_replay_v1 import exact_replay_lookup, LOOKUP_HIT
        if exact_replay_lookup(value, expected_identity=value.get('identity') or {}).status != LOOKUP_HIT:
            fail('replay_invalid')
        meta = {k:value[k] for k in ('version','validation','formation_method','origin_execution',
            'semantic_execution','proposal_hash','replay_from_proposal_hash','replay_rejection_reason') if k in value}
        provider = value.get('provider_evidence') or {}
        intrinsic = {k:provider[k] for k in ('formation_incomplete','pending_rejections','task_policy','tasks',
            'task_plan_summary','formation_progress','formation_state') if k in provider}
        # Keep original stop/error observations, without provider requests or responses.
        calls = [provider, *(provider.get('supplementary_calls') or [])]
        intrinsic['supplementary_calls'] = [{k:c[k] for k in ('error_code','target_spans','failure_reason') if k in c}
                                          for c in calls if c.get('error_code')]
        return [('meta','0',None,meta), ('identity','0',None,value['identity']),
                ('proposal','0',None,value['proposal']), ('provider','0',None,intrinsic)]
    if kind == 'quality_processing_run':
        rows = [('meta','0',None,{k:value[k] for k in ('run_id','outcome','extractor_versions') if k in value})]
        for key in ('source_fragments','document_extraction'):
            if key in value:
                rows.append((key,'0',None,value[key]))
        rows += [('candidate',str(i).zfill(10),c.get('object_id'),c) for i,c in enumerate(value.get('candidates') or [])]
        return rows
    if kind=='tree_formation':
        rows=[(key,'0',None,value[key]) for key in sorted(TREE_FIELDS) if key in value]
        if 'decision_graph_evidence' in value:
            rows.append(('tree_card','0',None,tree_card_inventory(value['decision_graph_evidence'])))
        return rows
    fail('kind_unsupported')


class ProcessingArchiveInputs:
    def active_replay_input(self, envelope):
        """Complete selected replay for explicit worker/proof preparation only."""
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        pins=envelope.get('_document_inputs')
        if pins is None:
            return envelope.get('semantic_replay') or {}
        reference=pins.get('replay')
        if reference is None:
            if pins.get('formation_variant')=='semantic':
                fail('required_replay_missing')
            return {}
        return self.read_processing_archive(reference,envelope=envelope)

    def prepare_archive_inputs(self, reference, *, envelope):
        if workflow_transaction_active():
            fail('requires_independent_transaction')
        # Membership is derived from the actual owner record, never a caller's
        # self-consistent replacement manifest or projection of that record.
        value = self.read_processing_archive(reference, envelope=envelope)
        records = sorted((role,key,oid,digest(encoded(payload)),encoded(payload))
                         for role,key,oid,payload in _parts(reference['kind'], value))
        from src.workflows.formation_evidence_v1 import activation_replay
        header = {'layout':1,'archive_id':reference['archive_id'],'payload_hash':reference['payload_hash'],
                  'source':source_binding(envelope),'kind':reference['kind'],
                  'manifest':[[r,k,o,h] for r,k,o,h,_ in records]}
        if reference['kind'] == 'semantic_replay':
            header['activation_replay_hash'] = digest(encoded(activation_replay(value)))
            header['pending_rejection_count']=len((value.get('provider_evidence') or {}).get('pending_rejections') or [])
            header['notice'] = {'provider_evidence': {
                'formation_incomplete': (value.get('provider_evidence') or {}).get('formation_incomplete')}}
        if reference['kind']=='tree_formation':
            header['tree_route']=bool(value.get('decision_tree_formation'))
        if reference['kind']=='quality_processing_run':
            header['source_fragment_count']=len(value.get('source_fragments') or [])
        with self.documents._connect() as con:
            con.execute('INSERT INTO workflow.processing_archive_inputs(archive_id,header,header_hash) '
                'VALUES(%s,%s::jsonb,%s) ON CONFLICT DO NOTHING',
                (reference['archive_id'],encoded(header),digest(encoded(header))))
            current = con.execute('SELECT header,sealed FROM workflow.processing_archive_inputs '
                'WHERE archive_id=%s FOR UPDATE',(reference['archive_id'],)).fetchone()
            if current['header'] != header:
                fail('conflict')
            if not current['sealed']:
                with con.cursor() as cur:
                    cur.executemany('INSERT INTO workflow.processing_archive_input_members '
                        '(archive_id,role,member_key,object_id,payload_hash,payload_text) VALUES(%s,%s,%s,%s,%s,%s)',
                        [(reference['archive_id'],*row) for row in records])
                con.execute('UPDATE workflow.processing_archive_inputs SET sealed=true WHERE archive_id=%s',
                            (reference['archive_id'],))
        return reference

    def read_archive_inputs(self, reference, *, envelope, roles, object_ids=None):
        if (not isinstance(reference, dict) or type(reference.get('layout')) is not int
                or reference['layout'] != 1
                or set(reference) != {'layout','archive_id','kind','record_key','payload_hash'}):
            fail('reference_invalid')
        with self.documents._connect() as con:
            from src.workflows.processing_archives_v1 import HEADER, reference as archive_reference
            archive = con.execute('SELECT ' + HEADER + ' FROM workflow.processing_archives WHERE archive_id=%s',
                                  (reference['archive_id'],)).fetchone()
            if not archive:
                fail('missing')
            self._check_archive_header(archive, envelope=envelope)
            if archive_reference(archive) != reference:
                fail('reference_invalid')
            root = con.execute('SELECT header,header_hash,sealed FROM workflow.processing_archive_inputs '
                               'WHERE archive_id=%s',(reference['archive_id'],)).fetchone()
            if root is None:
                fail('missing')
            header = root['header']
            if (not root['sealed'] or digest(encoded(header)) != root['header_hash']
                    or header.get('layout') != 1 or header.get('source') != source_binding(envelope)
                    or header.get('kind') != reference.get('kind')
                    or header.get('archive_id') != reference['archive_id']
                    or header.get('payload_hash') != reference.get('payload_hash')):
                fail('integrity_failed')
            rows = con.execute('SELECT role,member_key,object_id,payload_hash,payload_text '
                'FROM workflow.processing_archive_input_members WHERE archive_id=%s AND role=ANY(%s) '
                + ('AND (role<>\'candidate\' OR object_id=ANY(%s)) ' if object_ids is not None else '')
                + 'ORDER BY role,member_key',
                ((reference['archive_id'],list(roles),list(object_ids)) if object_ids is not None
                 else (reference['archive_id'],list(roles)))).fetchall()
        expected = [m for m in header['manifest'] if m[0] in roles and (
            object_ids is None or m[0] != 'candidate' or m[2] in object_ids)]
        if [[r[k] for k in ('role','member_key','object_id','payload_hash')] for r in rows] != expected:
            fail('membership_incomplete')
        result = []
        for row in rows:
            if digest(row['payload_text']) != row['payload_hash']:
                fail('integrity_failed')
            value = json.loads(row['payload_text'])
            if encoded(value) != row['payload_text']:
                fail('integrity_failed')
            result.append((row['role'],row['member_key'],value))
        return result

    def formation_assessment_input(self, envelope):
        pins = envelope.get('_document_inputs')
        if not pins:
            return None  # Existing explicit legacy contract still owns this input.
        if pins.get('formation_variant') != 'semantic':
            fail('formation_variant_unsupported')
        reference = pins.get('replay')
        if reference is None:
            fail('required_replay_missing')
        parts = dict((role,value) for role,_,value in self.read_archive_inputs(reference,envelope=envelope,
            roles=('meta','identity','proposal','provider')))
        if set(parts) != {'meta','identity','proposal','provider'}:
            fail('membership_incomplete')
        replay = {**parts['meta'],'identity':parts['identity'],'proposal':parts['proposal'],
                  'provider_evidence':parts['provider']}
        from src.vorming.semantic_replay_v1 import exact_replay_lookup, LOOKUP_HIT
        if exact_replay_lookup(replay,expected_identity=replay['identity']).status != LOOKUP_HIT:
            fail('replay_invalid')
        # The full original replay, not only its proposal, is bound to the native
        # proof. Legacy adapters retain the original exact-lookup contract.
        proof_id = pins.get('proof_id')
        if proof_id is not None:
            with self.documents._connect() as con:
                proof = con.execute('SELECT header,sealed FROM workflow.formation_evidence_roots WHERE proof_id=%s',
                                    (proof_id,)).fetchone()
                archive_input = con.execute('SELECT header FROM workflow.processing_archive_inputs WHERE archive_id=%s',
                                            (reference['archive_id'],)).fetchone()
            if (not proof or not proof['sealed'] or proof['header']['source'] != source_binding(envelope)
                    or digest(encoded(proof['header'])) != proof_id
                    or not archive_input or proof['header']['activation_replay_hash']
                        != archive_input['header'].get('activation_replay_hash')
                    or not (reference == proof['header']['capture']['replay_ref']
                            or reference['payload_hash'] == proof['header']['activation_replay_hash'])):
                fail('proof_binding_failed')
        return FormationAssessmentInput(replay,reference['archive_id'],reference['payload_hash'],source_binding(envelope))
