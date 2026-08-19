## Change

Describe what changed and why.

## Protocol / schema impact

- [ ] No protocol/schema impact
- [ ] Protocol/schema impact documented and versioned

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
