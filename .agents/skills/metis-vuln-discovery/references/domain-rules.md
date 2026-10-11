# METIS / ATHENA Domain Rules for Vulnerability Work

Use these as constraints when hypothesizing impact or proposing fixes.

## Product stance
- Metis is the data service / knowledge layer. Canonical objects stay human-reviewed.
- AI must not generate, fill gaps, or publish into the answer/truth path.
- A trusted-feeling wrong answer is worse than no answer.
- Athena is the companion product; mentor behaviour stays unnamed. Athena is the only speaker.
- No third brand. Mentor behaviour is not a separate persona.

## Hard invariants to protect
- Only explicitly human-reviewed objects are treated as canonical.
- Untrusted or agent-generated content must not silently become authoritative.
- Authorization and tenant/role boundaries must hold across API, persistence, and any background jobs.
- Audit/evidence of human review and provenance must remain reconstructable.
- The answer/truth path must not rely on unreviewed AI output.

## Preferred analysis order
1. Identify entry points and trust boundaries.
2. Trace whether untrusted input can reach a sink that affects canonical data, authZ decisions, or the truth path.
3. Check for missing human-review gates or provenance gaps.
4. Only then consider classic issues (injection, IDOR, dependency risks, SSRF).

## What not to propose
- Automatic generation or publishing of knowledge objects.
- Bypassing human review for convenience.
- Changes that weaken provenance or audit of canonical state.
- Direct writes from agents into the truth path.

## Domain-first gates to apply before proposing fixes
When a finding implies a state change or new flow:
- Classify as stateful or stateless.
- Confirm the owning bounded context.
- State the invariant that is at risk.
- Identify the lifecycle transition (if any) and who is authorized to perform it.
- Note transaction boundary and failure/recovery behaviour.
- Require human review for anything that mutates canonical objects.

See the domain-first-architecture skill for the full gate sequence.
