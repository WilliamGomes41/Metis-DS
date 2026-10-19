# Vervanging beslisboomvorming — omschakeling, verwijdering en open bewijs

**Peildatum:** 2026-10-18 · **Basis:** main `00586b9d` · **Norm:** Protocol v4.2 §5.2, §5.4 (strategie C), §10, §15

Werkbewijs bij de PR die de beslisboomvorming vervangt. Geen acceptatiebesluit.

## 1. Besluit en classificatie

```text
Change class: A
Promise: nieuwe beslisbomen (PDF en JSON-export) worden uitsluitend gevormd via bronextractie → brongebonden voorstel → deterministische constructie met materialise_knowledge_candidates als enige kandidaatmaker → bestaande validatie, review en publicatie; de oude structurele vorming bestaat niet meer.
Touches lifecycle invariants: yes
Rewrite risk: high
```

**Besluit William 2026-10-18:** geen oude en nieuwe vormingsarchitectuur naast elkaar. De omschakeling en de verwijdering gebeuren in één wijziging, zonder voorafgaand §10-experiment. Protocol 4.2.0 legt de route vast; de 4.1.0-stand staat onder `docs/history/protocol-v4.1/`. Inhoudelijke acceptatie van de route blijft open (§5).

| Mitigatieveld | Invulling |
| --- | --- |
| Rewrite target | Kandidaatvorming voor `class=beslisboom`, `kind ∈ {pdf, boom}`. |
| Why local patching is insufficient | Twee kandidaatmakers buiten de materialiser (`construction_spec`, `boom_spec_from_fragments`) en graafvorming uit geometrische heuristiek (`propose_routes`) zonder relatiegebonden bewijs. |
| Authority/writer/reader map | §3. Enige schrijver: bestaande verwerkingspoging en ingestcommit onder de WorkingRevision. |
| Supported runtime topologies | Ongewijzigd; geen nieuwe opslag, dispatcher, reviewpoort of publicatieroute. |
| Persisted-state impact | Nieuwe envelopevelden `decision_tree_formation` (route, policyversie, contracten, model, voorstelhash, actor, reden) en `decision_tree_construction` (referenties, bevindingen). Object-ID's van nieuwe bomen komen van de materialiser (`{document}-sem-{hash}`). Geen backfill. |
| Compatibility | Vóór de omschakeling gevormde bomen blijven leesbaar en verifieerbaar; hun eenheden worden niet opnieuw gevormd of met vervallen logica gecorrigeerd. |
| Rollback/recovery | Rollback = vorig vastgelegd softwareartefact. Nieuwe-route-envelopes zijn dan onbekend voor de oude code; vóór een rollback moet worden vastgesteld of er al nieuwe-route-snapshots zijn (inventaris). Een getest herstelplan voor die situatie ontbreekt nog. |
| Cutover trigger | Besluit William 2026-10-18. |
| Cleanup criteria | Uitgevoerd in deze wijziging (§4). |
| Failure blast radius | Alle nieuwe beslisboomverwerking. PDF zonder geconfigureerde provider faalt gesloten (`pre_review_llm_decision_tree_proposer_unbound`). |
| Adversarial proof matrix | §6. |

## 2. De route

| Stap | Eigenaar |
| --- | --- |
| Extractie en bronrepresentatie | `decision_tree_route_v1.source_fragments` (PDF: `decision_graph_v1.pdf_fragments` met regelsplitsing; JSON: exportfragmenten + bundelsplitsing). Ook gebruikt bij herlezen (`_read_source_fragments` op route-marker). |
| Bewijs | `decision_graph_v1.source_evidence`: tekst, tekeningen, expliciete exportrelaties. Zelfde functie bij ingest en bij bronverificatie. |
| Voorstel | PDF: `decision_tree_route_v1.request_proposal` (begrensd modelverzoek, strikt schema, geen terugval). JSON: `export_proposal` (één eenheid per exportitem, rollen open voor de reviewer, verbindingen uit exportrecords). |
| Contract en relatiebewijs | `decision_tree_proposal_v1`: gesloten vorm; per verbinding: samenhangende lijn tussen precies deze eindpunten, pijlrichting, label op die lijn, exportrecord van/naar/label, of brongebonden paginaovergang. |
| Constructie | `decision_tree_construction_v1.construct` → `materialise_knowledge_candidates` (enige maker van tekst, identiteit, bronmapping); graafplan, contextbindingen, bundels; onzekerheid blijft `unresolved`, menselijke bevestiging altijd verplicht. |
| Afronding | `decision_tree_route_v1.finalize`: bundelstempel, graafbinding aan exacte objectversies, afgeleide toelating (`apply_gate`), passage-register, routevastlegging. |
| Review/publicatie | Ongewijzigd: `decision_review_commands_v1`, `publication_issues`, `release_graph`, `read_active_graph`. |
| Correctie | Bronselectie-reparatie via `source_units` → materialiser (zelfde pad als proza). |

## 3. Productiecallers: voor en na

| Plek (main) | Was | Is |
| --- | --- | --- |
| `pre_review_semantic_v1.py:1103` | PDF-beslisboom naar oude structurele verwerking | `class=beslisboom` (pdf/boom) naar `decision_tree_route_v1.prepare`; modelvoorsteller per console gebonden |
| `operations_console_v1.py:2921` (`_deterministic_fragments_and_spec`) | `boom_spec_from_fragments` + `construction_spec` (PDF en JSON) | `decision_tree_route_v1.prepare` |
| `operations_console_v1.py:2045` en `:2554` (ingest, herverwerking) | `prepare_graph` | `decision_tree_route_v1.finalize` |
| `decision_graph_v1.py:129` | `propose_routes` vormde graafverbindingen | verwijderd; geometrie alleen nog als relatiebewijs in het contract |
| `decision_graph_v1.py:305` (`verify_source_evidence`) | riep graafopbouw aan | reconstrueert uitsluitend bewijs (`source_evidence`) |
| reviewcorrectie (`correct_object`, boom-pad) | `rebuild_for_revision` met groeperingslogica | nieuwe eenheden: materialiser; oude eenheden: `decision_unit_legacy_revision_retired` |
| `reextract_unpublished` | — | oude-routewerk: `decision_tree_legacy_route_retired` |
| `_bounded_semantic_preparation` | beslisbomen uitgesloten | PDF-beslisboom is een begrensde poging (deadline, faalregistratie) |

## 4. Verwijderingsinventaris

| Onderdeel | Uitkomst | Reden |
| --- | --- | --- |
| `decision_unit_construction_v1.construction_spec`, `groups`, `_compatible`, `_continues`, `record`, `rebuild_for_revision` | **verwijderd** | vormings- en groeperingslogica |
| `pdf_route_proposals_v1` (module) | **verwijderd** | graafvorming uit geometrie; benodigde geometrie zit smal in het contract |
| `beslisboom_path_v1.boom_spec_from_fragments` | **verwijderd** | tweede kandidaatmaker (JSON-export) |
| `decision_graph_v1.prepare_graph` | **verwijderd** | vervangen door `source_evidence` + `finalize` |
| `decision_graph_proposals` (envelope/UI) | **verwijderd** | UI toont nu open punten van de route |
| `explicit_decision_graph` (formatiecontext) | **verwijderd** | bundelsplitsing hoort bij de vastgelegde bronrepresentatie |
| Experiment-baseline | **verwijderd** | er is geen oude route meer om mee te vergelijken |
| `tests/test_decision_unit_construction.py`, `tests/test_pdf_route_proposals.py`, `tests/test_decision_release_source_repair.py` | **verwijderd** | hielden alleen afgeschafte vorming in stand; veiligheidsgedrag herschreven in `tests/test_decision_tree_route_lifecycle_v1.py` en `tests/test_decision_tree_proposal_route_v1.py` |
| `add_layout`, `source_lines` | **verplaatst** naar `decision_graph_v1`, actief | bronrepresentatie; historische fragment-ID's hangen ervan af |
| `reconstruct`, `unit_issues`, `_complete`, `finalized_source_refs`, `label_usage`, `branch_label` | **behouden, alleen historische uitlezing/validatie** | gepubliceerde en lopende oude-routebomen moeten verifieerbaar blijven |
| `apply_gate` | **behouden, actief** | afgeleide toelating voor oude én nieuwe eenheden |
| `evidence_inventory`, `pdf_fragments`, `graph_issues`, `publication_issues`, `release_graph`, `read_active_graph`, `ordered_paths` | **behouden, actief** | bewijs, validatie, review, publicatie, retrieval |
| `passage_formation_policy_v1` (`kind=boom` → deterministisch) | **behouden** | geldt alleen nog voor JSON-exports van andere klassen dan beslisboom |

Geen featureflag, wrapper of `legacy`-kopie toegevoegd.

## 5. Status

| | Geïmplementeerd | Getest | Inhoudelijk geaccepteerd |
| --- | --- | --- | --- |
| Eén route PDF + JSON, oude vorming verwijderd | ja | ja (synthetische PDF's en exports, volledige suite) | **nee** |
| Routevastlegging op envelope | ja | ja | n.v.t. |
| Providerfout/ongeldig voorstel faalt gesloten zonder objecten | ja | ja | n.v.t. |
| Oude-routewerk leesbaar, niet opnieuw gevormd | ja | ja | n.v.t. |
| Paginaovergang als relatiebewijs in de graafvalidator | nee (constructie levert het; validator blokkeert) | ja (blokkade) | nee |
| Contextbindingen reviewgebonden in canonieke hash | nee (vastgelegd op envelope, niet in objecthash) | — | nee |
| Echte provideruitvoer op productieachtige PDF's | nee | nee | nee |
| Getest rollbackplan na eerste nieuwe-route-snapshots | nee | nee | nee |

## 6. Adversariële bewijsmatrix

| Scenario | Bewijs |
| --- | --- |
| Model levert object-ID/canonieke tekst, verzonnen citaat, onbekend blok/bewijs/eindpunt | geweigerd (contract/materialiser), ingest geblokkeerd zonder objecten |
| Geen of falende provider | `pre_review_llm_decision_tree_proposer_unbound` / `_proposal_rejected`; geen andere route |
| Lijn verbindt andere eindpunten / label op verkeerde lijn / pijl verkeerd | `graphic_not_bound_to_endpoints` / `label_not_on_route` / `direction_conflict` → geen verbinding |
| Onzeker volgens voorsteller zelf | verbinding niet aangemaakt, blijft `unresolved` |
| Gepubliceerde graaf gemanipuleerd (tekst, span, modus, review) | `read_active_graph` weigert |
| Herverwerking/correctie van oude-routewerk | gesloten geweigerd; bronverificatie werkt zonder vormingscode |
| Vervallen code bereikbaar via import/attribuut | AST-proef over `src/`, `ModuleNotFoundError` voor de verwijderde module |
| Bronreparatie na cachewissel, verouderde revisie, nieuwe revisie | bestaande A10-tests, nu ook voor beslisboom-PDF en -JSON |
