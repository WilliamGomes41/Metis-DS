"""Child process shared by the current and pinned pre-D5 rollback checkout."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import uuid

from fastapi.testclient import TestClient
from src.canonical_publication_postgres_v1 import PostgresCanonicalConfig
from src.product_api_v1 import create_product_app
from src.review.review_ledger import read_events
from src.usage_ledger_v1 import UsageLedger
from src.settings import quality_evidence_v1
from src.workflows.workflow_badge_counts_postgres_v1 import (
    FastBadgePostgresCompleteWorkflowAzureAuthoritativePublicationConsole as Azure,
    FastBadgePostgresCompleteWorkflowDurablePublicationConsole as Durable,
)
from src.workflows.workflow_chain_recovery_v1 import PostgresWorkflowRecoveryAdapter
from tests.complete_workflow_support import complete_console
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_live_v1_working_v2_v1 import _complete_review
from tests.test_product_api_postgres_authority_v1 import _paths, _registry, KEY
from tests.test_vsa_publish_readiness_ui_v1 import MemorySourceStore


def main():
    payload = json.loads(Path(sys.argv[1]).read_text())
    root = Path(payload['root'])
    source = MemorySourceStore()
    source.blobs = {key: base64.b64decode(value) for key, value in payload['blobs'].items()}
    config = PostgresCanonicalConfig(dsn=os.environ['METIS_TEST_POSTGRES_DSN'])
    counters = {}
    def fixed_uuid():
        caller = sys._getframe(1)
        key = (Path(caller.f_code.co_filename).name, caller.f_code.co_name)
        counters[key] = counters.get(key, 0) + 1
        return uuid.UUID(hex=hashlib.sha256(repr((key, counters[key])).encode()).hexdigest()[:32])
    uuid.uuid4 = fixed_uuid
    quality_evidence_v1.uuid4 = fixed_uuid
    object_reads = []
    original_open = io.open
    def checked_open(file, mode='r', *args, **kwargs):
        if not isinstance(file, int) and Path(file).parent == root / 'runtime' / 'objects' and ('r' in mode or '+' in mode):
            object_reads.append(str(file))
        return original_open(file, mode, *args, **kwargs)
    io.open = checked_open
    console = complete_console(root, config, console_cls=Azure if payload['kind'] == 'azure' else Durable,
                               immutable_source_store=source)
    bind_fixture_selections(console)
    if payload['legacy']:
        # The pinned pre-D6a helper did not run ASGI startup itself.
        console.reconcile_durable_publications()
    if payload['legacy']:
        # Prove startup actually replaced the poisoned copies from PG, rather
        # than inferring that rebuilding happens from constructor source alone.
        runtime = root / 'runtime'
        envelopes = {row['snapshot_id']: row for row in console.workflow_document_store.list_envelopes()}
        copied = json.loads((runtime / 'envelopes.json').read_text())
        assert copied == envelopes, {sid: sorted(key for key in set(copied.get(sid, {})) | set(row)
            if copied.get(sid, {}).get(key) != row.get(key)) for sid, row in envelopes.items()}
        assert json.loads((runtime / 'publish_authorizations.json').read_text()) == console.workflow_review_store.read_bindings()
        ledger = [json.loads(line) for line in (runtime / 'review_ledger.jsonl').read_text().splitlines() if line.strip()]
        assert ledger == console.workflow_review_store.read_events()
        projection = [json.loads(line) for line in (runtime / 'published_projection.jsonl').read_text().splitlines() if line.strip()]
        assert projection == console._projection_from_authority()
        releases = 0
        for sid in envelopes:
            release = console._durable_release_for_snapshot(sid)
            if release is not None:
                manifest = runtime / 'release_manifests' / (release['release_id'] + '.json')
                assert json.loads(manifest.read_text()) == console._manifest_from_release(release)
                releases += 1
        assert releases == 2
    accounts, sid = payload['accounts'], payload['snapshot_id']
    _complete_review(console, reviewer_id=accounts['reviewer']['account_id'], snapshot_id=sid)
    result = console.publish(actor_id=accounts['publisher']['account_id'], snapshot_id=sid)
    assert result['status'] == 'PASS'
    app = create_product_app('real', paths=_paths(root), tenant_registry=_registry(),
                             canonical_publication_store=console.canonical_publication_store,
                             immutable_source_store=source,
                             usage_ledger=UsageLedger(root / (Path(sys.argv[2]).stem + "-usage.sqlite")))
    client = TestClient(app)
    api_calls = []
    def api():
        api_calls.append(1)
        response = client.get('/v1/documents', headers={'Authorization': f'Bearer {KEY}',
                                                     'X-Request-ID': f'd5-rollback-proof-{len(api_calls)}'})
        assert response.status_code == 200, response.text
        return response.json()
    published = api()
    assert published['documents']
    console.withdraw_document(actor_id=accounts['publisher']['account_id'], snapshot_id=sid,
                              expected_release_id=result['release_id'], reason='D5 rollback proof')
    withdrawn = api()
    assert not withdrawn['documents']
    state = PostgresWorkflowRecoveryAdapter(console.canonical_publication_store).export_state()
    assert read_events(console._ledger_path) == console.workflow_review_store.read_events()
    assert not object_reads, object_reads
    Path(sys.argv[2]).write_text(json.dumps({'state': state, 'published': published,
                                           'withdrawn': withdrawn, 'object_reads': object_reads}))


if __name__ == '__main__':
    main()
