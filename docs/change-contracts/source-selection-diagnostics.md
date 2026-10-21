Change class: B
Rewrite risk: none
Touches lifecycle invariants: no
Promise: Reuse document and object reads within a source-selection GET and add bounded request diagnostics without changing authorization, publication or command revision decisions.
Proof: Focused tests cover authenticated HTTP output, bounded reads, context isolation, freshness, failure cleanup and stale revision rejection. Full-suite and remote CI success remain unverified.

The read scope exists only during one GET. It reuses validated document records and object rows and excludes large replay evidence before copying receipts. Write paths bypass this read reuse. Existing authorization and publication checks remain in place. No schema migration or durable state mutation is introduced.

Diagnostic phases measure inclusive durations and logical calls; they must not be added or interpreted as physical database reads. Optional telemetry configuration is external to this PR. Request diagnostics exclude source contents, query strings and credentials.

A remaining performance concern is repeated source representation reconstruction during overview status checks. The source-selection renderer checks every visible document. Follow-up work should reproduce this path and test existing request-scoped reconstruction reuse, retaining all source and review checks. This PR does not claim that overview performance is acceptable or that document processing failures are resolved.

Publication note: runtime and test files correspond to the prepared deployment source; deployment-specific documentation and configuration scripts are intentionally excluded from this PR. The full repository tree is therefore not identical to the deployment package.
