# MET-5 / #878 — diagnose vormingsafwijzingen en authority-map

Change class: C (onderzoek). Rewrite risk: none. Touches lifecycle invariants: no.
Geen productcode gewijzigd. Dit dossier is een werkdocument onder #878 en #877;
het voegt geen norm toe boven `PROTOCOL.md → ROADMAP.md → acceptatietests → code`.

## 0. Gepinde basis en bewijsgrenzen

| Gegeven | Waarde |
| --- | --- |
| Code-SHA (onderzocht) | `69b4f6b8b819259a3e04d2434bbf7cf2cfdaa47e` (main na #901) |
| Incidentbewijs | `tests/fixtures/diagnostics/slice3-v12-anonymized.json`, sha256 `2be98e35db906ee95a552a2b5ae419fdffb77383ed3cf67d81e12e15eaf87462` |
| Contract in incident | `semantic_contract_version = source-bound-fields-v3`, `policy_version = bounded-formation-v1`, replay-identiteit `semantic-replay-identity-v1` |
| Baseline tests op deze SHA | 262 passed, 0 skipped (native PostgreSQL 16 via `scripts/test_postgres.sh`): `test_source_evidence_resolution_v1`, `test_recoverable_formation_v1`, `test_a07_strength_binding`, `test_v3_proposal_repairs`, `test_recommendation_context_v3`, `test_blockage_diagnostics_v1`, `test_source_strength_labels` |
| Azure/productie-SHA | UNKNOWN — niet waargenomen |

**Bewijsgrens.** Het enige incidentbewijs in de repository is geanonimiseerd: bron-SHA,
bronteksten, spans, modelvoorstellen en relaties zijn vervangen of weggelaten. Per geval
zijn daarom *snapshot, exacte bronspans, letterlijk veldbewijs en modelvoorstel* UNKNOWN.
Oorzaakklassen hieronder zijn per mechanisme **aangetoond in code en met falsificatieproeven**,
maar per incidentgeval alleen **verenigbaar**, niet bewezen. Voor bewijs per geval is een
export van de echte processing-evidence (`docs/PROCESSING_EVIDENCE_EXPORT.md`,
`scripts/export_section_incident.py`) op één snapshot nodig; private bron en ruwe
provideruitvoer blijven buiten GitHub.

Toegepaste werkwijzen: skill-dispatcher (afbakening), domain-first-architecture
(eigenaar/invariant vóór oplossing). De falsificatieproeven zijn uitgevoerd tegen de
bestaande validators met bestaande testhelpers en worden in §4 reproduceerbaar beschreven.

## 1. Keten en routeverschil V2/V3

```
bronbytes → extractie (docling_pdf_v1 / extract_html_v1) → semantic_source_blocks
 → bounded_formation_v1.tasks_for (sectiegebonden taken, ≤12 000 tekens / 48 blokken)
 → provider (pre_review_semantic_v1) → source_evidence_resolution_v1.resolve_proposal_evidence
 → [V3] recoverable_formation_v1.prepare  |  [V2] hele voorstel valideren
 → semantic_passage_v1.semantic_units_from_proposal (incl. strength/direction)
 → knowledge_materialisation_v1.materialise_knowledge_candidates (enige kandidaatmaker)
 → bounded_formation_v1: restrict_supplement (taakgrens) → TaskResults/checkpoint
 → candidate_eligibility_v1 / admission_gate_v1 → WorkingRevision → Review → publicatie
```

Materieel verschil per route (aangetoond in `pre_review_semantic_v1.py:723–735`):

- **V3** (`field_contract_v3`): `recoverable_formation_v1.prepare` isoleert afwijzingen per
  object/relatie/bronbeoordeling. De zes foutcodes verschijnen als *per-object findings*
  met spans; geldig naastliggend werk blijft behouden en wordt herstelbaar werk.
- **V2**: iedere fout maakt het hele voorstel ongeldig (`pre_review_llm_proposal_rejected`
  met de onderliggende code). Er is geen isolatie; `semantic_dependency_rejected` en
  `semantic_supplement_outside_target` bestaan daar niet als per-objectbevinding.

Een telling van foutcodes is dus alleen vergelijkbaar binnen één route.

## 2. Evidence matrix per foutcode

Legenda oorzaakklasse: (a) kandidaatgrens, (b) contextbinding, (c) ambigue bronlokalisatie,
(d) modelvoorstel, (e) terechte domeinregel, (f) cascade, (g) onbeslist.

### 2.1 `source_bound_field_outside_candidate`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `source_bound_fields_v2.py:80` (`bind_fields`); V3 hergebruikt die per veld via `source_bound_fields_v3.py:55–81` |
| Trigger | Veldspan ligt niet binnen een geselecteerde kandidaatspan. In V3 mogen alleen `actor_span`, `target_group_span`, `scope_span` en `condition_span` ook in een opgeloste contextentry met passende rol liggen (`CONTEXT_FIELDS`) |
| Incident v12 | call-10 obj1 (historical), call-23 obj2 (pending), call-75 obj2 (pending) |
| Mogelijke oorzaken | (d) model verwijst naar tekst buiten de kern; (a) kern te krap gekozen; (b) context ontbreekt of heeft verkeerde rol; (e) terecht bij een kernveld buiten de kern |
| Bevestigend | P1 (§4): een `exception`-rol-contextentry kan `exception_span` niet dragen → deze code, terwijl `condition`/`scope` wél binden |
| Ontkrachtend | Voor kernvelden (`recommended_action`, `recommendation_evidence_span`, …) is de weigering de bedoelde invariant: kern blijft letterlijk de kandidaat |
| Huidige V3-dekking | Context buiten de kern voor actor/doelgroep/scope/conditie: gedekt. Uitzondering buiten de kern: **niet** gedekt, terwijl `CONTEXT_ROLES` de rol `exception` kent en `additional_context_codes` die rol wel als realisatie van scope accepteert |
| Kleinste wijziging | Geen, totdat een bevroren bronreferentie aantoont dat een uitzondering terecht buiten de kern staat (B5). Dan: `exception_span: {"exception"}` toevoegen aan `CONTEXT_FIELDS` — versiegebonden, geen herinterpretatie van bestaand V3-werk |
| Regressietest | Positief: exception-context bindt; negatief: kernveld buiten kern blijft geweigerd; context zonder rol of met `unresolved_reason` blijft geweigerd |
| Eigenaar | MET-6 (#880), alleen na referentiegeval uit MET-7/#530 |

### 2.2 `semantic_evidence_literal_ambiguous`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `source_evidence_resolution_v1.py:108` |
| Trigger | Letterlijke verwijzing zonder `occurrence` komt ≥2× voor in hetzelfde blok. Enige uitzondering: V3-sterktestempel (`Sterk/Zwak – voor/tegen`) direct na een uniek geselecteerde kern |
| Incident v12 | call-17 obj1 (historical), call-73 obj3 en call-74 obj3 (beide pending) |
| Oorzaak | (c) bronlokalisatie, met (d) als directe veroorzaker: het contract biedt `occurrence`, het model laat die weg |
| Bevestigend | Code eist uniciteit; geen eerste-of-dichtstbijzijnde-keuze. Dezelfde index in opeenvolgende calls 73/74 is verenigbaar met een herhaalde, niet door retry opgeloste ambiguïteit (UNKNOWN zonder voorstel) |
| Ontkrachtend | Geen: herhaalde identieke literal zonder locator moet volgens #877 K3 falen |
| Huidige V3-dekking | Volledig voor de domeinregel; afwijking ligt bij de producer |
| Kleinste wijziging | Geen domeinwijziging. Eventueel: promptinstructie/schema dat `occurrence` verplicht stelt bij herhaalde literal, binnen bestaande providerroute |
| Regressietest | Bestaand: `test_source_evidence_resolution_v1`, `test_v3_proposal_repairs` |
| Eigenaar | Geen contractwijziging; producerverbetering eventueel MET-6 |

### 2.3 `semantic_dependency_rejected`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `recoverable_formation_v1.py:128`, `:155`, `:349` |
| Trigger | Per definitie een **cascade (f)**: een object is via een relatie verbonden met een afgewezen object, of een relatie in dezelfde call kon niet worden opgelost |
| Incident v12 | call-10 obj0 naast obj1 `source_bound_field_outside_candidate`; call-75 obj3 naast obj0 `semantic_span_hidden_gap` en obj2 `source_bound_field_outside_candidate`. Beide keren in dezelfde call als een primaire afwijzing — verenigbaar met cascade; relaties zelf zijn niet in de fixture |
| Bevestigend | P2 (§4): één relatie met een niet-vindbare evidence-literal wijst **alle** objecten in de call af, ook een zelfstandig object zonder relatie |
| Ontkrachtend | Bij een fout in een eindpuntobject wordt alleen het verbonden object meegenomen; het onafhankelijke object blijft (bestaande test `test_invalid_candidate_quarantines_related_candidate_not_independent_one`) |
| Huidige dekking | Correct voor objectfouten. Bij relatiefouten is de quarantaine call-breed (`bad.update(objects)`, regel 115), ook als bron- en doelspans exact oplosbaar zijn en alleen `evidence_spans` faalt |
| Kleinste wijziging | Open besluit (B5): bij een relatiefout de quarantaine beperken tot eindpunten wanneer `source_spans`/`target_spans` afzonderlijk exact oplossen; call-breed alleen bij onbekende eindpunten. Geen versoepeling van de relatie zelf |
| Regressietest | Positief: onafhankelijk object blijft bij relatie-evidencefout; negatief: onoplosbaar eindpunt quarantaineert nog steeds de call; eindpunten blijven afgewezen |
| Eigenaar | MET-6 (#880) |

### 2.4 `recommendation_strength_literal_mismatch`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `semantic_passage_v1.py:445` |
| Trigger | `strength_status = explicit` en `source_literal_strength(strength_text) != strength`. Bij een span zonder herkenbare sterktecue, of met tegenstrijdige cues, is `literal = None` → óók deze code |
| Incident v12 | Geen geval → **ontbrekend bewijs** voor dit incident |
| Oorzaak | (d) model kiest verkeerde sterkte, of (d/c) verwijst naar tekst zonder sterktelabel; (e) terecht bij echte mismatch |
| Bevestigend | P3 (§4): `observed_value` in de finding onderscheidt de twee (concrete waarde versus `None`) |
| Ontkrachtend | Bestaande tests `test_a07_strength_binding`, `test_source_strength_labels` bewijzen terechte weigering |
| Kleinste wijziging | Geen domeinwijziging. Diagnose op echte exports: tel `observed_value is None` apart |
| Eigenaar | Diagnose MET-5 vervolg; richtlijnsterkte MET-7 |

### 2.5 `recommendation_strength_evidence_not_applicable`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `semantic_passage_v1.py:473` |
| Trigger | Sterkte-evidence ligt buiten bronbepaalde toepasbare bereiken: geselecteerde tekst, direct volgende stempel(s), of sectiekop die de groep afbakent (`_applicable_strength_ranges`) |
| Incident v12 | Geen geval → ontbrekend bewijs |
| Oorzaak | (e) terechte regel bij een stempel van een andere aanbeveling; (a) als de kern te krap is gekozen zodat de stempel niet "direct volgend" is |
| Eigenaar | MET-7 (#530/#515 tabelcontext) |

### 2.6 `semantic_supplement_outside_target`

| Aspect | Bevinding |
| --- | --- |
| Emissie | `recoverable_formation_v1.py:333` (object), `:363` (bronbeoordeling) |
| Trigger | In **iedere** fase van `bounded_formation_v1` (niet alleen recovery, `bounded_formation_v1.py:360`): een objectspan of bronbeoordeling ligt niet volledig binnen de `target_spans` van de taak |
| Incident v12 | Geen geval → ontbrekend bewijs |
| Oorzaak | (e) terecht: een taak mag geen werk van een andere taak overschrijven; (a) mogelijk wanneer een sectie >12 000 tekens/48 blokken over taken wordt gesplitst en een betekeniseenheid de taakgrens kruist; (d) model selecteert buiten de opgegeven bereiken |
| Testdekking | Bronbeoordeling buiten doel: gedekt (`test_conflicting_reselection_cannot_replace_primary_or_clear_itself`). **Object** buiten doel: geen gerichte test gevonden |
| Kleinste wijziging | Eerst testgat dichten (negatieve test object buiten doel). Taakgrenssplitsing alleen herzien bij bewezen kruisende betekeniseenheid |
| Eigenaar | MET-6 (testgat); MET-10 (taakplanning/herstel) |

### 2.7 Overige codes in het incident (context, geen scope van MET-5)

`semantic_evidence_literal_not_found` (5×, calls 3/68), `source_assessment_bounds_invalid` (4×, call-13),
`semantic_span_hidden_gap` (1×, call-75). Admissionbevindingen (84 regels) zijn een andere laag
(kandidaat, niet voorstel): o.a. `type_contract_incomplete`, `supported_object_missing`,
`no_independent_claim` (elk 16×), `incomplete_sentence` (9×).

## 3. Incident v12: oorzaak versus gevolg

| Meting (fixture) | Waarde |
| --- | --- |
| Geplande taken / terminal / pending / not started | 67 / 22 / 45 / 39 |
| Modelcalls: `source_task_budget_exhausted` | **83 van 116** |
| Modelcalls: validated / partial | 24 / 9 |
| Producerbevindingen pending / historical | 13 / 4 |
| Pogingen | 2, beide `succeeded`, geen checkpoints |

**Conclusie (afgeleid, niet bewezen per bron):** in dit incident is het uitgeputte taakbudget
de eerste blokkerende oorzaak van open werk (45 pending taken), niet de veldafwijzingen
(13 pending bevindingen). De zes foutcodes verklaren een minderheid van het openstaande werk.
`blockage_report` classificeert de oorzaak terecht als `not_established`. Herstel van
budgetgebonden werk valt onder MET-10 (#836/#839/#840).

## 4. Falsificatieproeven (uitgevoerd op `69b4f6b`)

Uitgevoerd in een scratchmap, zonder productcode te wijzigen.

**P1 — V3-contextrol per veld.** `source_bound_fields_v3.bind_fields` met kern
`"Geef paracetamol."` en een opgeloste contextentry `"tenzij de patiënt allergisch is"`:

| Rol | Veld | Uitkomst |
| --- | --- | --- |
| `exception` | `exception_span` | `source_bound_field_outside_candidate` |
| `condition` | `condition_span` | geaccepteerd |
| `scope` | `scope_span` | geaccepteerd |

**P2 — reikwijdte van de cascade.** `recoverable_formation_v1.prepare` met de helpers uit
`tests/test_recoverable_formation_v1.py` (drie objecten; één relatie tussen obj1→obj0; obj2 zelfstandig):

| Variant | Behouden objecten | Afwijzingen |
| --- | --- | --- |
| Geldig voorstel | 3 | — |
| Relatie-`evidence_spans` niet vindbaar | **0** | 1× relatie `semantic_evidence_literal_not_found`, **3×** `semantic_dependency_rejected` |
| Veld in obj0 verzonnen | 1 (obj2) | 1× `semantic_evidence_literal_not_found`, 1× `semantic_dependency_rejected` |

**P3 — strength mismatch.** Codepad gelezen: `observed_value = source_literal_strength(text)`;
`None` betekent geen of tegenstrijdige cue, niet een andere sterkte.

**P4 — dominante blokkade.** Tellingen uit §3 op de fixture.

## 5. Authority-map K1–K12 (bestaan geverifieerd op `69b4f6b`)

| K | Eigenaar (entrypoint) | Handhaving | Bewijsplek |
| --- | --- | --- | --- |
| K1 | `docling_contract_v1`, `OperationsConsole._read_source_fragments`, `source_reconstruction_v1` | bron-/hash-/versieconflict faalt gesloten (`semantic_evidence_block_conflict`) | `test_docling_contract_v1.py` |
| K2 | `knowledge_materialisation_v1.materialise_knowledge_candidates`; ook aangeroepen in `recoverable_formation_v1.prepare.validate` | enige kandidaatmaker; `prepare` valideert alleen | `test_t8_materialisation_admission_integrity.py`, `test_semantic_only_formation_v1.py` |
| K3 | `source_bound_fields_v2/v3`, `source_evidence_resolution_v1`, `candidate_eligibility_v1`, `admission_gate_v1` | uniciteit literal; veld in kern of passende context | `test_source_evidence_resolution_v1.py`, `test_recommendation_context_v3.py` |
| K4 | `semantic_passage_v1` (strength/direction), `source_bound_fields_v3.recommendation_codes` | kern-volledigheidscodes, sterkte-binding | `test_a07_strength_binding.py`; inhoud: #530/#515 |
| K5 | `decision_tree_route_v1`, `decision_tree_proposal_v1`, `decision_tree_construction_v1` | enige boomroute | `test_decision_tree_proposal_route_v1.py`, `test_decision_tree_route_lifecycle_v1.py` |
| K6 | `recoverable_formation_v1` (`pending_rejections`, `unresolved_rejections`), `source_accountability_v1`, `formation_problems_v1` | afwijzing blijft zichtbaar werk | `test_recoverable_formation_v1.py`, `test_t10_source_accountability_authority.py` |
| K7 | **Geen duurzame eigenaar.** `pre_review_semantic_v1.active_passage_formation_mode` leest de omgeving bij iedere verwerking; `source_selection_v1.assert_resume_configuration` fenst alleen V3-resume | zie §6 | open: #879 / MET-13 |
| K8 | `workflow_transaction_v1.workflow_transaction`, `workflow_document_concurrency_v1.write_bundle`, `formation_task_store_v1.FormationTaskStore`, `formation_checkpoint_v1` | claims/CAS/checkpoints | `test_workflow_transaction_v1.py`, `test_workflow_postgres_concurrency.py` |
| K9 | `integrity_kernel`, `review/revision_workflow.py` | exacte reviewbinding, opvolgerrevisie | `test_t9_review_knowledge_authority.py`, `test_t11_knowledge_revision_lineage.py` |
| K10 | `publication_readiness_v1`, `durable_publication_console_v1._publish_locked`, `azure_authoritative_publication_console_v1` | registry is enige serving-autoriteit | `test_publication_registry_serving_authority_v1.py` |
| K11 | `product_api_v1`, `settings/api_access_v1` | alleen gepubliceerd | MET-9 |
| K12 | `scripts/check_architecture_boundaries.py`, `docs/LEGACY_ROUTES.md`, `docs/audit/decision-tree-route-replacement.md` | statische afhankelijkheidscheck | MET-11 |

Writers van vormingsafwijzingen: `prepare` → `evidence["formation"]` (provider-evidence) en
`bounded_formation_v1` → `call["formation"]["rejections"]` → TaskResults/checkpoint.
Readers: `formation_problems_v1` (review), `blockage_diagnostics_v1`, `forensic_trace_v1`,
`processing_evidence_export_v1`, `operations_console_v1.incomplete`. Geen tweede writer gevonden.

## 6. Routevastlegging versus omgevingsconfiguratie (K7)

Aangetoond (`pre_review_semantic_v1.py:1123–1153`, `source_selection_v1.py:48–68`):

1. Nieuwe verwerking leest `METIS_PASSAGE_FORMATION_MODE` per run; de route is geen documenttoestand.
2. Resume eist dat de *huidige* omgeving V3 is én overeenkomt met de vastgelegde replay-identiteit;
   anders `processing_resume_configuration_incompatible`. Werk dat onder V2 begon kan dus niet worden
   hervat. Na een omgevingswissel V2→V3 wordt een nieuwe verwerking stil V3.
3. Dit bevestigt de R4.6-kloof. Het routeontwerp hoort bij #879/MET-13 (Class A, high); niet hier.

## 7. Bestaand werk versus nieuw

| Issue | Rol | Overlap met dit dossier |
| --- | --- | --- |
| #530 | inhoudelijke acceptatie richtlijnen | referentiegevallen voor 2.1 (uitzondering) en 2.4/2.5 |
| #515 | Smetten-tabelcontext | `row_header`/`column_header` in `CONTEXT_FIELDS["scope_span"]`; niet herbouwen |
| #837 | bronvolledigheid | disposition van afgewezen bereiken (K6) |
| #848 | reviewweergave vormingsproblemen | reader van `pending_rejections`; geen wijziging nodig |
| #836/#839/#840 | checkpoints, taakhergebruik, overdracht | budgetuitputting (§3) |

Nieuw: P2-cascadereikwijdte (#909), testgat 2.6 (#910), bewijs per geval (#911); P1-uitzonderingscontext blijft besluit B5-a.

## 8. Open besluiten en ontbrekend bewijs

| ID | Vraag | Status |
| --- | --- | --- |
| B5-a | Mag een `exception`-contextentry `exception_span` dragen (V3)? | OPEN — vereist bronreferentie (#530) |
| B5-b | Beperken we de quarantaine bij een relatiefout tot oplosbare eindpunten? | OPEN — voorstel MET-6 |
| E1 | Echte export per foutcode op één snapshot (bron-SHA, spans, voorstel) | ONTBREEKT |
| E2 | Gevallen van 2.4/2.5/2.6 in echte evidence | ONTBREEKT |
| E3 | Azure-SHA en route van het v12-incident | UNKNOWN |
| E4 | Baseline reads/writes/runtime per snapshot | NOT TESTED |

## 9. Vervolgissues (needs-triage)

1. **#909 — MET-6 — relatiefout begrenst quarantaine tot eindpunten.** Class B, rewrite risk none
   (validator in bestaande producergrens, geen persistentie- of lifecyclewijziging). Promise: een
   relatie-evidencefout wijst alleen de eindpunten af; onbekende eindpunten blijven call-breed.
   Proof: P2 als regressietest, positief en negatief. Pas na besluit B5-b.
2. **#910 — MET-6 — negatieve test voor een object buiten de taakgrens** (`semantic_supplement_outside_target`).
   Class C, alleen een test.
3. **#911 — MET-5 vervolg — echte evidence-export per foutcode** (E1/E2) op één snapshot, om de
   oorzaakklasse per geval te bewijzen; `observed_value is None` apart tellen voor 2.4.

## 10. Status gereedcriteria #878

- [x] Alle foutklassen: representatief geval (2.1–2.3) of expliciet ontbrekend bewijs (2.4–2.6).
- [x] K1–K12 verwijzen naar eigenaar, handhaving en toets (§5); K7 heeft aantoonbaar geen duurzame eigenaar.
- [x] #530/#515/#837/#848 onderscheiden van nieuw werk (§7).
- [x] Routevastlegging versus omgevingsconfiguratie onderzocht (§6).
- [x] Materiële besluiten en ontbrekende bronnen apart zichtbaar (§8); vervolgissues geclassificeerd (§9).
- [ ] Oorzaak **per echt geval** bewezen — open tot E1 beschikbaar is.

Geen runtime- of productieacceptatie geclaimd.
