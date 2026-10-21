-- Isolated experimental evidence. This table has no canonical or review authority.
CREATE TABLE IF NOT EXISTS workflow.route_comparisons (
    comparison_id text PRIMARY KEY,
    owner_account_id text NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS route_comparisons_owner
    ON workflow.route_comparisons(owner_account_id, updated_at DESC);
