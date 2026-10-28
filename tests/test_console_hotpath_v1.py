"""Regression proof for the Documenten/Review interactive hot path.

# release-control-evidence: scope/belofte
# release-control-evidence: opslag concurrent stale
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from __future__ import annotations
from tests.semantic_fixture_support import bind_fixture_selections

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport

from src.azure_postgres_credential_v1 import CachedAzurePostgresCredential
from src.publication.canonical_publication_postgres_v1 import (
    PostgresCanonicalConfig,
    PostgresCanonicalPublicationStore,
)
from src.documents.document_status_ui_v1 import install_document_status_ui
from src.operations_console_app import create_console_app
from src.operations_console_v1 import OperationsConsole
from src.review.review_workboard_v1 import install_review_workboard
from src.workflows.workflow_badge_counts_postgres_v1 import _PostgresBadgeCountsMixin
from src.workflows.workflow_documents_postgres_v1 import PostgresWorkflowDocumentStore


pytestmark = [
    pytest.mark.release_control_scope_belofte,
    pytest.mark.release_control_opslag,
    pytest.mark.release_control_toegang,
    pytest.mark.release_control_kwaliteit,
    pytest.mark.release_control_slop,
    pytest.mark.release_control_releasebewijs,
]


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)


class _CanonicalConnection:
    def __init__(self, owner: "_CanonicalStore") -> None:
        self.owner = owner

    def __enter__(self) -> "_CanonicalConnection":
        self.owner.connect_calls += 1
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def execute(self, sql: str, params: tuple[Any, ...]) -> _Result:
        self.owner.execute_calls += 1
        if self.owner.fail:
            raise RuntimeError("canonical unavailable")
        assert "release_published" in sql
        candidates = set(str(value) for value in params[0])
        return _Result(
            [{"snapshot_id": value} for value in sorted(candidates & self.owner.published)]
        )


class _CanonicalStore:
    def __init__(self, published: set[str], *, fail: bool = False) -> None:
        self.published = set(published)
        self.fail = fail
        self.connect_calls = 0
        self.execute_calls = 0

    def _connect(self) -> _CanonicalConnection:
        return _CanonicalConnection(self)


class _TreeBase:
    def __init__(self, canonical: _CanonicalStore) -> None:
        self.canonical_publication_store = canonical
        self.fallback_publication_calls = 0

    def family_tree(self) -> dict[str, Any]:
        return {
            "families": {
                "hotpath": {
                    "children": [
                        {"snapshot_id": "snap-published"},
                        {"snapshot_id": "snap-unpublished"},
                    ]
                }
            }
        }

    def snapshot_is_published(self, _snapshot_id: str) -> bool:
        self.fallback_publication_calls += 1
        return False


class _TreeSubject(_PostgresBadgeCountsMixin, _TreeBase):
    def _document_reads(self):
        return None

    pass


def test_tree_batches_publication_history_once_then_uses_prefetched_truth() -> None:
    canonical = _CanonicalStore({"snap-published"})
    subject = _TreeSubject(canonical)

    tree = subject.family_tree()
    assert len(tree["families"]["hotpath"]["children"]) == 2
    assert canonical.connect_calls == 1
    assert canonical.execute_calls == 1

    assert subject.snapshot_is_published("snap-published") is True
    assert subject.snapshot_is_published("snap-unpublished") is False
    assert subject.fallback_publication_calls == 0

    # The request-local batch is exhausted after all tree cards consume it.
    assert subject.snapshot_is_published("snap-published") is False
    assert subject.fallback_publication_calls == 1


def test_tree_publication_prefetch_fails_closed_for_delete_affordance() -> None:
    canonical = _CanonicalStore(set(), fail=True)
    subject = _TreeSubject(canonical)

    subject.family_tree()
    assert canonical.connect_calls == 1
    assert canonical.execute_calls == 1
    assert subject.snapshot_is_published("snap-published") is True
    assert subject.snapshot_is_published("snap-unpublished") is True
    assert subject.fallback_publication_calls == 0


class _Token:
    def __init__(self, value: str, expires_on: int) -> None:
        self.token = value
        self.expires_on = expires_on


class _RawCredential:
    def __init__(self) -> None:
        self.calls = 0

    def get_token(self, *_scopes: str, **_kwargs: Any) -> _Token:
        self.calls += 1
        return _Token(f"token-{self.calls}", int(time.time()) + 3600)


def test_shared_cached_credential_avoids_token_request_per_connect(monkeypatch: Any) -> None:
    raw = _RawCredential()
    cached = CachedAzurePostgresCredential(raw)
    config = PostgresCanonicalConfig(host="postgres.test", database="metis", user="metis")
    connect_calls: list[dict[str, Any]] = []

    def fake_connect(*_args: Any, **kwargs: Any) -> object:
        connect_calls.append(dict(kwargs))
        return object()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    canonical = PostgresCanonicalPublicationStore(config, credential=cached)
    workflow = PostgresWorkflowDocumentStore(config, credential=cached)

    canonical._connect()
    workflow._connect()
    canonical._connect()

    assert len(connect_calls) == 3
    assert raw.calls == 1
    assert {call["password"] for call in connect_calls} == {"token-1"}


@pytest.fixture
def hotpath(production_console,production_app,monkeypatch):
    from collections import Counter
    from functools import wraps
    from types import SimpleNamespace
    from tests.complete_workflow_support import seed_canonical_release
    console=production_console(processing_binder=bind_fixture_selections)
    author=console.create_account(username='author',password='fixture-password',roles=['researcher'])
    reviewer=console.create_account(username='reviewer',password='fixture-password',roles=['reviewer'])
    snapshots=[]
    for index,title in enumerate(['Published fixture','Unpublished fixture']):
        data=('<html><h1>'+title+'</h1>'+''.join(
            f'<p>Een observatie {index}-{j} is een systematische waarneming.</p>' for j in range(205))+'</html>').encode()
        snapshots.append(console.ingest(actor_id=author['account_id'],filename=f'fixture-{index}.html',data=data,
            content_type='text/html',ingest_kind='new',title=title,version='1',date='2026-10-20',live_url='',
            class_='richtlijn',family='hotpath',named_reviewers=[reviewer['account_id']])['snapshot_id'])
    assert sum(len(console.workflow_document_store.list_document_objects(sid)) for sid in snapshots)>=410
    seed_canonical_release(console.canonical_publication_store,snapshot_id=snapshots[0],token='hotpath')
    expected=console.review_workboard_summaries(reviewer['account_id'],snapshots[1])[snapshots[1]]
    calls=Counter()
    single_reads=[]
    def spy(owner,name,label):
        real=getattr(owner,name)
        @wraps(real)
        def observe(*args,**kwargs):
            key=label+('_navigation' if kwargs.get('navigation_only') else '')
            calls[key]+=1
            if label=='single_objects':single_reads.append(args[0])
            return real(*args,**kwargs)
        monkeypatch.setattr(owner,name,observe)
    for name,label in [('list_document_lifecycle_statuses','statuses'),('review_workboard_summaries','summaries'),
                       ('snapshot_objects_and_revision','snapshot_api'),('_published_snapshot_ids','publication_fallback')]:
        spy(console,name,label)
    spy(console.workflow_document_store,'list_document_objects','single_objects')
    spy(console.workflow_document_store,'list_current_objects_batch','bulk_objects')
    def forbidden_readiness(*args,**kwargs):
        raise AssertionError('List presentation must not run full publication readiness')
    monkeypatch.setattr(console,'document_readiness',forbidden_readiness)
    monkeypatch.setattr(console,'publication_readiness',forbidden_readiness)
    app=production_app(console)
    def client_for(username='reviewer'):
        client=TestClient(app,base_url='https://testserver')
        assert client.post('/login',data={'username':username,'password':'fixture-password'},follow_redirects=False).status_code==303
        return client
    client=client_for()
    calls.clear(); single_reads.clear()
    return SimpleNamespace(console=console,client=client,client_for=client_for,app=app,
                           calls=calls,single_reads=single_reads,snapshots=snapshots,summary=expected)


def test_authenticated_tree_and_review_gets_use_production_list_installers(hotpath):
    h=hotpath
    tree=h.client.get('/tree')
    assert tree.status_code==200
    assert 'Published fixture' in tree.text and 'Unpublished fixture' in tree.text
    assert h.calls['statuses']==1 and h.calls['snapshot_api']==0 and h.calls['single_objects']==0,dict(h.calls)
    assert h.calls['publication_fallback']==0,dict(h.calls)
    assert h.calls['bulk_objects']<=1,dict(h.calls)
    h.calls.clear();h.single_reads.clear()
    review=h.client.get('/review')
    assert review.status_code==200
    assert 'Published fixture' in review.text and 'Unpublished fixture' in review.text
    assert 'data-personal-group=' in review.text
    assert review.text.count('data-workboard-document=')==2
    assert h.calls['statuses']==1 and h.calls['summaries']==1,dict(h.calls)
    assert h.calls['snapshot_api']==0 and h.calls['single_objects']==0,dict(h.calls)
    assert h.calls['bulk_objects']<=2,dict(h.calls)


def test_review_default_document_dashboard_uses_projection_without_snapshot_read(hotpath):
    h=hotpath
    review=h.client.get('/review',params={'document':h.snapshots[1]})
    assert review.status_code==200 and 'Unpublished fixture' in review.text
    assert 'Reviewvoortgang' not in review.text
    # The counts come from the projection; which passages start as handled is formation output.
    assert h.summary['progress_total']>=205 and h.summary['progress_done']<h.summary['progress_total']
    assert "bronpassages afgehandeld" not in review.text
    assert 'data-workboard-document=' in review.text
    assert h.calls['snapshot_api']==0 and h.calls['single_objects']==0,dict(h.calls)


def test_review_task_detail_keeps_one_bounded_selected_snapshot_read(hotpath):
    h=hotpath
    review=h.client.get('/review',params={'document':h.snapshots[1],'task':'headings'})
    assert review.status_code==200 and 'Unpublished fixture' in review.text
    assert h.calls['statuses']==1 and h.calls['snapshot_api']==1,dict(h.calls)
    assert set(h.single_reads)=={h.snapshots[1]},h.single_reads
    assert len(h.single_reads)==1,h.single_reads


def test_status_middleware_slow_sync_read_does_not_block_event_loop(hotpath,monkeypatch):
    h=hotpath
    started,release=threading.Event(),threading.Event()
    real=h.console.session_account
    def slow(token):
        started.set()
        assert release.wait(timeout=2)
        return real(token)
    monkeypatch.setattr(h.console,'session_account',slow)
    token=h.client.cookies.get('console_session')
    async def run():
        transport=ASGITransport(app=h.app)
        async with httpx.AsyncClient(transport=transport,base_url='https://testserver',cookies={'console_session':token}) as client:
            tree_task=asyncio.create_task(client.get('/tree'))
            for _ in range(80):
                if started.is_set():break
                await asyncio.sleep(0.01)
            assert started.is_set()
            t0=time.perf_counter()
            try:
                login=await client.get('/login')
                elapsed=time.perf_counter()-t0
            finally:
                release.set()
            tree=await tree_task
        assert login.status_code==200 and tree.status_code==200
        assert elapsed<0.25,f'Lightweight request waited {elapsed:.3f}s'
        assert h.calls['statuses']==1,dict(h.calls)
    asyncio.run(run())


def test_status_offload_preserves_tree_publication_batch_context(hotpath,monkeypatch):
    h=hotpath
    author=h.client_for('author')
    token=author.cookies.get('console_session')
    real=h.console.family_tree
    seen=[]
    def observed_tree():
        batch=h.console._tree_publication_batch.get()
        assert batch is not None
        assert batch[0]==frozenset(h.snapshots) and batch[1]==frozenset({h.snapshots[0]})
        seen.append(batch)
        return real()
    def forbidden_fallback(*args,**kwargs):
        raise AssertionError('The route worker lost the middleware publication prefetch')
    monkeypatch.setattr(h.console,'family_tree',observed_tree)
    monkeypatch.setattr(h.console,'_published_snapshot_ids',forbidden_fallback)
    async def run():
        transport=ASGITransport(app=h.app)
        async with httpx.AsyncClient(transport=transport,base_url='https://testserver',cookies={'console_session':token}) as client:
            response=await client.get('/tree')
        assert response.status_code==200,response.text
        assert 'Published fixture' in response.text and 'Unpublished fixture' in response.text
    asyncio.run(run())
    assert len(seen)==1 and h.calls['statuses']==1,dict(h.calls)
