# Weergavecontrole vanuit Documentdiagnose

Change class: B
Promise: Een toegewezen reviewer vraagt vanuit Documentdiagnose een alleen-lezen browsercontrole aan en leest de duurzame uitkomst terug bij hetzelfde document en dezelfde gekozen poging.
Proof: Native PostgreSQL registreert/dedupliceert/herneemt de taak; de echte app weigert doelmutaties en andere documenten; de browseracceptatie doorloopt aanvraag, afzonderlijke browserworker, resultaat, herladen en beschermd schermbewijs.
Touches lifecycle invariants: no
Rewrite risk: none

Issue #807; expliciete opdracht van William op 21 oktober 2026 om implementatie te starten. Deze opdracht autoriseert repositorywerk en een review-PR. Geen merge, migratietoepassing buiten test, deployment of productie-uitvoering.

## Gekozen uitvoering

De bestaande CJS/Node Playwright-integratie blijft de enige browserstack. Eén vaste scenariodefinitie draait in een afzonderlijk Node-proces; geen browser in de webrequest. Een kleine backendpoller levert PostgreSQL-taken af, met maximaal één actieve browser, een lease van 60 seconden, een subprocesslimiet van 45 seconden en maximaal twee uitvoerpogingen. Geen generiek jobsysteem en geen wijziging van de source-processing-dispatcher: die beheert domeinmutaties en heeft hier een andere verantwoordelijkheid.

`workflow.view_checks` is uitsluitend autoriteit voor operationele onderzoekstoestand. De backend gebruikt de oorspronkelijke PG-connectie van de bestaande documentstore, buiten documenttransacties. Geen bestandsfallback. Registratie en events zijn één transactie; claims en resultaatfences zijn korte transacties. Een late worker heeft geen geldige capability en activeert niets. Browserwerk en Blob-I/O vallen buiten die transacties. De bestaande bron-, review- en publicatieautoriteiten veranderen niet.

De scoped capability verwijst naar een aangevraagde job en de actuele opdrachtgever. Er wordt geen menselijke sessie gekopieerd en geen nieuw reviewaccount gecreëerd. De middleware valideert de lease, documentrechten, revisie en context bij iedere request. De capability geldt alleen voor GET op Bronselectie, de volledige Review-inventaris en de bestaande passage-export voor dat document, plus brand-assets. POST, andere documenten, algemene overzichten en diagnose-commands worden geweigerd. Normale sessies houden hun bestaande gedrag. Bronselectie toont de capability alleen het gekozen document; geneste retained-only-leesscopes blijven retained-only zodat er geen verborgen native extractie volgt.

## Contextcontract

| Gegeven | Producent / eigenaar | Gebruik / geldigheid |
|---|---|---|
| Snapshot, bronhash, bronversie, gekozen historische poging | Bestaande documentauthority | Pin bij aanvraag; onbekende poging weigeren |
| Objectrevisie en envelope/bindings-hashes | Bestaande domeinqueries | Voor, tijdens en na uitvoering vergelijken; wijziging maakt vergelijking inconclusief |
| Origin en scenarioversie | Gevalideerde operatorconfiguratie / vaste code | Geen URL of script uit een melding; geen originwissel bij herstart |
| Job, poging, capability-hash, lease, events, uitkomst | PostgreSQL | Idempotente aanvraag; vervallen lease blokkeert oudere uitvoerder |
| Screenshotmanifest en hash | Backend / PostgreSQL | Alleen na gecontroleerde opslag en contextcontrole activeren |
| Screenshotbytes | Afzonderlijke private Blobcontainer | Nooit bronnamespace of algemene telemetrie; iedere download controleert actuele documentrechten |

De oorspronkelijke poging is een historische referentie; het nieuwe browseronderzoek is een actuele waarneming en wordt niet achteraf aan die oude poging toegeschreven. Een gelijke query/schermuitkomst is geen bewijs van klinische juistheid.

## Opslag en inschakelen

Migratie `019_view_checks.sql` MOET vóór inschakelen zijn toegepast via het bestaande migratieplan met target- en digestbevestiging. De migratie is additief en verandert geen brontabellen. Oude applicatiecode negeert de tabel; een coderollback verwijdert geen bewijs.

Standaard staat de uitvoering uit; Documentdiagnose legt uit dat de controle nog niet is ingericht. Voor een toegelaten testomgeving zijn nodig:

- `METIS_VIEW_CHECK_ORIGIN`: vaste HTTPS-origin; HTTP alleen op loopback voor de geïsoleerde browserproef.
- `METIS_PLAYWRIGHT_MODULE` en `METIS_BROWSER_EXECUTABLE`: bestaande CJS-tooling en vooraf geïnstalleerde Chromiumversie. Geen runtime-downloads.
- `METIS_VIEW_CHECK_EVIDENCE_CONTAINER`: bestaande private container, verschillend van de broncontainer, bereikbaar via de bestaande Azure-serviceclient. De feature maakt geen container of infrastructuur aan.

Het manifest laat bewijsdownloads zeven dagen toe. **Dat verwijdert Blobbytes niet fysiek.** Voor inschakelen buiten de synthetische test MOET een bijpassend opslagretentiebeleid worden ingericht, inclusief niet-geactiveerde uploads. Een crash tussen upload en manifestcommit laat een niet-geactiveerd artefact achter; dat verleent geen downloadrecht. Geen publiek Blobadres of SAS in de console. Ontbrekend, gewijzigd en verlopen bewijs krijgt een afzonderlijke foutuitkomst.

Productie blijft buiten deze opdracht. De runneromgeving MOET de toegelaten netwerkgrens leveren; Playwright-requestfilters en servercapabilities zijn geen bewijs van netwerkisolatie voor het hele Chromiumproces. #650 is alleen relevant als de rt-sandbox als uitvoeringsomgeving wordt gekozen.

## Begrensde eerste scenario-uitvoer

De eerste implementatie controleert de volledige inventaris tot 1.000 opgeslagen objecten: passage-ID's, bronregelpartitionering, reviewlinks, gekozen bron en browserfouten. Zij vangt een verkeerde ID bij gelijk aantal. De screenshot is een vast viewport, geen claim dat iedere rij op het screenshot staat. Bronlocators, uitsluitingsreden/status op iedere kaart, volledige broncontext en klinische volledigheid zijn **nog niet vastgesteld** door dit scenario. De UI en het resultaat noemen deze grens expliciet. Deze PR sluit daarom #807 niet: de bredere inhoudelijke acceptatiepunten blijven open.

Een taak met afwijkingen eindigt als completed met fail-checks; completed betekent niet dat het document goed is. Onvolledige uitvoering maakt eerdere pass-checks inconclusief; waargenomen afwijkingen blijven zichtbaar. De UI toont de laatste twintig onderzoeken; oudere onderzoeken blijven via hun ID bereikbaar.

## Verificatie

- Lokaal: 19 pure/architectuur/migratieplancontroles geslaagd; JavaScript-syntax, Python-compilatie, dependencygrenzen en repositorypreflight geslaagd.
- Native PG-tests zijn hier geblokkeerd door ontbrekende PostgreSQL 16; setup faalt op OS-groepsrechten. Dit is geen skip/pass.
- Native opslag/autorisatieproeven en een echte browserketen zijn toegevoegd. `source-processing-proof` moet ze met native PostgreSQL en Chromium uitvoeren en ontbrekend/overgeslagen browserbewijs afwijzen. Hun uitslag wordt op de PR bijgehouden.
- Geen actuele productie-uitvoering, performanceacceptatie, Azure-bewijsopslagacceptatie of volledige issue-acceptatie vastgesteld.
