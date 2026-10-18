# Vervanging beslisboomvorming — inventaris, status en omschakelplan

**Peildatum:** 2026-10-18 · **Basis:** main `00586b9d` · **Norm:** Protocol v4.1 §5.4 (strategie C), §10, §15

Dit document is werkbewijs bij de PR die de brongebonden voorstelroute voor beslisbomen bouwt. Het is geen protocoltekst en geen acceptatiebesluit.

## 1. Classificatie

```text
Change class: A
Promise: nieuwe PDF-beslisbomen worden gevormd via bronextractie → brongebonden semantisch voorstel → deterministische constructie via materialise_knowledge_candidates → bestaande validatie, review en publicatie.
Proof: experiment op bevroren bronnen met onafhankelijke menselijke referentie (§10), daarna black-box-lifecycleproef van de omschakeling.
Touches lifecycle invariants: yes (verwerkingsidentiteit, retry/herstel van de vastgelegde route, reviewbinding)
Rewrite risk: high
```

Deze PR levert alleen de **kandidaatroute binnen de experimentgrens**. Productie-ingest, review, publicatie en herstel zijn ongewijzigd.

### Verplichte mitigatievelden (continuous-development §2)

| Veld | Invulling |
| --- | --- |
| Rewrite target | Kandidaatvorming voor `kind=pdf, class=beslisboom`: `construction_spec` + groeperingsheuristiek + uitzonderingsvertakkingen in `pre_review_semantic_v1` en `_deterministic_fragments_and_spec`. |
| Why local patching is insufficient | De huidige route is een tweede kandidaatmaker vóór review (in strijd met de AGENTS-invariant) en groepeert via lexicale/layoutregels zonder brongebonden relatiebewijs. |
| Current authority/writer/reader map | Zie §3. Enige schrijver blijft de bestaande verwerkingspoging onder `WorkingRevision` (PostgreSQL); review via `decision_review_commands_v1`; publicatie via `release_graph`/`publication_issues`; lezen gepubliceerd via `read_active_graph`. |
| Supported runtime topologies | Ongewijzigd (§13 protocol). De kandidaatroute schrijft niets. |
| Persisted-state impact | Deze PR: geen. Omschakeling: nieuwe route-marker op envelope/poging; geen backfill. |
| Compatibility/migration plan | Expand → experiment → protocolwijziging → cutover-PR → afzonderlijke verwijder-PR. Historische snapshots behouden hun route (`decision_unit_contract`). |
| Rollback/recovery plan | Tot de verwijder-PR blijft de oude route code-aanwezig; rollback = vorig vastgelegd softwareartefact. Na verwijdering: herstel via vastgelegd artefact en getest herstelplan (open). |
| Cutover trigger | Experimentuitkomst `READY FOR IMPLEMENTATION` op vooraf vastgelegde criteria + protocolwijziging §15 + GO William. |
| Cleanup/decommission criteria | Inventaris §4 zonder blokkers (`scripts/decision_tree_route_inventory.py` exit 0), kandidaatroute geaccepteerd, historische uitleesproeven groen. |
| Failure blast radius | Deze PR: geen productiepad (statische importproef). Cutover: alleen nieuwe PDF-beslisboomverwerking. |
| Adversarial proof matrix | §5. |

## 2. Wat deze PR bouwt

| Onderdeel | Bestand | Rol |
| --- | --- | --- |
| Voorstelcontract `decision-tree-proposal-v1` | `src/decision_tree_proposal_v1.py` | Strikte vorm: eenheden met tijdelijke referenties, rol, exacte spans en geciteerde tekst; verbindingen met letterlijke labelspan en bewijs-ID's; contextbindingen; resultaatbundels; onopgeloste punten. Geen object-ID of canonieke tekst toegestaan. |
| Relatiebewijscontrole | idem, `relation_findings` | Controle 2 van 3: is het geciteerde bewijs aan déze relatie gekoppeld? Grafisch: hergebruik `pdf_route_proposals_v1` tussen dezelfde eindpunten; label moet op de verbindende lijn liggen. Export: record-van/naar/label moet kloppen. Paginaovergang: brontekst op de bronpagina noemt de doelpagina. Bevindingen bevestigen niets. |
| Constructie `decision-tree-construction-v1` | `src/decision_tree_construction_v1.py` | Stuurt spans naar `materialise_knowledge_candidates` (enige maker), vertaalt referenties, plant graaf/contextbindingen/bundels. Vult niets aan; ongebonden relaties worden `unresolved`. `human_route_confirmation_required` blijft altijd staan. |
| Experiment (Audit) | `src/decision_tree_experiment_v1.py` | Baseline- en kandidaatarm op dezelfde bevroren bytes, providervoorstel (begrensd, geen terugval), vergelijking met menselijke referentie, vooraf vastgelegde beslisregel (max. `READY FOR IMPLEMENTATION`). |
| Preregistratie | `data/audit/decision_tree_route_experiment_v1.json` | Metrics en vaste regels; grenswaarden en corpus bewust leeg. |
| Inventaris oude pogingen | `scripts/decision_tree_route_inventory.py` | Alleen-lezen; markeert lopende en herprobeerbare structurele pogingen. |

Kleine additieve wijzigingen in bestaande modules:

- `knowledge_materialisation_v1.selection_source_blocks`: publieke weergave van precies de bronblokken die de materialiser accepteert.
- `semantic_transform_generic_v1`: `formation_mode` accepteert `decision-tree-source-bound-v1` als formatieherkomst. Geen bestaande route zet deze waarde.

## 3. Huidige route: wie maakt kandidaten, wie levert bewijs, wie leest historie

| Functie | Verantwoordelijkheid | Callers | Na omschakeling |
| --- | --- | --- | --- |
| `pre_review_semantic_v1.configured_fragments_and_spec`, vertakking `kind=="pdf" and class_=="beslisboom"` | Routering: omzeilt de vormingspolicy en roept de structurele route aan | `SourceProcessingStrategy.prepare` | **verwijderen**; vervangen door dispatch op vastgelegde route |
| `operations_console_v1._deterministic_fragments_and_spec`, PDF-beslisboomtak | Extractie + `boom_spec_from_fragments` + `construction_spec` | `_fragments_and_spec`, rechtstreeks bij ontbrekende strategie | **verwijderen** (vormingsdeel); extractieaanroep `pdf_fragments` behouden |
| `decision_unit_construction_v1.construction_spec` | **Tweede kandidaatmaker** (tekst, identiteit `-unit-…`, bronmapping) | bovenstaande tak; experiment-baseline | **verwijderen** |
| `decision_unit_construction_v1._complete/_continues/_compatible/groups`, regex `ACTION/QUESTION/INSTRUCTION/TRAILING` | Lexicale/layoutgroepering en rolinterpretatie | `construction_spec`, `rebuild_for_revision` | **behouden uitsluitend voor lopende/historische werkrevisies** (reviewcorrectie via `rebuild_for_revision`) totdat inventaris leeg is; daarna verwijderen |
| `decision_unit_construction_v1.record`, `reconstruct`, `unit_issues`, `finalized_source_refs`, `rebuild_for_revision` | Lezen/valideren van bestaande unit-evidence | `semantic_transform_generic_v1`, `deterministic_review_repair_v1`, `operations_console_v1` (reviewcorrectie), `decision_graph_v1.graph_issues` | **behouden voor historische uitlezing en lopende review**; geen nieuwe vorming |
| `decision_unit_construction_v1.apply_gate`, `label_usage`, `branch_label` | Afgeleide toelating; labelgebruik in gepubliceerde grafen | `admission_gate_v1`, `decision_graph_v1` (incl. `read_active_graph`), `decision_review_commands_v1`, `decision_review_ui_v1` | **behouden** (actief voor gepubliceerde releases) |
| `decision_unit_construction_v1.add_layout`, `source_lines` | Bronrepresentatie (regelsplitsing, layoutbewijs) | `decision_graph_v1.pdf_fragments`; historische reconstructie via `_read_source_fragments(construct_units=…)` | **behouden actief**: ook de nieuwe route gebruikt deze fragmenten; historische fragment-ID's hangen ervan af |
| `pdf_route_proposals_v1.propose_routes` | Begrensd geometrisch bewijs | `prepare_graph`; nieuwe `relation_findings` | **behouden actief** (bewijsleverancier, geen autoriteit) |
| `decision_graph_v1.pdf_fragments`, `evidence_inventory`, `verify_source_evidence` | Extractie en reconstrueerbaar bewijs | ingest, review, herstel | **behouden actief** |
| `decision_graph_v1.prepare_graph`, PDF-tak (`proposals` → `edges` filter op `constructed`) | Graafopbouw uit geometrische voorstellen | ingest, re-preparatie (`operations_console_v1:2555`) | **vervangen** door `bind_graph` voor de nieuwe route; inventarisdeel blijft nodig voor `verify_source_evidence` |
| `decision_graph_v1.graph_issues`, `publication_issues`, `release_graph`, `read_active_graph`, `ordered_paths`, `review_target` | Validatie, reviewbinding, publicatie, retrieval | review, publicatie, Product API | **behouden**; gerichte uitbreiding nodig (paginaovergang, contextbindingen, zie §6) |
| `passage_formation_policy_v1` (`kind=="boom"` → structureel) | Policy voor JSON-export-bomen; PDF-bomen bereiken deze policy niet | `pre_review_semantic_v1` | **wijzigen bij omschakeling**: toegelaten routes per bronsoort |
| `beslisboom_path_v1.boom_spec_from_fragments` | Eén fragment = één kandidaat, ook voor JSON-export (`kind=boom`) | beide boomtakken | **open domeinbesluit**: de JSON-exportroute is óók een kandidaatmaker buiten de materialiser; buiten scope van deze opdracht (PDF) |
| `tests/test_decision_unit_construction.py` (groeperingsgedrag) | Houdt `construction_spec` in stand | — | **verwijderen of herschrijven** in de verwijder-PR; veiligheidstests (bronfideliteit, kolommen niet samenvoegen) herschrijven naar het nieuwe contract |
| `tests/test_decision_release_source_repair.py` | Historische reconstructie en reparatie | — | **behouden** |

Lopende werkrevisies en hun vastgelegde route worden bepaald met `scripts/decision_tree_route_inventory.py`. De vastgelegde `processing_configuration.mode` beschrijft voor PDF-bomen de prozaroute, níet de werkelijk gebruikte structurele route; de duurzame marker is `decision_unit_contract` (zie ook ROADMAP R4.6).

## 4. Status

| Onderdeel | Geïmplementeerd | Getest | Inhoudelijk geaccepteerd | Geblokkeerd door |
| --- | --- | --- | --- | --- |
| Voorstelcontract + relatiebewijscontrole | ja | ja (synthetisch) | nee | experiment |
| Constructie via enige materialiser | ja | ja (identiteit = materialiser, deterministisch, weigering verzonnen tekst) | nee | experiment |
| Experiment- en beslisregel | ja | ja | n.v.t. | grenswaarden, corpus, onafhankelijke referentie |
| Providervoorstel (begrensd, geen terugval) | ja | ja (fout/weigering/geen sleutel) | nee | echte provideruitvoer op bevroren bronnen |
| Transactionele toepassing in verwerkingspoging, retry/hervatting/herstart, dubbele uitvoering, gelijktijdige revisie, verlopen poging | nee | nee | nee | acceptatie + protocolwijziging (cutover-PR) |
| Contextbindingen en paginaovergangen in reviewgebonden graaf | gepland (constructie levert ze) | deels | nee | gerichte uitbreiding validator/graafschema |
| Verwijdering oude vormingsroute | nee | — | — | omschakeling, inventaris zonder blokkers |
| Historische uitlezing na verwijdering | bestaande tests groen | ja (bestaand) | — | wordt opnieuw bewezen in verwijder-PR |

**De vervangen route is nog actief en de enige productieroute.** Dat is bewust: Protocol v4.1 §5.4 staat voor strategie C alleen de structurele route toe; een nieuwe route mag pas na experiment (§10) en protocolwijziging (§15) worden geactiveerd.

## 5. Adversariële bewijsmatrix

| Scenario | Bewijs nu | Bij cutover |
| --- | --- | --- |
| Model levert object-ID of canonieke tekst | geweigerd (`decision_proposal_unit_invalid`) | idem |
| Geciteerde tekst wijkt af van bron | `materialisation_text_mismatch` | idem |
| Onbekend blok / span buiten grenzen / onbekend bewijs / onbekend eindpunt | fail-closed | idem |
| Dubbele eenheid (zelfde spans) | `decision_construction_duplicate_unit` | idem |
| Lijn bestaat maar verbindt andere eindpunten | `graphic_not_bound_to_endpoints` → unresolved | idem |
| Labels verwisseld (beide letterlijk aanwezig) | `label_not_on_route` → geen verbinding | idem |
| Onbekend doel | `target_unknown` → unresolved, publicatieblokkade | idem |
| Paginaovergang | brongebonden check; bestaande validator blokkeert nog | validator gericht uitbreiden |
| Providerfout/timeout/weigering | fout, geen baseline-aanroep | poging faalt zichtbaar, geen oude route |
| Materialiser weigert | constructie faalt geheel | geen gedeeltelijke activering |
| Productie kan nieuwe route aanroepen | statische importproef: alleen experiment importeert | registratie alleen via vastgelegde route |
| Dubbele uitvoering / gelijktijdige revisie / verlopen poging / herstart | — | bestaande pogingsmechanismen, black-box-proef verplicht |
| Bestaande publicatie bij mislukking | — | black-box-proef verplicht |

## 6. Benodigd vóór cutover (open)

1. Grenswaarden, corpus en onafhankelijke referentiemaker (William). Zonder dit is geen acceptatie mogelijk.
2. Experimentuitvoering met echte provider op bevroren bronnen; resultaten in Audit.
3. Protocolwijziging §5.4-tabel (strategie C: toegelaten routes, standaardroute) volgens §15 met historische snapshot.
4. Cutover-PR: route vastleggen op bronversie en poging; `_read_source_fragments` kiest `construct_units` ook voor de nieuwe route-marker; transform laat een gesloten metadata-sleutel voor contextbindingen toe (canonieke hash → reviewgebonden); `graph_issues` accepteert brongebonden paginaovergangen; atomaire toepassing kandidaten + graaf + bindingen + disposities + audit; black-box-lifecycleproef.
5. Domeinbesluit JSON-exportroute (`kind=boom`): ook naar de materialiser, of expliciet uitgezonderd.
6. Verwijder-PR na inventaris zonder blokkers.
