# Security policy

V&VN Data Services is a clinical-knowledge infrastructure pilot. Treat source integrity, review integrity and API credentials as security-sensitive.

## Never commit secrets

Do not commit API keys, passwords, database URLs containing credentials, certificates, private keys or production tenant registries.

`config/tenants.v1.json` must remain empty in the repository. Example structure belongs in `config/tenants.example.v1.json` only.

## Source integrity

Canonical source files are not stored in Git. They are registered by cryptographic checksum and are intended to reside in controlled immutable object storage. Canonical source HTML and PDF MUST NOT be committed.

During the declared MVP public-remote period, tracked fixtures, holdouts and historical `output/` artefacts MAY remain in the repository. They are software artefacts, not canonical source binaries.

## Reporting

During the declared MVP period the authoritative remote MAY be public. Security findings MUST be handled privately:

- use GitHub private vulnerability reporting when available;
- otherwise handle findings privately with the V&VN Data Services project owner and security/operations reviewers;
- MUST NOT post source bytes, credentials, unpublished knowledge, or exploit details in public issues, pull requests or discussions.

Do not dump canonical source content, secrets or unpublished knowledge into the public issue tracker.
