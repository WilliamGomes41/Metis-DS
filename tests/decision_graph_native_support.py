"""Native graph scenarios use the shared isolated DB and production composition."""
from src.publication.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore
from tests.decision_tree_test_support import install_fragment_proposer
from tests.production_support import production_application
from tests.test_durable_publication_console_v1 import MemorySourceStore


def native_state(tmp_path, config):
    store, source = PostgresCanonicalPublicationStore(config), MemorySourceStore()

    def state(node="default"):
        app = production_application(
            tmp_path, config, runtime=tmp_path / f"runtime-{node}",
            immutable_source_store=source, canonical_publication_store=store,
            processing_binder=install_fragment_proposer,
        )
        return app.state.operations_kernel
    return state, store, source


def receive_tree(console, actor, reviewer, title):
    from tests.test_v225_beslisboom_path import _boom_freeze_bytes
    return console.receive_source(actor_id=actor, class_='beslisboom', filename='boom.json',
        content_type='application/json', data=_boom_freeze_bytes(), title=title, version='1',
        family=title, date='2026-10-09', live_url='', ingest_kind='new',
        named_reviewers=[reviewer])['snapshot_id']
