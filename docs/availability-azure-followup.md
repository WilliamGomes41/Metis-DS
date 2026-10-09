# Beschikbaarheid en Azure-domeinautoriteit — GitHub-verificatie

Dit verslag vervangt de ontbrekende GitHub/native/browser-verificatie uit het eerdere lokale verslag. Historische bestanden in evidence/availability blijven behouden en zijn geen bewijs voor deze vervolgwijziging.

Basis van de auditreproductie: `0204045d1adc5e7a89e551844e3bf9751715e096`.
Bestaande reparatie bij aanvang: `6fd74d78fd594e604835f3e3c38d6393ba8ab01f`.
Domeincontract vóór vervolgcode: `57b4cf38d666e5ea37a8e6030df56abb047e343e`.
Eindrevisie van productiecode en tests: `cf549a945d03eb74b18d336d413253b167091cb1`.
Concept-PR: [#578](https://github.com/WilliamGomes41/Metis-DS/pull/578).
Alle vervolgwijzigingen en testuitvoering zijn via GitHub en GitHub Actions uitgevoerd. Geen lokale checkout, merge, deployment, productieverwerking of betaalde modelaanroep.

## Exacte wijzigingen en status

| Bevinding | Implementatie | Bewijs en ontwikkelstatus | Merge / productie |
| --- | --- | --- | --- |
| A26: ontvangst wacht op vorming | operations_console_app.ingest_post gebruikt receive_source; immutable bytes en lege documentregistratie staan vóór ontvangst vast. source_selection_v1 reserveert apart; source_processing_dispatch_v1 claimt de bestaande PostgreSQL-poging. Een HTTP-startsein is alleen een hint. Opstart/poll vindt pending werk terug. Een onzekere claimed poging wordt nooit blind herhaald. _durable_receipt leest de Blob-autoriteit terug, ook bij geldige cache. _record_processing_failure bewaart actuele blokkadereden en foutprovenance voor ontvangen bronnen. | Rood op basis; groen: ontvangst zonder provider, latere provider-/validatiefout, dubbele ontvangst/start, refresh, verloren HTTP-wake, nieuwe kernel na verwijderen van alle eerste caches, expiry/hervatten en fencing van oude poging. Native PostgreSQL; Azure-Blob-adapter is een deterministische stub. | Niet gemerged; niet in productie geverifieerd. |
| A04/A05: opvolger blokkeert eventloop / schrijflock | decision_successor_v1 registreert een eigen ontvangen revisie met parent guard; decision_review_ui_v1 start geen vorming. Expliciete selectie verwerkt in een thread na korte registratie/claim en vóór korte activatie. Autorisatie, revisie, bron, actieve lease en actuele parent-policy worden opnieuw gecontroleerd; dezelfde opdracht en dezelfde opvolgercontext dupliceren niet. | Rood op basis; groen: echte opvolgerroute, korte ontvangst, gelijktijdige health/Inleveren en onafhankelijke schrijver tijdens providerpauze, dubbel klikken, verschillende keys voor dezelfde context en parent-policywijziging vóór activatie. Parentobjecten blijven identiek; stale opvolger krijgt geen objecten. | Niet gemerged; niet in productie geverifieerd. |
| A02: herhaalde bronreconstructie | knowledge_materialisation_v1 bewaart alleen de twee bronrepresentaties binnen één berekening; inputinhoud bepaalt de entry. publication_readiness_v1 en geïnstalleerde review/workboard/detailroutes delen deze berekeningsscope. Validatie, reviewbesluiten en publicatiebevoegdheid worden steeds opnieuw berekend. | Rood: /publish reconstrueert 20 keer bij 20 bronrecords. Groen: alle zeven geïnstalleerde leesroutes met 30 bronrecords, op fixture én PostgreSQL. Maximaal twee reconstructies; HTML gelijk aan ongecachede berekening; de volgende berekening reconstrueert gewijzigde broninhoud; reviewer wordt opnieuw van Publicatie geweerd. | Niet gemerged; niet in productie geverifieerd. |
| Verborgen verwerkingsbinding | operations_console_v1 heeft een normale mutation-only _fragments_and_spec-grens met expliciete SourceProcessingStrategy. pre_review_semantic_v1 configureert de strategie en vervangt geen methods. deterministic_review_repair_v1 gebruikt de deterministische bronreader; semantic_suppressed en cataloguswrapper zijn verwijderd. De onafhankelijke diagnostische ContextVar blijft behouden. | Groen: geen methodreplacement; catalogus invokes geen provider; afwijkende opgeslagen verwerkingsconfiguratie faalt vóór providerwerk en wordt opnieuw bij activatie gecontroleerd. Historische readers en PDF-beslisboomcontract blijven. | Niet gemerged; niet in productie geverifieerd. |
| Azure als enige duurzame autoriteit | console_asgi.build_app en azure_console_startup.sh eisen de bestaande PostgreSQL identity/document/review/remaining-authoriteiten naast canonical PostgreSQL en immutable Azure Blob. Ontbrekende autoriteit stopt opstart. OperationsConsole is de bestaande Azure-backendkernel; de HTTP-console bezit geen duurzame status/queue/besluiten. | Groen: elke ontbrekende workflowautoriteit faalt gesloten; receipt faalt als Blob ontbreekt ondanks geldige cache; pending poging en bron worden door een nieuwe kernel zonder eerste caches teruggevonden. Geen tweede queue of schema toegevoegd. | Azure-configuratie/schema vóór een afzonderlijk toegestane deployment controleren. |
| Layout en selectie | Exact vijf hoofdblokken: Inleveren → Bronselectie → Review → Publicatie → Documenten. Receipt opent Bronselectie met snapshot geselecteerd. De eigen room leest de duurzaam vastgelegde fase, inclusief het begin van elke bounded V3-modeltaak; hij heeft titel/bestand/versie/omvang, status, fase/tijd, acties, kandidaten/bronpassages/blokkades en Naar Review. Tijdschatting gebruikt minimaal drie vergelijkbare complete metingen en een grove bandbreedte; zonder bewijs wordt onvoldoende gegevens getoond. Technisch succes is gescheiden van volledige vorming. | Groen: geïnstalleerde HTTP-layout en echte desktop/mobile Chromium; ontvangst start niets, refresh behoudt selectie, expliciet starten vormt kandidaten, uploader zonder toewijzing ziet traject en toegewezen reviewer opent Review. Vijf screenshots en browser-result.json. | Niet gemerged; niet in productie geverifieerd. |

## Rood/groen en metingen

[Verplichte bewijsrun](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37919109973) op de eindrevisie:
- Alle drie oude fouten worden opnieuw met providerstubs op de vastgelegde basis geassert. Iedere probe eindigt met de bedoelde assertion, niet een import-/infrastructuurfout.
- 67 gerichte tests geslaagd in 89,04 s; nul overgeslagen acceptatietests.
- Eén echte browserproef geslaagd in 11,79 s; nul overgeslagen browserchecks.
- Eén provideruitvoering bij twee concurrerende PostgreSQL-kernels; tien gemeten transactiegrenzen, maximale duur inclusief verkrijgen van de grens 0,087782451 s. Tijdens de providerpauze staat geen workflowtransactie of schrijflock open.
- Geen SLA afgeleid uit deze synthetische duurmeting.

| Leesroute (geïnstalleerde overrides) | Fixture / PostgreSQL reconstructies | Na wijziging bron, volgende aanvraag |
| --- | --- | --- |
| /publish | 2 / 2 | 2 / 2 |
| /review?work=all | 0 / 2 | 0 / 2 |
| /review | 2 / 2 | 2 / 2 |
| /review?task=disposition | 2 / 2 | 2 / 2 |
| /review?task=individual | 2 / 2 | 2 / 2 |
| /review?document=…&object=… | 2 / 2 | 2 / 2 |
| /review/bronpassage?document=…&object=… | 0 / 0 | 0 / 0 |

Een nul betekent dat die presentatie geen volledige blokreconstructie uitvoert. Counters meten bronreconstructie, niet cachebare beslissingen. Waar reconstructie nodig is, bevat de volgende reconstructie expliciet de gewijzigde brontekst.

[Native/browser-artefact](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37919109973/artifacts/11610418629): native/browser JUnit en logs, serverlog, home/received/formed/mobile/review screenshots en browser-result.json.
[Rode basislogs](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37919109973/artifacts/11611278567).

Brede CI op de voorafgaande codeversie 2785aab6bebeb84607ebc352f3d81345c27ad6aa is groen: Python 3.12 en 3.13 elk 3283 passed / 15 skipped; de aparte desktop/mobile-reviewbrowserjob 2 passed; echte PDF 12 passed op host en 12 passed in de begrensde container. De 15 opt-in skips zijn geen acceptatiebewijs; de afzonderlijke verplichte native/browser/PDF-proeven draaien daadwerkelijk.

[Brede CI van de vastgelegde eindrevisie](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37919109991) en [PDF/container-proef van die revisie](https://github.com/WilliamGomes41/Metis-DS/actions/runs/37919110028) waren bij vastlegging nog bezig. Hun definitieve resultaten worden in de PR-beschrijving vastgelegd. De laatste verslagcommit wijzigt uitsluitend documentatie; productiecode en tests blijven exact op de hierboven genoemde eindrevisie.

## Uitgevoerde commando’s in GitHub Actions

```bash
pip install -r requirements-dev.lock
git worktree add "$RUNNER_TEMP/metis-base" 0204045d1adc5e7a89e551844e3bf9751715e096
export METIS_PROBE_REPO="$RUNNER_TEMP/metis-base"
python evidence/availability/probe_upload_response_lifetime.py
python evidence/availability/probe_successor_availability.py
python evidence/availability/probe_publish_reconstructions.py
pytest -q -s tests/test_availability_repair.py tests/test_azure_source_processing.py tests/test_lifecycle_withdrawal_recovery_v1.py tests/test_pre_review_semantic_v1.py tests/test_pre_review_failure_diagnostics_v1.py --junitxml=proof/native.xml
npm install --prefix "$RUNNER_TEMP/metis-browser" playwright@1.58.2
"$RUNNER_TEMP/metis-browser/node_modules/.bin/playwright" install --with-deps chromium
pytest -q tests/test_browser_source_selection.py --basetemp="$RUNNER_TEMP/source-browser-proof" --junitxml=proof/browser.xml
```

Browserjob stelt METIS_PLAYWRIGHT_MODULE en METIS_BROWSER_EXECUTABLE in. Native job gebruikt de eigen PostgreSQL 16 service en METIS_TEST_POSTGRES_DSN. De workflow weigert ontbrekende XML, lege testsets, skips en failures. Foutlogs worden ook bewaard.

De volledige lifecycleproef gebruikt de bestaande volledige PostgreSQL-backend, echte ontvangst/start/publicatieroutes, menselijke review via gerenderde formulieren en HTTP-routes met bestaande kernelregels, Product API, actieve predecessor tijdens opvolgerversie, intrekking, credential-revocation, backup/recovery en herstart. De browserproef toetst tevens echte rolgebonden toegang; modelvoorstellen krijgen geen review- of servingautoriteit.

## Resterende grenzen

- Geen Azure-productieproef of causale verklaring voor een Azure-502. De Azure Blob-grens is gestubd; PostgreSQL en Chromium zijn native op GitHub Actions.
- Een pending opdracht kan worden herpakt na verloren wake. Een claimed opdracht met onzekere providerafloop wacht op bounded expiry en een expliciet geautoriseerde Hervatten-opdracht. Dit behoudt opdracht/evidence en voorkomt automatische dubbele modelaanroepen.
- De bestaande regels laten hervatten van vorming alleen toe vóór menselijke reviewarbeid. Daarna blijft het gecontroleerde opvolgerpad nodig; reviewwerk wordt niet overschreven of stilzwijgend gereset.
- De ondersteunde topologie blijft één Azure-instance met de bestaande één/twee-workergrens. Geen uitbreiding naar meerdere instances.
- Synchronous legacy kernel/CLI-ingest blijft compatibel; de HTTP-Inleveren-route is receipt-only. Historische pogingen zonder dispatchmarkering worden niet automatisch uitgevoerd.
- Receipt-commandkeys moeten door de aanroeper worden hergebruikt bij retry; de browserformulieren leveren deze key. Geen onbewezen exactly-once claim over een externe provider na onbekende netwerkafloop.
- Artefacten hebben de bestaande GitHub-retentie. Hun IDs, hashes en runs zijn ontwikkelbewijs; Azure blijft autoriteit voor runtime-documenten, review, releases en serving.

De brede CI voert daarnaast repository_preflight.py, release_control_preflight.py, product_api_contract.py (generatie en compatibiliteit), compileall, architectuur-/T5–T12-/lifecycle-regressies en pytest -q uit. De PDF-job gebruikt python -m pytest -q tests/test_docling_real_pdf.py op de host en dezelfde tests in Dockerfile.docling acceptance met 2 GiB en twee CPU’s.

Artefacthash native/browser: sha256:ed305d85fdd1332c9449fd4b41d6d19f8307c24c1209b7dc99b0b8b9c8004255. Rode-basisartefacthash: sha256:52492026c5cfe8b838b85723fc41558fa19d1124756589ce49b6c6565f0273a7.
