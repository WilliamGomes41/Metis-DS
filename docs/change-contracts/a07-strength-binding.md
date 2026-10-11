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
