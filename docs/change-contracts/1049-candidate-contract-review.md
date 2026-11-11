# Opschoning 2: bewijs per kandidaat en ongebruikte provenance-wrapper

Change class: C
Promise: Zestien kandidaten classificeren en uitsluitend de niet-aangeroepen provenance-wrapper verwijderen, met behoud van de actuele broncorrectie.
Proof: Versiegebonden bewijstabel/referentiekaart, 49 bestaande gedragsgevallen met PostgreSQL vóór wijzigen, AST-equivalentie en bestaande volledige suite plus verplichte repositorychecks na wijzigen.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht William, 11 november 2026. [#1049](https://github.com/WilliamGomes41/Metis-DS/issues/1049) /
[MET-70](https://linear.app/metis-phoenix/issue/MET-70), onder MET-11.
Basis `821692b4cda775cec62b3b137ea84fb94c447c5f`; deze slice bouwt op de nog open
PR #1048. De [bewijstabel](../plans/verwijderkandidaten-batch-2.md) bevat per functie
aanroepen, contract, testdoel, operatorstatus en besluit.

## Invariant en minimale wijziging

De oude `_finalize_source_provenance` heeft alleen een definitie en historische
documentreferenties. Sinds A09/#587 (`41307003`) geeft zowel bronselectie als merge het
repair-spec rechtstreeks aan de bestaande `OperationsConsole.correct_object`.
Die verifieert de volledige bronreferenties en de polymorfe patch-policy vóór
hash/schema/KO-guard en de bestaande commit. De wrapper wordt daar niet gebruikt.

Verwijder uitsluitend deze wrapper. Behoud `_verified_finalized_source_refs`,
beide `_source_repair_provenance_patch`-implementaties, autorisatie, materialisatie,
toelating, transactie, audit en historie. Canonieke inhoud/hash, brongetrouwheid,
publicatievoorwaarden en herstelgedrag blijven gelijk. Geen durable state,
gedeelde mutatie-/leesgrens of domeinregel wordt vervangen.

Het bronbestand moet AST-gelijk zijn na alleen de wrapper uit de basis-AST weg
te laten. Bestaande tests krijgen alleen een bewijscommentaar. Geen test of
weigering verdwijnt. Acht expliciete behoudskandidaten gaan uit de directe
verwijdersectie van de inventaris; vier migratiekandidaten en drie open vragen
blijven zichtbaar. Het levenscyclusregister en de GitHub/Linear-koppeling worden
binnen hun bestaande vorm bijgewerkt.

## Verificatie en grenzen

Baseline vóór verwijdering: `test_review_closure_v1.py` en
`test_a09_source_repair.py`, **49 passed, geen skips**, PostgreSQL 16.15/Python 3.13.5.
De volledige na-verwijderingrun en repositorychecks volgen op de codecommit.
Operatorgebruik en productielayouttelling zijn niet vastgesteld; de relevante
gevallen zijn OPEN, niet goedgekeurd voor verwijdering. Geen merge of deployment.
