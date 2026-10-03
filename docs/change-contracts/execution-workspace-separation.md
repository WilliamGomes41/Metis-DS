# Execution, help and technical management

Change class: B
Promise: Users submit, review, correct and publish without manuals, diagnostics or technical controls embedded in execution screens.
Proof: Installed HTTP surface tests separate destinations, preserve source evidence and explicit decisions, retain authorized retry/review recovery, and compare Mijn werk to the reference render.
Touches lifecycle invariants: no
Rewrite risk: none
Issue: #495

The existing mechanism is server-rendered console presentation, with readiness and review queues derived from the operations kernel. The production navigation middleware previously removed the recommended review action. Document processing status and retry permissions already belong to `processing_status` and `retry_pre_review`.

This change moves manuals to `/help/{topic}` and processing status, diagnostics and retry controls to `/settings/technical`. Review source/context and choices form two visible columns. The recommended task retains one primary action; alternative tasks retain their existing destinations. Local validation keeps input and gives actionable field errors. Model configuration, exports and quality checks remain separate management destinations.

Affected call path: authenticated GET → existing kernel read → renderer → existing production navigation middleware. POST review, correction, publication, retry and recovery continue to use the existing commands, revision tokens and role/assignment checks. No persisted authority, schema, identity, lifecycle transition, permission rule, extraction rule or publication rule changes. Help and management GETs do not write domain state. No migration or dependency is introduced.

Scope excludes `/` Mijn werk. Its renderer, shared page script, navigation and original stylesheet selectors remain unchanged. Only task-scoped CSS is added. Reference-render tests normalize the stylesheet cache version and preserve all other home markup for researcher and reviewer sessions; existing home tests cover roles and badges.

Validation: `tests/test_execution_workspace_separation_v1.py`, the updated presentation regressions, existing domain tests and repository preflights. Existing text assertions are changed only where the product promise intentionally removes or relocates text; authority/mutation assertions remain intact.

Rollback: revert the presentation commit. Domain records and command semantics remain compatible with the previous UI. Merge and deployment require a separate decision.
