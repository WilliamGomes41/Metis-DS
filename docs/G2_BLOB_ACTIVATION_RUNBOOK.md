# G2 Blob activation runbook

This is documentation only. It is **not** a live flip.

Do not grant Azure RBAC from this repository. Do not enable the
production app setting from CI or from this change. Do not call
`publish()`. Do not store storage keys, connection strings or SAS
tokens in Git. Do not delete blobs.

## Current status (2026-09-01)

- Azure Blob adapter exists in `src/g2_source_store.py`.
- Runtime SDK pins: `azure-identity==1.25.3`, `azure-storage-blob==12.30.1` in `pyproject.toml` and the lock files.
- Container `canonical-sources` on account `aidataservice` is empty.
- G2 remains **BLOCKED**. This is not a G2 PASS.
- `publish()` remains fail-closed.
- G0 Azure DEV remains **BLOCKED**.
- Activation app setting `CONSOLE_IMMUTABLE_SOURCE_STORE` is inactive unless it is set to `azure`.
- Expected managed identity: `vvn-metis-console`.
- Required role: Storage Blob Data Contributor on scope `aidataservice/canonical-sources` only.

## Report-only preflight

```bash
python scripts/g2_azure_preflight.py
```

The preflight reports. It never mutates. Unit tests stub Azure; they
do not require a live subscription.

## Activate later (owner only)

1. Assign role **Storage Blob Data Contributor** to managed identity `vvn-metis-console` on scope `aidataservice/canonical-sources` only. Do not assign the role on the storage account, resource group, or subscription for this activation.
2. Wait for RBAC propagation. Re-run the report-only preflight until the role is reported present on that scope.
3. Enable app setting `CONSOLE_IMMUTABLE_SOURCE_STORE=azure` on the console web app.
4. Restart the web app.
5. Check runtime: the console starts; ingest can bind `azure://` locators after a verified store; preflight still reports G2 **BLOCKED** until a SHA-256-verified source is stored and bound. Do not call `publish()`.

## Rollback

1. Disable or clear app setting `CONSOLE_IMMUTABLE_SOURCE_STORE`.
2. Restart the web app.
3. **NEVER** delete existing Blob bytes.
4. Role revocation is an owner decision; rollback of activation is the setting, not data deletion.

## Prepared synthetic SHA-256 smoke (inert)

`scripts/g2_synthetic_sha256_smoke.py` is prepared and **inert**.

- MUST NOT run in this change.
- MUST NOT run without later explicit owner consent.
- The script refuses by default (`SMOKE_INERT = True`).
- It never uploads, never deletes, and never calls `publish()`.
