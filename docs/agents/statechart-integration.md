# Statechart integration contract (proposed)

Status: integration preparation; the executable pstack statechart skill is not yet installed by this document.

## Purpose and boundaries

Use Poteto pstack `/statechart` only for a bounded, high-consequence stateful behavior where reachability, retry, concurrency or recovery is difficult to demonstrate with ordinary tests. The existing Metis domain contracts and Class A/B/C classification remain authoritative. A chart is not a domain-state source of truth.

- Domain-first establishes the object, kernel-owned state, transition semantics and hard invariants.
- Risk-proportional verification selects the smallest convincing check. Formal model checking is optional unless a specific change contract requires it.
- Statechart checks a bounded TLA+ specification with TLC and reports shortest counterexample paths.
- Actual kernel behavior must be checked separately: replay each reported counterexample against code, or record why the model differs.
- Postgres/Azure remain the authoritative persistence boundary. No new runtime status, persistence layer or lifecycle authority may be introduced for a diagram.

## Installation prerequisite

Source: https://github.com/cursor/plugins/tree/main/pstack/skills/statechart

The existing shared-skills manifest is a *single-commit snapshot* from WilliamGomes41/plugins. The statechart skill is absent at its currently pinned commit. Do not insert files from a different upstream revision under the existing commit: that would break reproducibility.

Before activating the skill:
1. Review the complete upstream statechart directory, executable scripts, dependencies, tests, license and security implications.
2. Choose either a reviewed update of the existing pinned fork commit containing all required files, or a separate, explicitly pinned source manifest with integrity hashes. Do not silently mix revisions.
3. Add canonical skill files and Claude adapter using the existing repository conventions. Confirm the skill is actually discoverable in the target agent host.
4. Run `python scripts/sync_shared_agent_skills.py --check`, relevant skill CLI tests, `python scripts/check_architecture_boundaries.py`, and the repository's applicable tests. A static checksum check alone does not establish that the executable works.
5. Record the checked upstream commit, commands, environment, outputs and limitations in the PR.

## First bounded application

Select one existing kernel-owned passage-processing lifecycle after tracing its actual owners, writers, readers, retry and recovery contracts. Do not assume the illustrative Pending/Processing/Completed statuses exist.

Model at least one agreed invariant, a normal completion path, a retry/interruption path and a duplicate/concurrent attempt when supported by the actual workflow. Check the bounded state space; include explicit assumptions and state-space limits. Translate any counterexample into a real regression test or document model mismatch.

## Completion gate

The integration is not complete until the skill is installed reproducibly, executable in the intended environment, its checks pass, and one real model has been checked against the corresponding implementation. Do not claim model checking proves the deployed code correct.
