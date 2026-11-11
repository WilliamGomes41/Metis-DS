# Bewijs per verwijderkandidaat — batch 2

Change class: C
Promise: Zestien kandidaten beoordelen op aanroepen, contract, testdoel en operatorgebruik; alleen de bewezen ongebruikte provenance-wrapper verwijderen.
Proof: Referentiekaart van alle gevolgde UTF-8-repobestanden, trace van de actuele herstelroute, native gedragsproeven, AST-equivalentie en verplichte repositorychecks.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht William, 11 november 2026. [#1049](https://github.com/WilliamGomes41/Metis-DS/issues/1049) /
[MET-70](https://linear.app/metis-phoenix/issue/MET-70), onder MET-11.
Onderzoeksbasis: `821692b4cda775cec62b3b137ea84fb94c447c5f`, head van de nog open
[PR #1048](https://github.com/WilliamGomes41/Metis-DS/pull/1048). Main was bij deze
controle `d5715e61ca47554b89853f190202ad388c30ed07`. Deze batch bouwt op die PR;
een open PR is geen merge of deployment.

## Methode en bewijsgrens

Per exacte identifier zijn vóór wijziging alle door Git gevolgde UTF-8-bestanden
doorzocht, inclusief `src`, tests, scripts, bewijsprobes, configuratie en docs.
De [referentiekaart](../../evidence/1049/references-before.json) bevat bron-SHA,
paden en regelnummers; definities tellen daarin mee als referentie. Geen naamtreffer
is geen zelfstandig bewijs van onbereikbaarheid. Voor de verwijderde wrapper zijn
ook decoratoren, overerving, directe/base-aanroepen, letterlijke dynamische dispatch
en de actuele broncorrectieketen beoordeeld. De actuele aanroepen van de behouden
helpers spreken het oude verwijdervermoeden juist tegen.

Dit is geen operatorinterview, productietelling of bewijs over onbekende externe
Python-consumenten. Onbekend gebruik wordt hieronder OPEN, niet stilzwijgend nul.
De tabel is het besluit; de JSON is het onderliggende zoekbewijs, geen runtimeconfig.

## Besluit per kandidaat

| Kandidaat | Aanroepen en contract | Testdoel | Operatorgebruik | Besluit en vervolgstap |
| --- | --- | --- | --- | --- |
| `deterministic_review_repair_v1._finalize_source_provenance` | Alleen eigen definitie; geen test-/scriptcaller. De in #505 beschreven taken gebeuren nu binnen `OperationsConsole.correct_object`, vóór de bestaande commit. | `test_review_closure_v1` en `test_a09_source_repair`: bronselectie/merge, beide hash-policies, stale/duplicate, mislukt commit en herstart. | Private helper; geen CLI-ingang of registratie gevonden. | **VERWIJDEREN**: uitsluitend de ongebruikte wrapper. Actuele verificatie, schema, hash, KO-guard en commit blijven gelijk. |
| `workflow_remaining_cutover_v1.prior_object_audit_history` | Alleen definitie, maar `semantic-only-formation.md` bepaalt expliciet behoud van reeds gearchiveerde objecthistorie. `prior_processing_history` blijft in opgeslagen envelopes en migraties bestaan. | De opvolger-/historietests bewaken behoud van ouderwerk; geen directe functietest gevonden. Dat is een bewijsgrens, geen toestemming het leescontract te schrappen. | Geen losse operatoraanroep gevonden; bestaande historie is niet op productie geteld. | **BEHOUDEN**: eerst expliciete historische leesacceptatie en eventuele vervangende lezer vaststellen. |
| `storage_prepare.py` | Geen runtime-/test-/scriptuitvoering gevonden. De vermelding in `release_control_preflight.py` is een padregel, geen aanroep. Module heeft wel een directe CLI. | Geen huidige producttestcaller. | `DEAD_CODE_REMOVAL.md` bewaart OPENVRAAG-S3 expliciet wegens mogelijk extern gebruik. | **OPEN**: operator bevestigt of dit CLI nog gebruikt wordt en zo ja waarvoor. Tot die tijd behouden. |
| `AuditRetentionService` | Geen huidige productinstantiatie; `audit-room-retirement.md` behoudt archief-/back-upherstel. | `test_audit_retention_v1`, `test_workflow_audit_retention_v1`, `test_lifecycle_withdrawal_recovery_v1`: uploadfout, checksum, herstel, native rollback en volledige ketenrestore. | Onderdeel van behouden herstelondersteuning; geen feitelijke operatorrun in deze batch. | **BEHOUDEN** als contractondersteuning. Uit de directe verwijderlijst halen. |
| `AuditRetentionService.list_archived` | Gedelegeerde lezer van behouden archiefreferenties. | Twee testmodules controleren lege lijst na rollback, één referentie na archiveren en herstel over nieuwe instanties. | Zelfde herstelcontract als de service. | **BEHOUDEN** met de service; testgebruik is hier nuttig herstelbewijs. |
| `PostgresAuditRegistry` | Native adapter voor hetzelfde behouden audit-/herstelcontract. | Drie testmodules; de volledige lifecycleproef exporteert en herstelt live én gearchiveerde records en vergelijkt tabellen/bronbytes. | Adapter voor herstelondersteuning; niet bewezen uitgefaseerd. | **BEHOUDEN**; gegevens-/tabel-/archiefuitfasering blijft de afzonderlijke auditstap. |
| `OperationsConsole.public_signup` | Alleen definitie en één testcaller; methode weigert expliciet met `public_signup_forbidden`. | `test_no_shared_login_and_role_authorization` bewijst deze weigering. Alleen een ontbrekende methode testen zou dit beleidsbewijs verliezen. | Geen CLI of operatorcaller gevonden. | **EERST MIGREREN**: ondersteunde account-/HTTP-grens aanwijzen en daar hetzelfde negatieve beleidsbewijs leveren; dan pas de oude methodesurface beoordelen. Nu behouden. |
| `OperationsConsole.silently_edit_object` | Alleen definitie en één testcaller; weigert `cannot_silently_mutate`. | Bestaande MVP-proef bewaart oorspronkelijke versie/hash en verwerpt stille mutatie. | Geen operatorcaller gevonden. | **EERST MIGREREN**: immutabiliteit op de actuele correctie-/opslaggrens aantonen en de oude publieke methode expliciet uitfaseren. Nu behouden. |
| `review_ledger.unregister_backend` | Vijf testmodules gebruiken dit om een oude backendregistratie los te laten. | Twee workers, coderollback, verdwenen disks en herstel moeten een nieuwe instantie gebruiken in plaats van een oude globale backend. | Geen productie-/operatorcaller gevonden. | **EERST MIGREREN** naar gedeelde testondersteuning, met behoud van proces-/workerisolatiebewijs; niet functie plus tests verwijderen. |
| `extract_metrics_v1.extract_quality_claim_allowed` | Module heeft geen runtime-importeur, maar is al `ACTIVE-TEST-SUPPORT` in het register; onafhankelijk meetcontract, geen productgate. | Drie modules verwerpen fixture-goud, ontbrekende review/locks en train/holdout-overlap als kwaliteitsclaim. | Geen actuele operatorrun vastgesteld; de expliciete acceptatiefunctie is voldoende reden tot behoud. | **BEHOUDEN** als acceptatieondersteuning; uit de directe verwijderlijst halen. |
| `extract_metrics_v1.compute_extract_metrics` | Zelfde onafhankelijke meetmodule; geen productiegebruik vereist voor dit doel. | Drie modules controleren false positives in de noemer, gemiste kennis, bronidentiteit, duplicaten, verslechterende scores en geen bestandswrites. | Geen operatoruitvoering waargenomen; geen runtime-import is geen uitfaseringsbesluit. | **BEHOUDEN** als onafhankelijke referentiemeting. |
| `extract_metrics_v1.measure_admission_language_variation` | Zelfde expliciete testondersteuning. | Twee modules toetsen taalvariatie en dat zelfverklaarde kwaliteitsvlaggen geen claim openen. | Geen huidige operatorcaller gevonden. | **BEHOUDEN** met de meetmodule; geen runtimegate toevoegen. |
| `prepare_operational_inputs` | Naast drie testmodules gebruikt ook `evidence/review-scoped-951/combined_probe.py` deze helper. `met41-operational-document-inputs.md` beschrijft voorbereiding buiten de lock. | Exacte input-/bron-/attemptbinding, back-up en herstel, vervalst plan en stale capture. | De bewijsprobe is aantoonbaar; actuele productielayoutverdeling en operatorgebruik zijn onbekend. | **OPEN** bij #953/MET-44: eerst layouttelling en migratie-/rollbackbesluit. Geen directe verwijdering. |
| `activate_operational_inputs` | Zelfde callers; activeert het voorbereide plan onder documentlock met CAS. | SQL-fout rolt layout/pins terug; herstart en dezelfde voorbereiding blijven veilig. | Zelfde onbekende uitfaseringsstand. | **OPEN** met voorbereiding; tests bewaken een duurzame overgang, niet alleen implementatiedetails. |
| `PostgresWorkflowReviewStore.read_events_after` | Geen huidige runtimecaller gevonden. #708 en `pg-command-review-evidence.md` benoemen dit expliciet als gecommitteerde auditreader. | `test_pg_command_review_evidence.py` controleert dat pending command-events niet als gecommitteerd bewijs zichtbaar worden. | Geen operatorcaller gevonden; contract nog niet als vervallen aangetoond. | **BEHOUDEN** tot de resterende committed-readerbelofte aantoonbaar op een behouden lezer ligt. |
| `runtime_data_inventory_v1.apply_clean_wwwroot` | Alleen één testmodule; model van clean deploy, geen productroute. | `test_clean_true_wipes_wwwroot_and_must_not_delete_runtime_data` controleert tijdelijke webroot, extern databehoud, clean=false en weigering bij overlappende paden. | Geen operatorcaller gevonden; geen echte webroot gewist in deze batch. | **EERST MIGREREN** naar testondersteuning als dit model nuttig blijft; deployment-/databehoudsbewijs behouden. |

Resultaat: **1 verwijderen, 8 behouden, 4 eerst migreren en 3 open**. Dit zijn
zestien kandidaten, niet zestien uitgefaseerde onderdelen. Overige A2/A3-symbolen
zijn in deze batch niet individueel afgesloten.

## Actieve helpers die bij de wrapper blijven staan

- `_verified_finalized_source_refs`: directe polymorfe aanroep vanuit
  `OperationsConsole.correct_object`; valideert de volledige gereconstrueerde
  bronverwijzingen en vraagt zo nodig echte PDF-fragmenten op.
- `_source_repair_provenance_patch`: dezelfde actuele correctie roept deze policy
  aan. De compatibility-implementatie hasht het repair-spec; `ReviewClosureConsole`
  bewaart het door de revision-engine berekende patch-hash. De bestaande test
  `test_compatibility_repair_hash_and_production_closure_patch_contract` controleert
  beide policies.

Deze helpers zijn via overerving actief. De oude wrapper verwijderen is geen
reden om de helpers, hun tests of de consoleklasse mee te verwijderen.

## Actuele correctieketen

`POST /review/resolve` → `submit_review_resolution` → `_source_repair` of
`_merge_repair` → `OperationsConsole.correct_object(source_repair_spec=…)` →
deterministische reconstructie/toelating → `_verified_finalized_source_refs` →
`_source_repair_provenance_patch` → `revise_object`/canonieke hash/schema → bestaande
lock/revisie-/rechtencontrole → `apply_ko_event` → `_commit_prepared_store`.

De verplaatsing naar de bestaande correctie is traceerbaar in commit
`413070035e85f9af58ce5207458d07aa0a868641` (A09/#587). Deze batch verandert geen stap
in die keten en introduceert geen nieuwe writer, state of opslaglayout.

Het [A09-contract](../change-contracts/a09-complete-source-repair.md) liet de helper
bewust staan tot een afzonderlijke controle van compatibility-callers/tests. Die
controle is deze batch: op de genoemde basis is geen caller of directe test meer
aanwezig; de oorspronkelijke herstelbelofte blijft op de actuele correctie getest.

## Uitvoering en verificatie

Vóór verwijderen: **49 bestaande broncorrectie-/closuregevallen geslaagd** op de
onderzoeksbasis, Python 3.13.5 met PostgreSQL 16.15. Geen skips. Hieronder vallen
daadwerkelijke HTTP-opslag, mergevolgorde, bronidentiteit, herstart, stale replay,
gelijktijdige correcties en rollback van objecten/bindings/audit.

De na-verwijderingcontroles en exacte codecommit worden vastgelegd in
[het uitvoeringscontract](../change-contracts/1049-candidate-contract-review.md).
Een testsuite bewijst geen afwezigheid van onbekende externe callers; operatorvragen
blijven zichtbaar open. Niemand hoeft voor de acht expliciete behoudsbesluiten
opnieuw te kiezen: hun bestaande contract is het uitgangspunt.
