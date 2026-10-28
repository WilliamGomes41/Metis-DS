# MET-13 / #879 — ontwerp R4.6: vormingsroute duurzaam binden aan bron en poging

Change class: C (ontwerp). Rewrite risk: none. Touches lifecycle invariants: no.
Dit document wijzigt geen code en geeft geen implementatie-GO. De latere runtime-implementatie is
**Class A, Rewrite risk high** (ROADMAP R4.6) en krijgt een eigen uitvoeringsissue. Basis:
main `6af3e18`. Norm: PROTOCOL.md §5.4 (vormingskader, punten 1–7) en
`docs/agents/lifecycle-vsa.md` §6–7.

## 1. Norm (Protocol §5.4, samengevat)

| # | Eis |
| --- | --- |
| N1 | Bronsoort en route worden bij de start vastgelegd **op de bronversie en de poging**, met policyversie, actor en reden. Het is documenttoestand en auditbewijs, geen runtime-instelling. |
| N2 | Retry, hervatting en herstel gebruiken altijd de vastgelegde route. Een andere route vereist een expliciete opvolger met een nieuwe werkrevisie. |
| N3 | De deploymentconfiguratie wijst alleen de standaardroute voor **nieuwe** verwerking aan en mag routes uitsluiten. Zij wijzigt nooit een vastgelegde of lopende route. |
| N4 | Alleen voor de bronsoort toegelaten routes zijn selecteerbaar. Een niet-uitvoerbare route faalt gesloten en blijft zichtbaar. |
| N5–N6 | Eén kandidaatmaker; §4.1/§4.2/§6/§7 gelden onverkort (ongewijzigd door dit ontwerp). |
| N7 | Bronversies zonder vastgelegde route behouden hun regels. Geen backfill. |

## 2. Huidig mechanisme (as-is, aangetoond in code)

**Wat wordt vastgelegd.** `source_selection_v1.configuration` (`:122–127`) bouwt
`{mode, model, docling, deployment}`. `mode` komt uit `METIS_PASSAGE_FORMATION_MODE` via
`pre_review_semantic_v1._configured_passage_formation_mode` (`:194–195`, standaard V2) en de
reader `console._processing_configuration_reader` (`:1123–1129`); `deployment` is de commit uit
`config/deployed_commit.txt`. Er wordt **geen** policyversie en **geen** reden vastgelegd. De actor
staat wel op de poging (`actor_id`).

**Writers.** Bij elke reservering schrijven ze `envelope["processing_configuration"]` en kopiëren
die naar de nieuwe poging. Dat gebeurt binnen de bestaande schrijfgrens
(`_store_write_lock`/`_reprocessing_transaction` → `_commit_prepared_store`, workflow-store in
PostgreSQL):

| Ingang | Plaats | Bron van `mode` |
| --- | --- | --- |
| Ingest (synchroon) | `operations_console_v1.py:1620` | **huidige omgeving** |
| Bronselectie (ingest/retry/resume) | `source_selection_v1.py:102` | omgeving; bij `resume` `assert_resume_configuration` |
| Retry van een lege geblokkeerde bron | `operations_console_v1.py:2178` | **huidige omgeving** (bewust: "configuration in force now") |
| Hervatten | `operations_console_v1.py:1964` | `assert_resume_configuration` |
| Opvolger (`decision_successor_v1`) | via `ingest` + `reserve_source_selection` | **huidige omgeving** |
| Directe herextractie (`reextract_unpublished`) | `operations_console_v1.py:2250–2263` (bounded: alleen op de poging, envelop ongewijzigd) en het synchrone pad (`:2266` → `_fragments_and_spec`) | **huidige omgeving** (`active_configuration`) |

**Readers en fences** (alle fail-closed bij een verschil met de huidige omgeving):
`source_preparation_context_v1.build_formation_context` (`:113–118`, ook `_unpinned`),
`formation_checkpoint_v1` (`:30–32`, `:52`), `worker_handover_v1` (`:100`), de dispatch in
`operations_console_v1` (`:2148–2151`) en `source_processing_dispatch_v1` (docling). Ook
`processing_trace_v1` (hash), `blockage_diagnostics_v1` en `decision_tree_experiment_v1` lezen het.
De UI (`operations_console_app._passage_formation_status_html`) en MCP (`metis_mcp_queries_v1:71`)
tonen de **omgevingsmodus**, niet de route van het document. De uitvoering zelf kiest de strategie
opnieuw uit de omgeving: `pre_review_semantic_v1.py:1150` (`active_passage_formation_mode()`). Dat
valt nu alleen samen met de gepinde poging dankzij de fence.

**Hervatten.** `assert_resume_configuration` (`source_selection_v1.py:48–68`) eist dat de huidige
omgeving V3 is, dat het model en het contract van de opgeslagen replay-identiteit overeenkomen, en
dat de vorige `mode/model/docling` gelijk zijn. Anders volgt
`processing_resume_configuration_incompatible`.

**Bronsoort.** `class == beslisboom` gaat altijd naar `decision_tree_route_v1`, ongeacht de modus
(`pre_review_semantic_v1.py:1150–1160`). Toegelaten modi staan in
`passage_formation_policy_v1._ALLOWED_MODES`. Voor een beslisboom bevat
`processing_configuration.mode` toch de prozamodus van de omgeving: de feitelijk uitgevoerde
route (`decision-tree-source-bound-v1`) staat nergens als route vastgelegd.

## 3. Kloof per eis

| Eis | Huidig | Kloof |
| --- | --- | --- |
| N1 | De poging pint `mode/model/docling/deployment` en de actor | Geen policyversie en geen reden. `envelope.processing_configuration` wordt per poging **overschreven**, dus het is geen stabiele binding van de bronversie |
| N2 | Een lopende poging is gefenst; resume faalt gesloten | **Een nieuwe poging (retry, herselectie, ingest-herstel) neemt de huidige omgevingsmodus over**: na een omgevingswissel V2→V3 krijgt een retry van een V2-bron stil V3. Resume van een V2-bron is nooit mogelijk, ook niet als V2 nog is toegelaten |
| N3 | De omgeving bepaalt de route van **iedere** nieuwe poging, niet alleen van nieuwe verwerking | De omgeving is nu de route-autoriteit voor retries |
| N4 | De modus wordt gevalideerd; de beslisboom is hard gekoppeld | Geen per-bronsoort toelatingslijst voor proza; geen uitsluitingsmechanisme |
| N7 | `_unpinned` faalt gesloten; geen backfill | Legacy zonder configuratie kan geen nieuwe poging met de oude route krijgen; het gedrag is ongedefinieerd (zie B2) |
| UI | Toont de omgevingsmodus als "momenteel" | Geen weergave van de vastgelegde route per document |

Bijvangst: `deployment` (de commit) staat in dezelfde configuratie en fenst elke lopende poging bij
een deploy (`processing_configuration_changed`). Dat is een terechte fence op exacte code, maar
het is iets anders dan de route. Het ontwerp scheidt die twee.

## 4. Ontwerp (voorstel)

**Route ≠ uitvoeringsconfiguratie.** De *route-identiteit* is de contractversie (`semantic-source-bound-v1/v2/v3`,
`decision-tree-source-bound-v1`) plus de policyversie (`PASSAGE_FORMATION_POLICY_VERSION`), niet de
modusnaam. Die is documenttoestand en verandert alleen via een opvolger (nieuwe werkrevisie, N2).
`model`, `docling` en `deployment` blijven uitvoeringsconfiguratie per poging, met de bestaande
fences.

1. **Eén binding per werkrevisie (B1, optie A).** In deze code is de envelop (`snapshot_id`) de
   werkrevisie: een opvolger is een nieuwe envelop, eventueel over dezelfde bronbytes. Een nieuw veld
   `envelope["formation_route"] = {route, source_kind, policy_version, actor_id, reason, command_id,
   bound_at, origin}`. Het wordt **eenmalig** geschreven door de eerste reservering, binnen de
   bestaande transactie- en CAS-grens. Daarna is het onveranderlijk; er komt geen nieuwe store.
   `origin ∈ {selected, default, confirmed_legacy}`. Er bestaat geen automatisch geschreven
   `derived_legacy`-binding (B2-b, lifecycle-vsa §4).
2. **Elke poging verwijst ernaar.** Iedere poging draagt een kopie van de binding (route,
   policyversie, actor, reden) als auditbewijs (N1: vastlegging op bronversie én poging).
   `attempt.processing_configuration.mode` moet gelijk zijn aan `formation_route.route`; een
   verschil geeft `formation_route_mismatch` (fail closed, vóór commit). De vergelijking gaat over
   de **effectieve route** van de poging, niet over de ruwe modus:
   `effective_route(source_kind, mode)` geeft voor een beslisboom `decision-tree-source-bound-v1`
   (enige toegelaten route, strategie C) en voor proza de contractversie van de modus. Die wordt als
   `attempt.formation_route` vastgelegd, los van `processing_configuration.mode` (de
   omgevingsstandaard). De uitvoering (`pre_review_semantic_v1.py:1150`) leest de route uit de
   binding en de poging, niet uit `active_passage_formation_mode()`.
3. **Bron van de route bij de eerste binding.** Expliciete selectie door de actor (met reden), of de
   omgevingsstandaard met `origin = default`. Voor een beslisboom is dat altijd de enige toegelaten
   route, ongeacht de prozamodus. Retry, resume, herextractie, herstel en workerwissel lezen **alleen**
   `formation_route`, nooit de omgeving. Daarmee vervallen de omgevingsreads op `:1620`, `:2178`,
   `:2251` (herextractie) en `source_selection_v1.py:102` voor bestaande werkrevisies.
4. **Resume.** `assert_resume_configuration` vergelijkt met `formation_route` in plaats van met de
   omgevingsmodus. Een V2-bron is dan hervatbaar zolang V2 niet is uitgesloten en een
   durable-taakroute bestaat. Als V2 geen bounded-taakopslag heeft, blijft resume voor V2 gesloten
   met een eigen code (`formation_route_not_resumable`). Daarvoor is geen omgevingswissel nodig.
5. **Opvolger.** Een routewissel vereist een nieuwe **werkrevisie** (N2; lifecycle-vsa §5–6), geen
   nieuwe bronversie. Dat kan over dezelfde bronbytes via `decision_successor_v1` (nieuwe
   policyrevisie, verplichte `revision_reason`) of bij een nieuwe bronversie via ingest (lifecycle-vsa §7). De
   opvolger kiest bij de eerste reservering expliciet een eigen route met actor en reden; de
   voorganger blijft ongewijzigd.
6. **Uitsluiting (B3-a).** De toegelaten routes per bronsoort komen uit de strategietabel (§5.4,
   N4); een nieuwe route vereist een protocolwijziging (§15). De omgeving mag alleen beperken: een
   standaardroute en een uitsluitingslijst binnen die toegelaten set. Een standaard buiten de set
   faalt gesloten. Is een
   vastgelegde route uitgesloten, dan faalt een nieuwe poging met `formation_route_excluded`. Dat is
   zichtbaar in de blokkade-diagnostiek en de UI, er is geen terugval, en een expliciete opvolger
   is de enige weg.
7. **Uitvoerbaarheid na een deploy (B3-c).** Een nieuwe poging onder een nieuwe deploy mag alleen
   als de vastgelegde contract- en policyversie nog uitvoerbaar zijn. Anders faalt zij met
   `formation_route_not_executable`: zichtbaar, zonder terugval; alleen een opvolger. Een lopende
   poging blijft gefenst op `deployment` (bestaand gedrag).
8. **Weergave.** UI en MCP tonen de vastgelegde route per document. De omgevingsmodus wordt
   gelabeld als "standaard voor nieuwe verwerking".

**Optie B (afgewezen voorstel):** de route afleiden uit de eerste poging, zonder nieuw veld.
Goedkoper, maar dan is de route geen expliciete documenttoestand (N1). Pogingen kunnen
inconsistent zijn, en elke reader moet afleiden, met risico op verschillende afleidingen.

## 5. Legacy (B2) — geen backfill

Afleiding bij lezen, nooit automatisch wegschrijven (B2-b). Een afgeleide route is uitsluitend
leesbewijs, gelabeld als "afgeleid". Doorwerken op dezelfde werkrevisie vereist dat een actor de
afgeleide route expliciet bevestigt met een reden; dat legt `origin = confirmed_legacy` vast.
Dat mag alleen als de afleiding eenduidig is en de contractversie nog toegelaten en uitvoerbaar is.
Herstel en reconciliatie binden nooit (lifecycle-vsa §4, §13).

| Bewijs in de envelope | Afgeleide status | Gedrag bij nieuwe poging |
| --- | --- | --- |
| Alle pogingen hebben dezelfde `processing_configuration.mode` | `derived_legacy` (eenduidig) | Zonder bevestiging weigeren met `formation_route_unconfirmed`; na expliciete bevestiging door een actor (met reden) binden met `origin = confirmed_legacy`; een andere route alleen via een opvolger |
| Geen poging met configuratie, wel `semantic_replay.identity` met een contractversie | `derived_legacy` uit de replay-identiteit | Idem |
| Geen enkel routebewijs | `unrecorded` | Weigeren met `formation_route_unrecorded` (besluit B2-a); alleen een opvolger |
| Tegenstrijdige modi tussen pogingen | `conflicting` | Weigeren met `formation_route_conflicting`; alleen een opvolger. Zichtbaar in de diagnostiek |
| Gepubliceerd | n.v.t. | Nooit opnieuw vormen (bestaande regel); alleen lezen |

## 6. Besluiten (projectlead)

Besloten door de projectlead op 2026-10-28 ("ga door" op het oorspronkelijke voorstel). Na
toetsing aan de invarianten (PROTOCOL §5.4, lifecycle-vsa §4–7, §13) heeft de projectlead
dezelfde dag het herziene B2-b en de voorwaarde bij B3-c bevestigd ("ja"). Beide stonden in de
WP-updates van MET-13.

| ID | Vraag | Besluit |
| --- | --- | --- |
| B1 | Waar staat de route-autoriteit? | Optie A: `envelope.formation_route`, eenmalig, binnen de bestaande transactie |
| B2-a | Legacy zonder enig routebewijs: weigeren of aan de standaard binden? | Weigeren (veiligst, N7); opvolger als uitweg |
| B2-b | Is `derived_legacy` uit `semantic_replay.identity` voldoende bewijs? | Alleen als leesbewijs. Doorwerken op dezelfde werkrevisie vereist expliciete bevestiging door een actor met reden (`confirmed_legacy`), alleen bij eenduidige afleiding en een toegelaten, uitvoerbare contractversie. Nooit automatisch binden (N1; lifecycle-vsa §4) |
| B3-a | Vorm van de uitsluiting: lijst in de omgeving of in beheerconfiguratie? | Omgevingsvariabele naast de standaard; alleen beperkend binnen de toegelaten set per bronsoort uit de strategietabel (N3, N4) |
| B3-b | Hoort het **model** bij de route (pinnen per bronversie) of bij de uitvoering (per poging, met fence)? | Bij de uitvoering (PROTOCOL: modelkeuze is deployment-owned); per poging vastgelegd; het model in `semantic_replay.identity` blijft de grens voor exacte replay. Verandert de contractversie mee, dan is het een routewissel |
| B3-c | Mag een retry onder een nieuwe deploy doorgaan als route, model en docling gelijk zijn? | Ja voor een *nieuwe* poging, mits de vastgelegde contract- en policyversie nog uitvoerbaar zijn; anders `formation_route_not_executable`, zonder terugval. Een lopende poging blijft gefenst op `deployment` (bestaand gedrag) |

## 7. Implementatiecontract (voor het latere uitvoeringsissue)

Lifecycle-velden (`docs/agents/lifecycle-vsa.md`, `validate_change_contract.LIFECYCLE_FIELDS`):

| Veld | Invulling |
| --- | --- |
| Lifecycle entity | WorkingRevision (route-binding op de envelop, met de SourceSnapshot als bron); verwerkingspoging |
| Lifecycle transition | eerste reservering: `unbound → bound(route)`; daarna alleen leesbaar; route-wissel = nieuwe WorkingRevision (opvolger), eventueel over dezelfde SourceSnapshot-bytes |
| Initial durable state | envelope zonder `formation_route` (nieuw of legacy) |
| Trigger | ingest, eerste bronselectie, retry/resume van een werkrevisie zonder binding (legacy: alleen na expliciete bevestiging; herstel bindt nooit) |
| Authorization | bestaande `authorize` (bronselectie) en ingestrechten; geen nieuwe rol |
| Validation | route ∈ toegelaten routes voor bronsoort (strategietabel); niet uitgesloten; contract- en policyversie uitvoerbaar; poging-`mode` == binding; legacy alleen na expliciete bevestiging |
| Mutable entities | poging (nieuw), envelope-veld `formation_route` (alleen bij eerste binding) |
| Immutable entities | bestaande `formation_route`, gepubliceerde releases, eerdere pogingen |
| Workflow state before/after | ongewijzigd (processing/in_review/...); route is geen workflowstatus |
| Release state before/after | ongewijzigd |
| Serving state before/after | ongewijzigd |
| Expected API result | receipt bevat `formation_route`; fouten `formation_route_mismatch/excluded/conflicting/unrecorded/unconfirmed/not_executable/not_resumable` |
| Expected UI result | document toont vastgelegde route; omgeving als "standaard voor nieuwe verwerking" |
| Failure result | fail closed vóór commit; geen gedeeltelijke binding; geen poging zonder binding |
| Restart result | binding staat in de durable envelope; herstart leest binding, niet omgeving |
| Recovery result | resume/herstel gebruiken binding; checkpoint-incompatibiliteit faalt gesloten |
| Legacy-data result | zie §5; geen backfill |
| Required black-box scenario | §8, scenario 1–3 op native PostgreSQL en de productiecompositie |
| Explicit non-goals | geen nieuwe store, geen V3-cutover, geen modelpinning per bron (B3-b), geen migratie van gepubliceerd werk |

High-risk-velden (`continuous-development.md`):

| Veld | Invulling |
| --- | --- |
| Rewrite target | routebepaling van nieuwe pogingen (omgeving → binding) |
| Why local patching is insufficient | zes writers (incl. directe herextractie) en de uitvoering lezen de omgeving onafhankelijk; zonder één binding blijft er een stille wissel mogelijk |
| Current authority/writer/reader map | §2 |
| Supported runtime topologies | console + PostgreSQL workflow-store; workers via dispatch/handover; Azure-productiecompositie (`console_asgi`) |
| Persisted-state impact | één additief envelope-veld; pogingen ongewijzigd van vorm |
| Compatibility/migration plan | expand: readers accepteren envelopes met én zonder binding (legacy-afleiding §5); geen migratie-run |
| Rollback/recovery plan | softwareterugzetting: de oude code negeert het extra veld en leest de omgeving (vorig gedrag); geen data-rollback nodig |
| Cutover trigger | alle zes writers en de uitvoering (`pre_review_semantic_v1.py:1150`) gebruiken de binding; tests §8 groen op native PostgreSQL |
| Cleanup/decommission criteria | omgevingsreads op `:1620`, `:2178`, `:2251`, `source_selection_v1.py:102` en `pre_review_semantic_v1.py:1150` alleen nog voor de eerste binding; `assert_resume_configuration` vergelijkt met de binding |
| Failure blast radius | alleen nieuwe pogingen; lopende pogingen houden bestaande fences; geen effect op review/publicatie/serving |
| Adversarial proof matrix | §8 plus: alternatieve ingang (MCP/CLI/ASGI) bereikt dezelfde writer; gelijktijdige eerste binding; deploy tussen reservering en uitvoering |

## 8. Falsificatiescenario's (vooraf vastgelegd)

1. Ingest onder V2 → omgeving wordt V3 → retry, directe herextractie, workerwissel en herstart blijven V2. Is V2
   uitgesloten, dan faalt een nieuwe poging met `formation_route_excluded`, zonder vervanging.
2. Een opvolger kiest V3; de voorganger (V2, eventueel gepubliceerd) blijft ongewijzigd en blijft
   serveren.
3. Een dubbele registratie (zelfde `command_id`) maakt geen tweede poging of binding. Een stale writer
   (verouderde revisie) faalt. Een commit-failure laat geen gedeeltelijke binding achter.
4. Gelijktijdige eerste reserveringen op dezelfde bronversie leveren precies één binding op.
5. Legacy: eenduidig, ontbrekend en tegenstrijdig bewijs geven respectievelijk binding,
   weigering (`formation_route_unrecorded`, B2-a) en weigering (`formation_route_conflicting`). Immutable releases en de live voorganger blijven intact.
6. Een providerfout leidt niet tot een andere route of een alternatieve kandidaatmaker.
7. Een deploy tussen reservering en uitvoering blijft gefenst (bestaand). Een nieuwe poging na de deploy
   met dezelfde route, hetzelfde model en docling is toegestaan (B3-c). Is de vastgelegde
   contractversie na de deploy niet meer uitvoerbaar, dan volgt `formation_route_not_executable`
   zonder terugval.
9. Legacy met eenduidige afleiding: zonder bevestiging `formation_route_unconfirmed`; herstel,
   herstart en reconciliatie leggen nooit zelf een binding vast; na bevestiging door een actor
   met reden volgt precies één `confirmed_legacy`-binding.
8. Een beslisboom kan geen prozaroute binden en omgekeerd (N4). Een beslisboom die onder een
   prozastandaard (V2/V3) wordt verwerkt, bindt `decision-tree-source-bound-v1` en slaagt; een
   wissel van de prozamodus raakt een gebonden beslisboom niet.

Bewijs op native PostgreSQL en de productiecompositie; mocks gelden niet als herstelbewijs.

## 9. Gereed (#879)

- [x] Eigenaar, opslag, commando's en alle writers/readers (§2).
- [x] Kloof per norm (§3) en ontwerpvoorstel zonder tweede autoriteit (§4).
- [x] Legacy-gedrag zonder backfill (§5); route-uitsluiting en checkpoint-incompatibiliteit (§4.4, §4.6).
- [x] Alle lifecycle- en high-riskvelden voor het uitvoeringsissue (§7); falsificatiescenario's (§8).
- [x] Bevoegd besluit over B1, B2-a/b en B3-a/b/c (projectlead, 2026-10-28, §6).
- [x] Uitvoeringsissue (Class A, rewrite risk high) aangemaakt: #915 (MET-29).
