# Legacy canonical release recovery

Use this route only for a release manifest created before canonical publication
moved to PostgreSQL. Planning is read-only:

```bash
python scripts/publication_chain_recovery.py recover-legacy-release \
  --manifest <manifest.json>
```

The plan re-reads exact object versions and publish authorizations from the
workflow authority, recomputes object hashes, and verifies immutable source
readback. Execute only with the release ID returned by the plan:

```bash
python scripts/publication_chain_recovery.py recover-legacy-release \
  --manifest <manifest.json> \
  --execute \
  --confirm-release-id <release-id>
```

Execution reuses the existing transactional, idempotent canonical publication
store. It does not create resources, change application settings, or remove
runtime files.

Workflow identity replay treats valid legacy sessions as a required subset.
Additional post-cutover sessions are allowed. A revoked legacy session remains
revoked and counts as present; a missing or changed legacy session still blocks.
