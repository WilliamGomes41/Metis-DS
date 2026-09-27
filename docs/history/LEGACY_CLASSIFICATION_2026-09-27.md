# Legacy-classificatie — 2026-09-27

Dit is een archiefindex en opruimregister, geen tweede protocol. De huidige norm is `PROTOCOL.md`.

| Oppervlak | Status | Bewijs / actie |
|---|---|---|
| `docs/PROTOCOL_V2_*`, `data/assurance/protocol_v2_*` | Historisch, padgebonden | Goedkeuringsmanifesten en regressietests refereren de oorspronkelijke paden en hashes. Behoud bytes en paden; zie `docs/history/protocol-v2/README.md`. |
| `docs/history/protocol-v3/` | Bevroren V3 | De voormalige rootstand van Protocol en Roadmap is hier ongewijzigd opgeslagen. |
| `config/pipeline.v2.yaml` | Historische pilotconfig | Codezoekactie leverde alleen `docs/history/FULL_TECHNICAL_AUDIT_2026-08-19.md` als verwijzing op. Behoud voor reconstructie; sluit uit als actuele configuratie. |
| `output/v2/` | Historisch outputbewijs | Niet gebruiken als runtimeautoriteit of nieuw testfixture; zie `docs/REPOSITORY_CONVENTIONS.md`. |
| `src/legacy_canonical_recovery_v1.py` | Actief operator-herstel | `scripts/publication_chain_recovery.py recover-legacy-release` importeert dit. Niet verwijderen zonder opvolger en herstelproef. |
| `src/azure_step9_cutover_v1.py` | Actief operator-cutover | `scripts/azure_step9_cutover.py` importeert dit. Niet verwijderen zonder expliciete vervanging. |
| `src/build_review_queue_v3.py` | Actieve CLI-route | `src/cli.py` importeert deze route. Nummer in bestandsnaam is geen verwijderbewijs. |
| `src/build_synthetic_fixture.py`, `scripts/run_step10_checks.sh` | Gearchiveerd uit actieve codeboom | Alleen het oude Step 10-script riep de fixturebouwer aan. Geen huidig runtime-, test-, packaging- of deploymentgebruik; exacte bronkopieën onder `docs/history/step10-code/`. |
| `src/operations_console_v1.py` | Actieve console en manifestcode | Publicatiemanifests worden hier aan de actuele protocolversie gebonden. Bestaande historische releases blijven ongewijzigd. |

## Aanroepinventaris

Op de uitgangscommit `24e4b329f8a485ef7146d6e6b626f29212bd73ab` zijn alle 128 Python-modules onder `src/`, 16 Python-scripts, 220 testbestanden, de shellscripts, package-entrypoint, Dockerfiles en GitHub Actions op module- en padverwijzingen gecontroleerd. Een negatieve statische zoekuitkomst bewijst op zichzelf geen afwezigheid van dynamische imports; daarom zijn alleen de twee aan elkaar gebonden Step 10-bestanden verplaatst en wordt de volledige CI gedraaid.

| Verder oud ogend pad | Aangetroffen gebruik | Besluit |
|---|---|---|
| `src/workflows/workflow_identity_cutover_v1.py`, `workflow_review_cutover_v1.py`, `workflow_remaining_cutover_v1.py`, `workflow_documents_cutover_v1.py` | Console, workflowmodules en/of migratiescripts | Actief compatibiliteits- en herstelpad; behouden. |
| `src/workflows/workflow_postgres_migration_v1.py`, `src/azure_step9_cutover_v1.py` | Operatorcommando's voor schema en Azure-cutover | Behouden tot een afzonderlijk herstel-/uitfaseringsbesluit. |
| `src/publication_chain_recovery_v1.py`, `src/publication_chain_recovery_guard_v1.py`, `src/legacy_canonical_recovery_v1.py` | Workflow-herstel en `scripts/publication_chain_recovery.py` | Behouden; veiligheid van historische releases. |
| `src/second_review_workflow_v3.py` | Uitsluitend historische V2-integriteitstests | Nog niet verwijderen: die tests controleren de oude four-eyes-contracten. Een vervangende huidige gedragsproef is eerst nodig. |
| `src/retrieval/safe_retrieval_v1.py` | Uitsluitend retrieval-/architectuurtests | Historische comparator; een aparte PR moet de testwaarde tegen de huidige Product API afwegen. |
| `src/protocol_approval_manifest.py` | Uitsluitend approval-manifesttests | Behouden voor de historische auditketen. |
| `src/audit_experiment_v1.py` | Uitsluitend experimentdatasettests | Niet als bewezen dode legacy classificeren; R4.3 beslist over deze nog niet aangesloten experimentroute. |
| `src/compiled_knowledge_v1.py` | Uitsluitend tests van toekomstige inputgrens | Geen huidige executor; behouden totdat R4.3 de capability expliciet beoordeelt. |
| `src/azure_deploy_package.py` | `scripts/create_azure_deploy_package.sh`, beide deployworkflows en tests | Actieve package-route; behouden. |

In deze vervolgstap zijn uitsluitend het historische Step 10-script en zijn fixturebouwer uit de actieve boom verwijderd. De genoemde herstel- en CLI-paden blijven actief. R4.1 blijft open voor hun afzonderlijke aanroep- en herstelbewijs.
