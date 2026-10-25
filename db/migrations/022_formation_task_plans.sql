-- Additive: no backfill or mutation of historical source/results/publications.
CREATE TABLE IF NOT EXISTS workflow.formation_task_plans (
    context_id TEXT PRIMARY KEY REFERENCES workflow.formation_contexts(context_id) ON DELETE CASCADE,
    plan_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
