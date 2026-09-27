-- Derived quality reports. No publication/review authority or canonical writes.
CREATE TABLE IF NOT EXISTS workflow.quality_measurements (
    calculation_id text PRIMARY KEY,
    owner_account_id text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS quality_measurements_owner
    ON workflow.quality_measurements(owner_account_id, updated_at DESC);
