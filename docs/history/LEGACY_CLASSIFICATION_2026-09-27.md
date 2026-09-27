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

In deze vervolgstap zijn uitsluitend het historische Step 10-script en zijn fixturebouwer uit de actieve boom verwijderd. De genoemde herstel- en CLI-paden blijven actief. R4.1 blijft open voor hun afzonderlijke aanroep- en herstelbewijs.
