# Karakterisering ingest en reviewruimte

Change class: C
Promise: Het huidige gedrag van ingest en de reviewruimte vastleggen zonder productcode te wijzigen.
Proof: 111 exacte golden-cases, gemeten takdekking, tijdelijke éénpuntsmutaties en opnieuw groene tests na herstel.
Touches lifecycle invariants: no
Rewrite risk: none

Basis: `e5573878a5bed4a885c6896f88fcb515f964a9d7`, de laatste opgehaalde `main` bij de start op 17 oktober 2026. Branch: `test/characterize-ingest-and-review-room`. Alleen nieuwe bestanden onder `tests/characterization/`. Productcode, bestaande tests en configuratie zijn ongewijzigd. Geen PR; geen deployment.

> **D6b:** `test_ingest.py`, `test_ingest_boundaries.py` en hun goldens legden de JSON-bestandsboom van de verwijderde bestandsopstelling vast en zijn met die opstelling verwijderd. De reviewruimte-goldens draaien op PostgreSQL en blijven. Dit rapport blijft het historische bewijs van die oorspronkelijke run.

## Bestanden en scenario's

| Bestand/groep | Cases | Wat is vastgelegd |
| --- | ---: | --- |
| `test_ingest.py` | 30 | Invoerweigeringen, reviewkeuze/policy, bestandclassificatie, normale ingest, ontvangst en commando-identiteit. |
| `test_ingest_boundaries.py` | 54 | Lokale/immutable opslagadapter, boom/PDF-classificatie, offline URL-fetch, nieuwe versie, replay, begrensde verwerking, beide deadlines, commitfouten en concurrerende/idempotente ontvangst. |
| `test_review_room.py` | 27 | Lege lijst, documentkeuze, index/detail/history/batch, meegegeven snapshot, rollen/publicatie, context/conflict, tweede onafhankelijke review en foutuitkomsten. |
| `golden/ingest/*.json` | 30 | Exacte return/fout, envelope(s), alle opgeslagen JSON/JSONL-objecten en bronbestanden (lengte/checksum). |
| `golden/ingest_boundaries/*.json` | 54 | Ook de achtergebleven duurzame toestand na fout, onderbreking of concurrentie. |
| `golden/review_room/*.json` | 27 | Volledige HTML of exact fouttype/foutcode; geen selectie van alleen losse tekstfragmenten. |
| `support.py`, `conftest.py`, `__init__.py` | — | Synthetische identiteiten zonder wachtwoorden/tokens, echte lokale opslag, vaste klok/UUID's, netwerkguard, golden-vergelijking en optionele mutatieproef. |
| `coverage_baseline.json` | — | Uitgevoerde regels/arcs, ontbrekende regels/arcs, bronhashes, uitslagen en namen van rode mutant-cases. |
| `REPORT.md` | — | Dit verslag, beperkingen en reproduceerbare opdrachten. |

Alle 111 cases vergelijken hun geobserveerde uitkomst exact met een vooraf opgeslagen golden. De fixtures karakteriseren het bestaande gedrag, ook wanneer dat een weigering of exception is; zij bewijzen niet dat het bestaande gedrag inhoudelijk gewenst is.

De ingevoerde tekst, namen, bestanden, boomdata, opdracht-ID's en example.test-URL's zijn volledig synthetisch. Accounts bevatten alleen identiteit/rollen; er worden geen wachtwoorden, API-sleutels of sessies aangemaakt. De broncode van de geteste functies wordt niet nagemaakt: echte ingest, transform, toelatingspoort, opslag, reviewroutering en HTML-renderers blijven actief. Alleen externe afhankelijkheden en expliciete fout-/racegrenzen krijgen gecontroleerde offline invulling. Reviewkandidaten worden door de bestaande deterministische materialisatie aangemaakt.

Normalisatie beperkt zich tot het tijdelijke pad (`<TMP>`) en de Python-versiestring (`<PYTHON>`). Tijd/UUID/runtime-identiteit worden als omgevingsinput vastgezet; inhoud, toestand, object-ID's, hashes, volgorde, HTML, foutcodes en concurrentie-uitkomsten worden vergeleken. Er wordt geen HTML-witruimte verwijderd en geen ontbrekend veld genegeerd. De normale testopdracht schrijft geen goldens. `--record-characterization` is een expliciete onderhoudsoptie en wordt geweigerd samen met een mutatie.

## Resultaat en dekking per regelbereik

Lokale runtime: Python 3.12.14, pytest 9.0.2, coverage.py 7.13.3. De gemeten 111 cases zijn uitgevoerd op de ongewijzigde productcode van de genoemde main-tip. Nul failures, nul errors, nul skips. Na beide mutatieproeven zijn dezelfde 111 cases opnieuw groen.

| Doelbereik | Uitgevoerde statements | Uitgevoerde branch-arcs | Niet uitgevoerd |
| --- | ---: | ---: | --- |
| `operations_console_v1.py:1691–2087` | 241/243 (99,18%) | 117/118 (99,15%) | Regels 1778–1779; arc 1904 → 1907. Zie OPEN-C01/C02. |
| `operations_console_app.py:3448–3649` | 70/74 (94,59%) | 40/40 (100%) | Regels 3533–3534 en 3575–3576. Zie OPEN-C03/C04. |

Dit zijn alleen de gevraagde bereiken, geen percentages over de volledige bestanden. Coverage.py telt exceptionhandlers en sommige éénregelige conditionele expressies niet als afzonderlijke branch-arcs. Daarom staan ook de gemotiveerd niet uitvoerbare exception- en ternary-armen expliciet in de OPENVRAAG-lijst. De fysieke regels bevatten daarnaast signatures, commentaar en witregels; die tellen niet als executable statements. Een volledig overzicht van gemeten regels/arcs staat in `coverage_baseline.json`.

De normale run weigert DNS/socketverbindingen, UDP-verzendingen en het starten van providerprocessen. Er zijn geen live cloud-, model-, URL- of databaseverbindingen gebruikt. De URL-fetchcases lezen uitsluitend meegegeven bytes via een lokale functie. De immutable adapter houdt uitsluitend fixturebytes in geheugen. De lokale bestanden zijn echte tijdelijke bestanden; de bestaande atomische commits/CAS blijven actief. Gecontroleerde stale reads simuleren een tweede schrijver; dit is geen bewijs van echte PostgreSQL-concurrentie.

## Mutatiebewijs en herstel

Er is één lokale mutatie per doelbereik uitgevoerd, elk afzonderlijk en uitsluitend in het geheugen:

| Mutatie | Enkele gewijzigde expressie | Uitkomst |
| --- | --- | --- |
| Ingest | De waarde `CAPTURED` in de nieuw opgebouwde envelope wordt `characterization-mutated-state`. | 46/84 ingest-cases rood op de golden-vergelijking; 38 voor deze toestand ongewijzigde weigeringen/fouten blijven groen. Exitcode 1, nul setup-errors. |
| Reviewruimte | Alleen `<h1>Review</h1>` wordt `<h1>Mutated review</h1>`. | 24/27 review-cases rood op de HTML-golden; de drie foutuitkomsten die geen HTML produceren blijven groen. Exitcode 1, nul setup-errors. |

De AST-mutator controleert dat precies één expressie verandert. De oorspronkelijke decoratoren blijven toegepast. Pytest herstelt de functie na iedere case met `monkeypatch`; het proces eindigt daarna. De productbestanden worden tijdens de mutatieproef nooit op schijf gewijzigd. Na herstel: **111/111 groen**, nul errors/skips. Een Git-/bronhashvergelijking bevestigt dat beide productbestanden en alle andere productcode gelijk zijn aan main.

Dit is concreet bewijs dat de goldens deze gedragswijzigingen detecteren. Het is geen bewijs dat iedere denkbare wijziging in niet-uitgevoerde of niet-geobserveerde omstandigheden wordt gedetecteerd. Een test van een geweigerde invoer hoeft niet rood te worden door een wijziging van een succesvolle opslagroute; hij moet zijn eigen veranderde uitkomst detecteren.

## OPENVRAAG-lijst

| ID | Locatie | Waarom niet uitgevoerd / afbakening |
| --- | --- | --- |
| OPEN-C01 | Ingest 1778–1779 | `validate_configuration` kan hier onder de huidige ondersteunde contracten niet weigeren: `_resolve_named_reviewers` heeft bestaande, toegestane menselijke reviewers en minstens één ander dan de uploader afgedwongen; `legacy_default` maakt daarna de vaste geldige one_other-configuratie. Een exception afdwingen door de validator zelf te vervangen zou geen bereikbare huidige invoer bewijzen. Onverwachte contractbreuk van deze helper blijft open. |
| OPEN-C02 | Ingest arc 1904 → 1907 | De `elif review_policy is not None` kan hier niet false zijn: zonder policy is eerder een gevalideerde legacy-configuratie opgebouwd, waardoor de voorgaande `if review_configuration is not None` true is; met een policy is deze elif true. De combinatie beide None kan deze plaats niet bereiken. |
| OPEN-C03 | Reviewruimte 3533–3534 | De bovenliggende `except AttributeError` is niet bereikbaar via de huidige `_review_bindings`: die helper vangt AttributeError zelf af en retourneert None. Er is geen helper vervangen om dit kunstmatig te laten tellen als productiepad. |
| OPEN-C04 | Reviewruimte 3575–3576 | Dezelfde reeds intern opgevangen AttributeError voor de detailroute. De legacy-case legt ook de huidige latere AttributeError van de gewone reviewkaart vast; dat maakt deze buitenste catch nog niet bereikbaar. |
| OPEN-C05 | Ingest 1919/1931 en 1947/1968/2085 | Dode armen van inline conditionals: binnen `_receive_only` is de gewone `_receipt`-arm onmogelijk; na de onvoorwaardelijk terugkerende ontvangsttak is de `_durable_receipt`-arm onmogelijk. Coverage.py meet hiervoor geen afzonderlijke armdekking. De bereikbare armen zijn wel uitgevoerd. |
| OPEN-C06 | Externe topologieën | Echte PostgreSQL-transacties, cloudopslag en Docling/providerprocessen vallen buiten de uitdrukkelijk offline karakterisering. Hun I/O-semantiek wordt niet bewezen door de lokale adapter of foutinjectie. Dit is een bewijsgrens, geen gevonden onbereikbare producttak. |

Geen bereikbare gemeten if/loop-arc is ongedekt gelaten. Deze OPENVRAGEN geven geen toestemming productcode te verwijderen of te wijzigen.

## Geprobeerd en mislukt

1. De eerste tweede-reviewfixtures gebruikten een deterministisch ongevormd bronobject; dat opende terecht bronherstel in plaats van de bedoelde reviewroute. De fixture is opgebouwd via echte semantische bronselectie en de bestaande deterministische candidate creator; daarna zijn de actionable en niet-onafhankelijke tweede-reviewtakken daadwerkelijk gemeten.
2. De eerste begrensde ingest-fixture had identiteiten alleen in geheugen. De bestaande actuele autorisatie leest accounts van schijf en gaf `unknown_account`. Er is daarna uitsluitend synthetische, credentialvrije accountmetadata in de tijdelijke lokale store gezet; de uiteindelijke goldens bewijzen de bedoelde persist/deadline-/commitpaden.
3. Een eerste klokfixture probeerde een module-attribuut `time` te patchen dat lokaal in een functie geïmporteerd wordt. Dat gaf setup-errors. De definitieve fixture fixeert alleen wall-clockinput; deadlines gebruiken dezelfde echte monotone klok, met gecontroleerde overschrijding op de twee geteste checks.
4. Een te vroeg geïnstalleerde procesguard blokkeerde het lokale `uname -p` waarmee een geïmporteerde SDK platformmetadata leest. Dit was geen netwerkverbinding. De procesguard is na de imports geplaatst; socket/DNS-guards staan tijdens de imports al aan. De definitieve runs hebben nul setup-errors.
5. De twee rode mutatieruns zijn bewust mislukt (exitcode 1) door veranderde golden-uitkomsten; zij zijn geen productfouten. De snapshots zijn tijdens die runs niet bijgewerkt. De daaropvolgende normale run is weer geheel groen.

## Reproduceren

```sh
python -m pytest -q tests/characterization
python -m coverage run --branch --source=src.operations_console_v1,src.operations_console_app -m pytest -q tests/characterization
python -m coverage json -o /tmp/characterization-coverage.json

# Verwacht rood, exitcode 1; slechts één expressie per run, geen bronbestand wijzigt:
python -m pytest -q tests/characterization/test_ingest.py tests/characterization/test_ingest_boundaries.py --characterization-mutation=ingest
python -m pytest -q tests/characterization/test_review_room.py --characterization-mutation=review

# Verwacht weer 111 groen na automatisch herstel:
python -m pytest -q tests/characterization
```

Een golden-update gebeurt uitsluitend bewust met `--record-characterization`, gevolgd door inhoudelijke beoordeling van de gewijzigde golden-bestanden. Aanvullende repositorychecks: repository-preflight PASS, architecture-boundaries PASS, change-contract-validatie PASS, release-control-preflight PASS en de bestaande architectuurtests groen. De volledige bestaande repositorysuite is niet als groen geclaimd; dit bewijs betreft de nieuwe karakteriseringstests en deze afzonderlijke repositorychecks.
