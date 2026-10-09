-- A02: immutable derived source payload and exact snapshot binding.
-- Payload and binding are accepted within the existing workflow transaction.
CREATE TABLE IF NOT EXISTS workflow.source_representations (
    representation_id text PRIMARY KEY,
    payload_hash text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (payload->>'representation_id' = representation_id),
    CHECK (payload->>'payload_hash' = payload_hash),
    CHECK (payload->>'version' = 'source-representation-v1')
);
CREATE TABLE IF NOT EXISTS workflow.source_representation_bindings (
    snapshot_id text PRIMARY KEY REFERENCES workflow.documents(snapshot_id) ON DELETE CASCADE,
    representation_id text NOT NULL REFERENCES workflow.source_representations(representation_id),
    evidence jsonb NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
