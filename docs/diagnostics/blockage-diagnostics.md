# Slice 3: explain a blockage and export its evidence

Issue #618; follows merged #617. Class B, rewrite risk none. The report observes
existing state and controls; it never changes publication/review/recovery rules.

## Open one document independently

The Bronselectie card links to **Blokkade en bewijs bekijken**. It also works
directly with an existing authenticated session:

- `GET /source-selection/blockage?document=SNAPSHOT_ID`: stored report as HTML.
- Add `download=1`: the same bounded metadata projection as JSON.
- Add `attempt=pa_...`: select an exact attempt. Multiple attempts are never
  silently reduced to the latest one as the incident. Current proposal findings
  remain separate from selected historical attempt evidence.
- Add `checks=1`: explicitly run existing current processing/readiness checks.
  The HTML also offers a separately labeled check-and-download action.

The default route does not list documents, load objects, reconstruct source,
claim/expire work, reserve a command or call a model. Researcher/named-reviewer
access reuses source_selection.authorize; responses use Cache-Control: no-store.
The report remains independent of a broken or heavy worklist. If the application
itself cannot start, use the slice-1 external probe/platform evidence instead.

Current checks are more expensive and remain optional. They use existing
processing_status, assert_resume_configuration and PublicationReadiness owners.
If accepted retained source evidence is missing, readiness is unavailable rather
than falling back to native extraction. The existing read scope's retained_only
option also enforces this inside the source reader when metadata changes during
the check. This mode is opt-in; other read/processing behavior is unchanged.
Existing verified-source access can still read/repopulate a disposable cache.
No authoritative workflow/review/object data is written by diagnostics.

## Understand the result

- Snapshot/revision/source/version/configuration and semantic identity are
  explicit, hashed where appropriate. Matching row contexts are required.
  Identity mismatches suppress action advice and take priority in the report.
- Formation progress and pending/historical rejection classification reuse the
  existing producers. A candidate admission observation is not independently
  treated as a publication blocker. Existing PublicationReadiness remains the
  only readiness authority.
- Exact known codes have a Dutch explanation and expected condition. These are
  descriptions of the code contract, not a second predicate implementation or
  proof that every rule ran. Unknown codes remain unexplained.
- Findings reference exact dataset/data-row/field positions. Matching call
  request/output references require a unique exact call ID. Missing/ambiguous
  links remain explicit. Raw source/model prose, actor identifiers and opaque
  caller command/version/revision strings are excluded from the bounded report.
- Attempt validation observations preserve available validator file hashes,
  Python/field-contract version and validator-input/proposal hashes with their
  evidence reference. Shared identity alone never attributes a current finding
  to an older attempt.
- A recorded rejection can be confirmed while its underlying cause remains
  unknown. Historical call errors are not assumed to still be active failures.
- Follow-up conditions are observations, never execution grants. Retry/resume
  fields state the limited checks observed; every command rechecks all its
  existing conditions and permissions. Context/revision changes invalidate the
  advice. Revoked access is denied, not downgraded to a partial response.
  Current observations include runtime/build identity when available and bounded
  kernel error codes; private exception/provider messages are not copied.
- Review follow-up is shown from existing curation blockers after formation is
  complete; pending formation keeps priority. A technically succeeded attempt
  does not establish formation completion, review completion or publication.

## Existing ZIP and offline incident CLI

CSV export v14 adds blockage_report.csv and blockage_summary.txt and bounded
source/version/configuration context to revision.csv. The stored report never
reruns current checks. Other datasets retain their existing access restrictions;
the complete old ZIP can contain private source/model content.

```sh
python scripts/export_section_incident.py \
  --evidence /private/processing-evidence.zip \
  --output /private/new-incident-directory
```

Existing --browser, --processing, --application and --platform options remain
available. A processing trace and evidence ZIP are independently observed; their
document/source match is explicit when combined. The output includes input SHA256,
a bounded incident JSON and readable summary. It never overwrites a directory.
ZIP bounds: 32 MiB compressed, 64 MiB total declared/unpacked data, 1024 entries,
50000 rows per selected table. Duplicate entries/malformed CSV are rejected.
The report retains at most 64 attempts/validation observations, 256 findings and
16 evidence references per call-error group, with omissions recorded. Source or
model text is not reconstructed to complete missing historical evidence.

## Executed incident proof

The supplied private v12 export SHA256 is
76205a85c4a75b6b19dfb96ac7669af21ada163b6b7c1f32e6176dd4de5a55a0.
The actual offline command produced two succeeded attempts, 45 pending tasks,
13 pending and four historical formation rejections. It additionally identified
73 stored candidate admission observations without calling those 73 current
publication blockers. Missing origin correlation/current action checks and
individual rule execution traces stayed explicit. The diagnosis identifies
incomplete formation, not a proven explanation of model behavior or a grant to
resume on the current deployment. Raw private input/output remains outside Git.

The anonymized fixture preserves recorded codes/counts/call links and uses
synthetic document/revision/attempt/call identities and placeholder model content.
It is not a replacement for the separately executed original incident proof.

## Acceptance and review boundaries

tests/test_blockage_diagnostics_v1.py proves independent HTTP access, no default
object/worklist/processing reads, permissions, actual kernel conditions and
configuration mismatch, changed revisions, partial failures, revocation, retained
source disappearing during a check, existing recovery followed by review, and
ZIP/CLI bounds and missing/history/identity cases. Cases run on local and native
PostgreSQL adapters. CI rejects skipped backend cases. The actual source-selection
browser proof also opens/downloads diagnostics before processing, checks mobile
overflow, then continues the existing selection/review journey.

Local focused checks and private incident reconstruction are executed before PR.
Native PostgreSQL/full CI/browser outcomes must be recorded in the PR before
acceptance; local skips are not native evidence. Live Azure telemetry/export and
the full publication journey remain deployment verification and slice 4.

Surface review: one report module, one test module, existing projection/CSV/CLI/UI
and read scope reused. The shared metadata helper removes a parallel projection.
The report contains explicit independent identity/missingness branches at an
untyped input boundary, not a workflow state machine. Readiness/authorization and
source reconstruction decisions remain with their existing owners. No new
infrastructure, mutable registry, service, repair executor or background worker.
