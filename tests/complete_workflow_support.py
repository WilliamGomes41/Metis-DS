"""Production PostgreSQL composition, shared fixtures and canonical seeds."""
from tests.semantic_fixture_support import bind_fixture_selections
import json

import pytest
from src.integrity_kernel import compute_canonical_object_hash
from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowDurablePublicationConsole


def complete_console(root, config, console_cls=FastBadgePostgresCompleteWorkflowDurablePublicationConsole, **overrides):
    """Legacy call signature, one actual production composition underneath."""
    from src.workflows.workflow_badge_counts_postgres_v1 import FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole
    from tests.production_support import production_application
    from tests.decision_tree_test_support import install_fragment_proposer
    if console_cls not in (FastBadgePostgresCompleteWorkflowDurablePublicationConsole,
                           FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole):
        raise ValueError('Console tests require a production FastBadge PostgreSQL class')
    options = dict(source_store=root / 'sources', runtime=root / 'runtime')
    options.update(overrides)
    app = production_application(root, config,
        azure=console_cls is FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole,
        processing_binder=bind_fixture_selections, **options)
    return install_fragment_proposer(app.state.operations_kernel)


@pytest.fixture
def _isolated_console_postgres(monkeypatch, postgres_template):
    """Full schema in an owned disposable database; never reset the supplied DB.

    METIS_TEST_POSTGRES_DSN must identify a test server with CREATEDB rights.
    Failure to create the isolated database is a test failure, not a skip.
    """
    from tests.postgres_support import database
    dsn, template = postgres_template
    with database(dsn, template=template) as config:
        # Child-process proofs must connect to this same isolated authority.
        monkeypatch.setenv("METIS_TEST_POSTGRES_DSN", config.dsn)
        yield config


@pytest.fixture
def complete_postgres(_isolated_console_postgres):
    """Aliases share the same function-scoped database, including the factories."""
    return _isolated_console_postgres


def seed_canonical_release(store, *, snapshot_id, token):
    """Record a complete published release for one snapshot in canonical history.

    R+ publication truth is the canonical release (release, release items with a
    matching content hash, release_published audit event), not the envelope flag.
    """
    release_id, version, at = f"release-{token}", f"1.0-{token}", "2026-09-16T09:30:00+00:00"
    obj = {"object_id": f"obj-{token}", "object_version": "1", "document_id": f"doc-{token}",
           "confirmed_object_type": "unclassified", "text": "seeded published object"}
    content_hash = compute_canonical_object_hash(obj)
    with store._connect() as con:
        con.execute(
            "INSERT INTO canonical_object_versions(object_id,object_version,document_id,object_type,"
            "validation_status,source_checksum,content_hash,canonical_json) "
            "VALUES(%s,'1',%s,'unclassified','approved','seed',%s,%s::jsonb)",
            (obj["object_id"], obj["document_id"], content_hash, json.dumps(obj)),
        )
        con.execute(
            "INSERT INTO publication_releases(release_id,release_version,release_owner,status,created_at,published_at) "
            "VALUES(%s,%s,'publisher','published',%s,%s)",
            (release_id, version, at, at),
        )
        con.execute(
            "INSERT INTO publication_release_items(release_id,object_id,object_version,content_hash) VALUES(%s,%s,'1',%s)",
            (release_id, obj["object_id"], content_hash),
        )
        con.execute(
            "INSERT INTO audit_events(entity_type,entity_id,entity_version,event_type,actor,event_at,details) "
            "VALUES('release',%s,%s,'release_published','publisher',%s,%s::jsonb)",
            (release_id, version, at, json.dumps({"snapshot_id": snapshot_id})),
        )
    return release_id
