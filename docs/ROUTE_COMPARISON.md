# Routevergelijking binnen Kwaliteit & werkproces

Issue #447. Class B, rewrite risk none. This is isolated experimental evidence;
it does not create KnowledgeObjects, review decisions, publication releases or
serving records. The normal deployment-owned passage-formation mode is never
changed by an experiment.

## Current bounded comparison

The owner creates a draft for an HTML/PDF source they own or review, selects up
to 30 extracted fragments (at most 20,000 characters of visible source text),
and freezes them against the source SHA-256, extraction result, code identity and
configured semantic model. One comparison is one bounded source case. Multiple
source cases require separate comparisons; there is currently no pooled effect
estimate or generalized clinical-quality score.

Each route receives identical frozen fragments. The deterministic arm uses
`split_context_aware_units`; the semantic arm uses
`semantic_units_before_review` and the existing shared LLM credential/model.
The semantic route never silently falls back. Both outputs are experimental
copies. Headings are excluded from human candidate counts. Failed attempts
remain visible; retry runs only the missing arm. A stale running attempt can be
reclaimed after ten minutes. Model or code changes block reuse of a frozen run.

The assessor sees A/B labels and the frozen source text, not route identity.
Assessment is per candidate plus one coverage judgment for the selected source
case. The report discloses routes only after both assessments are locked. It
shows counts, coverage, problems and recorded actions. Different segmentation
can change the candidate denominator, so the report does not compare candidate
percentages as if they were matched units.

## Lifecycle and recovery

`draft -> frozen -> running/blocked -> output_ready -> assessing -> assessed ->
analyzed -> closed`; the owner can cancel any nonterminal state with a reason.
Each state transition and its event are stored together in one versioned JSON
aggregate. The external model call is outside the storage transaction; a claim
and attempt ID guard its result. Concurrent or stale requests fail rather than
overwriting evidence. Cancellation retains evidence and blocks late model
results. An analyzed result can be read repeatedly; a changed source, model,
code or assessment requires a new comparison.

## Access, storage and deployment

Only the uploader or named reviewer of a currently accessible snapshot may
read the comparison. The owner freezes, runs, analyzes and closes; an assigned
reviewer may assess. Access is rechecked for every read and write. The frozen
source fragment text is stored with experimental evidence and follows the
source's access boundary. No API endpoint exposes it to external consumers.

Local runtime stores records in `route_comparisons/`, included in the
`experimental_evidence` backup category. PostgreSQL uses the additive
`014_route_comparisons.sql` migration and fails closed when its table is
unavailable. Apply that controlled migration before enabling the new page in
an Azure environment. No migration is executed by this code change itself.

Existing Audit frozen semantic safety cases retain their separate scope.
Regular Quality & workprocess metrics still count only committed workflow
evidence. Experimental assessments are never added to those counters.
