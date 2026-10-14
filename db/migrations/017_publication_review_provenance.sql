-- H2 (W4/H2-3): herkomst van de review per publicatierelease.
--
-- EXPAND only. Niet-destructief en idempotent: alleen ADD COLUMN met een
-- constante default (metadata-only in PostgreSQL) en een CHECK-constraint die
-- alleen wordt toegevoegd als die nog ontbreekt. Bestaande en nieuwe rijen
-- krijgen 'pending_verification' en zijn NOOIT 'verified_review' voor een
-- controle. Alleen het aparte backfill-commando (slice 2b-6) MOET geslaagde
-- releases promoveren naar 'verified_review' en gefaalde op
-- 'recovered_unverified' zetten.
-- Apply after db/schema_v2.sql en 007.

ALTER TABLE publication_releases
ADD COLUMN IF NOT EXISTS review_provenance TEXT NOT NULL DEFAULT 'pending_verification';

ALTER TABLE publication_releases
ADD COLUMN IF NOT EXISTS review_provenance_changed_at TIMESTAMPTZ NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'publication_releases_review_provenance_check'
          AND conrelid = 'publication_releases'::regclass
    ) THEN
        ALTER TABLE publication_releases
        ADD CONSTRAINT publication_releases_review_provenance_check
        CHECK (review_provenance IN ('pending_verification', 'verified_review', 'recovered_unverified'));
    END IF;
END
$$;
