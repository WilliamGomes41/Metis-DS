Change class: A
Promise: De uitgever ziet per kennisobject de actuele gereedheid en reden, terwijl bestaande publicatieblokkades, exact gepubliceerde versies en het afgeleide Athena-pakket dezelfde autoriteiten houden.
Proof: Native PostgreSQL-pariteit van blokkades; bestaande review → gereedheid → publicatie → retrieval → intrekking/herstart; desktop/mobiel/video; onafhankelijke adversariële controle en vooraf vastgelegde AB/BA-prestatievergelijking met maximaal 10% regressie.
Touches lifecycle invariants: yes
Rewrite risk: high

## Opdracht en scope
William geeft op 6 november 2026 expliciet opdracht: “Ga door met K03”. KO-3 uit #995 / MET-56 begint na gemergde KO-1 #996 en is onafhankelijk van de ongewijzigde KO-2-PR #1001. Base: main c6fa679b7c0cc630d24e32e4578e21398cb796c4. Werkbranch feat/ko3-derived-publication-readiness.

De drie operatorbesluiten staan in Appendix C van docs/plans/ko-statechart-program.md: onderbouwing verplicht (expliciet vastgelegd niet-van-toepassing sluit af), publicatie per object, pakket afgeleid bij lezen. KO-3 bouwt geen publicatieactie (#991), geen KO-4-bewijswachter en geen opslag/migratie. Operatorreview, merge en deployment blijven afzonderlijk; deze opdracht stopt bij een verifieerbare PR.

## Gegrond ontwerp vóór productcode
Bestaande readiness composeert T9 reviewplichten, T10 bronafhandeling, herstelplichten en technische poorten. KO-1-statelabels verliezen sommige van die feiten: Bewijs open kan ook een open eerste review hebben; niet-KO-bronrecords hebben state=None; een ongeldig object is niet automatisch een bestaand dispositieconflict. De bestaande blocker- en weigeringsauditsets moeten identiek blijven.

Gekozen vorm: één tijdelijke object_readiness-projectie binnen de bestaande readiness-eigenaar, met derive_ko_state plus de reeds berekende T9/T10/herstel/conflictfeiten. Geen nieuwe statusautoriteit, geen per-object SQL in een lus. Bestaande publieke console-signaturen, tellingen, globale/orphan-blokkades en bronherstelroutes blijven behouden.

De gepubliceerde retrieval-enveloppen bevatten geen live bindings. Zij behouden de bestaande canonieke publicatie-/registrygrens en structurele context. Een klein gedeeld has_recorded_approval leest uitsluitend de opgeslagen approvalstamp; het vervangt geen bindingscontrole en geeft geen publicatiebevoegdheid.

Per-object releasefeit moet exact snapshot/id/versie/hash matchen. Bestaande readers leveren dat niet compact voor alle registrytoestanden. Begrensde aanvulling op de bestandlijst: één batch-metadatareader op de bestaande PostgresCanonicalPublicationStore, plus de voorziene KO-state-module-aanpassing. Geen canonieke JSON/payloadscan en geen tweede SQL-eigenaar in de UI. Registry active blijft de enige servingautoriteit; een historische release.status wordt geen extra servingpoort.

## Rewrite mitigation
Rewrite target: readiness-weergave per object, afleiding van exacte publicatielidmaatschap en dubbele badge-finalset.
Why local patching is insufficient: losse UI-statusregels of documentbrede releasedetectie kunnen open bronwerk verliezen of een nieuwe werkversie ten onrechte gepubliceerd noemen.
Current authority/writer/reader map: workflow PostgreSQL/objectbindings en T9 review_duties; T10 source_accountability/source_closure; review_repair_duties; ClosedLoopReviewConsole._disposition_conflicts; PublicationReadinessMixin met expliciete compatibiliteitslezers in OperationsConsole/ClosedLoopReviewConsole; OperationsConsole.publish met workflowtransactie/rijlock; DurablePublicationConsole._publish_locked en bestaande refusal-audit; canonieke store met publication_registry, releases/items, versies en bronkoppeling; retrieval_projection_v2 en Product API; publish_readiness_ui; PostgreSQL-badges; snapshot_ko_states/inventaris; startup/recovery en withdraw gebruiken bestaande eigenaren.
Supported runtime topologies: volledige PostgreSQL, lokale bronopslag of Azure-immutable-source-adapter, een/twee workers. Lokale adapterproeven zijn geen Azure-productieclaim.
Persisted-state impact: geen nieuwe tabellen, kolommen, lifecyclewaarden, datawijziging, receipt-store of readiness-cache; bestaande commands schrijven onveranderd.
Compatibility/migration plan: additieve tijdelijke read-projectie, bestaande responsevelden en gatecodes behouden, badge-set vervangen door bestaande FINAL_VALIDATION_STATUSES. Geen dual writer of contractmigratie.
Rollback/recovery plan: code terug naar de base op dezelfde database; bestaande gepubliceerde releases/registry blijven intact. Native restart/rollbackproeven borgen dit.
Cutover trigger: volledige gerichte/brede CI, zichtbare browserproeven, onafhankelijke audit en prestatiepoort groen op exact PR-head; operatorreview vóór merge/deploy.
Cleanup/decommission criteria: geen lokale finale-statuslijst in badgecode; geen state-label-only gate of nieuwe servinggate; geen per-object DB-loop; geen gewijzigde bestaande blocker/auditsets.
Failure blast radius: uitgeversweergave en afgeleide gereedheid; foutieve serving of publicatietoelating moet door behouden bestaande grens geweigerd blijven.
Adversarial proof matrix: alternate readiness/publish/retrieval callers en MRO; bron-/bindingsfalen; ontbrekende/ongeldige/oude tuple; source non-KO en waiting_on_target; orphan-conflict; eerst/tweede review; all-rejected/technische fout; exact registry versus actieve voorganger; withdrawal/supersession; beide bronadapters; concurrentie; restart/recovery en coderollback.

## Lifecycle slice
Lifecycle entity: bestaande WorkingRevision met huidige KO-tuples en canonieke PublicationRelease.
Lifecycle transition: bestaande open review → ready_for_publication → bestaande publicatie naar closed/published/active; KO-3 voegt alleen afgeleide leesinformatie toe.
Initial durable state: fixture met open review/bronwerk, geen publicatie voor huidige werkversie; eventueel actieve vorige release.
Trigger: uitgever opent gereedheid, rondt bestaande review af en gebruikt bestaande publicatiecommand.
Authorization: publisher bij consider_publish/publish; actorvrije interne readiness blijft actorvrij; overige bestaande rol-/bronregels blijven gelden.
Validation: onveranderde T9/T10/technische poorten en exact versie/hash/bindingen; geen state-label-only goedkeuring.
Mutable entities: alleen bestaande review/publicatiecommands mogen bestaande workflow/binding/audit/registry muteren; KO-3-lezers schrijven niets.
Immutable entities: bronbytes/snapshotidentiteit, gepubliceerde canonieke objectversies, release-set en historische bewijzen.
Workflow state before: in_review/blocked.
Workflow state after: read verandert niets; na bestaande geldige publicatie closed.
Release state before: geen huidige release, eventueel gepubliceerde voorganger.
Release state after: bestaande geldige publicatie published; bij weigering ongewijzigd.
Serving state before: voorganger active of geen actieve release.
Serving state after: bestaande atomische activatie van huidige release; bij weigering blijft voorganger actief; na bestaande intrekking inactive.
Expected API result: uitsluitend canoniek geautoriseerde huidige actieve publicaties, behoud van noodzakelijke gepubliceerde context.
Expected UI result: per blokkerend object status en begrijpelijke reden; volledige readiness bepaalt Klaar om te publiceren, inclusief niet-lege publiceerbare set en technische poorten.
Failure result: dezelfde blokkercodes/refusal-audit, geen ongewenste mutatie of succesvolle publicatie.
Restart result: dezelfde afgeleide gereedheid en actieve/ingetrokken serving-set.
Recovery result: bestaande recovery mag geen reviewbesluit of activatie toevoegen.
Legacy-data result: opgeslagen revise blijft bestaand open herstel; geen startup-migratie of legacy-datawijziging.
Required black-box scenario: GIVEN open KO/bronwerk WHEN uitgever gereedheid opent THEN dezelfde weigering en per-object uitleg, zonder writes; na bestaande geldige review/publicatie alleen juiste exacte tuples in retrieval, ook na restart en intrekking.
Explicit non-goals: KO-2-wijzigingen, KO-4-transitietabel/nieuwe bewijswachter, per-object publicatieactie #991, nieuwe opslag/autoriteit, migratie, merge of deployment.
Rewrite risk: high

Part of MET-56.

## Architecture rationale

### Caller usage
```python
considered = console.consider_publish(actor_id=publisher_id, snapshot_id=snapshot_id)
# Existing fields and blocker codes remain; object_readiness adds display facts.
for row in considered["object_readiness"]:
    show(row["object_id"], row["state"], row["blockers"])

membership = store.object_publication_membership(snapshot_id, selected_tuples)
# Tuples are computed (object_id, object_version, canonical_hash), never a document-wide flag.

records, blocked = build_projection(canonical_envelopes)
# Existing canonical-payload contract; no live workflow reads or synthetic bindings.
```

### Shape and access patterns
The existing readiness result owns the additive transient list. Each row contains object identity/version, readable content, derived state/reasons/invalid diagnostics, existing review stage and existing blocker codes. Bindings/duties/source/repair facts are indexed once by object ID. Existing response counts and lists retain their meaning. Rows cover non-KO source obligations without inventing a KO state.

The pure state deriver keeps its signature. The snapshot inventory supplies canonical publication facts only for exact current tuples; it no longer gives every object the document's historical release status. Canonical metadata is read through the existing store owner, batched for the selected snapshot/tuples and without full canonical JSON. Legitimate predecessor-registry deletion during supersession must resolve through existing durable supersession evidence, never be guessed from an object ID alone.

Readiness's ordinary current-curation path reuses its captured inputs; release presentation remains a separate canonical fact. No canonical lookup per object, new readiness cache, additional schema or publication command is introduced. No unselected overview card may run full readiness. Public producer/consumer signatures remain unchanged except for the one narrow canonical metadata reader.

### Candidate comparison and decision
Two actual read-only agents inspected different boundaries on c6fa679b; both use the session's inherited model, not a cross-model consensus. Candidate A keeps T9/T10 and technical gate ownership and adds one per-object readiness view. Candidate B moves all obligations into a universal KO state deriver. A wins on exact blocker/audit compatibility, preservation of non-KO source obligations, change locality and observable proof. B loses information unless it broadens state ownership and rewrites classifiers, which is KO-4/domain redesign rather than KO-3.

For registry reads, composing current APIs either reads canonical payloads/the active corpus or lacks exact per-object inactive/replacement facts. A single metadata capability on the existing canonical owner is accepted in exchange for touching that owner file outside the initial four-file list. It does not change serving eligibility: active registry tuples remain the authority, not release-history status.

### Tradeoffs and scope concretization
A statelabel alone is insufficient to compute the four existing blocker categories. The per-object record combines that label with existing authoritative facts; aggregation preserves the original category order and inherited/orphan blockers. An all-final object set is ready only if a publishable tuple exists and all existing technical/source gates pass. Publisher badges continue to count documents needing publisher work, not ready KOs.

Published payload approval is a frozen recorded fact checked by the existing package validator. Sharing that exact stamp predicate does not authorize a live review or remove required published structural context. New evidence requirements remain KO-4; the per-object publication action remains #991.

### Implementation order
1. Capture focused existing readiness/projection/state/badge behavior and add regression cases for the new observable facts.
2. Consolidate the badge final set; add exact canonical membership read and state diagnostics on the existing owners.
3. Add the transient readiness rows and render blocking objects on the selected publish view.
4. Verify actual PG boundaries, all ten live scenarios grouped into isolated fixture runs, desktop/mobile screenshots and a 30–60 second video; independently challenge integrity/authorization/restart/rollback and measure six counterbalanced AB/BA pairs before the verdict.
5. Publish a ready PR on main, inspect bots/CI and stop for operator review. Do not modify handed-off KO-2 or merge/deploy.

No general scaffolding or unrelated cleanup is needed. Proof is pending: this document records source inspection and agreed design, not completed implementation or tests.

### Context validity
| Context | Owner / consumer | Lifetime and invalidation |
|---|---|---|
| Snapshot and exact object version/hash | Workflow reader → readiness; canonical metadata reader → state inventory | Captured current read; mismatched source/version/hash never receives historical publication status |
| Approval and independent second review | Existing exact bindings/T9 → readiness and KO state | Current policy/tuple; no stamp-only authorization |
| Source closure and repair | Existing T10/repair classifiers → readiness | Same source snapshot and captured fragments; non-KO obligations retained |
| Historical publication and serving | Canonical release/items/audit and active registry → existing projection/read presentation | Immutable history; active exact registry alone serves; no revival after withdrawal |
| UI request and role | Existing publisher/session check → selected view / command | Rechecked at protected entrypoint; rows carry no authority |

### Verification checklist
- [x] Ground existing runtime and recorded product decisions.
- [x] Compare structural candidates and document chosen public boundary.
- [x] Confirm implementation authorization; no additional design approval checkpoint requested.
- [ ] Implement one bounded feature with no persisted changes.
- [ ] Prove baseline blocker/audit parity, exact registry isolation, package context, badges and real lifecycle restart/withdrawal.
- [ ] Inspect rendered views and collect screenshots/video.
- [ ] Freeze/run balanced performance; all required CI and independent review green.
- [ ] Reconsider the design if facts require a new authority or a changed lifecycle policy.

