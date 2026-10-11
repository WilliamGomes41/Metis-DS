Change class: B
Promise: Only strength evidence applicable to a recommendation may determine its proposed strength.
Proof: Public source-reconstructed validation of A/B independence, plus fixed-provider V3 formation, materialisation and Admission.
Touches lifecycle invariants: no
Rewrite risk: none
Assigned issue: #557

## Before implementation: evidence and decision

Baseline: origin/main 9ca7bfc (2026-10-11); Python 3.12.14, existing requirements-dev environment. Synthetic source fragments with exact offsets and fixed provider output; no live provider or production data. `python -m pytest -q tests/test_a07_strength_binding.py`: 18 failed, 5 passed before production edits. `PYTHONPATH=. python /tmp/a07_probe.py --assert-independence` also failed: B accepted without A's label, rejected with A's label in same/ancestor section; borrowed A evidence accepted; A strong + B weak accepted as not_stated. The retained test file replaces the temporary probe as the reproducible command/fixture.

| Claim | Concrete failure | Control / expected result | Evidence boundary |
| --- | --- | --- | --- |
| A/B independence | A label rejects B | Same/separate blocks and ancestor path; B remains accepted | Synthetic reconstructed source, not production frequency |
| Evidence belongs to B | B borrows A's label | Explicit borrowed strength rejected | Public validator, including supplied offsets |
| Presence is not absence | Own weak label masked by A strong, or own conflicting labels | not_stated rejected; contradictory explicit strength rejected | Recognized literal labels, not semantic completeness |
| Useful external evidence survives | Real shared heading or trailing stamp lost | Source heading scope / exact V3 adjacency accepted; descriptive gap rejected | Extraction's structural heading/path is trusted source input |
| Candidate boundary preserves outcome | Helper fix not used downstream | Fixed provider -> V3 -> materialisation -> transform -> Admission, still needs_review | No provider-quality or production claim |
| Compatibility | Existing v1/v2, review/serving evidence overwritten | Existing version tests and replay identity; no backfill | Historical records remain unchanged |

## Existing program and ownership

Raw fragments/source reconstruction own source text, identifiers, offsets, heading type and section hierarchy. Provider spans are proposals. `pre_review_semantic_v1` resolves literal references; `recoverable_formation_v1.prepare` isolates invalid V3 proposals; `semantic_passage_v1._recommendation_semantics_from_proposal` owns proposed evidence validation; `knowledge_materialisation_v1` creates the literal candidate; `semantic_transform_generic_v1` forms canonical metadata; `admission_gate_v1` checks fields/context and eligibility. ASGI, CLI and direct preparation share the producer binding. Direct public validators must enforce the same association, including offset references, without relying on the literal resolver.

The calculation is stateless. Its output enters the existing WorkingRevision object-set commit. No store, transaction, writer, lifecycle transition or authorization boundary changes. Validated evidence does not confer human confirmation. Human review uses proposed evidence, candidate text and structural section headings; serving uses confirmed semantics. Those routes are checked through existing D3.3/D3.4 regressions; they are not redefined here.

Hard invariants: evidence solely owned by A is irrelevant to B; explicit strength needs literal and applicable evidence; any applicable known label blocks not_stated; contradictory labels are not absence; unknown association cannot justify explicit strength. Source fidelity, human confirmation and publication conditions remain unchanged.

Binding scope: selected literal text, a whitespace-adjacent trailing strength stamp in the same reconstructed block, complete standalone stamps in the next source blocks without intervening prose/heading/section boundaries, and genuine preceding source headings whose structural path contains the candidate. Section proximity or an arbitrary neighboring body is insufficient. Only explicit extractor heading metadata is used; looking like a short heading is not evidence. Intervening headings that close the scope prevent inheritance. Punctuation between consecutive trailing stamps cannot mask a conflict. General table/group associations without this structural proof remain unsupported for explicit strength rather than guessed.

Durable entity: existing candidate metadata in WorkingRevision. Before: old working set or no candidates. After: newly formed candidates/rejection observations under existing atomic commit; published set/review ledger untouched. Failure/recovery, idempotency and concurrency remain the existing ingest/re-extraction reservation, revision/CAS and atomic bundle rules; no new partial write exists. Rejected V3 candidates remain accounted for by source remainder/pending rejection, not silently lost. Recovery tests will check the durable caller; no unrelated authorization/performance/concurrency changes are planned.

## Retro: choose the bounded repair

| Option | Benefit / loss | Maintenance and migration | Decision |
| --- | --- | --- | --- |
| Keep broad section scan | Retains external evidence but demonstrably rejects B and legitimizes A evidence | No migration, continued incorrect attribution | Reject |
| Only inspect candidate | Removes borrowing but loses valid headings/trailing stamps | Small diff, fails promised external behavior | Reject |
| Reuse exact V3 adjacency plus structural heading scope | Fixes demonstrated attribution and keeps supported external evidence | One shared adjacency predicate; no durable migration | Choose |
| Replace formation architecture | Benefit not demonstrated for this bounded fault | Larger compatibility/cutover surface, opportunity cost unknown | Defer |

No comparable historic workload baseline or incident frequency is available; deterioration is not established. The code proves two defects: path relation substituted for applicability, and unambiguous normalization used as a presence detector. Reassessment trigger: a real source needing another group/table binding that current source structure cannot prove. Ownership remains the existing semantic proposal validator, tracked under #557.

## Data repair and release limits

Existing incorrectly rejected proposals may require an authorized retry/re-extraction of unpublished work. Incorrectly accepted strength, or masked own labels, may require source/reference review and a successor working revision with new human decisions. Do not mass-reprocess or rewrite published records/review decisions. A code fix or rollback does not repair historical data. Candidate and source/provider evidence can support investigation but are not proof that every affected historical object can be found automatically.

Deployment, merge, issue closure and production acceptance are outside this run. The user's explicit implementation assignment supplies execution authorization despite the issue's older needs-triage registration; no lifecycle/product decision is inferred from that label.

## Final boundary and surface review

New proposals receive recommendation-semantics-evidence-v2. Transformation and Admission revalidate these references through the same semantic operation using the existing per-calculation source-view reuse. Old v1 evidence is read without retrospective reinterpretation. Replay identity includes recommendation-strength-binding-v2; historical replays require new inference rather than silently reusing old validation. No SQL/schema migration or rewriting existing stores occurs. The wire reference and canonical recommendation-semantics-v1 value shapes are unchanged.

The source-fidelity read validator is deliberately unchanged: applicability is checked at formation and Admission, not during general source reads or before human repair. Invalid new semantics blocks Admission with an existing reason-code result. Missing source context for new evidence also blocks direct Admission. A fatal replacement preserves the previous persisted object set/replay; an isolated V3 rejection can commit open source work and retain prior candidate revisions under the existing retirement rules. Current revisions must be distinguished from retained history.

Surface verdict: APPROVE WITH NOTES. Six existing production modules are extended; no new module/store/policy authority, no parallel strength normalizer. The V3 literal resolver and the semantic validator share adjacent_source_strength_span (AST complexity 4). _applicable_strength_ranges has measured AST complexity 17: selection, trailing stamps and structurally scoped headings are kept in one local operation so maintainers can see the applicability rule together; splitting it into wrappers would not remove those decisions. validate_bound_recommendation_semantics measures 12. The established semantic validator and Admission evidence function remain the owners. No unrelated cleanup is included.

Engineering readiness remains limited to local fixed-provider/source tests until all mandatory checks and external acceptance evidence are reviewed. PostgreSQL/live-provider/production acceptance is not inferred from local persistence. Authorization/concurrency boundaries and resource limits are not modified; their additional tests are not added beyond the existing required suite.

## Executed acceptance evidence (2026-10-11)

Code revision: `c2f54b90cdabe0327e122ea9786bf73f672a15d9`, byte-identical Git tree `f3b1b105bbac2126c426bb9371f804c574fea875` to locally tested `6563743`. Subsequent report-only edits do not change product/test code. Environment: Python 3.12.14, freshly installed `requirements-dev.lock`, editable repository install; no production/provider credentials. Fixtures are the synthetic constructors in `tests/test_a07_strength_binding.py` and existing referenced test helpers. No evidence binding or Admission implementation is mocked; only provider output is fixed.

| Executed command | Result | Boundary |
| --- | --- | --- |
| `python -m pytest -q tests/test_a07_strength_binding.py` | 34 passed (included in full run) | Public v1/v2/v3 validator, fixed-provider V3, transform, Admission, local ingest/restart/replay/quarantine/fatal failure |
| Targeted D3.2, V3 repairs/context, v2 fields, literal resolution, D3.3/D3.4 and recoverable formation | 178 passed, 1 skipped before final extra stamp checks | Existing compatibility and human confirmation/serving contracts |
| Source strength labels, PDF line gutters and A07 set | 84 passed before final extra stamp checks | Preserves supported standalone labels and source reconstruction |
| Repair, navigation, availability, review source reuse, source labels/PDF and A07 | 147 passed, 28 skipped before final extra stamp checks | Current repair/read routes preserved, external PostgreSQL cases skipped |
| `python scripts/repository_preflight.py` | PASS, 963 files | Repository consistency only |
| `python scripts/release_control_preflight.py --base origin/main` | PASS on committed changed paths | Evidence mapping, not live release evidence |
| `python -m compileall -q src` | PASS | Compilation only |
| `python scripts/check_architecture_boundaries.py` | PASS | Bounded import contracts |
| `python -m pytest -q tests/test_architecture_invariants.py` | 6 passed | Existing invariant tests |
| `python scripts/product_api_contract.py --check --base-ref origin/main` | PASS in installed test environment | API compatibility only |
| `python -m pytest -q` on final code | 3312 passed, 308 skipped, 4 failed in 242.05 seconds | Entire local suite; NOT green |

The remaining failures are `test_bounded_model_transport.py::test_parent_process_death_terminates_transport_worker` and three `test_security_harden_wave3.py` cases: HTTPS SNI under DNS rebinding, redirect-hop revalidation/rebinding, and redirect to metadata rejection. All four were independently reproduced in the same fresh environment on unchanged `9ca7bfc` (`4 failed, 93 passed, 28 skipped` for the affected baseline files), and again on the final branch (`4 failed`). Their root causes were not established here; baseline failure is not proof they are harmless. No tests were deleted, skipped or weakened to hide them. They remain a repository acceptance gate for maintainers/CI, outside the A07 fix.

Measured final code/test/design diff before this report: 8 files, 478 additions, 26 deletions; six production files account for 151 additions/26 deletions, the rest is regressions and design evidence. Historical reader compatibility is covered by existing tests, without historical migration. No new authorization/concurrency/performance suite or production mutation was introduced.

Aangetoond: the three starting faults on main, repaired independence/binding/conflict behavior, preserved external label/headings, downstream local state and recovery, and the checks above. Redelijk afgeleid: newly formed recommendations through these supported validators will avoid this demonstrated borrowing/masking, assuming accurate source structure. Open: live-provider behavior, native PostgreSQL acceptance, deployed revision/original user route, historical affected-data inventory, and the four baseline failures. Oordeel: sufficient for a draft code-review PR; not a merge, deployment, issue-closure or production-resolution claim.

## Review corrections: bounded follow-up

Class B / rewrite risk none remains unchanged: no writer, durable schema, publication authority or historical mutation is replaced. Existing source-owned applicability and Admission remain the owners. Extend the existing standalone-label recognizer to sequences composed only of known cues and whitespace/punctuation; descriptive prose must still prevent attachment. Keep every cue for conflict detection. Recognized evidence-v1 retains its historical interpretation; missing/unknown versions cannot be interpreted as legacy. Advance the binding replay contract to v3 so previously cached v2 outcomes are not silently reused. No provenance system or migration is introduced: changing a valid version to v1 is not detected as tampering, and ordinary provider output cannot set this generated metadata.

| Claim | Failure scenario | Control / expected outcome | Boundary |
| --- | --- | --- | --- |
| Conflict is not absence | One following block contains strong/weak or opposite-direction labels | Public v1/v2/v3 reject not_stated and explicit strength | Synthetic source reconstruction |
| Attachment stays bounded | Repeated consistent stamps versus labels mixed with descriptive prose | Pure sequence usable; mixed prose not applicable | Existing adjacency convention, not arbitrary group attribution |
| V3 route preserves rejection | Fixed provider chooses not_stated before conflicting stamp block | Real formation/transform/Admission produce no allowed recommendation | Provider fixed, evidence boundary real |
| Unknown version cannot bypass | Candidate strength disagrees with source and version is missing/unknown | Transform rejects and Admission blocks with version error | Deliberately altered candidate metadata, not demonstrated provider exploit |
| Historical compatibility | Existing explicit evidence-v1 | Transform/Admission retain v1 and do not mutate input | No historical data repair |

Red baseline: dba5106, Python 3.12.14, requirements-dev.lock installed. `python -m pytest -q tests/test_a07_strength_binding.py -k 'combined or consistent_stamp or evidence_version or historical_v1'`: 15 failed, 1 passed, 34 deselected before product changes. The same retained tests are the reproducible fixtures/command.

Follow-up results (2026-10-11), product/test commit `70e2467`, Python 3.12.14:

- A07: **52 passed**. Targeted A07/source label/literal resolution/D3.2/D3.3/D3.4/V2/V3/recoverable formation/PDF gutter command: **231 passed, 1 skipped**. This includes real local ingest/restart/replay and failed-replacement state preservation.
- Full suite: **3329 passed, 308 skipped, 4 failed**, 287.60 seconds. Collection preceded the final extra ancillary-metadata variant; that variant passed in the final 52/231 checks. Product code was identical. All four failures are the transport termination and three SSRF cases listed above. They were also rerun individually against unchanged `9ca7bfc` in the same environment: **4 failed**. No new A07 failure remains; the full repository gate is not green.
- Repository preflight (969 files), release-control preflight on the committed diff, architecture boundary check, compilation, architecture invariants (**6 passed**), Product API compatibility and Git whitespace check: **PASS**.
- The first strict version patch exposed that ancillary `metadata.passage_formation` hid top-level evidence in formation specs. Evidence is now read from its established wire/canonical location; the added ancillary-metadata regression rejects incorrect strength at transformation. No-semantics candidates retain their existing Admission rejection instead of breaking source remainder/legacy review formation. Existing controls were retained. A transient Pydantic/core mismatch after editable installation was corrected to the locked core version before the completed runs; interrupted/incompatible runs are not acceptance evidence.

Retro/surface: **APPROVE WITH NOTES**, engineering readiness remains constrained by the four repository failures and missing production acceptance. The correction extends three existing product modules (27 additions, 9 deletions at 70e2467), uses the existing cue matcher, and shares a two-version allowlist; no parallel binder, parser framework, store or migration. `validate_bound_recommendation_semantics` has measured AST complexity 18 after adding explicit evidence version/shape boundaries and preserving existing no-semantics/type-correction paths. These decisions belong at this shared validator; no helper extraction solely to lower the score is justified. Formation specs and canonical revisions intentionally retain their existing different evidence locations.

Aangetoond: both review counterexamples are rejected, pure consistent stamp sequences remain usable, mixed prose does not bind, and historical v1 behavior remains unchanged. Redelijk afgeleid: supported new formation avoids these demonstrated conflicts and unknown-version bypasses, assuming source structure is accurate. Open: deliberate substitution of recognized historical v1 metadata is not provenance-verified, production impact/historical inventory remain unknown, and the four baseline failures remain unresolved. Oordeel: corrections are reviewable on #602; no merge, deployment, publication, historical rewrite or issue closure is claimed.
