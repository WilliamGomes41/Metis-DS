from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_SCHEMA = ROOT / "db" / "schema_v2.sql"
MIGRATION = ROOT / "db" / "migrations" / "006_publication_registry_single_authority.sql"


def _serving_view(sql: str) -> str:
    marker = "CREATE OR REPLACE VIEW published_knowledge_objects AS"
    assert marker in sql
    return sql.split(marker, 1)[1]


def test_base_schema_serves_only_from_registry_state() -> None:
    sql = BASE_SCHEMA.read_text(encoding="utf-8")
    view = _serving_view(sql)

    assert "WHERE r.state = 'active'" in view
    assert "rel.status = 'published'" not in view
    assert "canonical_json_no_publication_authority" in sql
    assert "trg_active_registry_release_integrity" in sql
    assert "trg_release_requires_registry_deactivation" in sql


def test_migration_converts_existing_database_to_registry_only_authority() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    view = _serving_view(sql)

    assert "WHERE r.state = 'active'" in view
    assert "rel.status = 'published'" not in view
    assert "canonical_json_no_publication_authority" in sql
    assert "publication_registry must be deactivated before release" in sql
    assert "canonical JSON contains publication authority" in sql
