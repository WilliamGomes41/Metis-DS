from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_SCHEMA = ROOT / "db" / "schema_v2.sql"
MIGRATION = ROOT / "db" / "migrations" / "006_publication_registry_single_authority.sql"
POSTGRES_STORE = ROOT / "src" / "canonical_publication_postgres_v1.py"


def _serving_view(sql: str) -> str:
    marker = "CREATE OR REPLACE VIEW published_knowledge_objects AS"
    assert marker in sql
    return sql.split(marker, 1)[1]


def _active_publication_reader(source: str) -> str:
    start = "    def active_publication_rows("
    end = "    def release_for_snapshot("
    assert start in source
    assert end in source
    return source.split(start, 1)[1].split(end, 1)[0]


def test_base_schema_serves_only_from_registry_state() -> None:
    sql = BASE_SCHEMA.read_text(encoding="utf-8")
    view = _serving_view(sql)

    assert "WHERE r.state = 'active'" in view
    assert "rel.status = 'published'" not in view
    assert "canonical_schema_version TEXT NOT NULL DEFAULT '1.3'" in sql
    assert "canonical_json_no_publication_authority" in sql
    assert "trg_strip_publication_governance" in sql
    assert "trg_active_registry_release_integrity" in sql
    assert "trg_release_requires_registry_deactivation" in sql
    for key in ("publication_status", "release_owner", "release_date", "superseded_by"):
        assert f"- '{key}'" in sql or f"'{key}'" in sql


def test_migration_resets_test_corpus_and_removes_publication_state_from_canonical_json() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    view = _serving_view(sql)

    assert "TRUNCATE TABLE" in sql
    for table in (
        "audit_events",
        "publication_registry",
        "publication_release_items",
        "canonical_object_sources",
        "publication_releases",
        "canonical_object_versions",
        "source_snapshots",
    ):
        assert table in sql

    assert "RESTART IDENTITY" in sql
    assert "canonical_schema_version TEXT NOT NULL DEFAULT '1.3'" in sql
    assert "trg_strip_publication_governance" in sql
    assert "canonical_json_no_publication_authority" in sql
    assert "WHERE r.state = 'active'" in view
    assert "rel.status = 'published'" not in view
    assert "publication_registry must be deactivated before release" in sql
    assert "canonical JSON contains publication authority" not in sql


def test_runtime_active_reader_uses_registry_as_only_publication_state_filter() -> None:
    source = POSTGRES_STORE.read_text(encoding="utf-8")
    reader = _active_publication_reader(source)

    assert "WHERE r.state='active'" in reader
    assert "rel.status='published'" not in reader
    assert 'governance' not in reader
    assert 'publication_status' not in reader
