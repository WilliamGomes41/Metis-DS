# Besluit past bij geschiktheid — #974 P4c / MET-48

Projectleidersbesluit 2026-11-05 (#974): na de keuze voor geschiktheid zijn
alleen eindoordelen kiesbaar die `ALLOWED_FINAL_BY_SUITABILITY` toestaat. Komt
een conflicterende combinatie toch binnen (oud formulier, geen JavaScript,
zelfgemaakt verzoek), dan noemt Metis de gekozen combinatie en de toegestane
eindoordelen in plaats van de algemene foutmelding.

Klasse B. Rewrite risk: none. Geen lifecycle-, identiteits- of schemawijziging.

## Class B program-design gate

- **Bestaand mechanisme en autoriteit.** `require_allowed_review_disposition`
  in `src/review/closed_review_loop_v1.py` weigert met
  `review_disposition_conflict` op basis van `ALLOWED_FINAL_BY_SUITABILITY`
  (P3). Het wordt aangeroepen in `review_command_v1._refuse_static_disposition`
  (voorbereid pad, behalve `revise`) en in `ClosedReviewLoopConsole.review_object`
  (serieel pad). `POST /review` (`review_post`) laat de fout door naar
  `console_errors`, dat `ERROR_COPY` raadpleegt; voor deze code bestond geen
  tekst, dus de gebruiker zag de algemene melding.
- **Beoogde verandering.** (1) Het formulier (`_render_review_card` in
  `src/operations_console_app.py`) laat na een geschiktheidskeuze alleen de
  eindoordelen zien die de regel toestaat, ook zonder JavaScript. (2) De
  weigering draagt de gekozen geschiktheid en het gekozen eindoordeel mee, en
  de foutpagina legt de combinatie en de toegestane eindoordelen uit.
- **Geraakte functies, typen, aanroeppad.** `closed_review_loop_v1`:
  nieuwe afgeleide `allowed_eindoordelen(suitability)` en
  `ReviewDispositionConflict(ConsoleError)` (zelfde code). Nieuwe UI-module
  `src/review/review_disposition_choices_ui_v1.py` (labels, opties, uitleg).
  `_render_review_card` rendert stap c en f via die module. In `console_errors`
  verandert alleen de regel die `message` bepaalt.
- **Welke staat mag muteren.** Geen. Het weigerpad schrijft niets; het
  formulier is presentatie.
- **Wat ongewijzigd blijft.** De regeltabel zelf, de serverweigering als
  autoriteit (400 `review_disposition_conflict`, geen event), `later` met
  geschiktheid (uitgesteld, niet geweigerd), `revise` → gestructureerd herstel,
  de veldnamen en waarden van het formulier, alle andere foutteksten.
- **Kleinste waarneembare bewijs.** Een test via de echte app die per
  geschiktheid de aangeboden eindoordelen vergelijkt met een letterlijke
  verwachte set, en een test die een conflicterende POST stuurt en de exacte
  Nederlandse uitleg, status 400, de code en het ongewijzigde aantal
  review-events controleert.

## Twee ontwerpen

| | A: tweestappenformulier (server) | B: één formulier, regel als data, CSS `:has()` |
| --- | --- | --- |
| Zonder JS | Stap 1 post geschiktheid, server rendert stap 2 met alleen toegestane opties. Werkt overal. | Opties die niet passen verdwijnen zodra een geschiktheid is aangevinkt (`:has()`, alle actuele browsers). Zonder `:has()`: alle opties zichtbaar, uitleg per geschiktheid blijft leesbaar, server weigert met precieze uitleg. |
| Toegankelijkheid | Twee paginaladingen; focus en context gaan verloren tussen stappen. | `fieldset`/`legend` per vraag; verborgen opties zijn `display: none` en dus niet focusbaar of voorgelezen; een zichtbare uitleg noemt wat wel kan (via `aria-describedby`). JS schakelt niet-passende opties ook `disabled` en meldt een gewist besluit in de bestaande hint (`aria-live`). |
| Diffgrootte | Groot: nieuwe GET/POST-stap, behoud van alle overige concepteerinvoer (type, kop, relaties, bronafwijking, toelichting) tussen stappen, nieuwe draft-route. | Klein: rendering van twee stappen, één afgeleide functie, één foutklasse, één regel in `console_errors`. |
| Eén bron van waarheid | Server filtert met de regel. | Server schrijft per optie `data-allowed-for` uit de regel; CSS-selectors worden gegenereerd uit `SUITABILITY_VALUES`; JS leest alleen die attributen. Geen tweede tabel. |
| Risico | Raakt reviewroute en P3-querybudget voor het weigerpad. | Een al aangevinkt besluit dat na een geschiktheidswijziging niet meer past, blijft zonder JS zichtbaar en wordt gemarkeerd; de server blijft weigeren. |

**Keuze: B.** Het is de kleinste wijziging die zonder JavaScript al voorkomt
dat een niet-passend besluit wordt gekozen, houdt alle andere invoer op één
pagina vast, en leidt alles af uit de bestaande regel. A zou een tweede
concept-/stapmechanisme naast het bestaande formulier introduceren.

Bewust niet gedaan: de conflictfout opnieuw renderen als reviewpagina met
behouden invoer. Dat kost de reviewkamer-leesronde op het weigerpad en breekt
het querybudget dat P3 vastlegde (`test_prepared_path_conflict_issues_fewer_queries_than_trunk`).
De bestaande foutpagina met precieze uitleg en de browser-terugknop (formulier
blijft gevuld) volstaat.

## Impeccable

`impeccable context` draaide (engine beschikbaar): geen PRODUCT.md/DESIGN.md,
afgebakende fix op bestaande code, modus Operate. Gelezen: `craft-floor.md`,
`clarify.md`. Bestaande `console.css`-tokens en klassen hergebruikt. Geen
gestructureerde vraagmogelijkheid in deze subagent; ontwerpkeuzes afgeleid uit
de brief en het projectleidersbesluit.

`impeccable detect --json` over de gewijzigde UI-bestanden meldt alleen
bestaande `border-left`-waarschuwingen elders in `console.css`; geen melding op
de nieuwe regels. Kleurcontrast: de markering gebruikt `--alert-text`
(#914500 op wit, ongeveer 5,9:1; donker thema #ffcf91 op #172232).

## Browserbewijs

Echte Chromium (Playwright) op de lokale productie-app met PostgreSQL
(`tests/browser_review_disposition_fixture.py`,
`tests/browser_review_disposition_check.cjs`), 1440 en 390 px breed,
deviceScaleFactor 2. Per geschiktheid zijn precies de toegestane
eindoordelen zichtbaar en kiesbaar, met en zonder JavaScript; pijltjestoetsen
in de besluitgroep doorlopen alleen die eindoordelen. Met JavaScript wordt een
niet meer passend besluit leeggemaakt en gemeld. Zonder JavaScript blijft een
eerder aangevinkt, niet-passend besluit zichtbaar met de markering; opslaan
geeft 400 met de precieze uitleg en schrijft geen review-event.

| Bestand | Wat |
| --- | --- |
| `js-mist-context-{1440,390}.png` | JS aan, ‘Nee, ik mis uitleg eromheen’: drie besluiten, gewist goedkeuren gemeld |
| `nojs-mismatch-{1440,390}.png` | JS uit, eerst goedkeuren, dan ‘Nee, ik mis uitleg eromheen’: markering |
| `nojs-conflict-page-{1440,390}.png` | Opslaan van die combinatie: foutpagina met uitleg |

Opnieuw draaien:

    METIS_BROWSER_EXECUTABLE=<chromium> METIS_PLAYWRIGHT_MODULE=<node playwright> \
      python -m pytest -q tests/test_browser_knowledge_context.py -k disposition

## Bekend, niet gewijzigd

`geen_kenniseenheid` + `goedkeuren_na_correctie` via een zelfgemaakt verzoek
leidt nog steeds naar het gestructureerde herstel in plaats van naar
`review_disposition_conflict` (P3-gedrag, `test_revise_keeps_the_structured_repair_flow`).
Het formulier biedt die combinatie niet meer aan.
