# Raad: controle na deploy

Change class: B
Promise: Na een deploy opent een aangemelde gebruiker in Raad met één knop alle hoofdpagina's van de console en ziet per pagina of die laadt, of welke foutmelding, foutstatus of scriptfout zij geeft.
Proof: Een echte Chromium op de PostgreSQL-console meldt alle hoofdpagina's als geslaagd; drie in de fixture aangebrachte fouten (status 500, foutbanner met code en referentie, scriptfout) worden elk bij de juiste pagina genoemd; een doorsturing naar de Entra-aanmelding stopt de controle bij die pagina; een door de rol geweigerde pagina heet "niet gecontroleerd"; alle autoriteitsrijen in PostgreSQL zijn vóór en na gelijk (alleen sessies uitgezonderd).
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht van William op 23 oktober 2026: "Controle na een deploy. Met één knop in Raad alle hoofdpagina's laten openen en melden welke pagina niet laadt of een fout toont." Geen merge, Azure-wijziging of deploy.

## Bestaand mechanisme en autoriteit

- Raad (`src/care_companion_v1.py`, `assets/brand/care-companion.js`) staat via `_nav()` op iedere aangemelde pagina en bezit geen duurzame toestand.
- Foutpagina's tonen `data-error-code` en `data-request-id` (bestaande `ConsoleError`-handler). Raad leest die al voor de foutuitleg.
- De Playwright-weergavecontrole (`src/view_check.py`) blijft ongewijzigd. Zij staat in productie uit en is per document. De deploy-controle gebruikt haar bewust niet: geen serverbrowser, geen capability, geen opslag of migratie.

## Wijziging

| Onderdeel | Wat | Toestand |
| --- | --- | --- |
| `assets/brand/care-companion.js` | Sectie "Controle na deploy": laadt de vaste lijst hoofdpagina's (de kamers van `_nav()` plus Inzicht) één voor één in een verborgen frame in de eigen browser, met de eigen aanmelding | Alleen GET-paginaladingen. De laatste uitslag staat in `sessionStorage` van dat tabblad; niets op de server. In de gekopieerde uitslag staat een niet-gecontroleerde pagina als `NIET`, nooit als `OK`. Een opgeslagen uitslag hoort bij de naam en rollen in de kop; na aanmelden als iemand anders in hetzelfde tabblad verschijnt hij niet |
| `assets/brand/console.css` | Verborgen frame buiten beeld (onderaan, als aanvulling) | — |
| `tests/test_browser_deploy_check.py`, fixture en `.cjs` | Echte browserproef; in CI naast de bestaande browserproef | Fixture-fouten bestaan alleen in de testfixture |

Per pagina: doorsturen naar `/login`, naar de Entra-aanmelding (`/auth/…`) of naar een andere origin, of de lokale foutcode `not_authenticated` of een aanmeldformulier → sessie verlopen, en de controle stopt zodat er geen verdere aanmeldstromen starten; `data-error-code` → foutmelding met code en referentie, behalve `<rol>_role_required` voor een rol die het account niet heeft (niet gecontroleerd: geen toegang met jouw rol); heeft het account die rol wel, dan is het een fout; HTTP-status ≥ 400; ontbrekende Raad-kop → niet volledig geladen; scriptfouten; geen antwoord binnen 20 seconden. Daarna 1,5 seconde wachten op late scriptfouten. Er loopt per pagina hoogstens één controle; sluiten en opnieuw openen van Raad toont de lopende controle en haar uitslag.

Het frame heeft `sandbox="allow-same-origin allow-scripts"`: geen formulieren, pop-ups, downloads of navigatie van de hoofdpagina. Raad in het frame opent zijn paneel niet en haalt niets op; het telt alleen scriptfouten. Omdat het frame dezelfde origin heeft, is de sandbox een vangnet tegen per ongeluk versturen, geen beveiligingsgrens tussen pagina's van dezelfde console.

## Ongewijzigd gedrag

- Alle routes, autorisatie, workflow, review, publicatie, de weergavecontrole en haar aanzetstappen.
- Wat een pagina bij laden doet: de controle opent precies de pagina's die een gebruiker via de navigatie opent, zonder documentparameter.

## Beperkingen

- De controle ziet wat de aangemelde rol ziet. Een publisher-account controleert dus meer pagina's dan een reviewer.
- Alleen de hoofdpagina's zonder gekozen document; documentdetails, Review van één passage en exports vallen erbuiten.
- De HTTP-status komt uit de Navigation Timing API (`responseStatus`). Waar een browser die niet levert, valt de controle terug op de foutbanner en de Raad-kop.
- Scriptfouten vóór het laden van Raad in het frame worden alleen gezien als ze ook na het laden optreden.
- Een volledige run duurt ongeveer acht keer de laadtijd van een pagina plus 1,5 seconde per pagina.

## Verificatie

- `tests/test_browser_deploy_check.py` (Chromium, PostgreSQL): uitgevoerd lokaal met Playwright en Chromium uit de ontwikkelomgeving, groen.
- `tests/test_care_companion.py`: paginalijst gelijk aan `_nav()` plus Inzicht, sandbox zonder formulieren of navigatie, Raad in het frame opent niet.
