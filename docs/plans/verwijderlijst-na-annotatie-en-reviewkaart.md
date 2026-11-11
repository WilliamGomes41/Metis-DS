# Verwijderlijst na annotatie-vorming en de nieuwe reviewkaart

> Tweede controle verwerkt op 11 november 2026. Uitvoering: [verwijderplan](verwijderplan-na-annotatie-en-reviewkaart.md), #1047 / MET-69 onder MET-11. Dit document blijft een kandidateninventaris.

Change class: C — deze inventaris verandert geen runtimegedrag.
Rewrite risk: none — voor deze lijst. Elke verwijdering uit deel B is Class A of B met
eigen contract; de vorming- en reviewkern zijn `Rewrite risk: high`.

Opdracht William (2026-11-11): neem de veranderingen in Linear en GitHub door en maak
een lijst van code en modules die ontkoppeld en verwijderd moeten worden, zodat er geen
dode code en geen tweede weg of tweede schrijfroute overblijft.

## Basis en methode

- Code: `main` `d5715e61ca47554b89853f190202ad388c30ed07` (na de merge van #1046).
- Gelezen: Linear MET-57 (#1013), MET-61 (#1017, HA-4), MET-56 (#995, KO-programma);
  `docs/plans/ko-statechart-program.md` (KO-5, KO-6);
  `docs/change-contracts/1012-ko5-single-way.md`,
  `1017-human-annotation-transition.md`, `1017-prose-transition.md`;
  `docs/architecture/prose-transition-1017.md`; `docs/LEGACY_ROUTES.md`;
  `config/code_lifecycle_inventory.v1.json` (peildatum 2026-10-04, dus van vóór de annotatieroute).
- Gemeten op de code: de importgraaf van alle `src`-modules, `vulture` over `src` en
  `scripts` (zonder tests, zodat "alleen door tests gebruikt" zichtbaar wordt), elke
  naam daarna met `grep -w` nagelopen in `src`, `scripts`, `.github` en `db`, en de
  volledige lijst van HTTP-routes met hun eigenaar.

Dit is statische inspectie. Aanroepen via `getattr`, een ingang die een operator
buiten de repo gebruikt, en gedrag op productiedata zijn hiermee niet uitgesloten.
Niets in deze lijst is uitgevoerd of getest als verwijdering.

## Doelbeeld: één weg

| Stap | De ene route | Eigenaar |
| --- | --- | --- |
| Vorming van proza | bron openen → annoteren → afsluiten → bouwen | `/annotations/*`, `human_annotation_v1`, `human_annotation_build_v1` |
| Kandidaten maken | deterministische materialisatie | `knowledge_materialisation_v1.materialise_knowledge_candidates` (harde invariant in `AGENTS.md`) |
| Vorming van een beslisboom | bestaande boomroute | `decision_tree_route_v1` |
| Beoordelen | reviewkaart met inhoudsopgave en drie vragen | `ko_review_page_v1`, `ko_document_context_ui_v1` |
| Opslaan van een besluit | één command, één transitietabel | `POST /review` → `review_command_v1` → `ko_transitions_v1.apply_ko_event` |
| Terugzien | bon na opslag | `ko_receipt_ui_v1` |
| Publiceren en serving | canoniek register | `PostgresCanonicalPublicationStore` |

Alles hieronder wijkt van dit doelbeeld af of wordt er niet meer door gebruikt.

## A. Kandidaten zonder aangetoonde productie-aanroep

### A1. Geen directe aanroep gevonden, ook niet door tests

#1047 verwijdert uitsluitend `validate_source_integrity`, `knowledge_open_count`,
`session_is_expired` en `list_processing_history_inputs`. De tabel bewaart hun
oorspronkelijke vindplaatsen. De twee overige functies en de module blijven behouden.

| Plek | Naam | Opmerking |
| --- | --- | --- |
| `src/integrity_kernel.py:160` | `validate_source_integrity` | Komt nergens anders voor |
| `src/operations_console_app.py:1997` | `knowledge_open_count` | Alleen nog genoemd in `docs/change-contracts/domain-workplaces.md` |
| `src/operations_console_v1.py:355` | `session_is_expired` | Komt nergens anders voor |
| `src/review/deterministic_review_repair_v1.py:360` | `_finalize_source_provenance` | Alleen nog in `console-read-dependencies.json` en het contract #505 |
| `src/workflows/workflow_documents_cutover_v1.py:420` | `list_processing_history_inputs` | Komt nergens anders voor |
| `src/workflows/workflow_remaining_cutover_v1.py:149` | `prior_object_audit_history` | Historische lezer; behoudscontract eerst beoordelen |
| `src/storage_prepare.py` | hele module | `LEGACY-UNUSED`, maar expliciet behouden als OPENVRAAG-S3 in `docs/history/DEAD_CODE_REMOVAL.md`; extern operatorgebruik eerst besluiten |

### A2. Alleen nog door tests gebruikt

De statische inspectie vond alleen testaanroepen; de aantallen horen bij de
inspectiebasis. Dit bewijst niet dat het contract vervalt. Bepaal eerst testdoel,
herstelcontract en operatorgebruik. Verwijder geen test om een verwijdering groen
te krijgen. Controleer ook of de functie bewust een weigering bewijst
(`public_signup`, `silently_edit_object`): dan hoort de weigering in de test thuis, niet
als methode op de console.

| Module | Namen (testbestanden) |
| --- | --- |
| `src/operations_console_v1.py` | `remaining_unclassified` (6), `remaining_not_duty` (1), `_save_objects_pinned` (1), `public_signup` (1), `snapshot_containers` (3), `silently_edit_object` (1), `live_snapshot` (1), `researcher_path` (1) |
| `src/operations_console_app.py` | `_coverage_panel` (1), `_processing_diagnostics_html` (2) |
| `src/review/beslisboom_path_v1.py` | `scorelist_item_model`, `boom_serving_activated`, `class_outranks`, `split_or_reject_multi_bullet_outcome`, `outcome_strength_applies`, `preferred_same_family_advice` (elk 1) |
| `src/review/proportionate_review_v1.py` | `normal_risk_batch_counts` (1) |
| `src/review/review_duty_v1.py` | `repair_duty_count` (1) |
| `src/review/domain_dimensions_v1.py` | `project_review_domain_dimensions` (1) |
| `src/review/review_ledger.py` | `unregister_backend` (5) — testhulp; hoort in testondersteuning |
| `src/vorming/admission_gate_v1.py` | `blocked_audit_lane` (5) |
| `src/vorming/extract_metrics_v1.py` | `extract_quality_claim_allowed` (3), `compute_extract_metrics` (3), `measure_admission_language_variation` (2) — de hele module (761 regels) heeft geen productie-importeur |
| `src/vorming/heading_parent_list_v1.py` | `freeze_heading_anchors` (1), `default_structural_parent` (1) |
| `src/vorming/recommendation_semantics_v1.py` | `legacy_recommendation_semantics_view` (1) |
| `src/knowledge_relations_v1.py` | `knowledge_relation_set_hash` (1), `legacy_knowledge_relations_view` (1) |
| `src/object_taxonomy_v1.py` | `stamp_value` (1), `is_truncated_sentence` (1), `is_tiny_confirmable_text` (4) |
| `src/serving_relations_v1.py` | `applies_if_targets` (1), `except_if_targets` (1) |
| `src/publication/published_projection_v1.py` | `PublishedProjection` (1) — hele module zonder productie-importeur |
| `src/publication/publication_refusal_store_v1.py` | `store_path` (2), `read_records` (1) |
| `src/publication/publish_refusal_audit_v1.py` | `suppressed_failure_count` (1) |
| `src/compiled_knowledge_v1.py` | `compiled_knowledge_inputs` (1) — hele module zonder productie-importeur |
| `src/audit_retention_v1.py` | `AuditRetentionService` (3), `list_archived` (2) — behouden onder `audit-room-retirement.md` |
| `src/workflows/workflow_remaining_cutover_v1.py` | `PostgresAuditRegistry` (3) — behouden audit-/herstelonderdeel |
| `src/workflows/workflow_review_postgres_v1.py` | `read_events_after` (1) |
| `src/workflows/operational_document_inputs_v1.py` | `prepare_operational_inputs` (3), `activate_operational_inputs` (3) — zie B8 |
| `src/workflows/processing_archives_v1.py` | `processing_archive_header` (1) |
| `src/vorming/decision_tree_experiment_v1.py` | `route_output` (1), `compare_to_reference` (1) |
| Overig | `storage_app_settings` (`deploy_identity_v1`), `class_change_consequence` (`klasse_wijzigen_v1`), `validate_extract_gold` (`evaluation/validate_golden_set`), `assert_url_destination_allowed` (`ingest_limits_v1`), `apply_clean_wwwroot` (`runtime_data_inventory_v1`) |

### A3. Modules zonder importeur in `src`

Geen andere `src`-module importeert deze. Ze leven op een script, een test of een
CLI-ingang. Het register noemt `protocol_approval_manifest`, `register_source_binary`,
`azure_step9_cutover_v1` en `g2_azure_preflight` al `ACTIVE-OPERATOR` onder oude
paden. Behoud die status tot nieuw bewijs of een expliciet uitfaseringsbesluit.

| Module | Regels | Gebruikt door | Voorstel |
| --- | --- | --- | --- |
| `src/audit_pdf_text_completeness.py` | 90 | 1 test | Verwijderen, tenzij een operator het los draait |
| `src/protocol_approval_manifest.py` | 69 | 1 test | `ACTIVE-OPERATOR`; gebruik en uitfasering eerst vaststellen |
| `src/ingest/register_source_binary.py` | 122 | 2 tests | `ACTIVE-OPERATOR` onder oud plat pad; behouden tot gebruik/uitfasering is vastgesteld |
| `src/vorming/decision_tree_experiment_v1.py` | 154 | 1 script, 1 test | Experiment; verwijderen na besluit over de boomroute |
| `src/evaluation/*` (vier modules) | 586 | tests, shellscripts | Evaluatiegereedschap; houden als dat zo bedoeld is |
| `src/publication/legacy_canonical_recovery_v1.py` | 238 | 1 script, 2 tests | Hersteltool; verwijderen zodra het herstel aantoonbaar klaar is |
| `src/azure_step9_cutover_v1.py`, `src/g2_azure_preflight.py` | 693 | eenmalige cutover-scripts | Verwijderen als de cutover is afgesloten |
| `src/workflows/workflow_postgres_migration_v1.py`, `workflow_chain_recovery_v1.py`, `account_retirement_v1.py` | 1.439 | scripts | Operatorgereedschap; houden |

## B. Tweede wegen die nog aanstaan: eerst ontkoppelen, dan verwijderen

### B1. Oude AI-vorming van proza naast annotatie

De kaart staat al in `docs/change-contracts/1017-human-annotation-transition.md`
("Huidige codekaart en benodigde subtractie"). Stand op deze code:

- **Al gedaan:** `document_spec` staat in `document_spec_v1`; bronfilters in
  `prepared_source_views_v1`; leescontracten in `semantic_proposal_contract_v1`;
  boomtransport in `bounded_model_call_v1`. Het stopcommando per werkrevisie bestaat
  (`prose_transition_v1`).
- **Nog aan:** `console_asgi` installeert `bind_pre_review_semantic_processing` bij
  elke start. `POST /source-selection/start` reserveert nog een AI-poging voor proza
  dat niet door een mens is overgenomen. De knop "Hervatten" gebruikt die ingang.
  `/tree/reprocess` en `/tree/resume-formation` navigeren alleen naar bronselectie.
  `/tree/processing-recovery` autoriseert herstel als afzonderlijke handeling.
  Bestaande pending taken en interne/achtergrondcallers moeten ook worden gesloten.

Te verwijderen na de bewezen overgang, in deze volgorde:

1. Ingangen: `POST /source-selection/start` voor proza, herstelautorisatie en
   interne/achtergrondcallers voor proza, en de experimenten die oude proza kunnen uitvoeren
   (`settings/audit_semantic_safety_v1`, `settings/route_comparison_app_v1` importeren
   `semantic_units_before_review`).
2. Uitvoering: in `pre_review_semantic_v1` de prompts, het proposalschema, de
   providercall en de modelmodi (`_semantic_instruction`, `_request_payload`,
   `_provider_proposal`, `_semantic_execution_before_review`,
   `semantic_units_before_review`, `semantic_spec_from_fragments`). Wat de boom nodig
   heeft, blijft in `decision_tree_route_v1` en `bounded_model_call_v1`.
3. Alles wat alleen de oude uitvoering dient. Kandidaten, per stuk na te lopen op
   boom- en historiegebruik: `semantic_passage_v1` (1.092 regels),
   `semantic_transform_generic_v1`, `semantic_replay_v1`, `bounded_formation_v1`,
   `recoverable_formation_v1`, `formation_checkpoint_v1`, `recommendation_task_plan_v1`,
   `recommendation_coverage_v1`, `context_scan_v1`, `source_bound_fields_v2` en `_v3`,
   `passage_formation_policy_v1`, `processing_document_budget_v1`.
4. De tijdelijke re-exports in `pre_review_semantic_v1`, daarna het bestand zelf en de
   startup-binding.
5. Scripts die de oude uitvoering aanroepen: `measure_source_task_reuse.py`,
   `measure_formation_validation.py`, `probes/probe_source_repair_mapping.py`
   (binden de oude verwerking), `replay_recorded_formation.py`,
   `verify_source_container_diagnostic.py`, `verify_eenzaamheid_semantic.py`
   (gebruiken oude helpers). Houden wat historie alleen leest; de rest weg.
6. Configuratie: `METIS_PASSAGE_FORMATION_MODE` en de modelinstellingen die alleen
   proza dienen; de pagina `/settings/llm` voor zover zij alleen proza instelt.

Voorwaarde: de praktijkvergelijking en cutover van HA-4 (#1017). Historische
bewijslezers en de beslisboom blijven werken zonder provider.

### B2. De oude reviewkaart naast de nieuwe

`_render_review_room` (`src/operations_console_app.py:3378`) kiest per object: een
kennisobject krijgt de nieuwe kaart (`render_review_page`); al het andere krijgt de
oude kaart. "Al het andere" is volgens `is_knowledge_object`: koppen en structuur,
bronrecords, en op het boompad een `path`. Daarnaast gebruikt
`review_command_response_v1.review_command_error` de oude kaart bij een mislukte
KO-opslag. De nieuwe kaart importeert `_source_bound_fields_html`; andere helpers
dienen bronselectie en deterministische correctie. Eerst die callers migreren;
de onderstaande bouwstenen niet collectief verwijderen.

Nog in gebruik voor die objecten, en dus de tweede weg:

| Oude onderdeel | Plek | Wat het nog doet |
| --- | --- | --- |
| `_render_review_card` | `operations_console_app.py:3045` | Kaart met stappen a–f voor niet-kennisobjecten |
| `_render_second_review_card` | `:2289` | Tweede beoordeling in de oude vorm |
| `_source_context_card`, `_source_context_panel` | `:3267`, `:2759` | Het oude contextpaneel; zie B3 |
| `_knowledge_review_html`, `_stamp_block`, `_recommendation_semantics_block`, `_heading_chooser`, `_review_context_block`, `_knowledge_relation_review_block`, `_source_bound_fields_html`, `_broncontext_html`, `_source_discrepancy_block`, `_review_conflict_html` | `:1072`–`:2264` | Bouwstenen van de oude kaart |
| Inline script voor het oude formulier | `:687`, `:736`–`:788`, `:922`–`:967` | Tonen en verbergen van oude velden |
| `_render_review_index`, `_review_inventory`, `_review_section_groups`, `_review_lane_copy`, `_lane_total` | `:1865`–`:3045` | Het documentoverzicht en de lanes |

Besluit dat eerst nodig is: krijgen koppen, structuur, bronrecords en boompaden een
eigen lichte kaart in de nieuwe vorm, of handelt de inhoudsopgave van de nieuwe kaart
ze af? Pas daarna kan de oude kaart weg. Het documentoverzicht blijft nodig, maar
hoort dan naast de nieuwe kaart in `src/review/`, niet in `operations_console_app.py`.

De 24 goldens in `tests/characterization/golden/review_room/` leggen het oude
overzicht en de oude kaart vast; die gaan mee.

### B3. "Broncontext vastleggen"

MET-61 noemt deze pagina als vervangen. Nog aanwezig: `render_context` in
`source_selection_ui_v1` (`:361`), het formulier `POST /review/source-context`, en
`POST /review/context/accept`. De nieuwe reviewkaart linkt er zelf nog naartoe
("Broncontext vastleggen of aanpassen in Vorming", `ko_review_page_v1.py:153`), dus
die link moet eerst een nieuw doel krijgen. Menselijke correctie hoort terug te gaan naar de
oorspronkelijke annotatie. Verwijderen samen met B1; de gedeelde context- en
reviewautoriteit (`source_context_review_v1`) blijft.

### B4. Schrijfroutes voor review

Het doelbeeld is één command. Nu bestaan deze schrijf-ingangen naast elkaar:

| Route | Eigenaar | Status ten opzichte van het doelbeeld |
| --- | --- | --- |
| `POST /review` | `operations_console_app.review_post` | Eerste review; de nieuwe kaart gebruikt bij tweede review nog `/review/second-review` |
| `POST /review/second-review` | `operations_console_app` | Aparte ingang voor dezelfde transitietabel; kan een `task` op `/review` worden |
| `POST /review/relations` | `operations_console_app` | Aparte ingang; de nieuwe kaart vraagt relaties in dezelfde beoordeling |
| `POST /review/headings/batch-confirm` | `operations_console_app`, daarna vervangen door `review_workboard_v1` | Zie B9 |
| `POST /review/resolve` | `deterministic_review_repair_v1` | Herstelroute uit de oude vorming; nalopen na B1 |
| `POST /review/source-context`, `/review/context/accept` | `operations_console_app` | Zie B3 |
| `POST /review/source-group`, `/review/source-group/reset`, `/review/source-exclusions` | `operations_console_app` | Groepsafhandeling van bronpassages (#941/#946, MET-33); blijft tot B6-acceptatie, daarna tegen annotatie leggen |
| `POST /review/decision-passage`, `/review/decision-graph`, `/review/successor`, `/review/policy` | `decision_review_ui_v1` | Boomroute; blijft |
| `POST /review/participants` | `review_participation_ui_v1` | Deelname; blijft |

Alle menselijke KO-besluiten gaan al langs `apply_ko_event`
(`tests/test_ko_single_way.py`). Wat overblijft is het aantal HTTP-ingangen en
formulieren, niet een tweede beslisregel.

### B5. Twee schrijvers voor bronrollen

Open onder #942 / MET-35 (`Rewrite risk: high`): de losse bronopdracht en
`source_role_version` schrijven beide bronrollen. KO-5 heeft dit bewust niet
samengevoegd. Eén schrijver, daarna de andere weg.

### B6. Spiegelvelden in opgeslagen data (KO-6)

KO-5 haalde de beslissende rol weg; de velden staan er nog. Verwijzingen in `src`:
`second_review` 47 in 11 bestanden, `clinical_rereview_required` 9 in 4,
`publication_status` 6 in 3, `review_passes` 1, `historical_has_publication` 2.
De schema's `knowledge_object.schema.v1.0`–`v1.4` eisen `publication_status` en
`second_review` nog. Verwijderen kan alleen onder KO-6: schriftelijke goedkeuring,
back-up en herstelproef.

### B7. Twee leesmodi voor reviewkaarten

`CONSOLE_REVIEW_CARD_READS` kent `legacy` en `compact`; de keuze vertakt op vier
plekken in `workflow_badge_counts_postgres_v1` en één in `document_status_ui_v1`.
Standaard is `legacy`. Kies er één, verwijder de andere tak en de vlag, en neem de
stappen uit `docs/AZURE_RELEASE_RUNBOOK.md` (1.7 en de terugwissel) mee.

### B8. Twee opslaglayouts voor verwerkingsinvoer

`processing_storage_version` vertakt 24 keer in `workflow_documents_cutover_v1`,
`operational_document_inputs_v1`, `formation_checkpoint_v1`, `formation_recovery_v1`
en `worker_handover_v1`. De stoproute ondersteunt bewust "beide inputlayouts".
`prepare_operational_inputs` en `activate_operational_inputs` hebben geen
productie-aanroeper meer. Na migratie van alle documenten naar één layout: de andere
tak en de migratiefuncties verwijderen.

### B9. Gedrag dat achteraf over de pagina heen wordt gelegd

Deze lagen veranderen een route of de HTML van een andere module nadat die is
geregistreerd. Functioneel werkt het; het is wel een tweede plek waar hetzelfde
scherm wordt bepaald.

| Laag | Plek | Voorstel |
| --- | --- | --- |
| `review_workboard_v1` haalt `GET /review` en `POST /review/headings/batch-confirm` uit de routelijst en zet eigen versies terug die de oude aanroepen | `review_workboard_v1.py:672`–`:887` | De workboard wordt de eigenaar; de oorspronkelijke handlers uit `operations_console_app.py` verdwijnen |
| `document_status_ui_v1` vervangt `_document_card_heading` in twee modules | `document_status_ui_v1.py:65`–`:68` | Status rechtstreeks in de kaartkop laten berekenen |
| `console_navigation_simplify_v1` verwijdert met reguliere expressies links uit elke HTML-respons | hele module, 100 regels | De links niet meer renderen; middleware weg |
| `GET /publish` staat in `publish_readiness_ui_v1`, `POST /publish` in `operations_console_app`; de installer weigert alleen een dubbele GET | `publish_readiness_ui_v1.py:389`–`:397` | Het hele Publiceren-scherm bij één eigenaar |

### B10. De ladder van consoleklassen

`console_asgi` gebruikt alleen `FastBadgePostgresCompleteWorkflow…Console`. Daaronder
staan vier tussenlagen met elk een Durable- en een Azure-variant
(`PostgresIdentity…`, `PostgresWorkflow…`, `PostgresReviewWorkflow…`,
`PostgresCompleteWorkflow…`). De productie-eindklassen erven via deze acht
tussenklassen hun mixins. Het ontbreken van directe instanties maakt ze niet dood.
Eventueel afvlakken is een afzonderlijke refactor met MRO-/`super()`-equivalentie,
geen directe dode-codeverwijdering.

### B11. Oude adressen die alleen doorverwijzen

`install_insight_legacy_routes` (elf adressen) en `/audit/review-signals` sturen door
naar `/inzicht/…`. `/settings/quality/compare/*` bestaat daarnaast nog als volledige
tweede set POST-routes naast `/inzicht/routevergelijking/*`. Redirects weg zodra geen
link of bladwijzer ze meer gebruikt; de dubbele POST-set direct.

### B12. Contractversies van de oude proza

`docs/LEGACY_ROUTES.md` L02, L03 en L07: semantisch V1, V2 en V3 zijn alle drie nog
kiesbaar. Met B1 vervalt het kiezen; wat blijft is het lezen van historische
contracten.

## C. Bewust laten staan

- `materialise_knowledge_candidates` en de admission- en bronbindingscontroles: de ene kandidaatmaker.
- De beslisboomroute (`decision_tree_*`, `decision_graph_v1`, `decision_review_*`).
- Historische bewijs- en diagnoselezers (`formation_evidence_v1`, `forensic_trace_v1`,
  `processing_evidence_export_v1`, `attempt_diagnostics_v1`), voor zover ze lezen en niet uitvoeren.
- `prose_transition_v1` en de drie database-guards: die houden gestopte pogingen gestopt.
- `service_app.py` naast `product_api_v1.py`: inspectie tegenover de product-API;
  `PROTOCOL_V2_23` verbiedt verwijdering.
- `review_workflow_v3._apply_review_state`: de private transformer achter de KO-4-policy.
- De fysieke kolom `clinical_rereview_required` en de serializers, tot KO-6.
- Operatorgereedschap voor migratie, herstel en accountbeëindiging.

## Volgorde

De uitvoeringsvolgorde staat in het [verwijderplan](verwijderplan-na-annotatie-en-reviewkaart.md).
Eerst vier A1-functies (#1047/MET-69); overige A-kandidaten vragen afzonderlijke
contractcontrole. Reviewmigratie omvat ook foutweergave en gedeelde helpers.
**B3 volgt samen met B1/B12 pas na de HA-4-praktijkcutover.** B5 blijft bij #942;
B6 bij KO-6. B10 is een actieve overervingsrefactor. Werk het bestaande register
per uitgevoerde stap bij, niet pas aan het einde.

## Besluiten die nodig zijn

- B2: hoe worden koppen, structuur, bronrecords en boompaden beoordeeld als de oude kaart weg is?
- B7: wordt `compact` de enige leesmodus?
- A3: welke losse modules zijn operatorgereedschap en welke restant?
- B4: blijft groepsafhandeling van bronpassages bestaan naast annotatie?

## Niet onderzocht

- Tests: welke van de 572 testbestanden alleen een oude route bewaken, is niet per
  bestand vastgesteld.
- JavaScript, CSS en de databasemigraties in `db/` zijn niet op dode delen nagelopen.
- Productiedata: of er nog documenten in de oude layout, met een lopende AI-poging of
  met `legacy_revise` bestaan, vraagt een telling door de operator.
- GitHub-issues zijn niet één voor één gelezen; de Linear-werkpakketten en de
  contracten in de repo zijn de bron geweest.
