"""Run the same v3 ingest/restart/replay/export/failure proof in PostgreSQL.

# release-control-evidence: scope/belofte
# release-control-evidence: beschikbaarheid
# release-control-evidence: toegang
# release-control-evidence: kwaliteit
# release-control-evidence: slop
# release-control-evidence: releasebewijs
"""
from tests.semantic_fixture_support import bind_fixture_selections
from tests.test_recommendation_coverage_v1 import console_v3_story


def test_native_postgres_v3_restart_replay_export_and_failed_replacement(tmp_path, *, production_app, production_console):
    console_v3_story(tmp_path, lambda: production_console(root=tmp_path, processing_binder=bind_fixture_selections),
                     production_app=production_app)
