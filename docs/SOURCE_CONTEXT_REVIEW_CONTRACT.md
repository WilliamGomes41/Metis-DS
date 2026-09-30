Change class: A
Promise: Een bevoegde reviewer legt een exact bronlabel of contextfragment vast bij één of meer bestaande passages, met aantoonbaar bronbewijs; contextwijziging maakt betrokken kennis opnieuw beoordeelbaar.
Proof: HTTP-command -> workflow objecten/bindings/audit -> restart -> CSV/MCP -> publicatie met exact contextbewijs -> opvolger/intrekking; fout/stale command laat alles ongewijzigd.
Touches lifecycle invariants: yes
Rewrite risk: high

Onderdeel van #471; gebruiker heeft expliciet opdracht gegeven het gehele herstel af te ronden en daarna te mergen. Geen productiehandeling.

Domain entity/aggregate: bestaande WorkingRevision en haar versioned KnowledgeObjects. De console verstuurt alleen commands; workflow PostgreSQL blijft Azure-kernel-authority.
Invariant(s): bronbytes en tekst onveranderd; geen automatisch type/sterkte; alleen named reviewer; geen writes aan gepubliceerde revisies; exact contextbewijs in canonieke passagehash; betekenisrelevante verandering vereist herreview.
Durable state before: open revisie met onbesliste bronfragmenten en eventueel beoordeelde passages.
Durable state after: contextbron heeft expliciete reviewerrol; gekozen doelpassages bevatten letterlijk contextbewijs, met oorspronkelijke labelversie, bronlocaties, reviewer en reden; veranderde doelpassages zijn opnieuw needs_review.
Transaction boundary: versies, context, passage-register, reviewbindings en audit in één bestaande workflow bundle/transaction.
Failure/recovery result: fout/conflict -> geen half besluit; restart leest dezelfde authority; geen automatische bevestiging.
Duplicate execution / idempotency result: dezelfde command-ID/payload levert eerder resultaat, afwijkende payload met dezelfde ID wordt geweigerd.
Concurrency result: verplichte objects_revision; serialisatie met bestaande store lock en PostgreSQL snapshot-revision CAS.
Publication concurrency boundary: contextcommand en publicatie vergrendelen dezelfde workflow.documents-rij vóór authority-read tot en met commit. Publicatie leest daardoor geen oude goedkeuring terwijl context wordt gewijzigd; canonieke commit blijft bestaande publicatie-authority. Een fout na canonieke commit wordt als bestaande herstelbare projectiefout behandeld, niet als teruggedraaide publicatie.
Audit/evidence requirement: bestaande review_events bewaart command-ID, payloadhash, source/target versies, bronhash, actor en reden.

Lifecycle entity: WorkingRevision met bestaande SourceSnapshot.
Lifecycle transition: expliciete broncontextbevestiging/correctie/afwijzing, met heropening van betrokken passage-review wanneer context verandert.
Initial durable state: ongepubliceerde open revisie; bron toegankelijk/verifieerbaar; bestaande objectversies.
Trigger: reviewer POST met command-ID, snapshot revision, bronobject, rol, doelobjecten en reden.
Authorization: reviewer moet named reviewer zijn; bestaande bronopenplicht; publisher is geen vervanging voor reviewer.
Validation: rol label/context/excluded; non-empty reden; context vereist minstens één niet-structurele doelpassage uit dezelfde snapshot; exact source fragments; geen eigen relatie; geen oude versie/conflict.
Mutable entities: huidige objectversies, register, bindings, audit.
Immutable entities: source bytes en eerder opgeslagen objectversies; alle releases/canonieke publicaties.
Workflow state before: in_review/ready_for_publication maar niet gesloten.
Workflow state after: contextbron afgehandeld; betrokken doelpassages needs_review bij gewijzigde context; onverwerkte of stale context blijft open.
Release state before: geen release van deze WorkingRevision; een eerdere release in dezelfde lineage kan actief zijn.
Release state after: ongewijzigd; bestaande publicatie moet daarna opnieuw alle gates doorlopen.
Serving state before: alleen bestaand publicatieregister.
Serving state after: ongewijzigd tot afzonderlijke atomische publicatie.
Expected API result: bevestigde bronrol plus exacte doelversies; conflict 409, invalid input 400; geen type/sterktebesluit.
Expected UI result: bronlabel/context afzonderlijk getoond, doelpassages met letterlijk bevestigd contextbewijs; aanwijzing opnieuw beoordelen.
Failure result: geen writes of audit bij validatiefout; DB/audit/CAS-fout rollback.
Restart result: rol, context en herreview blijven gelijk.
Recovery result: bestaande backup van JSONB objecten en review_events bewaart alles; geen nieuwe curatorbeslissing.
Legacy-data result: ontbrekende metadata blijft onbekend; hints blijven onbeslist; geen startup/backfill.
Required black-box scenario: ingest -> bevestig context -> restart -> doelpassage review -> publicatie -> restart -> policy upgrade en expliciete opvolger -> review/publicatie -> restart -> intrekking -> restart, zonder wijziging van eerdere release.
Explicit non-goals: automatic labels from adjacency; label -> strong/weak; free model text; automatic production reprocesing; irreversible migration.

Rewrite target: additive source-context decision and derived closure validation in existing object/register/readiness path.
Why local patching is insufficient: UI hint alone stores no decision or context evidence.
Current authority/writer/reader map: OperationsConsole command -> inherited _commit_prepared_store; ReviewClosure published guard; workflow_documents + workflow_review transaction; canonical hash -> canonical publication -> registry; review UI, diagnostics CSV, evidence ZIP, MCP object metadata readers; correction/revision paths preserve evidence but stale text is invalid.
Supported runtime topologies: production PostgreSQL workflow/canonical with immutable blob; existing file-backed compatibility via one atomic store bundle.
Persisted-state impact: additive metadata inside existing object JSONB; no SQL table/column migration or rewrite of historical rows.
Compatibility/migration plan: absence is legacy unknown; no automatic role assignment; newly confirmed links only under new code. Older readers may ignore additive evidence.
Rollback/recovery plan: preserve JSONB/audit; stop new curation/publication for revisions containing new context before binary downgrade; re-upgrade or restore existing chain backup before resuming. Old binaries are not permitted to validate new context semantics.
Cutover trigger: deploy tested code; only explicit reviewer commands create new data.
Cleanup/decommission criteria: old hint-only presentation marked legacy for confirmed records; unknown records continue to show possible labels; no removal of source bytes.
Failure blast radius: single snapshot command; source/release/serving remain unchanged.
Adversarial proof matrix: unauthorized/reviewer not named; direct command; stale revision; duplicate ID mismatch; source unavailable; changed source/target text; missing endpoint; published direct write; DB/audit failure; restart; native Postgres; canonical retained evidence; old rows unchanged.

Context-binding rule: link records source label version and target version at confirmation plus exact text/source-fragment hashes. Classification-only target version changes retain unchanged literal context evidence; a changed target text/source position or source label version invalidates that evidence. A new reviewer context command creates fresh exact object versions and invalidates approval bindings; it never carries an approval to changed context.

Remaining acceptance outside implementation: a reference set must be reviewed by a real human, and the exact Eenzaamheid PDF must undergo an actual provider call. Agent-authored expectations or mock calls MUST NOT be labeled human/model acceptance. These remain merge gates of #471.
