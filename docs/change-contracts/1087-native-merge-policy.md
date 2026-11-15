# #1087 — Native mergebescherming voor één beheerder

Change class: C (governance; gedragstests vereist)
Rewrite risk: none
Touches lifecycle invariants: no
Promise: G1 vereist de bestaande testchecks, de actuele PR-handoff en opgeloste reviewthreads zonder een tweede menselijke reviewer verplicht te stellen.
Proof: policy- en workflowtests plus native GitHub-readback; een plan is geen actieve bescherming.

## Ontwerp en besluit

William heeft stap 3 toegewezen en op 15 november 2026 bevestigd dat hij voorlopig
de enige bevoegde menselijke reviewer is. Daarom voegen we geen verplichte
approval, CODEOWNERS-approval of last-push-approval toe. Een agentgeschreven
GO-comment is geen menselijke goedkeuring. William beoordeelt kritieke test-,
rechten-, workflow- en deploymentwijzigingen inhoudelijk voordat hij merge uitvoert.
Opgeloste threads dwingen afhandeling van geplaatste feedback af; ze bewijzen
geen onafhankelijke inhoudelijke review. Die beperking blijft bij één beheerder.

Twee structurele opties zijn vergeleken:

| Optie | Gevolg | Keuze |
| --- | --- | --- |
| `handoff-contract` als native verplichte check toevoegen | GitHub blokkeert merge rechtstreeks; metadata-edits draaien alleen de kleine PR-check opnieuw | Gekozen |
| Handoff opnemen onder de bestaande `test`-jobs | Vereist dure volledige CI bij `edited`, of extra statuscoördinatie; een overgeslagen required job kan onterecht als succes gelden | Afgewezen |

De bestaande route blijft `change-contract`/architectuur → preflight/suites/browser/
characterization → `test (3.12)` en `test (3.13)`. `ci.yml` blijft ongewijzigd.
De handoffjob verhuist vanuit de gecombineerde sync naar `pr-handoff.yml`:
precies één job met die naam, alleen PR-events, inclusief `edited`, zonder
jobconditie. Zo produceert een issue-, schedule- of privileged target-event geen
overgeslagen check met dezelfde naam. De privileged sync blijft uitsluitend op
main draaien, zonder PR-code met secrets uit te voeren.

GitHub-ruleset **G1 main**, id **21686159**, blijft de mergeautoriteit.
`config/github_merge_policy.v1.json` beschrijft het minimum; de lokale checker
leest uitsluitend een API-snapshot en schrijft nooit GitHub-instellingen.
Hij accepteert alleen deze actieve repository-ruleset voor exact main zonder
exclusies of bypass, met de vier bestaande beschermingsregels elk precies één keer.
Het plan vereist actuele checks, handhaaft checks bij branchcreatie, bindt de drie
vereiste contexts aan GitHub Actions (app-id 15368, waargenomen in check-runs),
en vereist opgeloste threads. Bestaande extra checks, regels en sterkere
revieweisen blijven behouden. Een onverwachte bestaande integratie wordt niet
stil vervangen. Geen nieuwe runtimecomponent, rechten, secret of Azure-mutatie.

## Risico en bewijs

| Foutscenario | Controle | Bewijsgrens |
| --- | --- | --- |
| Handoff ontbreekt, een check komt van een andere integratie, branch is verouderd of threads hoeven niet dicht | Afwijzende policytests en CLI-exitcode | Snapshotcontrole bewijst geen live configuratie |
| Plan verliest bestaande bescherming of maakt solo-PR onmogelijk | Tests op behoud extra regels/checks/sterkere approvals, geen ongevraagde approval-eisen en idempotentie | GitHub valideert de uiteindelijke PUT |
| Een metadata-edit of ander event vervangt de required check door skipped-success | Eén ongeconditioneerde PR-job, geen filters, inclusief `edited`; bestaande stale-head/body-validatietests | GitHub-checkrun blijft nodig voor de actuele PR |
| Activatie mislukt of gebeurt niet | GET na PUT, validator op dat antwoord, resultaat in PR/handoff | Zonder readback blijft activering open |

Gerichte lokale verificatie en daadwerkelijke activeringsstatus staan in de PR
en de afsluitende handoff van MET-85. Geen deployment nodig; de Metis-runtime en
het deploymentprotocol veranderen niet. Linear Done-automatisering is buiten scope.

Verificatie op 15 november 2026: 75 gerichte tests geslaagd, inclusief de bestaande
architectuur-, handoff- en governancecontracten, zonder skips. Repositorypreflight,
compileall, architectuurchecker en shared-skills-controle geslaagd. Een geïsoleerde
mutatie die alle policyfouten accepteerde liet de drie ontbrekende-checktests
terecht falen. De volledige pytest-run stopte vóór uitvoering met exitcode 4:
PostgreSQL 16 ontbreekt in deze omgeving. Dat telt niet als geslaagde volledige suite;
de normale GitHub-CI blijft noodzakelijk.

Activeringspoging: PUT naar ruleset 21686159 gaf `Forbidden`. Native readback op
15 november 2026 bevestigde dezelfde bestaande twee checks zonder appbinding,
geen handoffcheck en thread resolution uit; `updated_at` bleef 28 augustus 2026.
De nieuwe bescherming is dus **nog niet actief**. Deze taak blijft open totdat
de native wijziging en daaropvolgende readback zijn geslaagd.

## Activeren en teruglezen

Voer dit uit met repository-administratierechten vanuit de gereviewde branch.
Haal de huidige regels direct vóór de wijziging op; pas nooit een oud plan toe.
Stem de wijziging af als een andere beheerder tegelijkertijd regels bewerkt:
de GitHub-API biedt hier geen transactionele compare-and-swap via deze tooling.
Bekijk de volledige diff: alleen de beschreven versterkingen mogen wijzigen.

```sh
gh api repos/WilliamGomes41/Metis-DS/rulesets/21686159 > /tmp/metis-g1-before.json
python scripts/check_github_merge_policy.py --ruleset /tmp/metis-g1-before.json --plan > /tmp/metis-g1-put.json
```

Controleer het plan en pas het vervolgens expliciet toe:

```sh
gh api --method PUT repos/WilliamGomes41/Metis-DS/rulesets/21686159 --input /tmp/metis-g1-put.json
gh api repos/WilliamGomes41/Metis-DS/rulesets/21686159 > /tmp/metis-g1-after.json
python scripts/check_github_merge_policy.py --ruleset /tmp/metis-g1-after.json
```

Stop bij een mislukte opdracht; voer vervolgstappen niet op ontbrekende of oude
bestanden uit. De checker vereist het volledige GET-antwoord, niet het PUT-plan.
Een PASS betekent dat de aangeboden snapshot voldoet; de uitvoerder legt ook
ophaaltijd, ruleset-URL en uitkomst vast. Bewaar dit bewijs in de PR.

Zonder API-writecapaciteit: open [G1 main](https://github.com/WilliamGomes41/Metis-DS/settings/rules/21686159),
voeg `handoff-contract` van GitHub Actions toe, bind de bestaande twee testchecks
aan dezelfde integratie en vink **Require conversation resolution before merging**
aan. Behoud strikte branchactualiteit en alle overige beschermingen. Houd het
aantal verplichte approvals op nul zolang er geen tweede bevoegde reviewer is.
Haal ook na een UI-wijziging de native instellingen opnieuw op en valideer ze.

Een code-rollback verandert geen GitHub-instellingen. Herstel bij een fout alleen
de zojuist gewijzigde velden tegen de dan actuele ruleset; overschrijf niet blind
de hele configuratie met een oude snapshot en schakel bestaande testchecks nooit uit.
