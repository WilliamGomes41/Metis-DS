"""Real HTTP/PostgreSQL app; controlled output replaces only external model I/O."""
import json
import time
from src.operations_console_v1 import ConsoleError
from src.vorming import human_annotation_suggestion_v1 as suggestions
from tests.browser_human_annotation_fixture import app
from tests.test_annotation_suggestions import proposal, provider


def controlled_transport(url, headers, payload, limits):
    selected = json.loads(payload['input'][1]['content'])['selected']
    text = selected[0]['text']
    time.sleep(1)
    if 'Foutvoorbeeld' in text:
        raise ConsoleError('pre_review_llm_timeout')
    if 'De huid is droog' in text:
        raw = proposal(subject_span='De huid', predicate_span='is', defined_term='De huid',
                       definiens_span='droog en de huid is rood.', type_evidence_spans=text)
        raw['object_type'] = 'definition'
        return provider(raw)
    raw = proposal(subject_span='Het zorgplan', predicate_span='is', defined_term='Het zorgplan',
                   definiens_span='een overzicht van afspraken.', type_evidence_spans=text)
    raw['object_type'] = 'definition'
    return provider(raw)


# Production endpoint and binders execute unchanged, no mocked API or persistence.
import os
os.environ['METIS_LLM_API_KEY'] = 'synthetic-browser-test-key'
os.environ['METIS_LLM_MODEL'] = 'synthetic-browser-model'
suggestions.logged_post_json = controlled_transport
