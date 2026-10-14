-- H2 (W4/H2-3): herkomst van de review per publicatierelease.
--
-- EXPAND only. Niet-destructief en idempotent: alleen ADD COLUMN met een
-- constante default (metadata-only in PostgreSQL) en een CHECK-constraint die
-- alleen wordt toegevoegd als die nog ontbreekt. Bestaande rijen krijgen
-- 'verified_review'. Alleen het aparte backfill-commando (slice 2b-6) zet
-- releases die de reviewregels niet doorstaan op 'recovered_unverified'.
-- Apply after db/schema_v2.sql en 007.

ALTER TABLE publication_releases
ADD COLUMN IF NOT EXISTS review_provenance TEXT NOT NULL DEFAULT 'verified_review';

ALTER TABLE publication_releases
ADD COLUMN IF NOT EXISTS review_provenance_changed_at TIMESTAMPTZ NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'publication_releases_review_provenance_check'
    ) THEN
        ALTER TABLE publication_releases
        ADD CONSTRAINT publication_releases_review_provenance_check
        CHECK (review_provenance IN ('verified_review', 'recovered_unverified'));
    END IF;
END
$$;
