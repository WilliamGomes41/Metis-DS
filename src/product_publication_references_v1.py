"""Public contract and authorization of exact, release-bound object references."""
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.object_taxonomy_v1 import serving_block_reason
from src.publication.publication_reference_read_v1 import PublicationObservation
from src.retrieval.retrieval_projection_v2 import build_projection

ORIGIN_SCOPE = {"knowledge": "knowledge:read", "retrieve": "retrieve"}


class PublicationReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: Literal["retrieve", "knowledge"]
    release_id: str = Field(min_length=1, max_length=512)
    knowledge_object_id: str = Field(min_length=1, max_length=512)
    object_version: str = Field(min_length=1, max_length=512)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    def selector(self):
        return self.release_id, self.knowledge_object_id, self.object_version, self.content_hash


class ReferenceBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    references: list[PublicationReference] = Field(min_length=1, max_length=100)


class ReferenceResult(BaseModel):
    index: int
    state: Literal["active", "superseded", "withdrawn", "unconfirmed"]


class ReferenceCheckResponse(BaseModel):
    api_version: str
    request_id: str
    observed_at: datetime
    results: list[ReferenceResult]


def visible_selectors(envelopes: list[dict], entitled: Callable, *, active: bool) -> set[tuple]:
    records, blocked = build_projection(envelopes)
    if active and blocked:
        raise ValueError("active publication projection invalid")
    documents = {row["knowledge_object"]["object_id"]: row["knowledge_object"]["document_id"]
                 for row in envelopes}
    visible = set()
    for record in records:
        md = record["metadata"]
        if not serving_block_reason(record) and entitled(record, documents):
            visible.add((md["release_id"], md["object_id"], md["object_version"], md["content_hash"]))
    return visible


def evaluate(observation: PublicationObservation, batch: ReferenceBatch, principal, entitled: Callable):
    visible_active = visible_selectors(observation.active, entitled, active=True)
    visible_history = set()
    for release in {key[0] for key, state in observation.states.items() if state != "active"}:
        visible_history.update(visible_selectors(observation.releases[release], entitled, active=False))
    results = []
    for index, reference in enumerate(batch.references):
        key = reference.selector()
        state = observation.states.get(key, "unconfirmed")
        visible = visible_active if state == "active" else visible_history
        if key not in visible or not principal.has_scope(ORIGIN_SCOPE[reference.origin]):
            state = "unconfirmed"
        results.append(ReferenceResult(index=index, state=state))
    return results
