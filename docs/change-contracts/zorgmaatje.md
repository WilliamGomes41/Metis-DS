# Zorgmaatje: paginahulp, meldingen en weergavecontrole na inloggen

Change class: B
Promise: Op elke pagina na inloggen helpt een klein figuurtje rechtsonder de gebruiker de pagina en zichtbare fouten te begrijpen, een melding op te stellen, de bestaande diagnostiek te openen en de bestaande weergavecontrole te starten. Het productie-image bevat de browser die de weergavecontrole nodig heeft.
Proof: Het figuurtje staat alleen in de navigatie van aangemelde pagina's; de enige nieuwe route leest uitsluitend en gebruikt de bestaande reviewerautorisatie van de weergavecontrole; alle reviewruimte-goldens verschillen alleen in het figuurtje en de stylesheet-hash; een echte browser op de lokale PostgreSQL-console toont hulp, foutuitleg met code en referentie, meldingen, Escape-gedrag, donker thema en mobiel; de Docker-stap installeert Playwright 1.58.2 met Chromium en de build faalt als de Docling-fontinventaris verandert.
Touches lifecycle invariants: no
Rewrite risk: none

Opdracht van William op 22 oktober 2026: de weergavecontrole als "zorg-widget/huisdier" op alle pagina's na inloggen, met hulp bij wat fout gaat en meldingen daarvan, het starten van de weergavecontrole, de status en een mascotte. Playwright en Chromium in hetzelfde PR. Geen merge, migratie, Azure-wijziging of deploy.

## Bestaand mechanisme en autoriteit

- Navigatie: `_nav()` in `src/operations_console_app.py` rendert de kop voor iedere pagina; `_session_warning()` alleen bij een aangemeld account. Het figuurtje volgt exact diezelfde voorwaarde.
- Diagnostiek: `GET /inzicht/api/documents` (`src/insight_v1.py::documents_projection`) geeft per gebruiker alleen geautoriseerde documenten, met de filters `blocked` en `errors`. Het figuurtje roept die route aan; er komt geen tweede diagnosebron.
- Weergavecontrole: `src/view_check.py` blijft de enige eigenaar van aanvraag, autorisatie (alleen een genoemde reviewer), context, PostgreSQL-taak (`workflow.view_checks`) en bewijs. Het figuurtje post naar de bestaande `POST /inzicht/document/weergavecontrole` met dezelfde velden als het bestaande paneel, inclusief de origin-controle.
- Foutpagina's: de bestaande `ConsoleError`-handler toont `data-error-code`. Nieuw is alleen `data-request-id`, de bestaande `x-metis-request-id` van die request, zodat een melding naar de telemetrie terug te leiden is.

## Wijziging

| Onderdeel | Wat | Toestand |
| --- | --- | --- |
| `src/care_companion_v1.py` | Markup voor de navigatie en `GET /zorgmaatje/weergavecontrole` | Leest alleen: `authorize`, `context` en `store.history` (maximaal 5) van de bestaande weergavecontrole |
| `assets/brand/care-companion.js` | Paneel: foutuitleg, hulp per pagina, meldingen uit Inzicht, weergavecontrole, melding opstellen | Geen serveropslag. Een melding blijft in de browser tot de gebruiker hem kopieert of mailt. De open/dicht-stand en een cache van 60 seconden staan in `sessionStorage`. |
| `assets/brand/console.css` | Opmaak rechtsonder; schuift boven een zichtbare sessiewaarschuwing; licht/donker; mobiel; `prefers-reduced-motion`; niet bij afdrukken | — |
| `src/operations_console_app.py` | `_nav()` voegt het figuurtje toe na de sessiewaarschuwing; foutbanner krijgt `data-request-id`; route-installatie | — |
| `Dockerfile.docling` | Node (Debian), Playwright 1.58.2 (gelijk aan CI) en de headless Chromium van Playwright; `METIS_PLAYWRIGHT_MODULE` en `METIS_BROWSER_EXECUTABLE` vast in het image | Build-tijd; geen downloads tijdens runtime |

Mutaties: geen nieuwe. De enige schrijvende handeling is de bestaande aanvraag van een weergavecontrole, via de bestaande route met de bestaande autorisatie.

## Ongewijzigd gedrag

- Workflow, review, four-eyes, publicatie, serving en Product API.
- Wie de weergavecontrole mag starten, wat zij controleert en waar haar uitkomst staat.
- Pagina's zonder aanmelding (login, health).
- De weergavecontrole staat uit zolang `METIS_VIEW_CHECK_ORIGIN` niet gezet is; het figuurtje meldt dat dan.
- De Docling-render-fonts. Playwright's font-pakketten (`fonts-*`, `xfonts-*`) en `xvfb` worden niet geïnstalleerd, en de build vergelijkt een hash over alle bestanden in de fontroots van `src/docling_render_fonts_v1.py` vóór en na de stap. Lokaal gebouwd op hetzelfde basisimage (`python:3.12-slim@sha256:cb33f7f7…`, Debian 13): 212 fontbestanden, ongewijzigd.

## Beperkingen

- De meldingen roepen `documents_projection` twee keer aan (`blocked` en `errors`, elk tot 5 resultaten), maar alleen wanneer het paneel opengaat, en maximaal één keer per minuut per tabblad. Met een filter scant die projectie tot 1.000 geautoriseerde documenten.
- Er is geen meldingeninbox. Een melding opslaan zou een nieuwe duurzame autoriteit zijn; dat is bewust buiten scope.
- De browserworker van de weergavecontrole bezoekt ook pagina's met het figuurtje. Het script doet bij het laden geen requests (pas bij openen) en `/brand/` is al toegestaan. De scenariochecks tellen alleen inventarisrijen.
- Het image wordt groter door Node en Chromium headless shell, en de app heeft meer geheugen nodig wanneer Chromium naast Docling draait. Productie-acceptatie van de weergavecontrole (#807: netwerkgrens van Chromium, prestatie, Azure-bewijsopslag) is met deze PR niet vastgesteld.

## Aanzetten in Azure (aparte stap, alleen met GO van William)

1. Image bouwen met deze code (`az acr build … --file Dockerfile.docling --target runtime`, met `config/deployed_commit.txt`) en wisselen via de digest. Zonder de stappen hieronder blijft de weergavecontrole uit en werkt de rest van het figuurtje gewoon.
2. Migratie 019 met de bestaande runner: `plan` → `apply` → `verify`. Daarna: `GRANT SELECT, INSERT, UPDATE, DELETE ON workflow.view_checks TO "vvn-metis-console";`
3. Een private Blob-container voor schermbewijs, gescheiden van `canonical-sources`, met een lifecycle-regel die blobs na 7 dagen verwijdert. Daarnaast `Storage Blob Data Contributor` op die container voor de app-identity.
4. App settings: `METIS_VIEW_CHECK_ORIGIN=https://<defaultHostName>` (exacte origin, zonder slash) en `METIS_VIEW_CHECK_EVIDENCE_CONTAINER=<container>`. De browserpaden staan al in het image.
5. Controleer na de herstart via het figuurtje op een document waarvan je genoemde reviewer bent: "Controleer weergave", daarna de status en het schermbewijs.

Rollback: `METIS_VIEW_CHECK_ORIGIN` verwijderen; de functie staat dan uit. Een code-rollback is een image-wissel naar de vorige digest. 019 is alleen-toevoegen.
