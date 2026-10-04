Closes #327
Depends on #326

Change class: A
Promise: Twee gelijktijdige eerste writes met case/whitespace-equivalente Onderwerpen leveren duurzaam precies één Topic-identiteit op, en alle betrokken documenten verwijzen na restart en recovery naar diezelfde Topic.
Proof: Twee onafhankelijke PostgreSQL store-instanties schrijven gelijktijdig snapshots met "Delier" en "  DELIER  "; exact één workflow.topics-row ontstaat, beide documents krijgen dezelfde topic_id, restart toont één canoniek Onderwerp en recovery behoudt de identiteit.
Touches lifecycle invariants: no
Rewrite risk: high

Lifecycle entity: Durable workflow Topic identity gekoppeld aan een document/SourceSnapshot; SourceSnapshot, WorkingRevision en PublicationRelease identities blijven ongewijzigd.
Lifecycle transition: Vrije Onderwerptekst wordt bij ingest/verplaatsen atomair opgelost naar één persisted Topic identity en workflow.documents.topic_id.
Initial durable state: Een Topic identity bestaat al of nog niet; pre-backfill documenten kunnen alleen family bevatten.
Trigger: Document ingest, expliciete Verplaatsen-write, legacy backfill of recovery restore.
Authorization: Ongewijzigd; ingest vereist researcher, Verplaatsen gebruikt bestaande curator-role regels en migratie/recovery blijft operatorwerk.
Validation: Niet-leeg Onderwerp; gedeelde deterministische normalisatie; UNIQUE(identity_key); topic_id moet bij identity_key horen.
Mutable entities: workflow.topics additief, workflow.documents.topic_id en bij nieuwe/expliciete writes de family/displayprojectie.
Immutable entities: Source bytes/SHA, SourceSnapshot identity, work-object inhoud/hashes, historische reviewevidence, canonical releases en serving registry.
Workflow state before: Ongewijzigd; deze identity-transitie verandert geen workflowstatus.
Workflow state after: Ongewijzigd; deze identity-transitie verandert geen workflowstatus.
Release state before: Ongewijzigd.
Release state after: Ongewijzigd.
Serving state before: Ongewijzigd.
Serving state after: Ongewijzigd.
Expected API result: Product API serving blijft inhoudelijk ongewijzigd; workflow readers krijgen een stabiele topic_id en canonieke family-display.
Expected UI result: Documenten toont één Onderwerp-branch voor case/whitespace-equivalente invoer, ook na concurrente eerste writes en restart.
Failure result: Write, backfill of recovery faalt closed; er ontstaat geen tweede Topic identity en geen stille partial cutover.
Restart result: Een verse runtime leest dezelfde persisted topic_id en reconstrueert de identiteit niet uit process memory.
Recovery result: Recovery v2 behoudt exact topics + topic_id-links; v1 wordt deterministisch opgewaardeerd zonder review- of publicatiebesluit.
Legacy-data result: Bestaande case/whitespace-equivalente family-strings worden door expliciete backfill aan dezelfde Topic gekoppeld; semantische synoniemen blijven apart.
Required black-box scenario: GIVEN geen Topic voor Delier WHEN twee onafhankelijke PostgreSQL stores tegelijk "Delier" en "  DELIER  " schrijven THEN bestaat één Topic, beide documenten delen topic_id, restart toont één Onderwerp en recovery behoudt diezelfde identiteit.
Explicit non-goals: Geen synonym-deduplicatie, Topic rename/merge UI, taxonomiehiërarchie, publicatie/serving-wijziging, productie-deploy, NOT NULL-contractie of verwijdering van family.

Rewrite target: De impliciete Onderwerp-identiteit in workflow.documents.family vervangen door een additieve durable Topic identity; workflow.topics is identity authority, documents.topic_id de link, family blijft compatibility/display.
Why local patching is insufficient: Process/file locks en read-before-write kunnen twee onafhankelijke databasewriters niet schema-level verhinderen tegelijk een equivalent nieuw Onderwerp te creëren; een unieke DB-identiteit ontbreekt.
Current authority/writer/reader map: Authority wordt workflow.topics; writers zijn create_document_bundle, runtime write_bundle/_write_envelope_locked, legacy migration en recovery restore; readers zijn workflow list/get envelopes, OperationsConsole family_tree/resolve, en backup/recovery; lokale envelopes.json blijft mirror.
Supported runtime topologies: File-backed G0 blijft compatibility zonder cross-process durable guarantee; PostgreSQL workflow runtime blijft de huidige ondersteunde één-instance/multiworker-topologie; de DB-unique key is tevens veilig tussen onafhankelijke DB-clients.
Persisted-state impact: Additieve workflow.topics en nullable workflow.documents.topic_id; family/envelope/source/object/review/release blijven bestaan; recoveryformat bevat Topic-state.
Compatibility/migration plan: EXPAND migration 010; MIGRATE expliciete idempotente backfill; CUTOVER nieuwe PostgreSQL-runtime fail-closed op ontbrekende Topic-link; CONTRACT/destructieve wijziging expliciet uit scope.
Rollback/recovery plan: family en nullable topic_id houden oude code rollback-capable; Topic-state is additief; recovery v2 bewaart identity; legacy v1 wordt deterministisch opgewaardeerd.
Cutover trigger: Schema 010 toegepast, backfill nul unresolved links, concurrency/restart/recovery proofs groen en volledige CI groen.
Cleanup/decommission criteria: Niets verwijderen in deze issue; family blijft compatibility/display; NOT NULL/drop/contractie vereist een aparte latere issue.
Failure blast radius: Verkeerde mapping kan documenten verkeerd groeperen; source bytes, object hashes, review, PublicationRelease en serving mogen niet wijzigen; ambiguïteit faalt closed.
Adversarial proof matrix: Concurrent first-create; stale/independent store; alternate create writer; runtime move/update; legacy backfill; historical spelling variants; partial migration; restart; v2 backup/restore; v1 recovery upgrade; failed transaction rollback; old-code rollback.

## Implementation boundary

- `workflow.topics` has `UNIQUE(identity_key)`.
- `topic_id` is deterministic from the normalized identity key.
- Topic resolution happens inside the same PostgreSQL transaction as the document mutation.
- `family` remains present and rollback-compatible.
- No destructive schema step is included.

## Evidence targeted by this PR

- two independent stores racing on the first Topic creation;
- Topic rollback when the document transaction fails;
- idempotent historical backfill without rewriting stored family;
- fail-closed partial migration;
- fresh-runtime read after restart;
- workflow recovery v2 roundtrip;
- deterministic workflow recovery v1 upgrade;
- full repository CI and separate adversarial review before merge.

## Metis eindrapportage

- **belofte**: concurrente eerste creatie kan geen syntactisch dubbel Onderwerp meer creëren in PostgreSQL workflow authority.
- **wijziging**: één durable Topic registry + FK, transactionele resolver, expliciete backfill en recovery-v2.
- **bewijs**: dedicated PostgreSQL concurrency/recovery tests plus full repository CI.
- **onzekerheid**: local file/G0 compatibility mode krijgt bewust geen cross-process durable Topic guarantee.
- **advies**: geen contract/drop/NOT NULL of productie-deploy in deze slice.

## Integration onto current main (2026-10-04)

Explicit owner instruction: merge Topic and other programmed work stranded on other branches. Original Topic PR #328 merged to fix/canonicalize-family-input-325, not main. Reuse its established domain/authority/migration contract; integrate into current workflow package and retain later lifecycle, API access, audit retention and retired-account invariants. Topic metadata remains syntactic and transactional; no semantic synonym merge. Migration is 016 because 010 is now API access. Existing deployment requires additive migration and explicit backfill before runtime cutover; repository merge performs neither production operation.

Recovery writes version 6, upgrading only complete current pre-Topic version 5 deterministically. Versions 1–4 retain their existing refusal to fabricate missing lifecycle/API/audit/account evidence. Topic creation/document links are atomic; original source, objects, reviewers, releases and serving remain unchanged. Backfill is explicit/idempotent and does not rewrite family, object/source hashes or published lineage. Downgrade preserves family and nullable topic links. No migration or data mutation is executed against production.

Separate integration/adversarial review: trace current create/update/read and guarded published projection, row-locked runtime inheritance, migration/backfill, recovery import/export/API/audit groups, corrupted/missing links, account preservation, duplicate/concurrent writers, rollback and old schema. CI must execute native PostgreSQL concurrency/recovery and the complete lifecycle regression suite; local skipped database checks are not evidence.

Companion already-programmed read-only PR #280 metrics distribution is restored to extract coverage/metrics with its existing gold-denial and register-count test. Its duplicate-text display fix and #279 primary-source preference already exist in newer main implementations and are not replaced. Other non-main PRs have their resulting source/recovery/status/test mechanisms on main; histories may diverge after squash/re-port.
