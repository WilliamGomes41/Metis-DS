"""Verified immutable source views for one exact extraction.

Adapted from the immutable-carrier approach in #581/PR #582. The current
workflow extraction/input records remain authoritative; carriers are disposable.
No validation decision, actor permission or candidate is cached here.
"""
from copy import deepcopy
import json

from src.integrity_kernel import stable_hash

VERSION = 'prepared-source-views-v1'


def contract():
    from src.vorming.source_reconstruction_v1 import RECONSTRUCTION_VERSION
    from src.vorming.semantic_passage_v1 import SEMANTIC_PASSAGE_VERSION
    return {'version':VERSION,'reconstruction':RECONSTRUCTION_VERSION,
            'blocks':SEMANTIC_PASSAGE_VERSION,'filters':'semantic-fragment-filters-v1'}


def fail(code):
    from src.operations_console_v1 import ConsoleError
    raise ConsoleError(code)


class FrozenDict(dict):
    def _immutable(self,*args,**kwargs):
        fail('source_views_carrier_immutable')
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable
    def __deepcopy__(self,memo):
        return {k:deepcopy(v,memo) for k,v in self.items()}


class FrozenList(list):
    def _immutable(self,*args,**kwargs):
        fail('source_views_carrier_immutable')
    __setitem__ = __delitem__ = append = extend = insert = pop = remove = clear = sort = reverse = __iadd__ = __imul__ = _immutable
    def __deepcopy__(self,memo):
        return [deepcopy(v,memo) for v in self]


def freeze(value, _memo=None):
    if isinstance(value,(FrozenDict,FrozenList)):
        return value
    if not isinstance(value,(dict,list,tuple)):
        return value
    memo = {} if _memo is None else _memo
    if id(value) in memo:
        return memo[id(value)]
    if isinstance(value,dict):
        result = FrozenDict({k:freeze(v,memo) for k,v in value.items()})
    elif isinstance(value,list):
        result = FrozenList(freeze(v,memo) for v in value)
    else:
        result = tuple(freeze(v,memo) for v in value)
    memo[id(value)] = result
    return result


class SourceFragments(FrozenList):
    def __init__(self,root,name):
        self.root,self.name=root,name
        self.indices=tuple(root.payload['views'][name]['fragment_indices'])
        list.__init__(self,[root.raw[i] for i in self.indices])
        self.blocks=FrozenList((freeze(public),freeze(source)) for public,source in root.payload['views'][name]['blocks'])
        self.block_index=FrozenDict({public['block_id']:(public,source) for public,source in self.blocks})
        self.fragment_index=FrozenDict({row['fragment_id']:row for row in self})
    def __deepcopy__(self,memo):
        return self
    @property
    def extraction_record(self):
        return deepcopy(self.root.docling_record)
    def filtered(self,name):
        carrier = self.root.filters[(self.name,name)]
        if carrier is not None:
            return carrier
        fail('source_views_filter_incompatible')


class PreparedSource:
    def __init__(self,raw,payload,*,docling_record=None):
        if payload.get('version')!=VERSION or payload.get('contract')!=contract():
            fail('source_views_contract_mismatch')
        if payload.get('fragments_hash')!=stable_hash(raw):
            fail('source_views_fragment_mismatch')
        self.raw=freeze(raw)
        self.payload=freeze(payload)
        self.docling_record=deepcopy(docling_record)
        self.carriers={}
        try:
            if set(payload['views'])!={'full','content','candidate','evidence','evidence_content','headings'}:
                raise ValueError()
            from src.vorming.semantic_passage_v1 import _block_id
            raw_by_id={row['fragment_id']:row for row in raw}
            raw_ids=set(raw_by_id)
            if len(raw_by_id)!=len(raw):
                raise ValueError()
            for name,view in payload['views'].items():
                indices=view['fragment_indices']
                if indices!=sorted(set(indices)) or any(type(i) is not int or not 0<=i<len(raw) for i in indices):
                    raise ValueError()
                seen=set()
                for public,source in view['blocks']:
                    if (public['block_id'] in seen or public['text']!=source['clean_text']
                            or any(fid not in raw_ids for fid in public['source_fragment_ids'])):
                        raise ValueError()
                    if public['block_id']!=_block_id(source,public['text']):
                        raise ValueError()
                    cursor=0
                    for span in source.get('_raw_source_mapping',[]):
                        if span['start']!=cursor or not cursor<span['end']<=len(public['text']):
                            raise ValueError()
                        cursor=span['end']
                        if span.get('kind')=='join_separator':
                            if any(span[key] not in raw_ids for key in ('left_fragment_id','right_fragment_id')):
                                raise ValueError()
                        else:
                            original=raw_by_id[span['fragment_id']]
                            if not 0<=span['raw_start']<span['raw_end']<=len(original['raw_text']):
                                raise ValueError()
                    if source.get('_raw_source_mapping') and cursor!=len(public['text']):
                        raise ValueError()
                    seen.add(public['block_id'])
                self.carriers[name]=SourceFragments(self,name)
            # Six immutable views have at most 36 intersections. Resolve them
            # once instead of intersecting the complete source per candidate.
            self.filters = {}
            for name, carrier in self.carriers.items():
                for target, other in self.carriers.items():
                    selected = set(other.indices)
                    indices = tuple(i for i in carrier.indices if i in selected)
                    self.filters[(name,target)] = next(
                        (row for row in self.carriers.values() if row.indices == indices), None)
        except (KeyError,ValueError,IndexError,TypeError):
            fail('source_views_integrity_failed')
    @property
    def fragments(self):
        return self.carriers['full']


def prepare(raw):
    if isinstance(raw,SourceFragments):
        return raw.root
    from src.vorming.pre_review_semantic_v1 import _content_fragments,_candidate_fragments,_evidence_fragments
    from src.vorming.semantic_passage_v1 import _reconstructed_blocks
    rows=list(raw)
    variants={'full':rows,'content':_content_fragments(rows),'candidate':_candidate_fragments(rows),
              'evidence':_evidence_fragments(rows),'evidence_content':_content_fragments(_evidence_fragments(rows))}
    from src.object_taxonomy_v1 import extract_object_type
    variants['headings']=[row for row in rows if extract_object_type(row)[0]=='heading']
    positions={id(row):i for i,row in enumerate(rows)}
    payload={'version':VERSION,'contract':contract(),'fragments_hash':stable_hash(rows),'views':{}}
    identical={}
    for name,fragments in variants.items():
        indices=[positions[id(row)] for row in fragments]
        key=tuple(indices)
        if key not in identical:
            # Normalize each distinct view once. Serializing the whole payload
            # duplicates identical full/content/candidate views before freezing.
            identical[key]=json.loads(json.dumps(_reconstructed_blocks(fragments),ensure_ascii=False))
        payload['views'][name]={'fragment_indices':indices,'blocks':identical[key]}
    return PreparedSource(rows,payload,docling_record=getattr(raw,'extraction_record',None))


def preserve_fragments(fragments):
    return fragments if isinstance(fragments,SourceFragments) else list(fragments)


def filtered_view(fragments,name):
    return fragments.filtered(name) if isinstance(fragments,SourceFragments) else None


def stored_blocks(fragments):
    return fragments.blocks if isinstance(fragments,SourceFragments) else None


def stored_index(fragments,*,include_headings=False):
    if not isinstance(fragments,SourceFragments):
        return None
    carrier=fragments if include_headings else fragments.filtered('content')
    return carrier.block_index


def fragment_index(fragments):
    return fragments.fragment_index if isinstance(fragments,SourceFragments) else {r.get('fragment_id'):r for r in fragments}
