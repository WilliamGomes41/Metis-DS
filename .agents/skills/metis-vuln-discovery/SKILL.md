---
name: metis-vuln-discovery
description: "Discover and report potential vulnerabilities in METIS/ATHENA codebases. Use when asked to security-review, threat-model, or find zero-days/bugs in Metis, Athena, or related V&VN data services. Observe and propose only; never execute against production."
---

# METIS/ATHENA Vulnerability Discovery

Discover potential vulnerabilities in METIS and ATHENA codebases using source analysis, static tools, and sandboxed verification. Always observe and propose. Never touch production systems, real credentials, or human-reviewed canonical objects without explicit approval.

## Core Rules

1. **Authority**: Observe and propose only. Do not execute destructive actions, deploy, or modify production data.
2. **Truth path**: Do not generate, fill, or publish canonical knowledge objects. Flag any path where untrusted input or agent output could reach the answer/truth path.
3. **Isolation**: Run dynamic tests only in an explicitly sandboxed environment with no production network access. Use `python scripts/security_sandbox.py check` to verify the supplied network boundary before execution; an environment variable alone is not proof. Read `docs/SECURITY_SANDBOX.md` for commands and limitations.
4. **Human review**: Every finding is a proposal. State confidence, reachability, and required human verification.
5. **Domain first**: Respect existing bounded contexts, invariants, and lifecycle rules. Prefer domain-first-architecture gates when analyzing stateful flows.

## Workflow

1. **Scope**
   - Confirm target: repository, branch, or specific slice/module.
   - Read current `AGENTS.md`, `PROTOCOL.md` and relevant repository contracts. Current repository authorities take precedence over general examples in this bundle. Do not equate human review alone with publication or serving eligibility.
   - Load any available architecture notes, threat models, or domain invariants.
   - Define what counts as in-scope (e.g. authZ, injection, data leakage, integrity of knowledge objects, supply chain).

2. **Threat model (lightweight)**
   - Identify trust boundaries, entry points, and assets (knowledge objects, credentials, tenant data).
   - Note hard invariants (e.g. only human-reviewed objects are canonical).
   - List high-value attack surfaces first.

3. **Static discovery**
   - Read relevant code (APIs, handlers, persistence, auth middleware).
   - Run or suggest static analysis (Semgrep, language linters, dependency checks) when available.
   - Hypothesize vulnerabilities with concrete code references.

4. **Verification (sandbox only)**
   - If a sandbox is available and authorized, generate minimal PoCs or tests.
   - Prefer proving reachability of untrusted input to a sink.
   - Stop immediately if isolation cannot be confirmed.

5. **Report**
   - For each finding: title, location, description, reachability, impact, confidence, suggested fix, and verification steps.
   - Separate confirmed, likely, and speculative.
   - Explicitly flag anything that could affect the truth path or human-review boundary.

## Output Format

```markdown
## Finding: [short title]
- **Location**: file:line or component
- **Type**: [injection | authZ | integrity | leakage | other]
- **Reachability**: [yes/no/unknown] + brief path
- **Impact**: [what an attacker could do]
- **Confidence**: [high/medium/low]
- **Suggested fix**: [concrete change]
- **Verification**: [how a human can confirm]
```

## Common Issues

| Issue | Action |
|-------|--------|
| No sandbox available | Stay at static analysis; do not invent dynamic results |
| Ambiguous domain rule | Flag for human; do not assume |
| Production access requested | Refuse and restate observe-only rule |
| Finding touches canonical objects | Elevate priority and note human-review requirement |

## References

- Domain rules and invariants: `references/domain-rules.md`
- Example report format: `references/example-report.md`
- Static analysis starting points: `references/static-patterns.md`
- Prefer domain-first-architecture skill for stateful changes before proposing fixes that alter lifecycle or persistence.
