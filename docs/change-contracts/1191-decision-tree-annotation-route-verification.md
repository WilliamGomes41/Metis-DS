# Verificatielijst: beslisboom via menselijke annotatie

Hoort bij [1191-decision-tree-annotation-route.md](1191-decision-tree-annotation-route.md). Werkwijze: de skill [`verify-this`](../../.agents/skills/verify-this/SKILL.md).

Elke claim wordt toetsbaar geformuleerd en daarna bewezen. Dat gebeurt met een baseline op main `147ee2d67f7e19322ba20061f1d7c512e968c8b8`, of op de laatste commit van de vorige fase, en een treatment op de branch. Baseline en treatment draaien met hetzelfde commando, dezelfde fixture en dezelfde omgeving. Per claim geldt precies één uitkomst: `VERIFIED`, `NOT VERIFIED` of `INCONCLUSIVE`. Een ontbrekende of mislukte claim is geen PASS (AGENTS.md, "Done means evidence"). PostgreSQL-skips tellen niet als bewijs.

Artefacten: `output/verify-this/<claim-slug>/{claim.md,baseline/,treatment/,diff/,verdict.md}`. In CI worden ze geüpload als artifact `decision-tree-annotation-verify`. Bewaar geen bronbinaries of geheimen.

## A. Vaste repositorycontroles (elke fase, elke PR)

| # | Controle | Commando | Drempel |
| --- | --- | --- | --- |
| R1 | Wijzigingscontract | `python scripts/validate_change_contract.py --text-file docs/change-contracts/1191-decision-tree-annotation-route.md` (in CI: PR-body) | exit 0 |
| R2 | Repository-preflight | `python scripts/repository_preflight.py` | exit 0 |
| R3 | Releasecontrole | `python scripts/release_control_preflight.py --base origin/main` | geen `required` categorie zonder marker of bewijs |
| R4 | Compileren | `python -m compileall -q src tests` | exit 0 |
| R5 | Architectuurgrenzen | `python scripts/check_architecture_boundaries.py` | exit 0 |
| R6 | Architectuurinvarianten | `python -m pytest -q tests/test_architecture_invariants.py` | 0 failed, 0 skipped |
| R7 | PostgreSQL | `bash scripts/test_postgres.sh` | beschikbaar; daarna 0 skips in de PostgreSQL-tests |
| R8 | Volledige suite | `python -m pytest -q` | 0 failed |
| R9 | UI-bewijs | Gerenderde browserproef van de kaart op relevante breedtes (Impeccable, AGENTS.md) | screenshots en trace aanwezig |

## B. Claims (verify-this)

Fase-kolom: **1** = expand, **3** = contract. Fase 2 is het experiment in Audit en wordt niet in CI gemeten.

| # | Fase | Claim (conditie → maatstaf → drempel) | Kleinste oppervlak | Baseline verwacht | Treatment verwacht |
| --- | --- | --- | --- | --- | --- |
| V01 | 1 | Met een PDF-beslisboom en zonder `METIS_LLM_MODEL` levert de route ingest → annotatie → bouw → review → publicatie een actieve release op. Maatstaf: releasestatus en het aantal modelaanroepen. Drempel: release aanwezig en 0 aanroepen. | `tests/test_decision_tree_annotation_route_v1.py::test_pdf_tree_publishes_without_a_model` (native PostgreSQL), met een netwerk-spy op `post_json` | `pre_review_llm_decision_tree_proposer_unbound`, geen release | release actief, spy 0 calls |
| V02 | 1 | Hetzelfde voor een JSON-export waarin alleen keuzesoort en startpunt zijn gelabeld. Drempel: release aanwezig, 0 modelaanroepen en `verify_export_preserved` slaagt. | `...::test_export_tree_publishes_with_only_selection_and_entry_labelled` | modelvoorstel vereist | release actief, 0 calls |
| V03 | 1 | `human_annotation_v1.prepare` accepteert `class=beslisboom`. Maatstaf: foutcode of annotatieset. | `...::test_prepare_accepts_a_decision_tree` | `annotation_prose_required` | annotatieset aangemaakt |
| V04 | 1 | De projectie levert een voorstel dat `validate_proposal` zonder bevinding doorstaat. In de annotatie-invoer zit geen vrije tekst: elke `quoted_text` is gelijk aan `resolve_source_selection(spans)`. Drempel: 0 afwijkingen. | `...::test_projection_is_a_valid_proposal_without_free_text` | n.v.t. (functie bestaat niet) | 0 afwijkingen |
| V05 | 1 | Een annotatie-invoer met woorden buiten de span, omgekeerde spans of een verzonnen blok faalt gesloten. Drempel: 3 van de 3 geweigerd met `materialisation_*`, 0 objecten. | parametrisch, naar het model van `test_model_cannot_add_words_reorder_spans_or_fabricate_a_block` | n.v.t. | 3/3 geweigerd |
| V06 | 1 | Een verbinding zonder bewijsitem, of met een label dat niet letterlijk in de bron staat, wordt geblokkeerd. Drempel: de verwachte `decision_graph_*`-code in beide gevallen. | `...::test_edge_without_evidence_or_literal_label_blocks` | n.v.t. | beide codes aanwezig |
| V07 | 1 | Bij een export kan de kaart een vooringevulde verbinding niet verwijderen, omleiden of van label veranderen, en geen verbinding toevoegen. Lukt het toch, dan faalt de bouw met `decision_export_*_not_preserved`. Drempel: 4 van de 4 mutaties geweigerd. | parametrisch, naar het model van `test_export_proposal_that_changes_the_explicit_graph_fails_closed` | modelvariant geweigerd | kaartvariant geweigerd, 4/4 |
| V08 | 1 | Elk van de zes twijfellabels geeft een `unresolved`-regel die publicatie blokkeert. Maatstaf: `publication_issues`. Drempel: 6 van de 6 blokkeren, en na het oplossen blokkeert er geen meer. | `...::test_each_uncertainty_label_blocks_publication` | n.v.t. | 6/6 blokkeren, 0 na oplossen |
| V09 | 1 | Bij dezelfde seal en twee bouwacties zijn `proposal_hash` en graafhash identiek. Drempel: delta 0. | `...::test_same_seal_builds_identical_hashes` | n.v.t. | gelijk |
| V10 | 1 | Twee gelijktijdige opslagacties op dezelfde entry: precies één slaagt, de andere krijgt een CAS-conflict, en er gaat geen opgeslagen revisie verloren. | uitbreiding van `test_workflow_postgres_concurrency.py` | n.v.t. | 1 succes, 1 conflict |
| V11 | 1 | Een herstart na de seal en vóór de commit leidt tot hervatting met één bundelcommit. Maatstaf: aantal objecten en revisies. Drempel: geen duplicaten. | naar het model van `test_worker_handover_v1.py` en `test_source_resume_acceptance` | n.v.t. | 1 commit, 0 duplicaten |
| V12 | 1 | Een reviewer die in dezelfde kaart aanpast, krijgt een nieuwe objectversie met de vorige in de versieregel. De reviewbinding hoort bij de nieuwe versie. | naar het model van de #1064/#1156-proef (native browser en PostgreSQL) | n.v.t. voor bomen | nieuwe versie, oude in regel |
| V13 | 1 | Een hoog-risicoboom vraagt twee onafhankelijke goedkeuringen. Dezelfde persoon telt niet twee keer. De annotator volgt het open besluit van §10.1. | uitbreiding van `four_eyes_v1`-tests | ongewijzigd | ongewijzigd, plus regel annotator |
| V14 | 1 | Een snapshot met annotatieset weigert semantische vorming en selectie. Drempel: `annotation_source_owned` op beide ingangen. | bestaande tests, uitgebreid met `class=beslisboom` | n.v.t. voor bomen | 2/2 geweigerd |
| V15 | 3 | Een openstaande poging met `route=decision-tree-source-bound-v1` wordt na fase 3 niet hervat en geeft `decision_tree_model_route_retired`. Een opvolger volgt de annotatieroute. | `...::test_open_model_attempt_is_retired_and_successor_annotates` | hervat met het model | geweigerd, opvolger slaagt |
| V16 | 1+3 | Een met het model gevormde boom blijft leesbaar, reviewbaar en verifieerbaar, en de publicatiereplay is byte-gelijk. Maatstaf: hash van de replay-uitvoer. Drempel: delta 0. | fixture-snapshot uit de baseline, gelezen op de treatment | hash H | hash H |
| V17 | 1+3 | De Product API geeft voor dezelfde gepubliceerde toestand een byte-gelijk antwoord. | `tests/test_product_api_contract_guard_v1.py` | antwoord A | antwoord A |
| V18 | 1+3 | Er is precies één kandidaatmaker. Statische scan: buiten `knowledge_materialisation_v1` maakt geen pad in de nieuwe module kandidaten aan. | uitbreiding van `test_t7_creator_cut.py` en `test_semantic_only_formation_v1.py` | 1 | 1 |
| V19 | 3 | Er zit geen modelvoorstel voor beslisbomen meer in `src/`. Maatstaf: aantal treffers op `llm_proposer`, `request_proposal`, `PROPOSER_PROMPT`, `EXPORT_PROMPT` en `_decision_tree_proposer`. Drempel: 0. | nieuwe statische test `test_no_model_proposer_for_decision_trees_remains` | > 0 | 0 |
| V20 | 3 | Bij exports geldt het exportbehoud zonder model. Een getrouwe export bouwt exact, en een gewijzigde export faalt gesloten. | omgezette tests uit `test_semantic_only_formation_v1.py` | met fixturemodel | zonder model, zelfde uitkomst |

## C. Uitvoer per claim (verify-this-format)

```text
VERIFIED | NOT VERIFIED | INCONCLUSIVE
Claim: <V-nummer en falsifieerbare claim>

Evidence:
<maatstaf>: baseline=<...>, treatment=<...>, delta=<...>, threshold=<...>

Reasoning:
<één alinea met het bewijs en eventuele confounds>
```

`INCONCLUSIVE` geldt bij een ontbrekende baseline, een overgeslagen PostgreSQL-test of een omgevingsverschil tussen baseline en treatment. Dat blokkeert de merge net als `NOT VERIFIED`.

## D. CI-inrichting

- Een nieuwe stap in `.github/workflows/ci.yml`, in de job met de PostgreSQL-service:
  - `bash scripts/test_postgres.sh`
  - `python -m pytest -q tests/test_decision_tree_annotation_route_v1.py --junitxml=output/decision-tree-annotation.xml`
  - een assert dat de junit-uitvoer testcases bevat en geen `skipped`, zoals bij de bestaande Python 3.12-proef.
- Upload van `output/decision-tree-annotation.*` en `output/verify-this/**` met `if-no-files-found: error`.
- V12 en R9 (browser) volgen de bestaande native browserproeven en draaien in dezelfde job als de andere `browser_*`-checks.
- De mergepoort blijft: de vereiste CI-checks, het controlerapport van Forge en de letterlijke GO van William.
