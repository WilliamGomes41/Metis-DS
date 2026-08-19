# Security policy

V&VN Data Services is a clinical-knowledge infrastructure pilot. Treat source integrity, review integrity and API credentials as security-sensitive.

## Never commit secrets

Do not commit API keys, passwords, database URLs containing credentials, certificates, private keys or production tenant registries.

`config/tenants.v1.json` must remain empty in the repository. Example structure belongs in `config/tenants.example.v1.json` only.

## Source integrity

Canonical source files are not stored in Git. They are registered by cryptographic checksum and are intended to reside in controlled immutable object storage.

## Reporting

Until a formal security contact is assigned, security findings should be handled privately within the V&VN Data Services project team and must not be posted in public issues.
