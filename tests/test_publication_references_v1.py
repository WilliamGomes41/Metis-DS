"""Public, release-pinned behavior using native PostgreSQL and synthetic Blob bytes.

# release-control-evidence: scope/belofte
# release-control-evidence: toegang
# release-control-evidence: opslag concurrent stale recovery
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from examples.publication_reference_consumer import Lesson, apply_check
from src.integrity_kernel import stamp_canonical_hashes
from src.product_api_v1 import create_product_app
from src.publication.canonical_publication_postgres_v1 import CanonicalPublicationStoreError, PostgresCanonicalPublicationStore
from src.settings.api_access_v1 import CHECK_SCOPE, ApiAccessStoreError, PostgresApiAccessStore
from tests.test_product_api_postgres_authority_v1 import BlobAuthority, LOCATOR, SOURCE_SHA, _object, _paths

pytestmark = [pytest.mark.release_control_scope_belofte, pytest.mark.release_control_toegang,
              pytest.mark.release_control_opslag, pytest.mark.release_control_kwaliteit,
              pytest.mark.release_control_slop, pytest.mark.release_control_releasebewijs]

URL = "/v1/publication-references/check"
SCOPES = (CHECK_SCOPE, "knowledge:read", "retrieve", "updates:read")
DOCS = ("x", "y", "z", "context")
START = datetime(2026, 11, 1, tzinfo=timezone.utc)


class Scenario:
    def __init__(self, config, tmp_path):
        self.store = PostgresCanonicalPublicationStore(config)
        self.access = PostgresApiAccessStore(config)
        self.start = START
        self.blob = BlobAuthority()
        self.paths = _paths(tmp_path)
        self.client = self.open()
        self.user = self.issue()

    def open(self):
        return TestClient(create_product_app("real", paths=self.paths, api_access_mode="postgres",
                                             api_access_store=self.access, canonical_publication_store=self.store,
                                             immutable_source_store=self.blob))

    def issue(self, *, docs=DOCS, scopes=SCOPES, rpm=100):
        return self.access.provision_consumer(actor_id="test-publisher", tenant_name="Example",
            tenant_content_scope="RESOURCE_SET", tenant_document_ids=DOCS, tenant_scopes=SCOPES,
            tenant_requests_per_minute=200, tenant_max_top_k=10, application_name="LMS", environment="TEST",
            application_content_scope="RESOURCE_SET", application_document_ids=docs, application_scopes=scopes,
            application_requests_per_minute=rpm, application_max_top_k=5)

    def publish(self, doc, release, names, *, day=0, recovery=False, parent=False):
        objects = []
        for name in names:
            obj = _object()
            obj.update(object_id=name, document_id="context" if name == "parent" else doc)
            obj["source"]["source_checksum"] = SOURCE_SHA
            obj["provenance"]["source_fragments"] = [{"source_locator": {"locator_type": "page", "locator_value": "1"}}]
            if parent and name != "parent":
                obj["parent_object_id"] = "parent"
            objects.append(stamp_canonical_hashes(obj))
        self.store.persist_published_release(logical_document_id=doc, working_revision_id="work-"+release,
            snapshot_id="snap-"+doc, source_sha256=SOURCE_SHA, source_locator=LOCATOR, release_id=release,
            release_version=release, release_owner="test", published_at=(self.start+timedelta(days=day)).isoformat(),
            objects=objects, preserve_newer_registry=recovery)
        return [dict(origin="knowledge", release_id=release, knowledge_object_id=o["object_id"],
                     object_version=o["object_version"], content_hash=o["provenance"]["content_hash"]) for o in objects]

    def withdraw(self, doc, release, day=7):
        self.store.withdraw_logical_document(logical_document_id=doc, expected_release_id=release,
            actor="publisher", reason="private reason", withdrawn_at=(self.start+timedelta(days=day)).isoformat())

    def check(self, refs, user=None):
        return self.client.post(URL, json={"references": refs}, headers=self.headers(user))

    def headers(self, user=None):
        return {"Authorization": "Bearer "+(user or self.user).credential}

    def read(self, name):
        response = self.client.get("/v1/knowledge/"+name, headers=self.headers())
        assert response.status_code == 200, response.text
        payload = response.json()
        return {"origin": "knowledge", "release_id": payload["release"]["release_id"],
                **{k: payload[k] for k in ("knowledge_object_id", "object_version", "content_hash")}}


@pytest.fixture
def scenario(complete_postgres, tmp_path):
    return Scenario(complete_postgres, tmp_path)


def states(response):
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"api_version", "request_id", "observed_at", "results"}
    assert [r["index"] for r in data["results"]] == list(range(len(data["results"])))
    assert all(set(r) == {"index", "state"} for r in data["results"])
    return [r["state"] for r in data["results"]]


def test_seven_day_consumer(scenario):
    s = scenario
    with s.store._connect() as con:
        s.start = con.execute("SELECT now() - interval '7 days' AS start").fetchone()["start"]
    for doc in "xyz":
        s.publish(doc, doc+"1", [doc])
    refs = [s.read(doc) for doc in "xyz"]
    lessons = {k: Lesson(1, v) for k,v in {"A": (0,), "B": (1,), "C": (0,1), "D": (2,)}.items()}
    revisions = dict.fromkeys(lessons, 1)
    s.publish("x", "x2", ["new-x"], day=7)
    s.withdraw("y", "y1")
    response = s.check(refs)
    assert states(response) == ["superseded", "withdrawn", "active"]
    assert (datetime.fromisoformat(response.json()["observed_at"]) - s.start).days == 7
    assert apply_check(lessons, revisions, len(refs), response.json()) == {"A", "B", "C"}
    assert lessons["C"].causes == {0:"superseded", 1:"withdrawn"} and not lessons["D"].causes
    assert apply_check(lessons, revisions, len(refs), response.json()) == set()
    lessons["A"] = Lesson(2, (2,))
    apply_check(lessons, revisions, len(refs), response.json())
    assert lessons["A"].last_check is None
    assert s.client.get("/v1/updates", headers=s.headers()).status_code == 200


def test_exact_release_and_recovery(scenario):
    s = scenario
    old, = s.publish("x", "r1", ["same"])
    current, = s.publish("x", "r2", ["same"], day=3)
    imported, = s.publish("x", "recovery", ["other"], day=1, recovery=True)
    assert current["content_hash"] == old["content_hash"]
    refs = [current, old, imported, dict(old, content_hash="0"*64)]
    assert states(s.check(refs)) == ["active","superseded","unconfirmed","unconfirmed"]
    s.publish("x", "r3", ["same"], day=4)
    with s.store._connect() as con:
        con.execute("""DELETE FROM audit_events WHERE event_type='superseded'
                       AND COALESCE(details->>'superseded_by_release_id',details->>'release_id')='r2'""")
    assert states(s.check([old])) == ["unconfirmed"]


def test_scope_and_disclosure(scenario):
    s = scenario
    child, _ = s.publish("x", "r1", ["child", "parent"], parent=True)
    assert states(s.check([child])) == ["active"]
    s.withdraw("x", "r1")
    assert states(s.check([child])) == ["withdrawn"]
    for docs, scopes in [(("x",), SCOPES), (("z",), SCOPES), (DOCS, (CHECK_SCOPE, "retrieve"))]:
        user = s.issue(docs=docs, scopes=scopes)
        assert states(s.check([child,dict(child, release_id="unknown")],user)) == ["unconfirmed"]*2
    assert states(s.check([dict(child, origin="retrieve")],s.issue(scopes=(CHECK_SCOPE,"retrieve")))) == ["withdrawn"]
    assert s.check([child],s.issue(scopes=("knowledge:read",))).status_code == 403
    assert s.client.post(URL,json={"references":[child]}).status_code == 401
    s.access.revoke_credential(actor_id="test", tenant_id=s.user.tenant_id, application_id=s.user.application_id,
                               credential_id=s.user.credential_id)
    assert s.check([child]).status_code == 401


@pytest.mark.parametrize("order", ["forward","reverse"])
def test_publication_snapshot_during_cutover(scenario, monkeypatch, order):
    s = scenario
    old = s.publish("x", "r1", ["a","b"])
    if order == "reverse":
        old.reverse()
    read = s.store.active_publication_rows
    def during(*, connection):
        result = read(connection=connection)
        s.publish("x", "r2", ["new"], day=7)
        return result
    with monkeypatch.context() as m:
        m.setattr(s.store, "active_publication_rows", during)
        assert states(s.check(old)) == ["active","active"]
    assert states(s.check(old)) == ["superseded","superseded"]


def test_parallel_tenants(scenario):
    s = scenario
    ref, = s.publish("x","r1",["a"])
    s.withdraw("x","r1")
    denied = s.issue(docs=("z",))
    barrier = Barrier(2)
    def run(user):
        barrier.wait(timeout=10)
        return states(s.check([ref],user))
    with ThreadPoolExecutor(2) as pool:
        assert list(pool.map(run,[s.user,denied])) == [["withdrawn"],["unconfirmed"]]


@pytest.mark.parametrize("repeated", [False,True], ids=["revocation","unstable"])
def test_access_change_during_read(scenario, monkeypatch, repeated):
    s = scenario
    ref, = s.publish("x","r1",["a"])
    s.withdraw("x","r1")
    read = s.store.publication_reference_observation
    version = 1
    def during(selectors):
        nonlocal version
        result = read(selectors)
        if version == 1 or repeated:
            s.access.set_application_grant(actor_id="test",tenant_id=s.user.tenant_id, application_id=s.user.application_id,
                expected_version=version,content_scope="RESOURCE_SET",document_ids=["z"],scopes=SCOPES,
                requests_per_minute=100-version,max_top_k=5)
            version += 1
        return result
    monkeypatch.setattr(s.store,"publication_reference_observation",during)
    response = s.check([ref])
    if repeated:
        assert response.status_code == 503 and "results" not in response.json()
    else:
        assert states(response) == ["unconfirmed"]


@pytest.mark.parametrize("outage", ["postgres","blob","access"])
def test_authority_failure_and_restart(scenario, monkeypatch, outage):
    s = scenario
    x, = s.publish("x","r1",["a"])
    y, = s.publish("y","r2",["b"])
    s.withdraw("y","r2")
    def fail(*args,**kwargs):
        raise (ApiAccessStoreError if outage == "access" else CanonicalPublicationStoreError)("unavailable")
    with monkeypatch.context() as m:
        if outage == "blob":
            m.setattr(s.blob,"fail",True)
        elif outage == "postgres":
            m.setattr(s.store,"_connect",fail)
        else:
            m.setattr(s.access,"_connect",fail)
        response = s.check([x,y])
        assert response.status_code == 503 and "results" not in response.json()
    s.client = s.open()
    assert s.client.get("/v1/knowledge/b",headers=s.headers()).status_code == 404
    assert states(s.check([x,y])) == ["active","withdrawn"]


def test_limits_order_and_repeat(scenario):
    s = scenario
    ref, = s.publish("x","r1",["a"])
    unknown = dict(ref, release_id="unknown")
    for batch in ([ref,unknown,ref], [unknown,ref,unknown], [ref]*100):
        assert states(s.check(batch)) == ["active" if r == ref else "unconfirmed" for r in batch]
    for batch in ([], [ref]*101, [dict(ref, content_hash="invalid")]):
        assert s.check(batch).status_code == 422
    limited = s.issue(rpm=1)
    assert states(s.check([ref],limited)) == ["active"]
    throttled = s.check([ref],limited)
    assert throttled.status_code == 429 and int(throttled.headers["Retry-After"]) > 0


def test_check_does_not_mutate_publication_or_access(scenario):
    from tests.test_ko3_publication_membership import physical_state
    s = scenario
    ref, = s.publish("x","r1",["a"])
    s.withdraw("x","r1")
    before = physical_state(s.store), s.access.list_consumers()
    assert states(s.check([ref,ref])) == ["withdrawn","withdrawn"]
    assert (physical_state(s.store), s.access.list_consumers()) == before


def test_evidence_gate_rejects_missing_variant(tmp_path):
    from scripts.check_publication_reference_evidence import REQUIRED, require_cases
    import xml.etree.ElementTree as ET
    root = ET.Element("testsuite")
    for name in sorted(REQUIRED):
        ET.SubElement(root, "testcase", classname="tests.test_publication_references_v1", name=name)
    require_cases(root)
    root.remove(next(c for c in root if c.get("name") == "test_access_change_during_read[revocation]"))
    with pytest.raises(ValueError, match="revocation"):
        require_cases(root)
