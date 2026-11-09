"""HA-4 helper relocation preserves the pre-move envelope and human build output.

Hashes were captured from c985eaf376f4c686851f198f526510ca32e98b9e,
before moving document_spec; they are compatibility evidence, not clinical acceptance.

# release-control-evidence: scope/belofte
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from copy import deepcopy
import hashlib
import json
from uuid import UUID

import pytest

pytestmark = pytest.mark.pure_function


@pytest.mark.parametrize("arguments, expected_hash", [
    (dict(document_id="empty", title="Leeg document", family="test", class_="richtlijn",
          content_kind="html", units=[]),
     "7f0009d0ba1501665b39b9849d4e29991acc265ed8ab82031f3b3cedd823a9fd"),
    (dict(document_id="human", title="Zorg — patiënt", family="huid", class_="richtlijn",
          content_kind="pdf", units=[dict(object_id="human-claim", object_type="explanation",
              text="De huid is droog.", source_fragment_ids=["p1", "p2"],
              metadata={"human_annotation": {"annotation_id": "annotation-1", "revision": 2},
                        "condition": "Alleen bij jeuk."})]),
     "4a9e89d1166af7ce7d17115f57b59377d06223845499830c1f1ab686eb58226b"),
    (dict(document_id="model", title="Bronselectie", family="test", class_="richtlijn",
          content_kind="html", units=[
              dict(object_id="model-core", object_type="recommendation", text="Beoordeel de huid.",
                   semantic_passage={"selection_origin": "model_proposal"}),
              dict(object_id="model-source", object_type="source_context", text="Bij klachten.", relations=[])]),
     "b073f279edaeb7690b45227da0cfaacba20873b2d77bd35d337423c771efeeba"),
])
def test_document_envelope_keeps_pre_move_hash_and_candidate_objects(arguments, expected_hash):
    from src.vorming.document_spec_v1 import document_spec

    before = deepcopy(arguments)
    result = document_spec(**arguments)
    encoded = json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert hashlib.sha256(encoded).hexdigest() == expected_hash
    assert arguments == before
    assert all(actual is candidate for actual, candidate in zip(result["objects"][1:], arguments["units"]))


def test_human_build_does_not_use_legacy_envelope_helper_and_keeps_object_hash(monkeypatch):
    from src.integrity_kernel import stable_hash
    from src.vorming.human_annotation_materialisation_v1 import build_objects
    from src.vorming import pre_review_semantic_v1 as legacy
    from tests import test_human_annotation_materialisation as fixtures
    from tests.test_human_annotation_preview import stored

    monkeypatch.setattr(fixtures, "uuid4", lambda: UUID("00000000-0000-0000-0000-000000000001"))
    fragments, entry = stored()
    seal = {"context": {"document_id": "human", "title": "Menselijke opbouw", "family": "test",
        "class": "richtlijn", "content_kind": "html", "source_id": "source-human",
        "sha256": "a" * 64, "version": "1.0", "date": "2026-11-09"}}

    def retired_helper(**kwargs):
        raise AssertionError("human build still calls the old module's document_spec")

    monkeypatch.setattr(legacy, "document_spec", retired_helper)
    result = build_objects(seal, [entry], fragments=fragments)
    assert stable_hash(result) == "876dd40c5ccbadabc35559fd15ab51f49e32b131bb261bb63472fa892261c859"
