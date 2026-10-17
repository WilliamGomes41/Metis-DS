-- db/checks/tier_d_damage_counts_v1.sql  (#665, deploy-acceptatie; NOOIT in CI of de PR-run)
-- Uitvoer: KANDIDATEN VOOR HANDMATIGE CONTROLE, NOOIT "schade".
-- Alleen Argos, alleen met William's GO, onder een read-only rol, na de migratie van de
-- schijf-ledger naar PostgreSQL. Detail per rij: psql -v detail=1, alleen met William's GO.
-- Leest uit workflow.document_objects, workflow.review_events en workflow.publish_authorizations
-- uitsluitend snapshot_id, object_id en object_version. NOOIT updated_at of revision (OPENVRAAG-15/-16):
-- een write_bundle of het verwijderen van een snapshot zet die op alle rijen opnieuw.
-- Blijkt er per object maar een versie te bestaan, dan is de uitkomst "niet informatief", NOOIT "0 kandidaten".
\set ON_ERROR_STOP on
BEGIN TRANSACTION READ ONLY;
SELECT bool_or(has_table_privilege(current_user, t, p)) AS heeft_schrijfrecht
FROM unnest(ARRAY['workflow.document_objects','workflow.review_events',
                  'workflow.publish_authorizations']) t,
     unnest(ARRAY['INSERT','UPDATE','DELETE','TRUNCATE']) p \gset
\if :heeft_schrijfrecht
  DO $$ BEGIN RAISE EXCEPTION 'weigering: rol heeft schrijfrecht op workflow.*'; END $$;
\endif
\echo 'kandidaten voor handmatige controle'
WITH v AS (
  SELECT snapshot_id, object_id, object_version,
         object_version ~ '^[0-9]+(\.[0-9]+)*$' AS numeriek
  FROM workflow.document_objects
),
o AS (
  SELECT *, CASE WHEN numeriek THEN string_to_array(object_version, '.')::int[] END AS vnum
  FROM v
),
r AS (
  SELECT *,
         rank() OVER (PARTITION BY snapshot_id, object_id ORDER BY vnum) AS n,
         lag(object_version) OVER (PARTITION BY snapshot_id, object_id ORDER BY vnum) AS vorige
  FROM o
),
kandidaten AS (
  SELECT snapshot_id, object_id, object_version,
    CASE
      WHEN NOT numeriek THEN 'versie_niet_numeriek'
      WHEN n = 1 THEN NULL
      WHEN EXISTS (SELECT 1 FROM workflow.review_events e
                   WHERE e.snapshot_id = r.snapshot_id AND e.object_id = r.object_id
                     AND e.object_version = r.object_version)
        THEN 'gedekt_event'
      WHEN EXISTS (SELECT 1 FROM workflow.review_events e
                   WHERE e.snapshot_id = r.snapshot_id AND e.object_id = r.object_id
                     AND e.object_version = r.vorige)
       AND NOT EXISTS (SELECT 1 FROM workflow.publish_authorizations a
                       WHERE a.snapshot_id = r.snapshot_id AND a.object_id = r.object_id
                         AND a.object_version = r.vorige)
        THEN 'gedekt_event'
      WHEN EXISTS (SELECT 1 FROM workflow.publish_authorizations a
                   WHERE a.snapshot_id = r.snapshot_id AND a.object_id = r.object_id
                     AND a.object_version = r.object_version)
        THEN 'gedekt_binding'
      ELSE 'kandidaat_geen_event_geen_binding'
    END AS redencategorie
  FROM r
)
SELECT redencategorie, count(*) AS versies, count(DISTINCT snapshot_id) AS snapshots
FROM kandidaten WHERE redencategorie IS NOT NULL
GROUP BY redencategorie ORDER BY redencategorie;
\if :{?detail}
WITH v AS (
  SELECT snapshot_id, object_id, object_version,
         object_version ~ '^[0-9]+(\.[0-9]+)*$' AS numeriek
  FROM workflow.document_objects
),
o AS (
  SELECT *, CASE WHEN numeriek THEN string_to_array(object_version, '.')::int[] END AS vnum
  FROM v
),
r AS (
  SELECT *,
         rank() OVER (PARTITION BY snapshot_id, object_id ORDER BY vnum) AS n,
         lag(object_version) OVER (PARTITION BY snapshot_id, object_id ORDER BY vnum) AS vorige
  FROM o
),
kandidaten AS (
  SELECT snapshot_id, object_id, object_version,
    CASE
      WHEN NOT numeriek THEN 'versie_niet_numeriek'
      WHEN n = 1 THEN NULL
      WHEN EXISTS (SELECT 1 FROM workflow.review_events e
                   WHERE e.snapshot_id = r.snapshot_id AND e.object_id = r.object_id
                     AND e.object_version = r.object_version)
        THEN 'gedekt_event'
      WHEN EXISTS (SELECT 1 FROM workflow.review_events e
                   WHERE e.snapshot_id = r.snapshot_id AND e.object_id = r.object_id
                     AND e.object_version = r.vorige)
       AND NOT EXISTS (SELECT 1 FROM workflow.publish_authorizations a
                       WHERE a.snapshot_id = r.snapshot_id AND a.object_id = r.object_id
                         AND a.object_version = r.vorige)
        THEN 'gedekt_event'
      WHEN EXISTS (SELECT 1 FROM workflow.publish_authorizations a
                   WHERE a.snapshot_id = r.snapshot_id AND a.object_id = r.object_id
                     AND a.object_version = r.object_version)
        THEN 'gedekt_binding'
      ELSE 'kandidaat_geen_event_geen_binding'
    END AS redencategorie
  FROM r
)
SELECT snapshot_id, object_id, object_version, redencategorie
FROM kandidaten
WHERE redencategorie IN ('kandidaat_geen_event_geen_binding', 'versie_niet_numeriek')
ORDER BY 1, 2, 3;
\endif
ROLLBACK;
