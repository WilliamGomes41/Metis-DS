"""Run the same v3 ingest/restart/replay/export/failure proof in PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.test_workflow_transaction_v1 import workflow_postgres  # noqa: F401
from tests.test_review_batch_atomic_postgres import _console
from tests.test_recommendation_coverage_v1 import console_v3_story


def test_native_postgres_v3_restart_replay_export_and_failed_replacement(workflow_postgres, tmp_path):
    console_v3_story(tmp_path, lambda: _console(tmp_path, workflow_postgres))
