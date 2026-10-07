# PR #529: T5-T7 audit repair

This repair uses the Class A / high rewrite-risk contract in PR #529. It changes
existing boundaries, not the publication registry or storage schema.

## Authority and compatibility

- Selection returns a decision. Materialisation is the single semantic candidate
  creator, including exact source text, original fragment IDs, raw mapping and
  source structure. The selector cannot override these through copied fields.
- Candidate IDs keep the pre-T7 pipe-joined ordered span digest; document identity
  remains the object ID prefix. No stored IDs, hashes or review bindings are
  rewritten. Candidates created under the unmerged regressed formula are not
  automatically migrated.
- Row-only review predicates validate selection/admission/span shape for routing.
  They do not prove source resolution. New first/second approval and publication
  authorization resolve against the verified source and accepted extraction.
  Missing source, unknown blocks, invalid bounds and text/mapping mismatches fail
  closed before approval writes.
- Explicit snapshot class selects the boom publication contract. A boom-looking
  type on a richtlijn row does not choose that route. Exact current tuple,
  independent reviewers, policy and G2/graph checks still apply.
- Historical headings remain in working evidence but are excluded from the
  published knowledge set. Direct heading authorization still fails closed.
- The current WorkingRevision uses existing workflow transaction/lock boundaries.
  Durable publication consumes the authorized IDs. Local, PostgreSQL and Azure
  composition reuse the same domain code. No new source or serving authority.

## Failure, restart and rollback

Source-validation failure does not modify object or review-binding bytes.
Unchanged recovery gets the historical candidate ID and can reuse its revision;
changed spans/content cannot acquire an old exact approval. Published history
and current serving are untouched by these readers. No SQL migration, backfill,
live deployment or destructive cleanup is part of this repair.

Revert unmerged repair commits if proof fails. Preserve source and working
evidence. Rolling an older binary over newly curated data requires separate
compatibility proof; automatic history rewriting is not a rollback strategy.

## Separate adversarial surface review

| Surface challenged | Contract / regression |
| --- | --- |
| Boom publication through shared console | Explicit review_path from snapshot class; path/node/outcome authorization tests |
| Forged boom type on richtlijn | content_reviewable excludes boom types; default publication contract rejects it |
| Changed identity despite unchanged source | Literal pre-T7 digest comparison over multiple spans; preserve_unchanged regression |
| Extra valid selector fragments/mapping/heading | Materialiser reconstructs selected provenance and structure |
| Historical heading alongside approved knowledge | Heading excluded before per-object authorization and durable publication selection |
| Syntactically valid but unresolvable persisted spans | Verified-source resolution in review_object, approve_second_review and consider_publish |
| Stale second binding / iterator consumption | Materialize bindings once; four-eyes/policy use exact eligible bindings |
| Storage override / recovery | Existing verified-source, workflow commit and publication ID boundaries retained; full PostgreSQL CI required |

The regression suite is tests/test_t5_t7_audit_repairs.py alongside T4/T7.
CI status and limitations are recorded in the PR; an uncompleted or failed full
check is not a merge recommendation. No production verification is claimed.

## PostgreSQL routing parity

Full CI exposed the legacy summary SQL still opening duties from Admission or
confirmed type alone. Its read-only content_candidate projection now mirrors
the selection/shape/admission predicate; it is never publication authority.
The parity test compares exact object sets and includes forged deterministic
and malformed-span rows. Source resolution remains in authoritative commands.
D5.3 fixture rows now use a real source block instead of an invented block ID.

The initial full suite exposed 139 failures and 8 fixture errors despite the
focused regression pass. This repair is not complete until remaining failures
are classified and fixed without restoring splitter-created knowledge authority.
