# Protocol v2 archive

This directory marks the Protocol v2 governance line as historical material for the Protocol v3 consolidation.

## Frozen snapshots

- `PROTOCOL_ROOT_FINAL_2026-09-10.md` is an exact snapshot of root `PROTOCOL.md` at pre-v3 `main` (`98147d3c419af9faa8fb24c5eca4ea3cf67bfcb1`).
- `ROADMAP_PRE_V3_2026-09-10.md` is an exact snapshot of root `ROADMAP.md` at the same commit.
- `GOVERNANCE_PRE_V3_2026-09-10.md` is the byte-identical pre-v3 `docs/GOVERNANCE.md` state retained for historical governance assertions and audit reconstruction.

## Legacy v2 documents

The individual `PROTOCOL_V2_*` documents are stored here with their original bytes. Their former `docs/PROTOCOL_V2_*` paths are relative compatibility symlinks into this directory. Existing approval manifests, historical links and regression evidence can still resolve the original paths and verify the same hashes. The `data/assurance/protocol_v2_*_approval.json` manifests remain unchanged.

After Protocol v3 activation, these files MUST NOT be treated as an additional current steering layer. `PROTOCOL.md` is the current norm; open work is tracked in [GitHub Issues](https://github.com/WilliamGomes41/Metis-DS/issues). Historical files are consulted only for audit, provenance, regression history, or reconstruction of prior decisions.

Historical Protocol-v2 regression tests use the frozen roadmap directly and resolve legacy protocol and governance reads to the snapshots above. Current governance tests use the active documents.

## Migration rule

Do not create new protocol delta chains. Persistent invariants are edited directly into the current root `PROTOCOL.md` (v4.1.0); temporary implementation history belongs in `CHANGELOG.md`, an audit report, or `docs/history/`.
