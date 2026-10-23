Change class: A
Promise: Designating reviewers MUST NOT set the number of required approvals. Under `review-configuration-v2` the uploader picks who may review (Alleen ik / Een collega / Een collega en ik / Twee collega's) and, only when two people are designated, whether four eyes is required. Without four eyes one valid approval from either designated person suffices; with four eyes both MUST approve. Content-bound four eyes MUST hold under every configuration and every review policy, including documents already in review. Published releases and v1 configurations MUST keep their original meaning.
Proof: tests/test_review_approvals_v2.py (acceptance 1–9: contract level, kernel ingest/review/readiness, restart, conflicts, beslisboom PDF), tests/test_review_configuration_upload_v1.py (form and HTTP), tests/test_review_configuration_gate_v1.py (v1 unchanged), the full suite on file and native PostgreSQL, tests/browser_source_selection_check.cjs.
Touches lifecycle invariants: yes
Rewrite risk: high

Decided by William on 2026-10-23 (thread "Besluiten beoordelingsmodel Metis"):

1. Option A: extend the existing review configuration with a new contract version.
2. Split technically from #822, with no incorrect intermediate state. This PR stacks on #822 and they merge together.
3. Close the policy gap for every unpublished document.
4. Under "Een collega en ik" without four eyes, the uploader alone may approve.
5. The B10 decision "two_others always needs both" lapses for new configurations.

Design: [Beoordelingsmodel: aanwijzen versus verplicht goedkeuren](https://claude.ai/artifact/3skM7rxDhXrYinKV3fr4jc).

Rewrite target: the approval rule read by `configured_approval`, `requires_four_eyes`, the policy branch of `publish_authorization_contract`, `review_stage`, and the participation floor.
Why local patching is insufficient: v1 hard-codes "every designated reviewer is required" (`configured_approval`, two_others). A policy with one required reviewer replaces the content check in `requires_four_eyes`. Giving v1 a new meaning would relax historical obligations, which decision 5 forbids.
Current authority/writer/reader map:
- Writer of the choice: `receive_source` via `_chosen_review_configuration`. Envelope field `review_configuration`.
- Writer of the policy: `receive_source`, and `review_participation_v1` (managed-review-v2).
- Readers of approval rules:
  - `four_eyes_v1.publish_authorization_contract`, per object, called from `publication_readiness`;
  - the readiness gate in `operations_console_v1` (policy membership, chosen-configuration independence);
  - `review_duty_v1.review_stage` and `reviewer_route_for` (work queue, second review);
  - the `second_review` kernel path;
  - `review_lane`/slow-review classification;
  - `decision_graph_v1.publication_issues` (beslisboom graph, policy only, unchanged);
  - `legacy_canonical_recovery_v1` (historical published releases);
  - `review_participation_v1` (floor);
  - `extract_metrics_v1` (reporting);
  - UI `review_participation_ui_v1`.
- One authority per document: the policy when one exists, otherwise the chosen configuration. `receive_source` derives the policy from a v2 choice (`policy_for_configuration`) and refuses a supplied policy that differs.
Supported runtime topologies: file store and native PostgreSQL workflow stores, through the same kernel. ASGI app and CLI.
Persisted-state impact:
- New uploads from the form store `review-configuration-v2`.
- Where a policy expresses the same duty (Alleen ik, Een collega, two people with four eyes), they also store an `explicit-review-v1` policy derived from it.
- No schema change, migration or backfill. v1 rows are untouched.
Compatibility/migration plan:
- Additive contract version.
- v1 validation, `configured_approval` and `from_review_policy` are unchanged, so historical `two_others` with four eyes off still needs both.
- Direct kernel callers that send a v1-shaped choice keep v1.
- The content-bound four-eyes rule applies to every unpublished document at read time (decision 3). Existing approvals and bindings are kept, and readiness lists `four_eyes_required` until a second authorised reviewer approves.
- The route to that reviewer is Reviewdeelname. The managed-policy floor now counts content four eyes, so activation needs a second required reviewer.
- Legacy canonical recovery re-verifies published releases with `historical_requires_four_eyes`, the rule they were published under.
Rollback/recovery plan:
- Revert before deployment if proof fails.
- After deployment, a rollback image reads a v2 configuration as invalid. Such documents fail closed with `review_configuration_invalid`, so nothing is published by mistake, but they stay blocked until the image comes back forward. A rollback also reinstates the old policy override for content four eyes.
- Both effects go in the release note. No data repair is needed in either direction.
Cutover trigger: a separately approved merge of #822 together with this PR, then an approved deployment. Neither is part of this run.
Cleanup/decommission criteria:
- One configuration module with two contract versions, and one policy module.
- `_policy_from_choice` from #822 is removed, because the kernel derives the policy.
- v1 stays as long as v1 documents exist.
Failure blast radius:
- Review closure and publication readiness for new uploads.
- For in-review documents, the stricter content four-eyes check can add a blocker. It can never remove one.
- Publication registry, serving and published releases are unchanged.
Adversarial proof matrix:
- v1 vs v2 for the same pattern.
- Policy vs chosen path.
- Uploader designated vs not designated.
- Reader, undesignated and agent approvals.
- Duplicate and stale-hash bindings.
- Revise before approve by the other designated person.
- Concurrent reviews on one revision.
- Content risk under v2 off, under a one-reviewer policy, and under historical recovery.
- Supplied policy differing from the derived one.
- Four eyes for one person.
- Beslisboom (PDF and JSON freeze) with and without an expressible policy.
- Restart.
- File and PostgreSQL.

Lifecycle entity: WorkingRevision (review closure that publication requires).
Lifecycle transition: an open WorkingRevision becomes publication-ready once its review requirements are met.
Initial durable state: received SourceSnapshot with envelope `review_configuration` (v2) and, where derived, `review_policy`. Open WorkingRevision.
Trigger: `review_object` / `second_review` approvals, then `publication_readiness` and publish.
Authorization:
- Unchanged. Only `named_reviewers` may review.
- Under v2, `named_reviewers` equals the designated set. The uploader is in it only for Alleen ik and Een collega en ik.
- Primary-first holds under a policy.
Validation:
- v2 contract, options and exact reviewer count.
- Four eyes only with two designated people.
- The uploader is never in `reviewers`.
- Readers are disjoint from reviewers.
- The derived policy must equal any supplied policy.
- A beslisboom upload (PDF or JSON freeze) needs an expressible policy (`decision_tree_needs_all_reviewers_required`); without one it would lose its graph review.
Mutable entities: envelope and objects of the new WorkingRevision, through the existing ingest and review transactions.
Immutable entities: source bytes, review bindings already recorded, published releases and serving rows.
Workflow state before: in review.
Workflow state after:
- publication-ready when `required_approvals` distinct designated approvals exist on the exact current tuple;
- or, with content four eyes, two distinct approvers with at least one who is not the uploader.
Release state before: none or an existing immutable release.
Release state after: unchanged until a separately authorised publish.
Serving state before: existing registry selection.
Serving state after: unchanged.
Expected API result:
- `publication_readiness` has no review blocker after one approval for two people with four eyes off.
- With four eyes on: `required_policy_review_missing` or `four_eyes_required` until the second approves.
Expected UI result:
- One question with four options.
- "Is het vierogenprincipe verplicht?" (Nee / Ja) appears only for Een collega en ik and Twee collega's, and must be answered (`review_four_eyes_choice_required`).
- Readers stay under "Meer opties".
- The four-eyes blocker text points to Reviewdeelname.
Failure result: invalid choices are refused before any write. A failed review commit leaves the earlier durable state intact.
Restart result: readiness is derived from the envelope and bindings alone, so a restarted process gives the same result.
Recovery result:
- Duplicate approvals by one person count once.
- Concurrent writes on one revision conflict (`snapshot_object_write_conflict`).
- A revise by the other designated person is not overridden by a later approval.
Legacy-data result:
- v1 configurations and existing policies keep their required reviewers.
- Unpublished policy documents now also need content four eyes.
- Published releases are re-verified by the historical rule.
Required black-box scenario:
- GIVEN a v2 upload "Twee collega's" with four eyes Nee,
- WHEN one designated colleague completes the review,
- THEN readiness has no review blocker, before and after restart.
- With Ja, or with high-risk content, the second approval stays required.
- A v1 `two_others` document with the same approvals stays blocked.
Explicit non-goals:
- Adding participants afterwards on a policy-less v2 document (the chosen path still refuses participant management, as before #820).
- A beslisboom with "een van beiden".
- Managed-review-v2 semantics.
- Merge and deployment.

Known limits:
- **"Een van beiden" for a beslisboom.** The beslisboom graph review requires every required reviewer of a policy (`decision_graph_v1.publication_issues`), and without a policy no graph is stored, so a beslisboom cannot express "een van beiden". It is refused with an explicit message rather than mapped to both required.
- **Sending back after approval.** Once one designated person has approved and no duty is open, the other cannot send the passage back (`content_duty_required`). Their review is refused, not ignored.
