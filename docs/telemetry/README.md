# Metis telemetrie

Eén plek voor alle operationele signalen van Metis: `src/telemetry/`, getoond in **Inzicht** (`/inzicht`). Dit document is de naslag. Het beschrijft wat er wordt gemeten, hoe signalen aan elkaar worden gekoppeld, wat er nooit wordt vastgelegd en hoe je de pagina en Azure gebruikt om een fout te vinden en op te lossen.

Telemetrie is operationeel bewijs. Het is nooit domeinstaat, nooit een authority en mag nooit de uitkomst van een verzoek veranderen.

## Architectuur

```text
producenten (waar het werk gebeurt)              hub (src/telemetry)                 gebruik
───────────────────────────────────              ───────────────────                 ───────
request_diagnostics_v1  ── metis_diagnostic ─┐   logging_bridge ─► hub.record ─┐     /telemetry (pagina)
processing_trace_v1     ── metis_diagnostic ─┤                                 ├─►  /telemetry/api/*
publication_evidence_v1 ── metis_diagnostic ─┤   errors (vingerafdruk)         │    Azure Monitor (OTel)
publish_refusal_audit   ── metis_diagnostic ─┤   ring (geheugen) + JsonlSink ◄─┘    export (JSONL)
console_performance_v1  ── db-metingen ──────┤   analysis (begrip)
store-lock / Storeopdracht ── fasen ─────────┤   playbook (volgende stap)
elke logger ≥ WARNING  ──────────────────────┘
proces: start/stop, faulthandler, onafgevangen excepties
```

- **Producenten blijven waar ze zijn.** De hub verzamelt hun uitvoer. Zo ontstaat er geen tweede meetsysteem en blijven de bestaande tests en karakterisering geldig.
- **Opslag:** per worker een append-only JSONL-bestand in `<runtime>/telemetry/` (te overschrijven met `METIS_TELEMETRY_DIR`). Rotatie gebeurt bij 8 MB, met een maximum van 64 MB in totaal en 7 dagen bewaartermijn. De pagina leest alle workers. Zonder configuratie (tests) is er alleen een ringbuffer in het geheugen.
- **Azure Monitor:** ongewijzigd via `APPLICATIONINSIGHTS_CONNECTION_STRING`. Request-events gaan als logs en als SERVER-span. De `trace_id` op de pagina is gelijk aan de OpenTelemetry-trace-id in Azure.

## Correlatie

| Sleutel | Bron | Waar zichtbaar |
| --- | --- | --- |
| `request_id` | per HTTP-verzoek gegenereerd; header `X-Metis-Request-Id` | elk request-event, elke JSON-logregel tijdens het verzoek |
| `trace_id` | W3C `traceparent` van de aanroeper, anders de OTel-span, anders nieuw; header `X-Metis-Trace-Id` | idem, en Azure `operation_Id` |
| `attempt_id` | header `X-Metis-Attempt-Id` (strikt gevalideerd) | request-events, verwerkingsdiagnostiek |
| `doc_ref` | pseudoniem van het document (`d_` + sha256[:16] van het snapshot-id) | request-events; zoeken op een snapshot-id op de pagina werkt via dezelfde hash |
| `commit`, `instance`, `pid`, `runtime_id` | deploy-identiteit | elk event |

Document-id's, gebruikers-id's, querystrings, SQL, broninhoud en foutteksten worden nooit vastgelegd. Dat contract wordt bewaakt door `tests/test_request_diagnostics.py` en `tests/test_telemetry_v1.py`.

## Wat wordt gemeten

| Signaal | Event | Velden |
| --- | --- | --- |
| Elk HTTP-verzoek, behalve polling (`/session/status`), statische bestanden en de telemetrie-API zelf | `request_started`, `request_running` (heartbeat elke 15 s), `request_finished` | route-sjabloon, methode, status, uitkomst, duur, fasen (inclusief/exclusief, boom), DB-metingen, fout |
| Fout in een verzoek | `request_finished.error` | `type`, `code` (ConsoleError), `frames` (`src/…:functie:regel`), `fingerprint` |
| Afgehandelde fout | `request_finished.error.handled` | ConsoleError-code, zonder tekst |
| Database | `request_finished.db` en fasen `db_connect`/`db_execute`/`db_fetch` | aantal verbindingen en queries, tijden |
| Store-lock | fasen `store_lock_wait`, `store_lock_hold` | wachttijd tot de lock; hoe lang de lock vastzat |
| Storeopdracht (#678) | fasen `store_transaction`, `store_remirror` | transactie- en spiegeltijd van de eigenaar |
| Logs ≥ WARNING | `log_record` | logger, geredigeerd bericht (max. 240 tekens), vingerafdruk bij een exceptie |
| Verwerking en publicatie | bestaande `processing_*`, `publication_*`, `publish_*` | zoals gedocumenteerd in `docs/diagnostics/` |
| Proces | `process_started`, `process_stopped`, `unhandled_exception` | python-versie, origin (thread/process) |
| Crash | faulthandler op stderr | stack (bestand, functie, regel) bij fatale signalen, ook bij SIGABRT van een time-out |

Een verzoek zonder `request_finished` waarvan de heartbeats zijn gestopt, krijgt voor API-compatibiliteit de status `aborted`. De pagina toont **Afronding ontbreekt** als waarschuwing: telemetrieverlies en onderbroken verwerking zijn beide mogelijk. Deze observatie alleen bewijst geen crash, time-out of herstart.

## Inzicht: één ruimte, vier tabbladen (`/inzicht`)

Instellingen kanaliseert informatie in drie groepen: **Inzicht** (wat er gebeurt), **Beheer** (accounts, technisch beheer, ChatGPT-koppeling) en **Uitleg** (Over Metis). Inzicht is één pagina met vier tabbladen die naar elkaar doorklikken:

| Tabblad | Bron (bestaande eigenaar) | Ververst | Doorklik |
| --- | --- | --- | --- |
| **Systeem** | `src/telemetry` (deze naslag) | live, elke 30 s, alleen zolang het tabblad open is | verzoek → documentdiagnose |
| **Kwaliteit & werkproces** | `quality_metrics_app_v1.quality_view`: dezelfde meting, scope en bewaarde rapporten als de tabelpagina `/settings/quality` | op aanvraag (zware meting onder de store-lock) | bron → documentdiagnose of verzoeken op dit document |
| **Documenten** | `processing_status(deep=False)`, `processing_diagnostics_v1`, telemetrie per `doc_ref` | bij openen | document → verzoeken en fouten, verwerkingsbeheer, diagnostiek en brondekking, passages corrigeren |
| **Controles** | semantische veiligheidstests (uitkomst direct, niets bewaard), routevergelijking, reviewsignalen, exports | — | naar de bestaande pagina's |

- **Bevoegdheden blijven per bron gelijk.** Systeem bevat geen inhoud en is zichtbaar voor iedere aangemelde gebruiker. Kwaliteit toont alleen bronnen waarvan je uploader of aangewezen reviewer bent. Documenten volgt dezelfde regel als Technisch beheer.
- **Oude adressen werken door.** `/telemetry` verwijst naar `/inzicht?tab=systeem`. De Auditruimte is opgeheven: `/audit`, `/audit/new` en `/audit/archive` verwijzen naar Controles, `/audit/semantic-safety` naar `/inzicht/veiligheidstests`. `/settings/quality` blijft de tabelweergave met rapporthistorie en toont dezelfde tabbalk.

### Systeem

- **Filterrij** (geldt voor alles eronder): tijdvenster, route, uitkomst, status, deploy en vrij zoeken op request-, trace-, poging- of document-id. Filters staan in de URL, dus een link deelt precies jouw beeld.
- **Inzichten**: gerangschikte bevindingen in gewone taal (ontbrekende afrondingen, nieuwe foutgroepen, regressie na een deploy, dominante fase, lock-wachttijd, samenhang). Klik erop en de filter wordt gezet.
- **Tegels en grafieken**: verzoeken, foutpercentage, p95, ontbrekende afrondingen en lock-wachttijd; responstijd p50/p95 en volume met fouten. Bij hover zie je de waarden. De knop "Tabel" toont dezelfde data als tabel.
- **Foutgroepen**: gegroepeerd per vingerafdruk (type, code en diepste Metis-functies, zonder middleware-wrappers). Per groep zie je eerst/laatst gezien, routes, deploys, codelocaties en de volgende stap uit `playbook.py`.
- **Routes, fasen, samenhang, deploys**: waar de tijd heen gaat en wat oververtegenwoordigd is bij fouten en trage verzoeken (lift ≥ 1,5×).
- **Verzoekdetail**: fasenboom (totale en eigen tijd), correlatie-id's, DB-metingen, tijdlijn, logregels van hetzelfde verzoek en andere verzoeken op hetzelfde document.

### Kwaliteit & werkproces

Grafieken over dezelfde meting als de tabelpagina:
- direct bruikbare voorstellen per route (onvolledig meetbaar is gearceerd, nooit als succes geteld);
- herstel, correcties en afwijzingen;
- open werk per bron;
- open werk over tijd (uit de bewaarde rapporthistorie);
- gewijzigde inhoud en verwerkingsruns;
- meetdefinities en beperkingen.

## Van signaal naar oplossing

1. Start bij **Inzichten**. Ontbreekt een afronding, controleer dan eerst de meetdekking en open de groep voor de laatst vastgelegde heartbeat-fase.
2. Bij een **exceptie**: het diepste frame in de foutgroep is waar het misging. "Komt alleen voor in commit X" wijst op een regressie: vergelijk met de vorige deploy.
3. Bij **traagheid**: kijk welke fase domineert. `db_execute` met veel aanroepen wijst op N+1. `store_lock_wait` wijst op contentie: zoek de opdracht met een lange `store_lock_hold`.
4. Bij een **ontbrekende afronding**: onderzoek na de meetdekking ook de App Service-logs (stderr) rond hetzelfde tijdstip op een faulthandler-stack of herstart. Ontbrekende logs bewijzen geen oorzaak.
5. Neem `request_id`/`trace_id` mee in issues. Daarmee vind je hetzelfde verzoek in Azure (`docs/telemetry/errors.kql`).

## Uitbreiden

- Een nieuwe fase: voeg de naam toe aan `PHASES` in `src/request_diagnostics_v1.py` en gebruik `diagnostic_phase(...)` (blok) of `diagnostic_since(...)` (gemeten wachttijd).
- Een nieuw event: `from src.telemetry import record_event; record_event("naam", kind="...", veld=waarde)`. Alleen begrensde waarden; strings worden geredigeerd en ingekort.
- Advies bij een foutcode: voeg een regel toe aan `CODE_ADVICE` of `PHASE_ADVICE` in `src/telemetry/playbook.py`.

## Grenzen

- **Meetkwaliteit:** summary en requestdetail tonen `telemetry.quality`: fouten per
  leesoperatie, verdringing uit de procesbuffer en exact uitgesloten events door
  de analyselimiet. Verliezen binnen het venster en in de extra terugkijkperiode
  voor reconstructie staan apart. Een niet meer gevonden verzoek heeft deze
  informatie ook in het 404-antwoord. Zonder requests is het foutpercentage `null`.
- De procescounters gelden sinds het ontstaan van deze hub en noemen de runtime;
  ze tellen geen productiebreed verlies. Bufferevents kunnen nog op schijf staan.
  Leesfouten gelden voor gescande bestanden, ook als hun tijd niet vast te stellen
  is. Een bestand dat een andere worker tijdens de scan opruimt, telt niet als leesfout. Oudste/nieuwste observaties bewijzen geen aaneengesloten dekking. Eerdere
  retentieverwijdering, ontbrekende producenten en exportverlies blijven onbekend;
  `coverage` blijft daarom `not_established`. Zeven dagen is geen garantie op
  zeven dagen beschikbare gegevens.
- Een 500-antwoord wordt buiten de diagnose-middleware opgebouwd en draagt daardoor geen `X-Metis-Request-Id`-header. Het event heeft het id wel.
- De lokale opslag is per instance. Meerdere instances zie je samen alleen in Azure.
- De Product API (`serve-api`) is nog niet aangesloten.

## Experimentele historische afwijkingen (PR 2)

Systeem vergelijkt de laatste 15 minuten met het voorafgaande uur, ook bij een
langer gekozen tijdvenster. Vergelijkingen blijven binnen route, methode en
commit. De bestaande lezer neemt ook vóór de historische referentie een
begrensde reconstructiemarge van één uur mee; ontbrekende starts of meetverlies
blijven zichtbaar als onvoldoende bewijs. Drie opeenvolgende afwijkende
vijfminutenvakken zijn nodig, met minstens
vijf afgeronde verzoeken per vak. Mediane responstijd, spreiding (p90 minus p50)
en voldoende complete faseaandelen gebruiken een robuuste mediaan/MAD-referentie.

Bij bekende meetverliezen, ontbrekende historie of uitkomst-/verzoekfilters volgt
geen vergelijking. Geen bevinding bewijst geen gezondheid. De weergave noemt
onzekerheid, uitgesloten metingen en limieten, geeft onderzoeksadvies en voert
geen maatregelen uit. Dit levert geen voorspelde storingstijd op. Zie het
[ontwerp en de bewijsgrenzen](../change-contracts/telemetry-historical-deviations.md).
