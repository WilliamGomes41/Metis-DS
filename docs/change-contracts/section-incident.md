# Issue #614 — section-opening evidence

Change class: B
Rewrite risk: none
Touches lifecycle invariants: no

Promise: an operator can distinguish the last observed browser/application boundary
from missing evidence before documents become accessible. No inferred root cause,
publication eligibility or domain completion is introduced.

Existing call path: console app -> console_performance installation ->
RequestDiagnostics -> authorization/route -> response send. This observer owns only
request-local evidence. Console/domain owners retain all authorization, writes,
review and publication decisions. Azure SDK export remains asynchronous.

Changes: bounded client attempt token (untrusted, never authorization), UTC event
times, distinct accepted response-start/body-end observations; fixed additional
section GET routes. External read-only Playwright probe and offline incident
export consume these observations. No new app endpoint or database table.
Browser request interception blocks non-GET/HEAD traffic; the operator supplies an
existing local authenticated storage-state file that is never copied to output.

Proof: real ASGI tests for pre-response correlation, transport failure and exporter
failure isolation; offline mismatched/ambiguous evidence and redaction tests;
controlled browser/server fixtures for navigation and usability. Domain snapshots
remain unchanged in existing authenticated route tests. Platform imports are
operator observations, explicitly weaker than correlated application events.

Branch: stacked on PR #613 (fix/source-selection-diagnostics). Local baseline
c58f018a has equivalent runtime/test content; only issue-614 file diffs are sent
to the remote branch. Existing deployment notes/configuration are excluded.

Critical path (provisional; durations unknown): observer boundaries -> browser
probe -> incident correlation/export -> failure proof -> review. Broader attempt,
checkpoint, publication and serving correlation remains subsequent work.
