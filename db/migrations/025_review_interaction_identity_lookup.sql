-- Derived access path for the existing global interaction-identity check.
-- Deliberately nonunique: interaction ID is identity evidence, not a receipt
-- or a universal idempotency key. Audit payload and ledger remain authority.
CREATE INDEX IF NOT EXISTS workflow_review_events_interaction_identity
    ON workflow.review_events ((event_payload#>>'{details,review_interaction,interaction_id}'))
    WHERE event_payload#>>'{details,review_interaction,interaction_id}' IS NOT NULL;
