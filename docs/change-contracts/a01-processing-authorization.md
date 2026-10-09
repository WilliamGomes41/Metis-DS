# A01: authorization before processing mutation (#551)

Change class: B
Promise: only currently authorized actors can reserve, execute or activate existing source-processing commands through HTTP, CLI, kernel and dispatcher entry points.
Proof: unchanged-state denial regression, positive controls, duplicate/revocation/restart tests on local and native PostgreSQL; native identity-lock observation and existing concurrency/lifecycle proofs.
Touches lifecycle invariants: no
Rewrite risk: high

## Domain and scope

The existing SourceSnapshot/WorkingRevision envelope owns processing_attempts,
retry limits and recovery grants. Identity/roles belong to the existing identity
store; document assignment belongs to the workflow envelope. HTTP/CLI adapt
commands and the dispatcher delivers them. None becomes a new authority.

Researchers retain existing processing rights; reviewers require current named
assignment. Publisher-only accounts do not gain processing rights. Publisher
recovery authorization is intentionally a separate existing command. Published
work, review closure and serving semantics are unchanged.

Denial before admission/claim leaves document, objects, review bindings, attempts,
budget and recovery grant unchanged. Role retirement is denial. Duplicate
commands do not bypass current authorization. A previously admitted attempt
retains its history if authority is revoked during preparation; existing failure
recording can close that accepted work, but no candidates activate. A dispatched
external request cannot be recalled by a later authorization check.

## Rewrite mitigation and boundaries

- Rewrite target: existing authorize/reservation/execution/checkpoint boundaries.
- Why local patching is insufficient: HTTP was already safe while direct retry
  persisted a denied attempt; claim and stale account reads were alternate paths.
- Authority/writer/reader map: source_selection.authorize/reserve_selection;
  OperationsConsole.retry_pre_review/resume_formation/reextract_unpublished,
  execute_source_selection/_execute_source_attempt, diagnostic/extraction
  checkpoints, failure recorder and guarded activation; source dispatcher claim;
  HTTP processing_status/selection/recovery and CLI processing-retry. PostgreSQL
  identity/document/review mixins retain their ownership and transaction binding.
- Topologies: existing local file compatibility and PostgreSQL one-instance
  one/two-process deployment. No multi-instance capacity change.
- Persisted impact/migration: none. Existing identity read supports a current
  read; PostgreSQL FOR SHARE holds the actor row through the short transaction.
  Local role assignment shares the existing store lock with processing writes.
- Compatibility/cutover: reuse authorize and reserve; keep operation-specific
  retry/resume/reextract conditions. No new service, permission mirror or queue.
- Rollback/recovery: existing data stays readable. Reverting reopens A01 and is
  not a secure rollback; retain this authorization behavior in rollback binaries.
  Historical attempts are not deleted or reclassified.
- Cleanup: affected duplicate role/assignment predicates are removed. Runtime
  command identities, existing leases, retry semantics and actor provenance stay.
- Blast radius: admission/execution of one unpublished source. No release writer.
- Adversarial matrix: outsider/publisher, active/retired/role-revoked account,
  removed assignment, stale kernel, duplicate successful command, actor mismatch,
  pending dispatcher claim, direct underscore attempt argument, revocation at
  extraction/provider/checkpoint/activation, native concurrent role writer,
  restart and existing duplicate/concurrent processing and review preservation.

Current authorization precedes reservation and claim within short document
transactions. PostgreSQL locks the actor FOR SHARE on the same borrowed workflow
connection, so committed revocation and admission/activation have an order.
Long extraction/provider work owns no such lock. Authorization is repeated at
diagnostic/extraction checkpoints and activation; source/config/revision/lease
fences remain separate required checks.

Kernel actor IDs are inputs from trusted in-process callers; HTTP authenticates
them through existing sessions, and CLI remains an operator/host boundary. This
change does not claim to defend against arbitrary code execution, direct database
writes or an administrator deliberately impersonating another actor.

## Evidence and limits

The pinned pre-fix regression reports A01_DENIED_RETRY_MUTATED_WORKFLOW. The
existing source-processing proof workflow runs that same denial test against
the pinned base on local and native PostgreSQL, requiring two intended failures.
Its current native suite includes test_processing_authorization and rejects
missing JUnit, failures, errors and skips. Positive tests use real HTML extraction
and synthetic providers; no Azure resources or paid model calls.

The separate surface/adversarial pass checks alternative callers and MRO,
current vs cached accounts, durable vs supplied attempts, existing checkpoint and
activation writers, supported topology, rollback and concurrency. No new durable
authority, schema, lifecycle state or authorization framework is introduced.

Implementation, development verification, PR/merge, deployment and production
acceptance remain separate. #551 stays open until production acceptance.
