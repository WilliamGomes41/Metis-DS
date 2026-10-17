"""Dependency-free admission rules shared by ASGI and local CLI entry points."""
import os

POSTGRES_STORE_SETTINGS = (
    "METIS_WORKFLOW_STORE", "METIS_WORKFLOW_DOCUMENT_STORE",
    "METIS_WORKFLOW_REVIEW_STORE", "METIS_WORKFLOW_REMAINING_STORE",
    "METIS_CANONICAL_STORE",
)


def running_in_azure() -> bool:
    return bool(os.environ.get("WEBSITE_SITE_NAME", "").strip())


def validate_workflow_store_configuration() -> bool:
    """Validate the entire authority configuration without opening any store.

    Return True for complete PostgreSQL, False for the local file harness.
    Preserve #665's tier-D refusal; #718 removes every other partial variant.
    """
    kinds = {name: os.environ.get(name, "").strip().lower()
             for name in POSTGRES_STORE_SETTINGS}
    for name, kind in kinds.items():
        if kind and kind != "postgres":
            raise RuntimeError("unsupported_" + name.removeprefix("METIS_").lower())
    if (kinds["METIS_WORKFLOW_DOCUMENT_STORE"] == "postgres"
            and kinds["METIS_WORKFLOW_REVIEW_STORE"] != "postgres"):
        raise RuntimeError("workflow_review_store_required_for_document_store")
    if not any(kinds.values()):
        if running_in_azure():
            raise RuntimeError("azure_workflow_authorities_required")
        return False
    if not kinds["METIS_CANONICAL_STORE"]:
        raise RuntimeError("canonical_store_required_for_postgres_workflow")
    if not all(kinds.values()):
        raise RuntimeError("complete_postgres_workflow_required")
    return True

