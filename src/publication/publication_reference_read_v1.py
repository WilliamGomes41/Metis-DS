"""Release-pinned facts for a single read-only observation of the publication store."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from src.integrity_kernel import compute_canonical_object_hash


@dataclass
class PublicationObservation:
    observed_at: datetime
    active: list[dict]
    sources: dict[str, dict]
    releases: dict[str, list[dict]]
    states: dict[tuple[str, str, str, str], str]


def observe(store, selectors: list[tuple[str, str, str, str]]) -> PublicationObservation:
    from src.publication.canonical_publication_postgres_v1 import CanonicalPublicationStoreError

    with store._connect() as con:
        con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        observed_at = con.execute("SELECT statement_timestamp() AS instant").fetchone()["instant"]
        active = store.active_publication_rows(connection=con)
        # Prove the recorded source for the active release, inside the same snapshot.
        source_rows = con.execute("""
            SELECT DISTINCT s.snapshot_id,s.source_locator,s.source_checksum AS source_sha256,
                   r.release_id
              FROM publication_registry r
              JOIN canonical_object_sources c USING (object_id,object_version)
              JOIN source_snapshots s USING (snapshot_id)
              JOIN audit_events e ON e.entity_type='release' AND e.entity_id=r.release_id
               AND e.event_type='release_published' AND e.details->>'snapshot_id'=s.snapshot_id
               AND e.details->>'source_locator'=s.source_locator
               AND e.details->>'source_sha256'=s.source_checksum
             WHERE r.state='active'
        """).fetchall()
        proofs = {(row["release_id"], row["snapshot_id"]) for row in source_rows}
        if any((row["publication"]["release_id"], row["snapshot_id"]) not in proofs for row in active):
            raise CanonicalPublicationStoreError("reference_source_lineage_missing")
        release_ids, ids, versions, hashes = map(list, zip(*selectors))
        rows = con.execute("""
            WITH requested AS (
                SELECT * FROM unnest(%s::text[],%s::text[],%s::text[],%s::text[])
                    AS q(release_id,object_id,object_version,content_hash)
            ), matching AS (
                SELECT DISTINCT r.release_id FROM requested r
                JOIN publication_release_items i USING (release_id,object_id,object_version,content_hash)
            )
            SELECT i.release_id,i.object_id,i.object_version,i.content_hash,
                   c.content_hash AS canonical_hash,c.canonical_json,
                   rel.release_version,rel.published_at,rel.status,rel.withdrawn_at,
                   pub.details->>'logical_document_id' AS lineage,
                   q.object_id IS NOT NULL AS requested,
                   EXISTS (SELECT 1 FROM audit_events a WHERE a.entity_type='object'
                       AND a.entity_id=i.object_id AND a.entity_version=i.object_version
                       AND a.event_type='published' AND a.details->>'release_id'=i.release_id
                       AND COALESCE(a.details->>'historical_recovery','false')='false'
                       AND COALESCE(a.details->>'registry_preserved','false')='false'
                   ) AS activated,
                   EXISTS (SELECT 1 FROM audit_events a WHERE a.entity_type='object'
                       AND a.entity_id=i.object_id AND a.entity_version=i.object_version
                       AND a.event_type='release_withdrawal_unpublished'
                       AND a.details->>'release_id'=i.release_id
                       AND a.details->>'logical_document_id'=pub.details->>'logical_document_id'
                   ) AS withdrawal,
                   EXISTS (SELECT 1 FROM audit_events a
                       JOIN audit_events next ON next.entity_type='release'
                         AND next.event_type='release_published'
                         AND next.entity_id=COALESCE(a.details->>'superseded_by_release_id',a.details->>'release_id')
                       JOIN publication_releases successor ON successor.release_id=next.entity_id
                       WHERE a.entity_type='object' AND a.entity_id=i.object_id
                         AND a.entity_version=i.object_version AND a.event_type='superseded'
                         AND next.details->>'logical_document_id'=pub.details->>'logical_document_id'
                         AND successor.published_at=(
                             SELECT min(later.published_at) FROM publication_releases later
                             JOIN audit_events event ON event.entity_type='release'
                               AND event.entity_id=later.release_id AND event.event_type='release_published'
                             WHERE later.published_at>rel.published_at
                               AND event.details->>'logical_document_id'=pub.details->>'logical_document_id'
                               AND EXISTS (SELECT 1 FROM audit_events activation
                                   WHERE activation.entity_type='object' AND activation.event_type='published'
                                     AND activation.details->>'release_id'=later.release_id
                                     AND COALESCE(activation.details->>'historical_recovery','false')='false'
                                     AND COALESCE(activation.details->>'registry_preserved','false')='false')
                         ) AND a.event_at=successor.published_at
                   ) AS supersession
              FROM matching m JOIN publication_release_items i USING (release_id)
              JOIN publication_releases rel USING (release_id)
              JOIN canonical_object_versions c USING (object_id,object_version)
              JOIN canonical_object_sources s USING (object_id,object_version)
              JOIN source_snapshots source ON source.snapshot_id=s.snapshot_id
              JOIN audit_events pub ON pub.entity_type='release' AND pub.entity_id=i.release_id
                  AND pub.event_type='release_published' AND pub.details->>'snapshot_id'=s.snapshot_id
                  AND pub.details->>'source_locator'=source.source_locator
                  AND pub.details->>'source_sha256'=source.source_checksum
              LEFT JOIN requested q ON (q.release_id,q.object_id,q.object_version,q.content_hash)
                                    =(i.release_id,i.object_id,i.object_version,i.content_hash)
        """, (release_ids, ids, versions, hashes)).fetchall()

    active_keys = {(r["publication"]["release_id"], r["knowledge_object"]["object_id"],
                    r["knowledge_object"]["object_version"], r["knowledge_object"]["provenance"]["content_hash"])
                   for r in active}
    releases: dict[str, list[dict]] = defaultdict(list)
    states = {}
    for row in rows:
        obj = row["canonical_json"]
        if (row["canonical_hash"] != row["content_hash"] or compute_canonical_object_hash(obj) != row["content_hash"]
                or obj["object_id"] != row["object_id"] or obj["object_version"] != row["object_version"]):
            raise CanonicalPublicationStoreError("reference_canonical_hash_mismatch")
        key = (row["release_id"], row["object_id"], row["object_version"], row["content_hash"])
        if row["activated"]:
            releases[key[0]].append({"knowledge_object": obj, "publication": {
                "release_id": key[0], "release_version": row["release_version"],
                "published_at": row["published_at"].isoformat()}})
        if not row["requested"]:
            continue
        if key in active_keys:
            if not row["withdrawal"] and not row["supersession"] and row["status"] == "published":
                states[key] = "active"
        elif row["activated"] and row["lineage"]:
            if row["status"] == "withdrawn" and row["withdrawn_at"] and row["withdrawal"]:
                states[key] = "withdrawn"
            elif row["status"] in {"published", "superseded"} and row["supersession"] and not row["withdrawal"]:
                states[key] = "superseded"
    return PublicationObservation(observed_at, active, {r["snapshot_id"]: r for r in source_rows}, releases, states)
