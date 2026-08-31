## Scope

This repository is V&VN Data Services only. Do not record status, phases or UI of other products in `PROTOCOL.md` or `ROADMAP.md`.

## Change

Describe what changed and why.

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

## Verification

- [ ] `python scripts/repository_preflight.py`
- [ ] `python -m compileall -q src`
- [ ] `pytest -q`
