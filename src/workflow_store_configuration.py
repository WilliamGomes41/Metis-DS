"""Dependency-free admission rules shared by ASGI and local CLI entry points.

D6b: PostgreSQL is the only workflow and canonical authority, locally, in tests
and in Azure. There is no file topology to select any more.
"""
import os

# Retired selectors from the file/PostgreSQL transition. Existing deployments may
# still set them to ``postgres``; any other explicit value is refused so that a
# stale ``file`` choice can never be silently ignored.
POSTGRES_STORE_SETTINGS = (
    "METIS_WORKFLOW_STORE", "METIS_WORKFLOW_DOCUMENT_STORE",
    "METIS_WORKFLOW_REVIEW_STORE", "METIS_WORKFLOW_REMAINING_STORE",
    "METIS_CANONICAL_STORE",
)
POSTGRES_CONNECTION_SETTINGS = ("METIS_CANONICAL_DB_HOST", "METIS_CANONICAL_DB_NAME", "METIS_CANONICAL_DB_USER")
POSTGRES_DSN_SETTING = "METIS_CANONICAL_DB_DSN"


def running_in_azure() -> bool:
    return bool(os.environ.get("WEBSITE_SITE_NAME", "").strip())


def postgres_dsn_configured() -> bool:
    return bool(os.environ.get(POSTGRES_DSN_SETTING, "").strip())


def validate_workflow_store_configuration() -> None:
    """Validate the PostgreSQL authority configuration without opening any store."""
    for name in POSTGRES_STORE_SETTINGS:
        kind = os.environ.get(name, "").strip().lower()
        if kind and kind != "postgres":
            raise RuntimeError("unsupported_" + name.removeprefix("METIS_").lower())
    if postgres_dsn_configured():
        return
    if not all(os.environ.get(name, "").strip() for name in POSTGRES_CONNECTION_SETTINGS):
        raise RuntimeError("postgres_authority_configuration_required")
