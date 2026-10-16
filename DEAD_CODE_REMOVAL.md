# Verwijdering bewezen ongebruikte code

Change class: C
Promise: Alleen de 17 opgegeven functies verwijderen waarvoor de volledige repository geen verwijzing buiten de definitie bevat.
Proof: Afzonderlijke rg-zoekopdrachten vóór verwijdering, inspectie dynamische routes, AST-vergelijking en volledige lokale pytest-run.
Touches lifecycle invariants: no
Rewrite risk: none

Basis: `e5573878a5bed4a885c6896f88fcb515f964a9d7` (`main` bij checkout op 16 oktober 2026).
Code na verwijdering: `a1d2d470f3b42cc151d2f98ce522f27954f1c1cc`. Branch: `chore/remove-proven-dead-code`.
De directe gebruikersopdracht bepaalt de scope en autoriseert uitsluitend het pushen van deze branch. Er wordt geen PR geopend en niets gedeployd.

## Bewijsopzet

Elke onderstaande opdracht is afzonderlijk uitgevoerd **vóór verwijdering** en opnieuw gecontroleerd direct vóór het bewerken van de betreffende module. Zoeklocatie was een ongewijzigde, afzonderlijke Git-worktree van de genoemde basis, zonder gegenereerde testbestanden. Reproduceer met:

```sh
git worktree add --detach ../Metis-dead-code-evidence e5573878a5bed4a885c6896f88fcb515f964a9d7
cd ../Metis-dead-code-evidence
```

De opdrachten doorzoeken de hele checkout: productiecode, tests, scripts, templates, configuratie, documentatie, verborgen en genegeerde bestanden en binaire inhoud. Alleen Git-metadata is uitgesloten. `-w -F` zoekt de exacte identifier; dat vindt ook imports, aliases, strings, attributen en letterlijke namen in `getattr`/dynamische imports. `-o` toont alleen de identifier, zodat omliggende mogelijk gevoelige tekst buiten de uitvoer blijft. Elke opdracht eindigde met exitcode 0 en **precies één match op de definitieregel**. Dat is nul aanroepen of andere naamverwijzingen, niet nul tekstmatches. De matchregels staan onder de tabel.

Aanvullend is de repository onderzocht op `getattr`, `setattr`, `__getattr__`, `globals`, `locals`, `vars`, `inspect`, `import_module`, `__import__`, wildcard-imports, `eval`, `exec` en `dir`. De variabele dispatchroutes zijn nagegaan: de console-authenticatielus noemt alleen accountmethoden; de gelijktijdigheidstest dispatcht expliciet benoemde broncommando's; de A08-tests kiezen concrete schrijf-, transactie- en refreshmethoden; de badge-test bindt twee expliciete summary-methoden. Geen daarvan kan een van de 17 kandidaten selecteren. De module-`__getattr__` in `console_asgi` levert uitsluitend `app`; overige delegaties betreffen verbindingen, registries of de verwerkingsstrategie. Er is geen framework-override of registratiedecorator op een verwijderde functie aangetroffen; de twee verwijderde methoden hebben geen gelijknamige basisdefinitie in de repository.

Bewijsgrens: dit is repo-lokaal statisch bewijs, aangevuld met lokale tests. Het is geen bewijs over onbekende externe consumenten of willekeurig extern aangeleverde Python-code. Er is geen concreet twijfelgeval bij deze 17 kandidaten gevonden. De expliciete externe onzekerheid rond `storage_prepare` blijft OPENVRAAG-S3.

## Besluit per functie

| Functie | Bestand | rg-bewijs vóór verwijdering | Verwijderd/OPENVRAAG |
| --- | --- | --- | --- |
| `supplementary_blocks` | `src/recommendation_coverage_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o supplementary_blocks .` → 1 definitie op regel 76; 0 aanroepen/verwijzingen | verwijderd |
| `live_publication_chain_integrity` | `src/publication_chain_recovery_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o live_publication_chain_integrity .` → 1 definitie op regel 829; 0 aanroepen/verwijzingen | verwijderd |
| `_source_count` | `src/extract_metrics_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _source_count .` → 1 definitie op regel 149; 0 aanroepen/verwijzingen | verwijderd |
| `_match_gold_row` | `src/extract_metrics_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _match_gold_row .` → 1 definitie op regel 433; 0 aanroepen/verwijzingen | verwijderd |
| `_status_ok` | `src/extract_metrics_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _status_ok .` → 1 definitie op regel 449; 0 aanroepen/verwijzingen | verwijderd |
| `_relation_checkboxes` | `src/operations_console_app.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _relation_checkboxes .` → 1 definitie op regel 975; 0 aanroepen/verwijzingen | verwijderd |
| `first_review_open` | `src/review_duty_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o first_review_open .` → 1 definitie op regel 200; 0 aanroepen/verwijzingen | verwijderd |
| `_archive_coordinates` | `src/audit_archive_store_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _archive_coordinates .` → 1 definitie op regel 63; 0 aanroepen/verwijzingen | verwijderd |
| `_objects_for_span` | `src/forensic_trace_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _objects_for_span .` → 1 definitie op regel 351; 0 aanroepen/verwijzingen | verwijderd |
| `pending_rejection_keys` | `src/forensic_trace_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o pending_rejection_keys .` → 1 definitie op regel 753; 0 aanroepen/verwijzingen | verwijderd |
| `source_lineage_acceptance` | `src/forensic_trace_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o source_lineage_acceptance .` → 1 definitie op regel 2242; 0 aanroepen/verwijzingen | verwijderd |
| `_invalidate_all_bindings` | `src/operations_console_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _invalidate_all_bindings .` → 1 definitie op regel 3152; 0 aanroepen/verwijzingen | verwijderd |
| `has_source_literal_strength` | `src/recommendation_semantics_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o has_source_literal_strength .` → 1 definitie op regel 189; 0 aanroepen/verwijzingen | verwijderd |
| `legacy_confirmed_semantic_relations_exist` | `src/knowledge_relations_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o legacy_confirmed_semantic_relations_exist .` → 1 definitie op regel 465; 0 aanroepen/verwijzingen | verwijderd |
| `_pending_count` | `src/review_workboard_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _pending_count .` → 1 definitie op regel 84; 0 aanroepen/verwijzingen | verwijderd |
| `delete_secret` | `src/workflows/workflow_remaining_postgres_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o delete_secret .` → 1 definitie op regel 251; 0 aanroepen/verwijzingen | verwijderd |
| `_record_text` | `src/retrieval/answerability_gate_v1.py` | `rg -a -n --hidden --no-ignore -g '!.git' -g '!.git/**' -w -F -o _record_text .` → 1 definitie op regel 243; 0 aanroepen/verwijzingen | verwijderd |
| `storage_prepare` (hele module) | `src/storage_prepare.py` | `rg -a -l --hidden --no-ignore -g '!.git' -g '!.git/**' -F storage_prepare .` → 6 bestanden met verwijzingen; externe aanroep niet uitgesloten | OPENVRAAG-S3; ongewijzigd conform laatste gebruikersinstructie |

### Letterlijke rg-uitvoer per verwijderde functie

```text
./src/recommendation_coverage_v1.py:76:supplementary_blocks
./src/publication_chain_recovery_v1.py:829:live_publication_chain_integrity
./src/extract_metrics_v1.py:149:_source_count
./src/extract_metrics_v1.py:433:_match_gold_row
./src/extract_metrics_v1.py:449:_status_ok
./src/operations_console_app.py:975:_relation_checkboxes
./src/review_duty_v1.py:200:first_review_open
./src/audit_archive_store_v1.py:63:_archive_coordinates
./src/forensic_trace_v1.py:351:_objects_for_span
./src/forensic_trace_v1.py:753:pending_rejection_keys
./src/forensic_trace_v1.py:2242:source_lineage_acceptance
./src/operations_console_v1.py:3152:_invalidate_all_bindings
./src/recommendation_semantics_v1.py:189:has_source_literal_strength
./src/knowledge_relations_v1.py:465:legacy_confirmed_semantic_relations_exist
./src/review_workboard_v1.py:84:_pending_count
./src/workflows/workflow_remaining_postgres_v1.py:251:delete_secret
./src/retrieval/answerability_gate_v1.py:243:_record_text
```

### Behouden bestanden en tests

`src/storage_prepare.py`, `scripts/release_control_preflight.py`, `config/code_lifecycle_inventory.v1.json` en `src/docling_worker_v1.py` blijven bytegelijk aan de basis. Ook `src/bounded_model_call_v1.py`, `src/ingest_limits_v1.py` en `src/open_original_v1.py` blijven bytegelijk; de genoemde framework-overrides blijven bestaan. Er zijn geen tests verwijderd of gewijzigd: geen test verwijst naar een van de 17 exacte functienamen. Gelijkende namen zoals `independent_source_lineage_acceptance` en testnamen met `relation_checkboxes` betreffen andere symbolen en zijn behouden.

Per productiemodule is één afzonderlijke commit gemaakt. Alleen de opgegeven functiedefinities en hun direct aangrenzende witregels zijn verwijderd. Imports en overige helpers zijn bewust ongemoeid gelaten. Een AST-vergelijking van vóór/na, waarbij uitsluitend de 17 geselecteerde definities uit het basis-AST zijn weggelaten, levert gelijke bomen op. Dit onderbouwt dat er geen overige semantische codewijzigingen zijn.

## Lokale verificatie

De omgeving gebruikt Python 3.12.14 en pytest 9.0.2. De dependencies uit `requirements-dev.lock` zijn geïnstalleerd in een afzonderlijke virtuele omgeving buiten de checkout; het project is editable geïnstalleerd met `--no-deps --no-build-isolation`.

- `python scripts/repository_preflight.py`: PASS.
- `python -m compileall -q src`: PASS.
- `python scripts/check_architecture_boundaries.py`: PASS.
- `git diff --check e5573878`: PASS na het verwijderen van achtergebleven eindwitregels in twee gewijzigde modules.
- `python -m pytest -q --junitxml=<extern tijdelijk bewijsbestand>` op `992da129c414e3a494a93f4798eebef1c81b43e8`: **FAIL (exitcode 1)**; 4.684 geslaagd, 4 gefaald, 448 overgeslagen, 6 xfailed; 5.142 verzamelde tests, 0 errors, 341,156 seconden. De latere commit wijzigt uitsluitend dit verslag; de geteste productcode blijft bytegelijk.
- `python -m pytest -q tests/test_architecture_invariants.py`: 6 geslaagd.
- Eindzoekronde in een schone worktree van de code na verwijdering, met uitsluitend `DEAD_CODE_REMOVAL.md` en Git-metadata uitgesloten: voor alle 17 identifiers 0 matches.
- Alle 7 beschermde bestanden zijn byte voor byte met de basis vergeleken: gelijk.
- Skipverdeling: 432 PostgreSQL-tests zonder lokale test-DSN, 12 echte Docling/model-acceptatietests en 4 optionele browsertests. De 6 xfails zijn bestaande B23-tests. Deze routes zijn dus niet als geslaagd bewezen.
- `python scripts/release_control_preflight.py --base origin/main`: BLOCKED; zie hieronder.

## Geprobeerd en mislukt

1. **PostgreSQL via apt installeren.** De standaardpoging faalde op `setgroups`/`seteuid`. Een poging met de apt-sandboxgebruiker `root` liep vast op schrijfrechten voor het pakketarchief. Er is geen productieverbinding gebruikt.
2. **Losse lokale PostgreSQL-server via pgserver.** Het pakket is buiten de repository geïnstalleerd, maar de server kon niet starten: de omgeving heeft alleen UID/GID 0 gemapt en `useradd` faalt. Een poging een namespace met een niet-rootgebruiker te starten faalde met `Operation not permitted`. De PostgreSQL-tests krijgen daarom geen test-DSN; hun bestaande skipvoorwaarden blijven intact. Er is geen vervangende database of mock gebruikt om native bewijs te suggereren.
3. **Eerste zoekpoging met volledige regeluitvoer in de actieve testcheckout.** Gegenereerde bytecode gaf een UTF-8-decodefout. Deze onvolledige zoekpoging telt niet als bewijs. Alle 17 opdrachten zijn daarna volledig opnieuw uitgevoerd in de schone basis-worktree, met binaire zoekmodus en alleen identifier-uitvoer zoals hierboven vastgelegd.
4. **Release-control-preflight.** De check scant alleen gewijzigde Python-testbestanden voor bewijsmarkers. Er zijn geen tests gewijzigd; daardoor blokkeert hij de categorieën `scope/belofte`, `opslag`, `toegang`, `kwaliteit`, `metrics`, `slop` en `releasebewijs` wegens ontbrekend gewijzigd testbewijs. De checker is ongewijzigd en niet omzeild. Dit is een open repositorycheck, ook als pytest slaagt.

5. **Volledige testsuite niet groen.** Vier tests falen in de definitieve eindrun. Alle vier zijn ook afzonderlijk uitgevoerd op de ongewijzigde basis `e5573878a5bed4a885c6896f88fcb515f964a9d7` en falen daar eveneens:

   - `tests/test_bounded_model_transport.py::test_parent_process_death_terminates_transport_worker`: `assert len(children) == 1` faalt. De test vergelijkt een PID van `subprocess` met PIDs in `/proc`; een aanvullende controle toont dat `os.getpid()` en de PID in `/proc/self/stat` in deze omgeving verschillen. Dit ondersteunt een namespaceprobleem in de testomgeving. De test en productcode zijn niet aangepast.
   - `tests/test_security_harden_wave3.py::test_ssrf_https_sni_stays_original_hostname_when_dns_rebinds`.
   - `tests/test_security_harden_wave3.py::test_ssrf_redirect_hop_revalidates_and_rebinds`.
   - `tests/test_security_harden_wave3.py::test_ssrf_redirect_from_pinned_public_to_metadata_is_rejected`.

   De drie SSRF-tests zijn aanvullend uitgevoerd met alleen de zes HTTP/HTTPS/ALL proxyvariabelen uit de testprocesomgeving weggelaten (`env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy ...`). Dan slagen ze alle drie, zowel op de ongewijzigde basis als op de branch. Dat is aanvullend omgevingsbewijs; het vervangt de mislukte volledige run niet. Er zijn geen tests uitgefilterd of verzwakt om een groene volledige suite te claimen.

Een eerste volledige pytest-aanroep begon vóór de verwijderingen en liep tijdens de bewerkingen. Die aanroep wordt niet gebruikt als definitief bewijs voor de eindversie. De hierboven gerapporteerde volledige eindrun is gestart nadat alle codewijzigingen waren afgerond. De vier vergelijkingen met de basis zijn afzonderlijke, uitgevoerde controles op een ongewijzigde worktree.

## Eindbesluit en pushstatus

De 17 verwijderingen en hun repo-lokale bewijs zijn vastgelegd in 13 afzonderlijke modulecommits; dit verslag vormt één aanvullende documentatiecommit. Er is geen concreet twijfelgeval bij de 17 kandidaten gevonden. `storage_prepare` blijft OPENVRAAG-S3.

**Lokale suite niet groen.** Aanvankelijk is de push geblokkeerd vanwege de eis dat alle lokale tests groen moesten zijn. Op 17 oktober 2026 heeft de gebruiker expliciet opdracht gegeven `chore/remove-proven-dead-code` alsnog naar origin te pushen: de vier fouten zijn op de basis aangetoond en omgevingsgebonden; CI is de beslissende run. Deze instructie heft uitsluitend de blokkade voor het publiceren van de branch op. Native PostgreSQL/Docling/browserbewijs en de release-control-preflight blijven open. Er wordt geen PR geopend en niets gedeployd.

De lokale Git-push kon geen GitHub-inloggegevens ophalen. Daarom wordt de branch gepubliceerd via de gekoppelde GitHub-verbinding. De modulecommits houden dezelfde afzonderlijke wijzigingen en exact dezelfde bestands- en treehashes; alleen de commitmetadata en commit-IDs veranderen door het transport. Dit verslag is uitsluitend bijgewerkt om de nieuwe gebruikersinstructie en transportkeuze vast te leggen. Er zijn geen gedragswijzigingen, refactors, hernoemingen of aanpassingen aan beschermde bestanden uitgevoerd om de verificatiebeperkingen te omzeilen. CI bepaalt het vervolg; er is geen merge- of deployopdracht gegeven.
