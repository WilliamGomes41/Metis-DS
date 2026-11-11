"""Closed human input/projection vocabulary; no storage or candidate creator."""
MODE = 'human-annotation-v1'
FIELDS_VERSION = 'human-source-bound-fields-v1'
CONTEXT_BINDING_FIELDS = {'population':'target_group_span', 'condition':'condition_span',
                        'actor':'actor_span', 'scope':'scope_span'}
CONTEXT_VERSION = 'human-source-bound-context-v1'
REFERENCE_KEY = 'human_annotation'
CORE_FIELDS = frozenset({'type_evidence_spans','recommendation_evidence_span','factual_claim_span',
                         'support_span','condition_span','exception_span'})
TYPE_CORE_FIELDS={'recommendation':'recommendation_evidence_span','factual_finding':'factual_claim_span',
                  'explanation':'support_span','condition':'condition_span','exception':'exception_span'}
ROLE_MAP = {'population':'target_group','context':'context','condition':'condition',
            'exception':'exception','explanation':'support','evidence':'support',
            'actor':'scope','scope':'scope','timing':'timing','list_introduction':'list_introduction',
            'row_header':'row_header','column_header':'column_header'}

