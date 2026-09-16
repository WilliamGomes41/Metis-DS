#!/usr/bin/env python3
"""Read-only audit of historical Metis lifecycle consistency.

The audit deliberately reports evidence without repairing it. It uses the same
PostgreSQL connection configuration as canonical publication, starts an
explicit READ ONLY transaction, and emits JSON suitable for attaching to a
repair decision.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any

from src.canonical_publication_postgres_v1 import PostgresCanonicalPublicationStore


@dataclass(frozen=True)
class AuditCheck:
    name: str
    severity: str
    sql: str


CHECKS: tuple[AuditCheck, ...] = (
    AuditCheck(
        "release_publication_event_missing",
        "error",
        """
        SELECT rel.release_id, rel.status, rel.published_at
        FROM publication_releases rel
        LEFT JOIN audit_events ev
          ON ev.entity_type='release'
         AND ev.entity_id=rel.release_id
         AND ev.event_type='release_published'
        WHERE rel.status IN ('published','withdrawn')
        GROUP BY rel.release_id, rel.status, rel.published_at
        HAVING COUNT(ev.event_id)=0
        ORDER BY rel.published_at NULLS FIRST, rel.release_id
        """,
    ),
    AuditCheck(
        "release_lineage_missing",
        "warning",
        """
        SELECT rel.release_id,
               ev.details->>'snapshot_id' AS snapshot_id,
               ev.details->>'logical_document_id' AS logical_document_id,
               ev.details->>'working_revision_id' AS working_revision_id
        FROM publication_releases rel
        JOIN audit_events ev
          ON ev.entity_type='release'
         AND ev.entity_id=rel.release_id
         AND ev.event_type='release_published'
        WHERE rel.status IN ('published','withdrawn')
          AND (
              NULLIF(BTRIM(ev.details->>'logical_document_id'), '') IS NULL
              OR NULLIF(BTRIM(ev.details->>'snapshot_id'), '') IS NULL
          )
        ORDER BY rel.published_at NULLS FIRST, rel.release_id, ev.event_id
        """,
    ),
    AuditCheck(
        "release_lineage_conflicting",
        "error",
        """
        SELECT ev.entity_id AS release_id,
               ARRAY_AGG(DISTINCT NULLIF(BTRIM(ev.details->>'logical_document_id'), ''))
                   FILTER (WHERE NULLIF(BTRIM(ev.details->>'logical_document_id'), '') IS NOT NULL)
                   AS logical_document_ids,
               ARRAY_AGG(DISTINCT NULLIF(BTRIM(ev.details->>'snapshot_id'), ''))
                   FILTER (WHERE NULLIF(BTRIM(ev.details->>'snapshot_id'), '') IS NOT NULL)
                   AS snapshot_ids,
               ARRAY_AGG(DISTINCT NULLIF(BTRIM(ev.details->>'working_revision_id'), ''))
                   FILTER (WHERE NULLIF(BTRIM(ev.details->>'working_revision_id'), '') IS NOT NULL)
                   AS working_revision_ids
        FROM audit_events ev
        WHERE ev.entity_type='release'
          AND ev.event_type='release_published'
        GROUP BY ev.entity_id
        HAVING COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'logical_document_id'), '')) > 1
            OR COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'snapshot_id'), '')) > 1
            OR COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'working_revision_id'), '')) > 1
        ORDER BY ev.entity_id
        """,
    ),
    AuditCheck(
        "release_workflow_lineage_mismatch",
        "error",
        """
        SELECT ev.entity_id AS release_id,
               ev.details->>'snapshot_id' AS snapshot_id,
               ev.details->>'logical_document_id' AS release_logical_document_id,
               ev.details->>'working_revision_id' AS release_working_revision_id,
               d.logical_document_id AS workflow_logical_document_id,
               d.working_revision_id AS workflow_working_revision_id
        FROM audit_events ev
        LEFT JOIN workflow.documents d
          ON d.snapshot_id=ev.details->>'snapshot_id'
        WHERE ev.entity_type='release'
          AND ev.event_type='release_published'
          AND NULLIF(BTRIM(ev.details->>'snapshot_id'), '') IS NOT NULL
          AND (
              d.snapshot_id IS NULL
              OR (
                  NULLIF(BTRIM(ev.details->>'logical_document_id'), '') IS NOT NULL
                  AND ev.details->>'logical_document_id' <> d.logical_document_id
              )
              OR (
                  NULLIF(BTRIM(ev.details->>'working_revision_id'), '') IS NOT NULL
                  AND ev.details->>'working_revision_id' <> d.working_revision_id
              )
          )
        ORDER BY ev.entity_id, ev.event_id
        """,
    ),
    AuditCheck(
        "active_release_lineage_missing_or_ambiguous",
        "error",
        """
        WITH lineage AS (
            SELECT ev.entity_id AS release_id,
                   COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'logical_document_id'), '')) AS document_count,
                   MIN(NULLIF(BTRIM(ev.details->>'logical_document_id'), '')) AS logical_document_id
            FROM audit_events ev
            WHERE ev.entity_type='release'
              AND ev.event_type='release_published'
            GROUP BY ev.entity_id
        )
        SELECT DISTINCT r.release_id, l.document_count, l.logical_document_id
        FROM publication_registry r
        LEFT JOIN lineage l ON l.release_id=r.release_id
        WHERE r.state='active'
          AND COALESCE(l.document_count, 0) <> 1
        ORDER BY r.release_id
        """,
    ),
    AuditCheck(
        "multiple_active_releases_per_logical_document",
        "error",
        """
        WITH lineage AS (
            SELECT ev.entity_id AS release_id,
                   MIN(NULLIF(BTRIM(ev.details->>'logical_document_id'), '')) AS logical_document_id
            FROM audit_events ev
            WHERE ev.entity_type='release'
              AND ev.event_type='release_published'
            GROUP BY ev.entity_id
            HAVING COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'logical_document_id'), ''))=1
        )
        SELECT l.logical_document_id,
               ARRAY_AGG(DISTINCT r.release_id ORDER BY r.release_id) AS active_release_ids
        FROM publication_registry r
        JOIN lineage l ON l.release_id=r.release_id
        WHERE r.state='active'
          AND l.logical_document_id IS NOT NULL
        GROUP BY l.logical_document_id
        HAVING COUNT(DISTINCT r.release_id) > 1
        ORDER BY l.logical_document_id
        """,
    ),
    AuditCheck(
        "withdrawn_release_still_active",
        "error",
        """
        SELECT r.release_id, COUNT(*) AS active_object_count, rel.withdrawn_at
        FROM publication_registry r
        JOIN publication_releases rel ON rel.release_id=r.release_id
        WHERE r.state='active'
          AND rel.status='withdrawn'
        GROUP BY r.release_id, rel.withdrawn_at
        ORDER BY r.release_id
        """,
    ),
    AuditCheck(
        "historical_release_still_active_after_later_release",
        "error",
        """
        WITH lineage AS (
            SELECT ev.entity_id AS release_id,
                   MIN(NULLIF(BTRIM(ev.details->>'logical_document_id'), '')) AS logical_document_id
            FROM audit_events ev
            WHERE ev.entity_type='release'
              AND ev.event_type='release_published'
            GROUP BY ev.entity_id
            HAVING COUNT(DISTINCT NULLIF(BTRIM(ev.details->>'logical_document_id'), ''))=1
        ), active_releases AS (
            SELECT DISTINCT r.release_id, l.logical_document_id
            FROM publication_registry r
            JOIN lineage l ON l.release_id=r.release_id
            WHERE r.state='active' AND l.logical_document_id IS NOT NULL
        )
        SELECT a.logical_document_id,
               a.release_id AS active_release_id,
               active_rel.published_at AS active_published_at,
               later.release_id AS later_release_id,
               later.published_at AS later_published_at,
               later.status AS later_status
        FROM active_releases a
        JOIN publication_releases active_rel ON active_rel.release_id=a.release_id
        JOIN lineage later_lineage ON later_lineage.logical_document_id=a.logical_document_id
        JOIN publication_releases later ON later.release_id=later_lineage.release_id
        WHERE later.release_id<>a.release_id
          AND later.published_at IS NOT NULL
          AND active_rel.published_at IS NOT NULL
          AND later.published_at > active_rel.published_at
          AND later.status IN ('published','withdrawn')
        ORDER BY a.logical_document_id, later.published_at, later.release_id
        """,
    ),
    AuditCheck(
        "withdrawal_before_publication",
        "error",
        """
        SELECT release_id, published_at, withdrawn_at
        FROM publication_releases
        WHERE withdrawn_at IS NOT NULL
          AND (published_at IS NULL OR withdrawn_at < published_at)
        ORDER BY release_id
        """,
    ),
    AuditCheck(
        "active_registry_item_missing_from_release",
        "error",
        """
        SELECT r.object_id, r.object_version, r.release_id
        FROM publication_registry r
        LEFT JOIN publication_release_items i
          ON i.release_id=r.release_id
         AND i.object_id=r.object_id
         AND i.object_version=r.object_version
        WHERE r.state='active'
          AND i.release_id IS NULL
        ORDER BY r.release_id, r.object_id, r.object_version
        """,
    ),
)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def run_audit(connection: Any) -> dict[str, Any]:
    """Run all checks inside an explicit read-only transaction."""
    findings: list[dict[str, Any]] = []
    connection.execute("BEGIN READ ONLY")
    try:
        for check in CHECKS:
            rows = connection.execute(check.sql).fetchall()
            for row in rows:
                findings.append(
                    {
                        "check": check.name,
                        "severity": check.severity,
                        "evidence": _json_safe(dict(row)),
                    }
                )
    finally:
        connection.rollback()

    counts = {"error": 0, "warning": 0}
    by_check: dict[str, int] = {check.name: 0 for check in CHECKS}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
        by_check[finding["check"]] += 1

    return {
        "audit": "historical_lifecycle",
        "read_only": True,
        "status": "clean" if not findings else "findings",
        "counts": counts,
        "by_check": by_check,
        "findings": findings,
    }


def main() -> int:
    store = PostgresCanonicalPublicationStore()
    with store._connect() as connection:
        report = run_audit(connection)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "clean" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"audit": "historical_lifecycle", "status": "error", "error": str(exc)}))
        raise SystemExit(1)
