# Beslisgraaf: verificatie en overdracht, 1 oktober 2026

Dit is een herbouw, geen herstel van de oude lokale implementatie. Basis:
`d6fe3cbc3335d96256969d63e878de41468496d4`; main
`f385ade48712061317b43b2ab0b8464ac53bc1ce` is geïntegreerd. Overdracht loopt via
branch `decision-graph-recovery` en [concept-PR #478](https://github.com/WilliamGomes41/Metis-DS/pull/478).
Geen merge, deployment, bulkverwerking of herschrijving van historische publicaties.

## Uitgevoerde verificatie

- Gepubliceerde implementatie `572b41c8d04281c3fd4284473f5c01bd387352bc`:
  [CI 36881889362](https://github.com/WilliamGomes41/Metis-DS/actions/runs/36881889362)
  geslaagd op Python 3.12 én 3.13, PostgreSQL 16: elk **2419 passed, 5 warnings**.
- Volledige lokale suite met Python 3.12, PostgreSQL 17.11 en aanvullende native
  resultaatbundeltest: **2420 passed, 5 warnings in 168.79s**.
- Daarna toegevoegde policy/publicatierace, vertraagde extractie en timeout/retry:
  `pytest -q tests/test_decision_graph_native_concurrency.py tests/test_decision_ingest_recovery.py tests/test_decision_bundles.py`:
  **9 passed, 1 warning in 4.49s**. Deze aanvullende tests worden met dit rapport
  overgedragen. De actuele CI op de uiteindelijke head staat bij PR #478.
- Repository preflight, release-control mapping tegen origin/main, compileall,
  architectuurinvarianten en Product API-compatibiliteit zijn geslaagd.

De native fixtures gebruiken echte PostgreSQL-transacties en onafhankelijke
console/workerruntimes; bronopslag gebruikt een geheugenfixture met immutable bytes.
Herstart betekent een nieuwe console/runtime op dezelfde duurzame opslag, geen
OS-kill. Timeout en fouten vóór commit zijn doelgericht geïnjecteerd; geen echte
OOM of productiestoring. Geen live Azure- of productievalidatie.

Lokaal volledige suite: `pytest -q`, met `METIS_TEST_POSTGRES_DSN` gericht op de
uitsluitend synthetische testdatabase en `PGOPTIONS='-c statement_timeout=20000 -c lock_timeout=10000'`.
Alleen de fictieve hosts `rebind.example.test,hop.example.test` zijn toegevoegd aan
`NO_PROXY` en `no_proxy`. Zonder die correctie faalden drie SSRF-fixturetests door
de omgevingsproxy, ook op de oorspronkelijke basiscommit. Productcode is daarvoor
niet gewijzigd. De PostgreSQL-fixtures wissen testschema's: nooit een productie-DSN gebruiken.

## Negen acceptatiepoorten

| Poort | Stand | Concrete bewijzen en grens |
| --- | --- | --- |
| 1. Originele PDF, bronhash, alle pagina's en volledige disposition | Geblokkeerd voor Mantelzorg | Synthetische PDF-ingest en bronbinding getest in `test_decision_graph_chain.py`; oorspronkelijke bytes ontbreken. Oude aantallen 71 onderdelen/31 verbindingen niet gereproduceerd. |
| 2. Visueel juiste routes en menselijke correctie | Gedeeltelijk | `test_pdf_route_proposals.py` en `test_decision_graph_structure.py`: pijlen in beide richtingen, letterlijke labels, onzekere lijnen/krommen, single/multiple, gedeeld doel, expliciete paginaovergang, ontbrekende/verzonnen labels en cycli. Werkelijke pagina's en bewuste Ja/Nee-correctie daarop nog visueel toetsen. |
| 3. Single/optional zonder verborgen vier ogen | Geautomatiseerd bewezen | `test_explicit_review_policy.py` plus lokale/native parametrisatie in `test_decision_graph_chain.py`: risico maakt optional niet required; bevoegde primaire reviewer kan afronden; afzonderlijke graafbevestiging blijft nodig. |
| 4. Alle verplichte personen exact laten goedkeuren | Geautomatiseerd bewezen | Dezelfde suites: passages én boombevestiging nodig, verschillende personen, optional vervangt required niet; meerdere required lokaal en tweede required native getest. |
| 5. Correctie/policywissel invalideert bewijs en stale werk faalt | Geautomatiseerd bewezen binnen genoemde scenario's | Routecorrectie invalideert passages; bundelleden blijven gebonden. Native policy/graafrace heeft één winnaar. Policy/publicatierace publiceert óf gesloten oude policy waarna wijziging faalt, óf blokkeert publicatie na nieuwe policy. Vertraagde extractie faalt met `snapshot_object_write_conflict` en behoudt nieuwe policy/objecten. Geen aparte visuele optional-correctieproef met Mantelzorg. |
| 6. Dubbele ingest, timeout, retry en herstel | Geautomatiseerd bewezen binnen foutinjectie | Native identieke gelijktijdige ingest levert één snapshot. Lokale/native timeout na bronopslag behoudt exact bytes zonder envelope; nieuwe runtime en retry leveren één snapshot/bron. Geen echte proceskill/OOM getest. |
| 7. v1 beschikbaar tijdens v2 en atomair omschakelen | Native bewezen | `test_decision_successors.py::test_native_successor_cutover_and_failed_publication_preserve_v1`: v1 actief tijdens v2, geïnjecteerde publicatiefout behoudt v1, nieuwe runtime publiceert volledige v2, historische v1 blijft bestaan. Native rollback na object-/auditwrites vóór outer commit behoudt oude staat. |
| 8. Intrekking en geen losse boomadviezen | Geautomatiseerd bewezen | `test_decision_graph_chain.py`: native publicatie/herstart/intrekking; API-authenticatie en 404 na intrekking; resultaatbundel native gepubliceerd en uitgesloten uit proseretrieval. Bestaande lifecycle withdrawal/recovery-regressies meegenomen. Geen live externe retrievalclient getest. |
| 9. Lokale/native/UI/readiness/badge-pariteit | Gedeeltelijk | PostgreSQL 16 CI en 17.11 lokaal groen; native single/optional/required en SQL-badges; HTTP-graaf/policy/opvolgerformulieren en API getest. Visuele browseracceptatie met originele bron ontbreekt. |

**Geen volledige bron- of productieacceptatie:** poorten 1, 2 en 9 hebben nog
representatieve/visuele controles nodig. Groen CI vervangt deze controles niet.

## Kleinste ontbrekende aanlevering

Lever de oorspronkelijke Mantelzorg-PDF als ondersteunde bestandsbijlage aan deze
taak aan (vijf pagina's; eerder Library-record `libfile_456960968d948191ae0cbe1f4cda3edd`).
De Library-tekst was leesbaar, maar de originele bytes konden niet worden
geënsceneerd in deze executor; de ondersteunde route is al opnieuw geprobeerd.
Geen blinde herhaling of omweg langs niet-ondersteunde toegang. Geen JSON-conversie
of nieuw ontwerp nodig.

Daarna: bytes/hash en alle pagina's controleren; ingest uitvoeren; iedere passage
én route afhandelen; visueel gedeelde Ja-uitkomst, Nee-vervolg, leeftijdsvraag,
instructiestappen, paginaovergangen, multiselect op pagina 4 en evaluatielabels op
pagina 5 vergelijken. Corrigeer een opzettelijk fout Ja/Nee-voorstel via de UI en
toets hernieuwde review/publicatie. Leg correctiewerk en onbewezen bronvarianten vast.

## Feitelijke verklaring van de doorlooptijd

De oude executor leverde geen branch, code of test-PDF mee; eerst moest worden
vastgesteld wat nog bestond. Het ontwerp kon via Library worden gelezen, de oude
code niet, waarna herbouw volgde. Reviewpolicy raakt ingest, passage- en graafreview,
publicatie, retrieval en herstel tegelijk; uitsluitend een parser toevoegen was
onvoldoende. Native tests brachten vervolgens concrete transactie-, fixture- en
badgeproblemen aan het licht, die zijn opgelost en opnieuw geverifieerd.

Daarnaast kostten overdracht, geblokkeerde PDF-materialisatie, het opzetten van een
bruikbare lokale PostgreSQL en de afwijzing van PR-creatie op basis van alleen
doorgestuurde toestemming tijd. Dat was geen productfunctionaliteit. Eerder een
overdraagbare branch, native testbasis en zichtbare mijlpalen opleveren had de
voortgang duidelijker gemaakt. PR-creatie is pas uitgevoerd na de directe opdracht.
