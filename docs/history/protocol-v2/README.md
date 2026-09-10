# Protocol v2 archive

This directory marks the Protocol v2 governance line as historical material for the Protocol v3 consolidation.

## Frozen snapshots

- `PROTOCOL_ROOT_FINAL_2026-09-10.md` is an exact snapshot of root `PROTOCOL.md` at pre-v3 `main` (`98147d3c419af9faa8fb24c5eca4ea3cf67bfcb1`).
- `ROADMAP_PRE_V3_2026-09-10.md` is an exact snapshot of root `ROADMAP.md` at the same commit.
- `GOVERNANCE_PRE_V3_2026-09-10.md` is the byte-identical pre-v3 `docs/GOVERNANCE.md` state retained for historical governance assertions and audit reconstruction.

## Legacy v2 documents

The individual `docs/PROTOCOL_V2_*` files and `data/assurance/protocol_v2_*_approval.json` manifests are historical evidence. They intentionally remain at their original repository paths wherever approval manifests or regression evidence bind those paths and/or bytes. Moving them merely for directory tidiness would weaken the audit chain.

After Protocol v3 activation, these files MUST NOT be treated as an additional current steering layer. `PROTOCOL.md` is the current norm; `ROADMAP.md` is the active change register. Historical files are consulted only for audit, provenance, regression history, or reconstruction of prior decisions.

Historical Protocol-v2 regression tests resolve legacy reads of the former root steering documents to these frozen snapshots. Current Protocol-v3 tests always read the live root documents.

## Migration rule

Do not create new Protocol v2 deltas. Do not create a new chain of Protocol v3 delta files. Persistent invariants are edited directly into the current Protocol v3; temporary implementation history belongs in `CHANGELOG.md`, an audit report, or `docs/history/`.
