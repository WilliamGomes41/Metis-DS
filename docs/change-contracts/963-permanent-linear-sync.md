# Permanente GitHub–Linear-overdracht

Change class: B
Promise: Een repositoryworkflow projecteert geverifieerde GitHub-voortgang en expliciete overdracht naar bestaande MET-issues, onafhankelijk van een chat.
Proof: Gerichte gedragsproeven voor scope, paginering, herhaling, concurrency, ontbrekende overdracht en uitblijven van statusmutaties; live bewijs blijft open tot de workflow met de benodigde sleutel op main draait.
Touches lifecycle invariants: no
Rewrite risk: none

## Gebruik vóór implementatie

De beheerder voegt `LINEAR_API_KEY` toe aan repositorysecrets. Na menselijke
merge draait `.github/workflows/linear-github-sync.yml` vanuit main op
GitHub-gebeurtenissen, handmatig en periodiek. De lokale standaard is dry-run:

```sh
python scripts/linear_github_sync.py --check-config
python scripts/linear_github_sync.py
python scripts/linear_github_sync.py --apply
```

Een PR heeft precies één primaire `Part of MET-…`-koppeling en bevat een kleine
machineleesbare overdracht met de echte PR-head. CI weigert ontbrekende,
ambigu gekoppelde of achterhaalde overdracht. CI-status moet nog als vereiste
branchcheck worden ingericht voordat dit een afdwingbare mergevoorwaarde is.

## Bestaande werking en oorzaken

`docs/agents/linear-github-handoff.md` schrijft GitHub-waarheid, Linear-voortgang,
concreet Done-bewijs en een sessiehandoff voor. `tests/test_agent_skill_docs.py`
controleert deze documentatie; er is op basis `3b6e83e` geen zelfstandige
synchronisatieworkflow. Een chatgebonden uurtaak kan verdwijnen met de chat.
Bij de bordcontrole waren gemergde deelslices en complete werkpakketten
verwisseld. De PowerPoint-lessen 1, 4, 5, 7 en 15 vragen om minder handwerk,
structurele controle, zichtbaar bewijs en blijvende overdracht.

## Twee vormen en keuze

Deze twee alternatieven zijn door één agent onderzocht, niet door onafhankelijke
modelrunners.

| Criterium | A: native Linear Loop | B: deterministische GitHub Actions-worker |
| --- | --- | --- |
| Eigendom en opslag | Configuratie in Linear | Versiebeheer, tests en runhistorie in dezelfde repository |
| Beheer met beschikbare tools | Geen Loop-/integratiebeheer beschikbaar | Branch, bestanden, tests en PR beschikbaar |
| Aantoonbaar gedrag | AI-instructies en runcontrole | Gedragstest op commentmutaties en PR-ingang |
| Credentials | Linear-codeleesconfiguratie en eventuele credits | Bestaand GitHub-token en beperkte Linear-sleutel |
| Werkkeuze en Done | Moet expliciet begrensd worden | Geen issue-/projectmutatie in de API-surface |

B is gekozen: één kleine worker, geen database, modeldienst, webhookserver of
tweede workflow-engine. A blijft een mogelijk alternatief als een beheerder de
native configuratie later aantoonbaar kan inrichten. Er wordt niet gedaan alsof
beide primaire writers tegelijk nodig zijn.

## Data en eigendom

`Binding(github_issue, linear_issue)` is uitsluitend de unieke identiteitsbrug
in `config/linear_github_sync.v1.json`, geen tweede backlog. Klassen, statussen,
prioriteiten, afhankelijkheden en eigenaarschap worden er niet gekopieerd.
Gedeelde registerverwijzingen (#877) en het incident zonder unieke eigen
GitHub-opdracht worden niet als unieke koppeling behandeld.

`Snapshot` bevat alleen issue- en PR-feiten (nummer, toestand, URL, head,
mergefeit) plus een expliciete overdracht van een repositorycollaborator.
GitHub bezit deze feiten. Linear bezit menselijke werkkeuze en opleverstatus.
De worker kan alleen één eigen comment maken/bijwerken; de implementatie heeft
geen `issueUpdate`- of projectmutatie. Daardoor kan een merge nooit via deze
worker Done, prioriteit of een volgende opdracht veroorzaken.

Een vast commentmarker en een digest over betekenisvolle bronfeiten maken
herhaling zonder ongewijzigde datumupdates mogelijk. Alle API-pagina's worden
gelezen. Eerst worden alle bronnen en doelissues gevalideerd, daarna pas
geschreven. Voor een mutatie wordt het doel opnieuw gelezen; conflict stopt de
run. Een Actions-concurrencygroep serialiseert eigen runs. Externe writers
blijven mogelijk: er is geen atomische compare-and-swap of cross-service
transactie. Bij onzekere create-uitkomst wordt niet blind opnieuw gemaakt.

## Risico en kleinste bewijslast

| Fout | Bewijs |
| --- | --- |
| Merge sluit volledig werk | Test: merge wijzigt uitsluitend de comment; protected issuevelden blijven gelijk |
| Verkeerd team of dubbele mapping | Afwijzing vóór eerste mutatie |
| Verloren overdracht na nieuwe commit | PR-ingang weigert ontbrekende/onjuiste head en ontbrekende next_step |
| Dubbele comments of oneindige updates | Tweede identieke run doet nul writes; bestaande eigen comment wordt bijgewerkt |
| Geheimen bij onbetrouwbare PR | Privileged job checkt alleen main uit; geen eventtekst in shell en geen PR-code met secrets |
| API- of pagineringsfout geeft schijnsucces | Niet-nul exit, geen geruisloze skip, eigen foutbericht zonder credentialwaarden |

## Oplevervolgorde, activatie en grenzen

Geen bestaande productcode of oorspronkelijke handoff verwijderen. Eerst deze
sketch en falende gedragsproeven; daarna configuratie, worker en workflow;
dan canonieke instructies en concrete activatie-/rollbackstappen. De tijdelijke
ChatGPT-taak wordt pas na bewezen GitHub-run uitgezet om een bewakingsgat te
voorkomen. De workflow controleert feitelijke voortgang en overdracht; hij
interpreteert geen ongestructureerde acceptatiebesluiten en herstelt geen
bestuurlijke statusvelden zelfstandig.

Open: Linear-sleutel, echte GraphQL-/Actions-run, vereiste branchcheck en
menselijke review/merge. Lokale mocks bewijzen geen live API-compatibiliteit.

## Uitgevoerde verificatie op de implementatie

- 15 gerichte synchronisatie-/workflowproeven PASS; samen met de bestaande
  agentcontract- en architectuurinvarianten: 30 tests PASS.
- Gerichte mutatie in een geïsoleerde wegwerpkopie: verwijderen van de exacte
  headcontrole laat de negatieve stale-headtest falen door het ontbreken van
  de verwachte weigering. De oorspronkelijke implementatie bleef intact.
- Repositorypreflight, release-control op de acht daadwerkelijke paden,
  architectuurgrenzen, compileall, wijzigingscontract en whitespacecontrole PASS.
- Volledige `pytest -q` geprobeerd, maar tijdens verzamelen geblokkeerd:
  PostgreSQL 16 ontbreekt. De aanwezige PostgreSQL 17 is door de bestaande
  testpreflight terecht geweigerd; er is geen test geskipt of norm versoepeld.
- Geen live Linear-API-/GitHub-Actions-run: de Linear-sleutel ontbreekt en deze
  branch is nog niet door de projectlead gemerged. Activatie blijft expliciet open.
