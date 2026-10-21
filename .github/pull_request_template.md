## Scope

This repository is V&VN Data Services only. Do not record status, phases or UI of other products in `PROTOCOL.md` or `ROADMAP.md`.

## Change

Describe what changed and why.

## Change class / rewrite risk

- **Change class**: A | B | C
- **Rewrite risk**: none | high

If `Rewrite risk: high`:

- [ ] Rewrite target and why local patching is insufficient are explicit
- [ ] Current authority/writer/reader map and supported runtime/storage topologies are documented
- [ ] Persisted-state impact and compatibility/migration plan are documented
- [ ] Rollback/recovery path is tested or explicitly blocked pending approval
- [ ] Cutover trigger and cleanup/decommission criteria are explicit
- [ ] Failure blast radius is explicit
- [ ] Big-bang replacement is avoided; otherwise staged coexistence is shown unsafe/impossible and human approval is recorded
- [ ] Any temporary dual-read/dual-write has one named authority, deterministic reconciliation, detectable divergence, and removal criteria
- [ ] Any destructive/irreversible migration is not executed autonomously and has human approval plus tested backup/recovery evidence
- [ ] Separate adversarial review challenged alternate writers/readers, override/fallback paths, topology gaps, stale state, duplicate authorities, partial cutover, restart/recovery and rollback

## Protocol / schema impact

- [ ] No protocol/schema impact
- [ ] Protocol/schema impact documented and versioned

## Infrastructure / cost impact

Select one:

- [ ] None
- [ ] Uses an already-declared dependency
- [ ] Changes an existing dependency
- [ ] Introduces a new dependency
- [ ] Removes a dependency

If anything other than `None` applies:

- [ ] `config/infrastructure_manifest.v1.json` is updated or the change is explicitly blocked pending a linked decision
- [ ] `docs/STACK_SETUP_BASELINE.md` is updated when the human-readable stack changes
- [ ] Provider/account/plan/region/secret requirements are explicit
- [ ] Cost model and expected cost range are recorded, or `TBD` has a deadline before provisioning
- [ ] Required versus optional/future dependencies are not conflated

## Safety checks

- [ ] No secrets or source binaries committed
- [ ] Canonical hashes remain deterministic where applicable
- [ ] Publication remains fail-closed
- [ ] Retrieval safety/abstention tests updated where applicable
- [ ] High-risk clinical changes require review workflow
- [ ] Green CI is not being used as the sole proof of a high-risk rewrite

## Metis eindrapportage (stub)

- **belofte**:
- **wijziging**:
- **bewijs**:
- **onzekerheid**:
- **advies**:

## Verification

- [ ] `python scripts/repository_preflight.py`
- [ ] `python scripts/release_control_preflight.py`
- [ ] `python -m compileall -q src`
- [ ] `pytest -q`
