# Protocol v2 archive

This directory marks the Protocol v2 governance line as historical material for the Protocol v3 consolidation.

## Frozen snapshots

- `PROTOCOL_ROOT_FINAL_2026-09-10.md` is an exact snapshot of root `PROTOCOL.md` at pre-v3 `main` (`98147d3c419af9faa8fb24c5eca4ea3cf67bfcb1`).
- `ROADMAP_PRE_V3_2026-09-10.md` is an exact snapshot of root `ROADMAP.md` at the same commit.

## Legacy v2 documents

The individual `docs/PROTOCOL_V2_*` files and `data/assurance/protocol_v2_*_approval.json` manifests are historical evidence. During the V3 migration they intentionally remain at their original repository paths because approval manifests and regression tests bind those paths and/or their content. Moving or deleting them before those tests are decoupled would break the audit chain.

After Protocol v3 activation, these files MUST NOT be treated as an additional current steering layer. `PROTOCOL.md` is the current norm; `ROADMAP.md` is the active change register. Historical files are consulted only for audit, provenance, regression history, or reconstruction of prior decisions.

## Migration rule

Do not create new Protocol v2 deltas. Do not create a new chain of Protocol v3 delta files. Persistent invariants are edited directly into the current Protocol v3; temporary implementation history belongs in `CHANGELOG.md`, an audit report, or `docs/history/`.
