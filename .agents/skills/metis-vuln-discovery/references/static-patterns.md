# Suggested Semgrep / static patterns

These are starting points. Adapt to the actual stack (Python, TypeScript, etc.).

## Missing review gate on write
```yaml
rules:
  - id: metis-missing-review-gate
    message: Potential write of knowledge object without human-review check
    severity: ERROR
    languages: [python]
    pattern-either:
      - pattern: |
          def $FUNC(...):
            ...
            $REPO.create($OBJ)
      - pattern: |
          $REPO.save($OBJ)
    pattern-not-inside: |
      if $OBJ.review_status == "reviewed":
        ...
```

## Client-controlled tenant / authZ
```yaml
rules:
  - id: metis-client-controlled-tenant
    message: Tenant identifier taken from request instead of authenticated context
    severity: WARNING
    languages: [python]
    pattern: |
      tenant_id = request.$FIELD
```

## Agent source reaching truth path
Look for:
- Direct assignment of agent-generated content into response builders.
- Absence of a review or provenance filter before serving to Athena.
- Background jobs that promote DRAFT → CANONICAL without an explicit human action.

## Dependency / supply chain
- Flag unpinned or floating versions in requirements/package files.
- Check for known vulnerable packages via existing SCA tools (Trivy, Dependabot, etc.).

Prefer combining these patterns with manual reading of auth middleware and domain services.
